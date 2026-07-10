import json

import models


def test_manager_dashboard_shows_active_tasks_only(client, login_as_user):
    login_as_user("andrew@nudge.local")

    response = client.get("/dashboard/manager")

    assert response.status_code == 200
    assert b"Create customer rollout notes" in response.data
    assert b"Finalize pricing page copy" not in response.data
    assert b"Investigate flaky checkout test" not in response.data


def test_employee_dashboard_shows_only_assigned_active_tasks(client, login_as_user):
    login_as_user("jayden@nudge.local")

    response = client.get("/dashboard/employee")

    assert response.status_code == 200
    assert b"Create customer rollout notes" in response.data
    assert b"Finalize pricing page copy" not in response.data


def test_manager_dashboard_shows_zoom_connected_when_token_exists(
    client,
    login_as_user,
):
    login_as_user("andrew@nudge.local")
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
                provider="zoom",
                access_token="zoom-access-token",
                refresh_token="zoom-refresh-token",
            ),
        )

    response = client.get("/dashboard/manager")

    assert response.status_code == 200
    assert b"Zoom" in response.data
    assert b"Connected" in response.data
    assert b"Reconnect" in response.data


def test_manager_dashboard_shows_google_calendar_connected_when_token_exists(
    client,
    login_as_user,
):
    login_as_user("andrew@nudge.local")
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
            ),
        )

    response = client.get("/dashboard/manager")

    assert response.status_code == 200
    assert b"Google Calendar" in response.data
    assert b"Connected" in response.data
    assert b"Reconnect Google" in response.data


def test_manager_can_access_live_meeting_page(client, login_as_user):
    login_as_user("andrew@nudge.local")

    response = client.get("/dashboard/live")

    assert response.status_code == 200
    assert b"Live Meeting" in response.data
    assert b"Live Transcript" in response.data
    assert b"Andrew: Before we wrap, Jayden" in response.data
    assert b"Dat you can fix the backend errors by tomorrow." in response.data
    assert response.data.count(b"Extract Tasks") == 2
    assert b"Live Meeting Transcript" in response.data


def test_live_meeting_page_shows_zoom_disconnected_by_default(client, login_as_user):
    login_as_user("andrew@nudge.local")

    response = client.get("/dashboard/live")

    assert response.status_code == 200
    assert b"Not connected" in response.data
    assert b"Zoom is not connected" in response.data


def test_live_meeting_page_shows_zoom_connected_when_token_exists(
    client,
    login_as_user,
):
    login_as_user("andrew@nudge.local")
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
                provider="zoom",
                access_token="zoom-access-token",
                refresh_token="zoom-refresh-token",
            ),
        )

    response = client.get("/dashboard/live")

    assert response.status_code == 200
    assert b"Listening" in response.data
    assert b"Zoom is not connected" not in response.data


def test_approval_sets_stub_calendar_event_id(client, login_as_user):
    login_as_user("andrew@nudge.local")
    with models.get_db() as db:
        row = db.execute(
            """
            SELECT id
            FROM tasks
            WHERE description = 'Finalize pricing page copy'
              AND status = 'draft'
            """
        ).fetchone()

    response = client.post(
        f"/review/{row['id']}/approve",
        data={
            "owner": "Dat Nguyen",
            "description": "Finalize pricing page copy",
            "due_date": "2026-07-10",
            "priority": "urgent",
        },
    )

    assert response.status_code == 302
    with models.get_db() as db:
        task = db.execute(
            """
            SELECT status, calendar_event_id, calendar_event_metadata
            FROM tasks
            WHERE id = ?
            """,
            (row["id"],),
        ).fetchone()
    assert task["status"] == "pending"
    assert task["calendar_event_id"].startswith("stub-calendar-")
    metadata = json.loads(task["calendar_event_metadata"])
    assert metadata["status"] == "stubbed"
    assert metadata["provider"] == "stub"
    assert metadata["event_id"] == task["calendar_event_id"]
    assert metadata["calendar_id"] is None
    assert metadata["html_link"] is None
    assert metadata["error"] is None
    assert metadata["synced_at"]
