"""Run a sync from cron / Kubernetes CronJob / GitHub Actions instead of the in-process scheduler.

    python -m app.cli sync            # all sources
    python -m app.cli sync stripe     # one source
Exit code is 1 if any source failed, so your scheduler can alert on it.
"""

import json
import sys

from .config import Settings
from .db import Database
from .logging_setup import setup_logging
from .sync import SyncEngine


def main(argv: list[str]) -> int:
    if not argv or argv[0] != "sync":
        print(__doc__)
        return 2
    setup_logging()
    s = Settings()
    engine = SyncEngine.from_settings(Database(s.database_path), s)
    results = [engine.run(argv[1], "scheduled")] if len(argv) > 1 else engine.run_all("scheduled")
    print(json.dumps(results, indent=2))
    return 1 if any(r["status"] == "failed" for r in results) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
