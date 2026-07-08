import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import models
from app import create_app


@pytest.fixture
def app(tmp_path, monkeypatch):
    db_path = tmp_path / "nudge.db"
    monkeypatch.setattr(models, "DB_PATH", str(db_path))
    monkeypatch.setenv("SOCKETIO_ASYNC_MODE", "threading")
    monkeypatch.setenv("NUDGE_EXTRACTION_BACKEND", "deterministic")
    monkeypatch.setenv("NUDGE_START_SCHEDULER", "false")
    models.init_db(db_path, seed_demo_data=True)

    flask_app = create_app()
    flask_app.config.update(TESTING=True)
    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def login_as_user(client):
    def _login(email):
        login_as(client, email)

    return _login


def login_as(client, email):
    with models.get_db() as db:
        row = db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    assert row is not None

    with client.session_transaction() as session:
        session["_user_id"] = str(row["id"])
        session["_fresh"] = True
