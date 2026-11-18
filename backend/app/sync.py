"""Sync engine: runs a source end to end, records every run, never double-counts.

Guarantees
* **Idempotent writes**: records are upserted by their source id, so re-running a sync is always safe.
* **Incremental**: a per-source cursor (max created/updated timestamp, minus an overlap window for
  late-arriving updates) is only advanced after a *successful* run. A failed run is simply re-done.
* **Retries**: every page request retries transient errors (429/5xx/timeouts) with exponential backoff.
* **One run per source at a time**: a second "sync now" while one is running gets a 409, not a race.
* **Crash safety**: runs left in "running" by a crash are marked failed on startup and can be retried.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

from .connectors import HelpdeskConnector, StripeConnector
from .db import Database
from .retry import with_retry

log = logging.getLogger("ops.sync")
OVERLAP_SECONDS = 300


class AlreadyRunning(Exception):
    pass


@dataclass
class Source:
    connector: object
    table: str
    columns: list[str]
    cursor_field: str


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class SyncEngine:
    def __init__(self, db: Database, sources: dict[str, Source], *, attempts: int = 3, base_delay: float = 1.0,
                 sleep: Callable[[float], None] = time.sleep):
        self.db = db
        self.sources = sources
        self.attempts = attempts
        self.base_delay = base_delay
        self.sleep = sleep
        self._locks = {name: threading.Lock() for name in sources}
        self._recover_interrupted()

    @classmethod
    def from_settings(cls, db: Database, s, clients: dict | None = None, **kw) -> "SyncEngine":
        clients = clients or {}
        stripe = StripeConnector(s.stripe_api_base, s.stripe_api_key, clients.get("stripe"), s.request_timeout)
        helpdesk = HelpdeskConnector(s.helpdesk_api_base, s.helpdesk_api_key, clients.get("helpdesk"), s.request_timeout)
        sources = {
            "stripe": Source(stripe, "charges", ["id", "amount", "currency", "status", "refunded", "failure_message",
                                                 "customer_email", "description", "created"], "created"),
            "helpdesk": Source(helpdesk, "tickets", ["id", "subject", "status", "priority", "requester_email",
                                                     "created_at", "updated_at"], "updated_at"),
        }
        return cls(db, sources, attempts=s.retry_attempts, base_delay=s.retry_base_delay, **kw)

    # -- run bookkeeping -------------------------------------------------------
    def _recover_interrupted(self) -> None:
        with self.db.tx() as c:
            c.execute("UPDATE sync_runs SET status='failed', error='interrupted (process restarted)', finished_at=? "
                      "WHERE status='running'", (_now_iso(),))

    def start_run(self, source: str, trigger: str, retry_of: int | None = None) -> int:
        if source not in self.sources:
            raise KeyError(source)
        if not self._locks[source].acquire(blocking=False):
            raise AlreadyRunning(source)
        try:
            with self.db.tx() as c:
                cur = c.execute("INSERT INTO sync_runs (source, trigger, status, retry_of) VALUES (?, ?, 'running', ?)",
                                (source, trigger, retry_of))
                return int(cur.lastrowid)
        except Exception:
            self._locks[source].release()
            raise

    def _finish(self, run_id: int, status: str, records: int, attempts: int, error: str | None) -> None:
        with self.db.tx() as c:
            c.execute("UPDATE sync_runs SET status=?, records=?, attempts=?, error=?, finished_at=? WHERE id=?",
                      (status, records, attempts, error, _now_iso(), run_id))

    # -- the actual sync -------------------------------------------------------
    def execute(self, run_id: int) -> dict:
        run = self.db.one("SELECT * FROM sync_runs WHERE id=?", (run_id,))
        name = run["source"]
        src = self.sources[name]
        attempts = 0
        records = 0
        max_seen = 0

        def count_attempt(_n: int) -> None:
            nonlocal attempts
            attempts += 1

        try:
            state = self.db.one("SELECT cursor FROM sync_state WHERE source=?", (name,))
            since = state["cursor"] if state else None
            fetch = lambda a, b: with_retry(lambda: src.connector.fetch_page(a, b), attempts=self.attempts,  # noqa: E731
                                            base_delay=self.base_delay, label=name, sleep=self.sleep,
                                            on_attempt=count_attempt)
            log.info("sync started", extra={"run_id": run_id, "source": name, "since": since, "trigger": run["trigger"]})
            for page in src.connector.pages(since, fetch=fetch):
                self._upsert(src, page)
                records += len(page)
                max_seen = max([max_seen] + [int(r[src.cursor_field] or 0) for r in page])
            if max_seen:
                with self.db.tx() as c:
                    c.execute("INSERT INTO sync_state (source, cursor) VALUES (?, ?) "
                              "ON CONFLICT(source) DO UPDATE SET cursor=excluded.cursor",
                              (name, max_seen - OVERLAP_SECONDS))
            self._finish(run_id, "success", records, attempts, None)
            log.info("sync finished", extra={"run_id": run_id, "source": name, "records": records, "attempts": attempts})
            return {"id": run_id, "status": "success", "records": records}
        except Exception as exc:  # noqa: BLE001 - every failure is recorded on the run, then surfaced in the UI
            self._finish(run_id, "failed", records, attempts, str(exc)[:500])
            log.error("sync failed", extra={"run_id": run_id, "source": name, "error": str(exc), "attempts": attempts})
            return {"id": run_id, "status": "failed", "error": str(exc)}
        finally:
            self._locks[name].release()

    def _upsert(self, src: Source, rows: list[dict]) -> None:
        cols = src.columns
        sql = (f"INSERT INTO {src.table} ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)}) "
               f"ON CONFLICT(id) DO UPDATE SET {', '.join(f'{c}=excluded.{c}' for c in cols if c != 'id')}, "
               f"synced_at=CURRENT_TIMESTAMP")
        with self.db.tx() as c:
            c.executemany(sql, [[r.get(col) for col in cols] for r in rows])

    # -- convenience -----------------------------------------------------------
    def run(self, source: str, trigger: str = "manual") -> dict:
        return self.execute(self.start_run(source, trigger))

    def run_all(self, trigger: str = "scheduled") -> list[dict]:
        out = []
        for name in self.sources:
            try:
                out.append(self.run(name, trigger))
            except AlreadyRunning:
                log.info("skipping, already running", extra={"source": name})
        return out

    def start_retry(self, run_id: int) -> int:
        run = self.db.one("SELECT * FROM sync_runs WHERE id=?", (run_id,))
        if run is None:
            raise KeyError(run_id)
        if run["status"] != "failed":
            raise ValueError("only failed runs can be retried")
        return self.start_run(run["source"], "retry", retry_of=run_id)


class Scheduler:
    """Runs all sources every ``interval`` seconds in a daemon thread (cron-free, survives errors)."""

    def __init__(self, engine: SyncEngine, interval: int):
        self.engine = engine
        self.interval = interval
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.next_run_at: float | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._loop, name="sync-scheduler", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                self.engine.run_all("scheduled")
            except Exception:  # noqa: BLE001
                log.exception("scheduled sync crashed")
            self.next_run_at = time.time() + self.interval
            self._stop.wait(self.interval)
