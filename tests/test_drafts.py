import models


def test_rejected_draft_does_not_show_in_review_queue(client, login_as_user):
    login_as_user("maya@nudge.local")
    with models.get_db() as db:
        row = db.execute(
            """
            SELECT id
            FROM tasks
            WHERE description = 'Investigate flaky checkout test'
              AND status = 'draft'
            """
        ).fetchone()

    response = client.post(f"/review/{row['id']}/reject", follow_redirects=True)

    assert response.status_code == 200
    assert b"Investigate flaky checkout test" not in response.data
    with models.get_db() as db:
        task = db.execute("SELECT status FROM tasks WHERE id = ?", (row["id"],)).fetchone()
    assert task["status"] == "rejected"
