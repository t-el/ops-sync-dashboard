#!/usr/bin/env bash
# Start everything locally in mock mode: mock Stripe/help-desk APIs (:9100), FastAPI (:8000), Next.js (:3000).
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT=$(pwd)
PY=${PYTHON:-python3}
[ -f .env ] && set -a && . ./.env && set +a
export DATABASE_PATH=${DATABASE_PATH:-$ROOT/backend/data/ops.db}

pids=()
cleanup() { kill "${pids[@]}" 2>/dev/null || true; }
trap cleanup EXIT INT TERM

(cd backend && $PY -m uvicorn mock_apis.server:app --port 9100 --log-level warning) & pids+=($!)
(cd backend && $PY -m uvicorn app.main:create_app --factory --port 8000 --log-level warning) & pids+=($!)
if [ "${FRONTEND_MODE:-dev}" = "prod" ]; then
  (cd frontend && npx next build >/dev/null && npx next start -p 3000) & pids+=($!)
else
  (cd frontend && npx next dev -p 3000) & pids+=($!)
fi
echo "Dashboard: http://localhost:3000   API docs: http://localhost:8000/docs   Mock APIs: http://localhost:9100/docs"
wait
