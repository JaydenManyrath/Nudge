import models


def test_manager_dashboard_shows_active_tasks_only(client, login_as_user):
    login_as_user("maya@nudge.local")

    response = client.get("/dashboard/manager")

    assert response.status_code == 200
    assert b"Create customer rollout notes" in response.data
    assert b"Finalize pricing page copy" not in response.data
    assert b"Investigate flaky checkout test" not in response.data


def test_employee_dashboard_shows_only_assigned_active_tasks(client, login_as_user):
    login_as_user("marco@nudge.local")

    response = client.get("/dashboard/employee")

    assert response.status_code == 200
    assert b"Create customer rollout notes" in response.data
    assert b"Finalize pricing page copy" not in response.data


def test_approval_sets_stub_calendar_event_id(client, login_as_user):
    login_as_user("maya@nudge.local")
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
            "owner": "Priya Shah",
            "description": "Finalize pricing page copy",
            "due_date": "2026-07-10",
            "priority": "urgent",
        },
    )

    assert response.status_code == 302
    with models.get_db() as db:
        task = db.execute(
            "SELECT status, calendar_event_id FROM tasks WHERE id = ?",
            (row["id"],),
        ).fetchone()
    assert task["status"] == "pending"
    assert task["calendar_event_id"].startswith("stub-calendar-")
