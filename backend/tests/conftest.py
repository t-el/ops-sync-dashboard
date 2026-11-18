import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import Settings  # noqa: E402
from app.db import Database  # noqa: E402
from app.sync import SyncEngine  # noqa: E402
from mock_apis import server as mock_server  # noqa: E402


@pytest.fixture
def mock_api():
    mock_server.reset()
    return TestClient(mock_server.app, base_url="http://mock")


@pytest.fixture
def settings(tmp_path):
    s = Settings()
    s.database_path = str(tmp_path / "ops.db")
    s.stripe_api_base = "http://mock/stripe"
    s.helpdesk_api_base = "http://mock/helpdesk"
    s.stripe_api_key = "sk_test_x"
    s.helpdesk_api_key = "hd_x"
    s.scheduler_enabled = False
    s.admin_token = ""
    return s


@pytest.fixture
def engine(settings, mock_api):
    db = Database(settings.database_path)
    return SyncEngine.from_settings(db, settings, clients={"stripe": mock_api, "helpdesk": mock_api}, sleep=lambda _s: None)
