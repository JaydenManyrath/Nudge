import integrations
import models


def test_create_calendar_invite_falls_back_to_stub_without_google_token(app):
    task = _task("Finalize pricing page copy")

    event_id = integrations.create_calendar_invite(
        task,
        {"id": task.assignee_id, "name": task.assignee_name},
    )

    assert event_id.startswith("stub-calendar-")


def test_create_calendar_invite_uses_google_calendar_when_token_exists(
    app,
    monkeypatch,
):
    task = _task("Finalize pricing page copy")
    _connect_google_calendar()
    captured = {}

    class FakeInsert:
        def execute(self):
            return {"id": "google-event-123"}

    class FakeEvents:
        def insert(self, **kwargs):
            captured.update(kwargs)
            return FakeInsert()

    class FakeService:
        def events(self):
            return FakeEvents()

    monkeypatch.setattr(
        integrations,
        "_build_google_calendar_service",
        lambda token: FakeService(),
    )

    event_id = integrations.create_calendar_invite(
        task,
        {"id": task.assignee_id, "name": task.assignee_name},
    )

    assert event_id == "google-event-123"
    assert captured["calendarId"] == "primary"
    assert captured["sendUpdates"] == "all"
    assert captured["body"] == {
        "summary": "Finalize pricing page copy",
        "description": (
            "Created from a Nudge-approved meeting task.\n\n"
            "Priya said she would finish pricing copy by Friday."
        ),
        "start": {"date": "2026-07-10"},
        "end": {"date": "2026-07-11"},
        "attendees": [{"email": "priya@nudge.local"}],
    }


def test_create_calendar_invite_skips_tasks_without_due_date(app):
    task = _task("Investigate flaky checkout test")

    assert integrations.create_calendar_invite(task, None) is None


def _connect_google_calendar():
    with models.get_db() as db:
        row = db.execute(
            "SELECT id FROM users WHERE email = ?",
            ("maya@nudge.local",),
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


def _task(description):
    with models.get_db() as db:
        row = db.execute(
            "SELECT * FROM tasks WHERE description = ?",
            (description,),
        ).fetchone()
    task = models.row_to_task(row)
    assert task is not None
    return task
