import models


def test_sample_transcript_upload_creates_summary_and_draft_task(client, login_as_user):
    login_as_user("maya@nudge.local")

    response = client.post(
        "/upload/",
        data={"sample_transcript": "sprint_review.txt"},
    )

    assert response.status_code == 302
    with models.get_db() as db:
        meeting = db.execute(
            """
            SELECT *
            FROM meetings
            WHERE title = 'Sprint Review'
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()
        tasks = db.execute(
            "SELECT * FROM tasks WHERE meeting_id = ?",
            (meeting["id"],),
        ).fetchall()

    assert meeting["summary"]
    assert meeting["extraction_status"] == "parsed"
    assert len(tasks) >= 1
    assert all(task["status"] == "draft" for task in tasks)
    assert any(task["description"] for task in tasks)
