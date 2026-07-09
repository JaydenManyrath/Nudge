import json

import integrations
import models
import sockets


def test_review_lists_draft_tasks_for_manager(client, login_as_user):
    login_as_user("andrew@nudge.local")

    response = client.get("/review/")

    assert response.status_code == 200
    # Scope the check to the review list (the top-bar notification dropdown
    # can surface pending tasks by name, which is a separate feature).
    body = response.get_data(as_text=True)
    review_main = body.split('class="review-main"', 1)[1].split("review-sidebar", 1)[0]
    assert "Finalize pricing page copy" in review_main
    assert "Investigate flaky checkout test" in review_main
    # A pending (non-draft) task is not listed as an approvable draft.
    assert "Create customer rollout notes" not in review_main


def test_approving_a_draft_moves_it_to_pending(client, login_as_user, monkeypatch):
    emitted = []
    monkeypatch.setattr(
        sockets.socketio,
        "emit",
        lambda event, data, **kwargs: emitted.append((event, data)),
    )
    login_as_user("andrew@nudge.local")
    task_id = _draft_task_id("Finalize pricing page copy")

    response = client.post(
        f"/review/{task_id}/approve",
        data={
            "owner": "Dat Nguyen",
            "description": "Finalize pricing page copy for launch",
            "due_date": "2026-07-10",
            "priority": "urgent",
        },
    )

    assert response.status_code == 302
    task = _task(task_id)
    assert task["status"] == "pending"
    assert task["description"] == "Finalize pricing page copy for launch"
    assert task["assignee_name"] == "Dat Nguyen"
    assert task["assignee_id"] is not None
    assert emitted == [
        (
            "task_updated",
            {
                "id": task_id,
                "status": "pending",
                "priority": "urgent",
                "due_date": "2026-07-10",
                "due_date_iso": "2026-07-10",
                "description": "Finalize pricing page copy for launch",
                "owner": "Dat Nguyen",
            },
        )
    ]


def test_editing_a_draft_keeps_it_in_review_queue(client, login_as_user, monkeypatch):
    emitted = []
    monkeypatch.setattr(
        sockets.socketio,
        "emit",
        lambda event, data, **kwargs: emitted.append((event, data)),
    )
    login_as_user("andrew@nudge.local")
    task_id = _draft_task_id("Investigate flaky checkout test")

    response = client.post(
        f"/review/{task_id}/edit",
        data={
            "owner": "",
            "description": "Assign an owner for the flaky checkout test",
            "due_date": "",
            "priority": "normal",
        },
    )

    assert response.status_code == 302
    task = _task(task_id)
    assert task["status"] == "draft"
    assert task["description"] == "Assign an owner for the flaky checkout test"
    assert task["assignee_name"] == "unassigned"
    assert task["due_date"] is None
    assert emitted == [
        (
            "task_updated",
            {
                "id": task_id,
                "status": "draft",
                "priority": "normal",
                "due_date": "No due date",
                "due_date_iso": None,
                "description": "Assign an owner for the flaky checkout test",
                "owner": "unassigned",
            },
        )
    ]


def test_rejecting_a_draft_retains_rejected_task(client, login_as_user, monkeypatch):
    emitted = []
    monkeypatch.setattr(
        sockets.socketio,
        "emit",
        lambda event, data, **kwargs: emitted.append((event, data)),
    )
    login_as_user("andrew@nudge.local")
    task_id = _draft_task_id("Investigate flaky checkout test")

    response = client.post(f"/review/{task_id}/reject")

    assert response.status_code == 302
    task = _task(task_id)
    assert task is not None
    assert task["status"] == "rejected"
    assert emitted == [
        (
            "task_updated",
            {
                "id": task_id,
                "status": "rejected",
                "priority": "normal",
                "due_date": "No due date",
                "due_date_iso": None,
                "description": "Investigate flaky checkout test",
                "owner": "unassigned",
            },
        )
    ]


def test_approving_a_draft_stores_created_calendar_metadata(
    client,
    login_as_user,
    monkeypatch,
):
    login_as_user("andrew@nudge.local")
    _connect_google_calendar()
    task_id = _draft_task_id("Finalize pricing page copy")

    class FakeInsert:
        def execute(self):
            return {
                "id": "google-event-123",
                "htmlLink": "https://calendar.google.test/event/123",
            }

    class FakeEvents:
        def insert(self, **kwargs):
            return FakeInsert()

    class FakeService:
        def events(self):
            return FakeEvents()

    monkeypatch.setattr(
        integrations,
        "_build_google_calendar_service",
        lambda token: FakeService(),
    )

    response = client.post(
        f"/review/{task_id}/approve",
        data={
            "owner": "Dat Nguyen",
            "description": "Finalize pricing page copy",
            "due_date": "2026-07-10",
            "priority": "urgent",
        },
    )

    assert response.status_code == 302
    task = _task(task_id)
    metadata = json.loads(task["calendar_event_metadata"])
    assert task["calendar_event_id"] == "google-event-123"
    assert metadata["status"] == "created"
    assert metadata["provider"] == "google"
    assert metadata["calendar_id"] == "primary"
    assert metadata["event_id"] == "google-event-123"
    assert metadata["html_link"] == "https://calendar.google.test/event/123"
    assert metadata["error"] is None
    assert metadata["synced_at"]


def test_approving_a_draft_stores_failed_calendar_metadata(
    client,
    login_as_user,
    monkeypatch,
):
    login_as_user("andrew@nudge.local")
    _connect_google_calendar()
    task_id = _draft_task_id("Finalize pricing page copy")

    def raise_google_error(token):
        raise RuntimeError("Google API unavailable")

    monkeypatch.setattr(
        integrations,
        "_build_google_calendar_service",
        raise_google_error,
    )

    response = client.post(
        f"/review/{task_id}/approve",
        data={
            "owner": "Dat Nguyen",
            "description": "Finalize pricing page copy",
            "due_date": "2026-07-10",
            "priority": "urgent",
        },
    )

    assert response.status_code == 302
    task = _task(task_id)
    metadata = json.loads(task["calendar_event_metadata"])
    assert task["status"] == "pending"
    assert task["calendar_event_id"] is None
    assert metadata["status"] == "failed"
    assert metadata["provider"] == "google"
    assert metadata["calendar_id"] == "primary"
    assert metadata["event_id"] is None
    assert metadata["html_link"] is None
    assert metadata["error"] == "Google API unavailable"
    assert metadata["synced_at"]


def test_approving_a_draft_without_due_date_stores_skipped_calendar_metadata(
    client,
    login_as_user,
):
    login_as_user("andrew@nudge.local")
    task_id = _draft_task_id("Investigate flaky checkout test")

    response = client.post(
        f"/review/{task_id}/approve",
        data={
            "owner": "",
            "description": "Investigate flaky checkout test",
            "due_date": "",
            "priority": "normal",
        },
    )

    assert response.status_code == 302
    task = _task(task_id)
    metadata = json.loads(task["calendar_event_metadata"])
    assert task["status"] == "pending"
    assert task["calendar_event_id"] is None
    assert metadata["status"] == "skipped"
    assert metadata["provider"] is None
    assert metadata["calendar_id"] is None
    assert metadata["event_id"] is None
    assert metadata["html_link"] is None
    assert metadata["error"] == "missing_due_date"
    assert metadata["synced_at"]


def _connect_google_calendar():
    with models.get_db() as db:
        row = db.execute(
            "SELECT id FROM users WHERE email = ?",
            ("andrew@nudge.local",),
        ).fetchone()
        models.upsert_oauth_token(
            db,
            models.OAuthToken(
                id=None,
                user_id=row["id"],
                provider="google",
                access_token="google-access-token",
                refresh_token="google-refresh-token",
                scope="https://www.googleapis.com/auth/calendar.events",
            ),
        )


def _draft_task_id(description):
    with models.get_db() as db:
        row = db.execute(
            "SELECT id FROM tasks WHERE description = ? AND status = 'draft'",
            (description,),
        ).fetchone()
    assert row is not None
    return row["id"]


def _task(task_id):
    with models.get_db() as db:
        return db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()


def test_manager_can_add_task_manually(client, login_as_user):
    login_as_user("andrew@nudge.local")
    response = client.post(
        "/review/add",
        data={
            "description": "Manually added task",
            "owner": "jayden@nudge.local",
            "priority": "urgent",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    body = client.get("/review/").get_data(as_text=True)
    assert "Manually added task" in body


def test_manual_task_requires_description(client, login_as_user):
    login_as_user("andrew@nudge.local")
    response = client.post("/review/add", data={"owner": "", "priority": "normal"})
    assert response.status_code == 302  # redirects back with a flash


def test_employee_cannot_add_task(client, login_as_user):
    login_as_user("jayden@nudge.local")
    response = client.post("/review/add", data={"description": "nope"})
    assert response.status_code == 403
