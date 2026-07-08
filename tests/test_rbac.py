import models


def test_employee_cannot_access_manager_routes(client, login_as_user):
    login_as_user("priya@nudge.local")

    response = client.get("/review/")

    assert response.status_code == 403


def test_employee_cannot_post_manager_review_actions(client, login_as_user):
    login_as_user("priya@nudge.local")
    with models.get_db() as db:
        row = db.execute("SELECT id FROM tasks WHERE status = 'draft' LIMIT 1").fetchone()

    response = client.post(f"/review/{row['id']}/approve")

    assert response.status_code == 403
    with models.get_db() as db:
        task = db.execute("SELECT status FROM tasks WHERE id = ?", (row["id"],)).fetchone()
    assert task["status"] == "draft"
