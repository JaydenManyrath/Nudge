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


def test_urgent_priority_sample_produces_an_urgent_task(client, login_as_user):
    """Sprint 3 edge case: explicit urgent/critical language should surface
    at least one urgent-priority draft task, backing the demo-data
    requirement for an urgent-priority example."""
    login_as_user("maya@nudge.local")

    response = client.post(
        "/upload/",
        data={"sample_transcript": "urgent_priority.txt"},
    )

    assert response.status_code == 302
    with models.get_db() as db:
        meeting = db.execute(
            """
            SELECT *
            FROM meetings
            WHERE title = 'Urgent Priority'
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()
        tasks = db.execute(
            "SELECT * FROM tasks WHERE meeting_id = ?",
            (meeting["id"],),
        ).fetchall()

    assert meeting["summary"]
    assert len(tasks) >= 1
    assert any(task["priority"] == "urgent" for task in tasks)


def test_no_deadline_sample_produces_task_without_due_date(client, login_as_user):
    """Sprint 3 edge case: a real, clearly-owned task with no timing
    language anywhere should come out with due_date left empty rather
    than a guessed date."""
    login_as_user("maya@nudge.local")

    response = client.post(
        "/upload/",
        data={"sample_transcript": "task_no_deadline.txt"},
    )

    assert response.status_code == 302
    with models.get_db() as db:
        meeting = db.execute(
            """
            SELECT *
            FROM meetings
            WHERE title = 'Task No Deadline'
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()
        tasks = db.execute(
            "SELECT * FROM tasks WHERE meeting_id = ?",
            (meeting["id"],),
        ).fetchall()

    assert meeting["summary"]
    assert len(tasks) >= 1
    assert any(task["assignee_name"] == "Theo" for task in tasks)
    assert all(not task["due_date"] for task in tasks)
