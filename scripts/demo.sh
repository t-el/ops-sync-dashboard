#!/usr/bin/env bash
# Headless end-to-end demo against the running stack (start it with scripts/dev.sh first).
# Shows: scheduled sync, retry-then-success, a hard failure, and the retry button's API.
set -euo pipefail
API=${API:-http://127.0.0.1:8000}; MOCK=${MOCK:-http://127.0.0.1:9100}
j() { python3 -c "import json,sys; d=json.load(sys.stdin); print(json.dumps(d, indent=None)[:400])"; }
wait_idle() { for _ in $(seq 1 60); do curl -s "$API/api/runs?limit=5" | grep -q '"running"' || return 0; sleep 0.5; done; }

echo "### Health";                    curl -s "$API/api/health" | j
wait_idle
echo "### 1. Flaky Stripe API (fails twice) -> sync still succeeds thanks to retries"
curl -s -X POST "$MOCK/__chaos" -H 'content-type: application/json' -d '{"source":"stripe","fail_next":2}' >/dev/null
curl -s -X POST "$API/api/sync?source=stripe" | j; wait_idle
curl -s "$API/api/runs?source=stripe&limit=1" | j
echo "### 2. Help desk API down -> run marked failed, cursor not advanced"
curl -s -X POST "$MOCK/__chaos" -H 'content-type: application/json' -d '{"source":"helpdesk","fail_next":100}' >/dev/null
curl -s -X POST "$API/api/sync?source=helpdesk" | j; wait_idle
FAILED=$(curl -s "$API/api/runs?source=helpdesk&limit=1" | python3 -c "import json,sys; r=json.load(sys.stdin)[0]; print(r['id']); print(r['status'], r['error'], file=sys.stderr)")
echo "### 3. API recovers -> retry failed run #$FAILED (what the Retry button calls)"
curl -s -X POST "$MOCK/__chaos" -H 'content-type: application/json' -d '{"source":"helpdesk","fail_next":0}' >/dev/null
curl -s -X POST "$API/api/runs/$FAILED/retry" | j; wait_idle
curl -s "$API/api/runs?source=helpdesk&limit=1" | j
echo "### 4. KPIs";                   curl -s "$API/api/summary" | python3 -c "import json,sys; d=json.load(sys.stdin); d.pop('daily_revenue'); d.pop('sources'); print(d)"
echo "### 5. At-risk customers";      curl -s "$API/api/insights/at-risk" | j
