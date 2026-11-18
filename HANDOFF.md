# Handoff: Ops Sync Dashboard

## What runs where

| Component | Port | Start command | Notes |
|---|---|---|---|
| FastAPI backend | 8000 | `uvicorn app.main:create_app --factory` (from `backend/`) | Includes the scheduler (`SCHEDULER_ENABLED`) |
| Next.js dashboard | 3000 | `npm run build && npm start` (from `frontend/`) | `BACKEND_URL` is read **at build time** for the `/api` proxy |
| Mock APIs | 9100 | `uvicorn mock_apis.server:app` | Demo and tests only. Not needed with real credentials |

Data lives in a single SQLite file (`DATABASE_PATH`, default `backend/data/ops.db`). Tables: `charges`, `tickets`, `sync_runs`, `sync_state`.

## Day-to-day

- **Is it healthy?** The "Sync health" card says *All good*, or shows how many failed runs still need action. Each source card says Healthy, Syncing, Failing, or Stale (no success for over 2 hours).
- **A run failed:** read the error in the runs table (hover for the full text) and fix the cause, then click **Retry**. The new run is linked to the failed one.
- **Force a refresh:** click **Sync now** (all sources) or "Sync <source> now".
- **API:** `GET /api/runs`, `POST /api/sync[?source=]`, `POST /api/runs/{id}/retry`. Interactive docs are at `:8000/docs`.

## Troubleshooting

| Error in the run | Meaning | Fix |
|---|---|---|
| `stripe HTTP 401` | Key revoked or wrong | Create a new restricted key (Charges: read), update `.env`, restart the backend |
| `... HTTP 503 (after 3 attempts)` | Provider outage | Nothing to fix on our side. Retry later, or let the next scheduled run pick it up |
| `HTTP 429` repeatedly | Rate limited | Raise `SYNC_INTERVAL_SECONDS` or `RETRY_BASE_DELAY` |
| `interrupted (process restarted)` | Backend restarted mid-sync | Click Retry |
| Dashboard banner "Backend unreachable" | API down, or the frontend was built with the wrong `BACKEND_URL` | Check the backend logs. Rebuild the frontend with the correct `BACKEND_URL` |
| 409 on Sync now | That source is already syncing | Wait. The per-source lock prevents overlapping runs |

## Changing things

- **Schedule:** `SYNC_INTERVAL_SECONDS`, or turn off `SCHEDULER_ENABLED` and run `python -m app.cli sync` from cron. It exits 1 on failure so cron can alert.
- **New source:** add a connector with `fetch_page(cursor, since)`, `pages(since, fetch)` and `normalize(record)`, a table in `db.py`, and register it in `SyncEngine.from_settings`. The run history, retries and UI cards pick it up automatically.
- **Known limitation:** the Stripe connector syncs incrementally on `created`. Status changes to *old* charges (late refunds) are only caught by a full resync. Delete the `stripe` row from `sync_state` to force one. Moving to Stripe's Events API is the next step for production.
- Run `pytest` (backend) and `npm test` (frontend) before deploying.

## Security

- Keys live only in `.env`, which is git-ignored. Use **restricted, read-only** Stripe keys.
- Set `ADMIN_TOKEN` to protect Sync now and Retry. Read endpoints are open, so deploy behind your VPN or SSO (for example Cloudflare Access).
- The database holds customer emails. Store it on an encrypted volume and back it up with `sqlite3 ops.db ".backup ops-backup.db"`.
