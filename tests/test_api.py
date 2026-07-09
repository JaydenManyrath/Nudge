import models
import sockets


def test_employee_can_mark_own_task_done(client, login_as_user, monkeypatch):
    emitted = []
    monkeypatch.setattr(
        sockets.socketio,
        "emit",
        lambda event, data, **kwargs: emitted.append((event, data)),
    )
    login_as_user("jayden@nudge.local")
    task_id = _task_id("Create customer rollout notes")

    response = client.post(f"/api/tasks/{task_id}/done")

    assert response.status_code == 200
    assert response.get_json()["task"]["status"] == "done"
    assert _task(task_id)["status"] == "done"
    assert emitted == [
        (
            "task_updated",
            {
                "id": task_id,
                "status": "done",
                "priority": "normal",
                "due_date": "2026-07-11",
                "due_date_iso": "2026-07-11",
                "description": "Create customer rollout notes",
                "owner": "Jayden",
            },
        )
    ]


def test_employee_cannot_update_someone_elses_task(client, login_as_user):
    login_as_user("dat@nudge.local")
    task_id = _task_id("Create customer rollout notes")

    response = client.post(f"/api/tasks/{task_id}/done")

    assert response.status_code == 403
    assert _task(task_id)["status"] == "pending"


def test_comment_is_attached_to_task(client, login_as_user, monkeypatch):
    emitted = []
    monkeypatch.setattr(
        sockets.socketio,
        "emit",
        lambda event, data, **kwargs: emitted.append((event, data)),
    )
    login_as_user("jayden@nudge.local")
    task_id = _task_id("Create customer rollout notes")

    response = client.post(
        f"/api/tasks/{task_id}/comments",
        json={"body": "Draft is ready for review."},
    )

    assert response.status_code == 201
    comment = response.get_json()["comment"]
    assert comment["author"] == "Jayden Manyrath"
    assert comment["role"] == "employee"
    assert comment["body"] == "Draft is ready for review."
    assert comment["created_at"]
    assert emitted == [("comment_added", {"task_id": task_id, "comment": comment})]

    list_response = client.get(f"/api/tasks/{task_id}/comments")
    assert list_response.status_code == 200
    assert list_response.get_json()["comments"] == [comment]


def test_employee_can_report_and_manager_can_resolve_blocker(
    client,
    login_as_user,
    monkeypatch,
):
    emitted = []
    monkeypatch.setattr(
        sockets.socketio,
        "emit",
        lambda event, data, **kwargs: emitted.append((event, data)),
    )
    login_as_user("jayden@nudge.local")
    task_id = _task_id("Create customer rollout notes")

    block_response = client.post(
        f"/api/tasks/{task_id}/blockers",
        json={"description": "Waiting on customer list export."},
    )

    assert block_response.status_code == 200
    assert _task(task_id)["status"] == "blocked"
    assert [event for event, _payload in emitted] == [
        "task_updated",
        "blocker_updated",
        "comment_added",
    ]
    assert emitted[1][1] == {
        "task_id": task_id,
        "status": "blocked",
        "description": "Waiting on customer list export.",
    }

    login_as_user("andrew@nudge.local")
    resolve_response = client.post(f"/api/tasks/{task_id}/blockers/resolve")

    assert resolve_response.status_code == 200
    assert _task(task_id)["status"] == "pending"
    assert emitted[-3][0] == "task_updated"
    assert emitted[-2][1] == {
        "task_id": task_id,
        "status": "pending",
        "description": None,
    }
    assert emitted[-1][0] == "comment_added"


def test_reopen_moves_done_task_back_to_pending(client, login_as_user, monkeypatch):
    monkeypatch.setattr(
        sockets.socketio, "emit", lambda event, data, **kwargs: None
    )
    login_as_user("jayden@nudge.local")
    task_id = _task_id("Create customer rollout notes")

    client.post(f"/api/tasks/{task_id}/done")
    assert _task(task_id)["status"] == "done"

    response = client.post(f"/api/tasks/{task_id}/reopen")
    assert response.status_code == 200
    assert _task(task_id)["status"] == "pending"


def _task_id(description):
    with models.get_db() as db:
        row = db.execute(
            "SELECT id FROM tasks WHERE description = ?",
            (description,),
        ).fetchone()
    assert row is not None
    return row["id"]


def _task(task_id):
    with models.get_db() as db:
        return db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
