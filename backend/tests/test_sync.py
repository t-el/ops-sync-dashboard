from app.db import Database
from app.sync import AlreadyRunning, SyncEngine


def test_full_sync_pulls_every_page(engine, mock_api):
    assert engine.run("stripe")["records"] == 140
    assert engine.run("helpdesk")["records"] == 48
    assert engine.db.one("SELECT COUNT(*) n FROM charges")["n"] == 140
    assert engine.db.one("SELECT COUNT(*) n FROM tickets")["n"] == 48


def test_resync_is_idempotent_and_incremental(engine):
    engine.run("stripe")
    second = engine.run("stripe")
    assert second["status"] == "success"
    assert second["records"] < 140  # only the overlap window is re-fetched
    assert engine.db.one("SELECT COUNT(*) n FROM charges")["n"] == 140  # no duplicates


def test_transient_errors_are_retried(engine, mock_api):
    mock_api.post("/__chaos", json={"source": "helpdesk", "fail_next": 2})
    r = engine.run("helpdesk")
    assert r["status"] == "success"
    run = engine.db.one("SELECT * FROM sync_runs WHERE id=?", (r["id"],))
    assert run["attempts"] >= 3


def test_persistent_failure_marks_run_failed_and_keeps_cursor(engine, mock_api):
    engine.run("stripe")
    cursor_before = engine.db.one("SELECT cursor FROM sync_state WHERE source='stripe'")["cursor"]
    mock_api.post("/__chaos", json={"source": "stripe", "fail_next": 50})
    r = engine.run("stripe")
    assert r["status"] == "failed" and "503" in r["error"]
    assert engine.db.one("SELECT cursor FROM sync_state WHERE source='stripe'")["cursor"] == cursor_before


def test_auth_errors_fail_fast_without_retries(settings, mock_api):
    settings.stripe_api_key = "wrong"
    eng = SyncEngine.from_settings(Database(settings.database_path), settings,
                                   clients={"stripe": mock_api, "helpdesk": mock_api}, sleep=lambda _s: None)
    r = eng.run("stripe")
    assert r["status"] == "failed" and "401" in r["error"]
    assert eng.db.one("SELECT attempts FROM sync_runs WHERE id=?", (r["id"],))["attempts"] == 1


def test_retry_failed_run(engine, mock_api):
    mock_api.post("/__chaos", json={"source": "helpdesk", "fail_next": 50})
    failed = engine.run("helpdesk")
    mock_api.post("/__chaos", json={"source": "helpdesk", "fail_next": 0})
    new_id = engine.start_retry(failed["id"])
    assert engine.execute(new_id)["status"] == "success"
    run = engine.db.one("SELECT * FROM sync_runs WHERE id=?", (new_id,))
    assert run["trigger"] == "retry" and run["retry_of"] == failed["id"]


def test_only_one_run_per_source(engine):
    run_id = engine.start_run("stripe", "manual")
    try:
        engine.start_run("stripe", "manual")
        raise AssertionError("expected AlreadyRunning")
    except AlreadyRunning:
        pass
    engine.execute(run_id)
    engine.run("stripe")  # lock released afterwards


def test_interrupted_runs_are_recovered_on_startup(settings, mock_api):
    db = Database(settings.database_path)
    with db.tx() as c:
        c.execute("INSERT INTO sync_runs (source, trigger, status) VALUES ('stripe', 'manual', 'running')")
    SyncEngine.from_settings(db, settings, clients={"stripe": mock_api, "helpdesk": mock_api})
    run = db.one("SELECT * FROM sync_runs")
    assert run["status"] == "failed" and "interrupted" in run["error"]
