import models
from extensions import socketio


def _login(flask_client, email):
    with models.get_db() as db:
        row = db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    with flask_client.session_transaction() as sess:
        sess["_user_id"] = str(row["id"])
        sess["_fresh"] = True


def _task_id(description):
    with models.get_db() as db:
        row = db.execute(
            "SELECT id FROM tasks WHERE description = ?", (description,)
        ).fetchone()
    return row["id"]


def _received_events(client):
    return {event["name"] for event in client.get_received()}


def test_task_update_scoped_to_owner_and_managers(app):
    """A task update reaches its assignee and managers, but not other employees."""
    mgr_fc = app.test_client()
    _login(mgr_fc, "andrew@nudge.local")
    marco_fc = app.test_client()
    _login(marco_fc, "jayden@nudge.local")
    priya_fc = app.test_client()
    _login(priya_fc, "dat@nudge.local")

    mgr = socketio.test_client(app, flask_test_client=mgr_fc)
    marco = socketio.test_client(app, flask_test_client=marco_fc)
    priya = socketio.test_client(app, flask_test_client=priya_fc)

    assert mgr.is_connected()
    assert marco.is_connected()
    assert priya.is_connected()

    # Drain the connect handshake.
    for client in (mgr, marco, priya):
        client.get_received()

    # Marco owns this pending task; marking it done emits task_updated.
    task_id = _task_id("Create customer rollout notes")
    response = marco_fc.post(f"/api/tasks/{task_id}/done")
    assert response.status_code == 200

    assert "task_updated" in _received_events(marco)  # owner receives
    assert "task_updated" in _received_events(mgr)  # manager observes all
    assert "task_updated" not in _received_events(priya)  # other employee does not
