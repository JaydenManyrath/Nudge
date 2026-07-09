from io import BytesIO

import models


def test_sample_transcript_upload_creates_summary_and_draft_task(client, login_as_user):
    login_as_user("andrew@nudge.local")

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
    login_as_user("andrew@nudge.local")

    response = client.post(
        "/upload/",
        data={"sample_transcript": "urgent_priority.txt"},
    )

    assert response.status_code == 302
    meeting, tasks = _meeting_and_tasks_by_title("Urgent Priority")

    assert meeting["summary"]
    assert len(tasks) >= 1
    assert any(task["priority"] == "urgent" for task in tasks)


def test_no_deadline_sample_produces_task_without_due_date(client, login_as_user):
    """Sprint 3 edge case: a real, clearly-owned task with no timing
    language anywhere should come out with due_date left empty rather
    than a guessed date."""
    login_as_user("andrew@nudge.local")

    response = client.post(
        "/upload/",
        data={"sample_transcript": "task_no_deadline.txt"},
    )

    assert response.status_code == 302
    meeting, tasks = _meeting_and_tasks_by_title("Task No Deadline")

    assert meeting["summary"]
    assert len(tasks) >= 1
    assert any(task["assignee_name"] == "Theo" for task in tasks)
    assert all(not task["due_date"] for task in tasks)


def test_manager_can_access_manual_upload_fallback(client, login_as_user):
    login_as_user("andrew@nudge.local")

    response = client.get("/upload/")

    assert response.status_code == 200
    assert b"Upload Transcript" in response.data
    assert b"Create drafts" in response.data


def test_pasted_transcript_upload_creates_manual_upload_draft(client, login_as_user):
    login_as_user("andrew@nudge.local")

    response = client.post(
        "/upload/",
        data={
            "title": "Fallback Paste",
            "transcript_text": "Maya: Priya, can you prepare the fallback checklist?",
        },
    )

    assert response.status_code == 302
    meeting, tasks = _meeting_and_tasks_by_title("Fallback Paste")

    assert meeting["source"] == "manual_upload"
    assert meeting["zoom_meeting_id"] is None
    assert meeting["extraction_status"] == "parsed"
    assert [task["status"] for task in tasks] == ["draft"]
    assert tasks[0]["description"] == "Prepare the fallback checklist"


def test_uploaded_transcript_file_creates_manual_upload_draft(client, login_as_user):
    login_as_user("andrew@nudge.local")

    response = client.post(
        "/upload/",
        data={
            "title": "Fallback File",
            "transcript_file": (
                BytesIO(b"Marco: I'll send the backup notes."),
                "fallback.txt",
            ),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 302
    meeting, tasks = _meeting_and_tasks_by_title("Fallback File")

    assert meeting["source"] == "manual_upload"
    assert meeting["zoom_meeting_id"] is None
    assert meeting["extraction_status"] == "parsed"
    assert [task["status"] for task in tasks] == ["draft"]
    assert tasks[0]["description"] == "Send the backup notes"


def test_empty_manual_upload_returns_bad_request(client, login_as_user):
    login_as_user("andrew@nudge.local")

    response = client.post("/upload/", data={})

    assert response.status_code == 400
    assert b"Provide transcript text" in response.data


def _meeting_and_tasks_by_title(title):
    with models.get_db() as db:
        meeting = db.execute(
            """
            SELECT *
            FROM meetings
            WHERE title = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (title,),
        ).fetchone()
        assert meeting is not None
        tasks = db.execute(
            "SELECT * FROM tasks WHERE meeting_id = ? ORDER BY id",
            (meeting["id"],),
        ).fetchall()
    return meeting, tasks
