from fastapi.testclient import TestClient

from app.main import create_app


def test_dashboard_flow(settings, engine, mock_api):
    c = TestClient(create_app(settings, engine))
    assert c.get("/api/health").json()["ok"]

    # sync now (background tasks run before TestClient returns)
    r = c.post("/api/sync")
    assert r.status_code == 202 and len(r.json()["started"]) == 2
    runs = c.get("/api/runs").json()
    assert {x["status"] for x in runs} == {"success"}

    s = c.get("/api/summary").json()
    assert s["revenue_30d_cents"] > 0 and s["payments_30d"] > 0
    assert s["total_tickets"] == 48
    assert {x["name"] for x in s["sources"]} == {"stripe", "helpdesk"}
    assert s["daily_revenue"]
    assert len(c.get("/api/tickets?open_only=true").json()) == s["open_tickets"] + s["pending_tickets"]
    assert isinstance(c.get("/api/insights/at-risk").json(), list)


def test_failed_run_then_retry_from_api(settings, engine, mock_api):
    c = TestClient(create_app(settings, engine))
    mock_api.post("/__chaos", json={"source": "stripe", "fail_next": 50})
    c.post("/api/sync?source=stripe")
    failed = c.get("/api/runs?source=stripe").json()[0]
    assert failed["status"] == "failed"
    assert c.post(f"/api/runs/{failed['id']}/retry").status_code == 202  # still failing upstream
    mock_api.post("/__chaos", json={"source": "stripe", "fail_next": 0})
    latest_failed = c.get("/api/runs?source=stripe").json()[0]
    r = c.post(f"/api/runs/{latest_failed['id']}/retry")
    assert r.status_code == 202
    assert c.get("/api/runs?source=stripe").json()[0]["status"] == "success"
    ok_run = c.get("/api/runs?source=stripe").json()[0]
    assert c.post(f"/api/runs/{ok_run['id']}/retry").status_code == 400
    assert c.post("/api/runs/9999/retry").status_code == 404
    assert c.post("/api/sync?source=nope").status_code == 404


def test_admin_token_protects_mutations(settings, engine):
    settings.admin_token = "t0ken"
    c = TestClient(create_app(settings, engine))
    assert c.post("/api/sync").status_code == 401
    assert c.post("/api/sync", headers={"Authorization": "Bearer t0ken"}).status_code == 202
    assert c.get("/api/summary").status_code == 200  # reads stay open (put the app behind your SSO/VPN)
