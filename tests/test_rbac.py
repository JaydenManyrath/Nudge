import models


def test_employee_cannot_access_manager_routes(client, login_as_user):
    login_as_user("dat@nudge.local")

    response = client.get("/review/")

    assert response.status_code == 403


def test_employee_cannot_access_manual_upload_fallback(client, login_as_user):
    login_as_user("dat@nudge.local")

    response = client.get("/upload/")

    assert response.status_code == 403


def test_employee_cannot_access_live_meeting_page(client, login_as_user):
    login_as_user("dat@nudge.local")

    response = client.get("/dashboard/live")

    assert response.status_code == 403


def test_employee_cannot_post_manager_review_actions(client, login_as_user):
    login_as_user("dat@nudge.local")
    with models.get_db() as db:
        row = db.execute("SELECT id FROM tasks WHERE status = 'draft' LIMIT 1").fetchone()

    response = client.post(f"/review/{row['id']}/approve")

    assert response.status_code == 403
    with models.get_db() as db:
        task = db.execute("SELECT status FROM tasks WHERE id = ?", (row["id"],)).fetchone()
    assert task["status"] == "draft"


def test_employee_cannot_post_manual_upload_fallback(client, login_as_user):
    login_as_user("dat@nudge.local")

    response = client.post(
        "/upload/",
        data={
            "title": "Employee Upload Attempt",
            "transcript_text": "Priya: I'll create an unauthorized draft.",
        },
    )

    assert response.status_code == 403
    with models.get_db() as db:
        meeting = db.execute(
            "SELECT id FROM meetings WHERE title = ?",
            ("Employee Upload Attempt",),
        ).fetchone()
    assert meeting is None
