"""Ops Sync API: data, KPIs, run history, 'sync now', retry, and a built-in scheduler.

    uvicorn app.main:create_app --factory --port 8000
"""

from __future__ import annotations

import hmac
import logging
import time
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from . import __version__
from .config import Settings
from .db import Database
from .logging_setup import setup_logging
from .sync import AlreadyRunning, Scheduler, SyncEngine

log = logging.getLogger("ops.api")
DAY = 86400


def create_app(settings: Settings | None = None, engine: SyncEngine | None = None) -> FastAPI:
    s = settings or Settings()
    setup_logging()
    db = engine.db if engine else Database(s.database_path)
    engine = engine or SyncEngine.from_settings(db, s)
    scheduler = Scheduler(engine, s.sync_interval_seconds)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        if s.scheduler_enabled:
            scheduler.start()
            log.info("scheduler started", extra={"interval_s": s.sync_interval_seconds})
        yield
        scheduler.stop()

    app = FastAPI(title="Ops Sync API", version=__version__, lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=s.cors_origins.split(","), allow_methods=["*"], allow_headers=["*"])
    app.state.engine = engine

    def admin(authorization: Optional[str] = Header(default=None)) -> None:
        if s.admin_token and not hmac.compare_digest(authorization or "", f"Bearer {s.admin_token}"):
            raise HTTPException(401, "admin token required")

    @app.get("/api/health")
    def health() -> dict:
        return {"ok": True, "version": __version__, "scheduler": s.scheduler_enabled,
                "interval_s": s.sync_interval_seconds, "next_run_at": scheduler.next_run_at}

    @app.get("/api/summary")
    def summary() -> dict:
        since = int(time.time()) - 30 * DAY
        rev = db.one("SELECT COALESCE(SUM(amount),0) AS cents, COUNT(*) AS n FROM charges "
                     "WHERE status='succeeded' AND created>=?", (since,))
        failed = db.one("SELECT COUNT(*) AS n, COALESCE(SUM(amount),0) AS cents FROM charges "
                        "WHERE status='failed' AND created>=?", (since,))
        refunds = db.one("SELECT COUNT(*) AS n FROM charges WHERE status='refunded' AND created>=?", (since,))
        tickets = db.one("SELECT SUM(status='open') AS open, SUM(status='pending') AS pending, "
                         "SUM(status IN ('open','pending') AND priority='urgent') AS urgent, COUNT(*) AS total FROM tickets")
        daily = db.query("SELECT strftime('%Y-%m-%d', created, 'unixepoch') AS day, SUM(amount) AS cents FROM charges "
                         "WHERE status='succeeded' AND created>=? GROUP BY day ORDER BY day", (since,))
        sources = []
        for name in engine.sources:
            last = db.one("SELECT * FROM sync_runs WHERE source=? ORDER BY id DESC LIMIT 1", (name,))
            last_ok = db.one("SELECT finished_at FROM sync_runs WHERE source=? AND status='success' "
                             "ORDER BY id DESC LIMIT 1", (name,))
            stats = db.one("SELECT SUM(status='success') AS ok, SUM(status='failed') AS failed FROM sync_runs "
                           "WHERE source=?", (name,))
            sources.append({"name": name, "last_run": last, "last_success_at": last_ok["finished_at"] if last_ok else None,
                            "success_count": stats["ok"] or 0, "failure_count": stats["failed"] or 0})
        return {
            "revenue_30d_cents": rev["cents"], "payments_30d": rev["n"],
            "failed_payments_30d": failed["n"], "failed_amount_30d_cents": failed["cents"],
            "refunds_30d": refunds["n"],
            "open_tickets": tickets["open"] or 0, "pending_tickets": tickets["pending"] or 0,
            "urgent_tickets": tickets["urgent"] or 0, "total_tickets": tickets["total"] or 0,
            "daily_revenue": daily, "sources": sources,
        }

    @app.get("/api/insights/at-risk")
    def at_risk() -> list[dict]:
        """Customers with a failed payment in the last 30 days AND an unresolved ticket: call them first."""
        return db.query(
            "SELECT c.customer_email AS email, COUNT(DISTINCT c.id) AS failed_payments, "
            "COUNT(DISTINCT t.id) AS open_tickets, MAX(t.priority='urgent') AS has_urgent "
            "FROM charges c JOIN tickets t ON t.requester_email = c.customer_email "
            "WHERE c.status='failed' AND c.created>=? AND t.status IN ('open','pending') "
            "GROUP BY c.customer_email ORDER BY has_urgent DESC, failed_payments DESC, open_tickets DESC LIMIT 10",
            (int(time.time()) - 30 * DAY,))

    @app.get("/api/runs")
    def runs(limit: int = 30, source: Optional[str] = None) -> list[dict]:
        if source:
            return db.query("SELECT * FROM sync_runs WHERE source=? ORDER BY id DESC LIMIT ?", (source, limit))
        return db.query("SELECT * FROM sync_runs ORDER BY id DESC LIMIT ?", (limit,))

    @app.get("/api/charges")
    def charges(limit: int = 50, status: Optional[str] = None) -> list[dict]:
        if status:
            return db.query("SELECT * FROM charges WHERE status=? ORDER BY created DESC LIMIT ?", (status, limit))
        return db.query("SELECT * FROM charges ORDER BY created DESC LIMIT ?", (limit,))

    @app.get("/api/tickets")
    def tickets(limit: int = 50, open_only: bool = False) -> list[dict]:
        where = "WHERE status IN ('open','pending')" if open_only else ""
        return db.query(f"SELECT * FROM tickets {where} ORDER BY "
                        "CASE priority WHEN 'urgent' THEN 0 WHEN 'high' THEN 1 WHEN 'normal' THEN 2 ELSE 3 END, "
                        "updated_at DESC LIMIT ?", (limit,))

    @app.post("/api/sync", status_code=202, dependencies=[Depends(admin)])
    def sync_now(background: BackgroundTasks, source: Optional[str] = None) -> dict:
        names = [source] if source else list(engine.sources)
        started, skipped = [], []
        for name in names:
            try:
                run_id = engine.start_run(name, "manual")
            except KeyError:
                raise HTTPException(404, f"unknown source {name}") from None
            except AlreadyRunning:
                skipped.append(name)
                continue
            background.add_task(engine.execute, run_id)
            started.append({"source": name, "run_id": run_id})
        if not started:
            raise HTTPException(409, f"already running: {', '.join(skipped)}")
        return {"started": started, "skipped_already_running": skipped}

    @app.post("/api/runs/{run_id}/retry", status_code=202, dependencies=[Depends(admin)])
    def retry(run_id: int, background: BackgroundTasks) -> dict:
        try:
            new_id = engine.start_retry(run_id)
        except KeyError:
            raise HTTPException(404, "run not found") from None
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from None
        except AlreadyRunning:
            raise HTTPException(409, "a sync for this source is already running") from None
        background.add_task(engine.execute, new_id)
        return {"run_id": new_id, "retry_of": run_id}

    return app
