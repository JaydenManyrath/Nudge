import models
import rtms
from backend.ai import extraction as ai_extraction


def setup_function():
    rtms.reset_active_meetings()


def test_rtms_chunks_create_zoom_meeting_and_draft_tasks(app, monkeypatch):
    emitted = []
    monkeypatch.setattr(rtms, "emit_transcript_line", emitted.append)

    started = rtms.handle_meeting_started(
        {
            "payload": {
                "object": {
                    "uuid": "zoom-rtms-123",
                    "topic": "Launch Follow Up",
                }
            }
        }
    )
    first_chunk = rtms.handle_transcript_chunk(
        {
            "meeting_uuid": "zoom-rtms-123",
            "speaker_name": "Priya",
            "text": "I'll finalize the launch checklist",
        }
    )
    second_chunk = rtms.handle_transcript_chunk(
        {
            "payload": {
                "meeting_uuid": "zoom-rtms-123",
                "user_name": "Marco",
                "text": "I'll send the customer update",
            }
        }
    )
    result = rtms.handle_meeting_ended({"meeting_uuid": "zoom-rtms-123"})

    assert started["status"] == "started"
    assert first_chunk["status"] == "recorded"
    assert second_chunk["chunk_count"] == 2
    assert emitted == [
        {
            "meeting_id": "zoom-rtms-123",
            "speaker": "Priya",
            "text": "I'll finalize the launch checklist",
            "line": "Priya: I'll finalize the launch checklist",
        },
        {
            "meeting_id": "zoom-rtms-123",
            "speaker": "Marco",
            "text": "I'll send the customer update",
            "line": "Marco: I'll send the customer update",
        },
    ]
    assert result["status"] == "parsed"
    assert rtms.active_meeting_count() == 0

    with models.get_db() as db:
        meeting = db.execute(
            """
            SELECT *
            FROM meetings
            WHERE zoom_meeting_id = ?
            """,
            ("zoom-rtms-123",),
        ).fetchone()
        tasks = db.execute(
            "SELECT * FROM tasks WHERE meeting_id = ? ORDER BY id",
            (meeting["id"],),
        ).fetchall()

    assert meeting["title"] == "Launch Follow Up"
    assert meeting["source"] == "zoom_rtms"
    assert meeting["extraction_status"] == "parsed"
    assert "Priya: I'll finalize the launch checklist" in meeting["transcript"]
    assert [task["status"] for task in tasks] == ["draft", "draft"]
    assert {task["assignee_name"] for task in tasks} == {"Priya", "Marco"}


def test_rtms_meeting_end_uses_openai_extractor_when_configured(app, monkeypatch):
    monkeypatch.setenv("NUDGE_EXTRACTION_BACKEND", "openai")
    monkeypatch.setattr(rtms, "emit_transcript_line", lambda event: None)
    captured = {}

    def fake_extract_tasks(transcript_text, job_id, meeting_date=None):
        captured["transcript_text"] = transcript_text
        captured["job_id"] = job_id
        captured["meeting_date"] = meeting_date
        return {
            "summary": "OpenAI summary",
            "tasks": [
                {
                    "owner": "Priya",
                    "description": "Finalize the launch checklist",
                    "due_date": None,
                    "priority": "normal",
                    "context": "Priya committed during the RTMS transcript.",
                }
            ],
        }

    monkeypatch.setattr(ai_extraction, "extract_tasks", fake_extract_tasks)

    rtms.handle_meeting_started(
        {
            "meeting_id": "zoom-openai-123",
            "topic": "OpenAI RTMS Follow Up",
        }
    )
    rtms.handle_transcript_chunk(
        {
            "meeting_id": "zoom-openai-123",
            "speaker_name": "Priya",
            "text": "I'll finalize the launch checklist",
        }
    )

    result = rtms.handle_meeting_ended({"meeting_id": "zoom-openai-123"})

    assert result["status"] == "parsed"
    assert captured["transcript_text"] == "Priya: I'll finalize the launch checklist"
    assert captured["job_id"] == 0
    assert captured["meeting_date"]
    assert result["extraction"]["summary"] == "OpenAI summary"

    with models.get_db() as db:
        meeting = db.execute(
            "SELECT * FROM meetings WHERE zoom_meeting_id = ?",
            ("zoom-openai-123",),
        ).fetchone()
        tasks = db.execute(
            "SELECT * FROM tasks WHERE meeting_id = ?",
            (meeting["id"],),
        ).fetchall()

    assert meeting["source"] == "zoom_rtms"
    assert meeting["extraction_status"] == "parsed"
    assert tasks[0]["description"] == "Finalize the launch checklist"


def test_rtms_ended_without_chunks_records_failed_meeting(app):
    rtms.handle_meeting_started(
        {
            "meeting_id": "zoom-empty-456",
            "topic": "Empty RTMS Meeting",
        }
    )

    result = rtms.handle_meeting_ended({"meeting_id": "zoom-empty-456"})

    assert result["status"] == "failed"
    assert result["tasks"] == []
    assert rtms.active_meeting_count() == 0

    with models.get_db() as db:
        meeting = db.execute(
            """
            SELECT *
            FROM meetings
            WHERE zoom_meeting_id = ?
            """,
            ("zoom-empty-456",),
        ).fetchone()

    assert meeting["title"] == "Empty RTMS Meeting"
    assert meeting["source"] == "zoom_rtms"
    assert meeting["extraction_status"] == "failed"
    assert meeting["transcript"] is None


def test_rtms_events_endpoint_dispatches_lifecycle_events(client, monkeypatch):
    monkeypatch.setenv("ZOOM_SECRET_TOKEN", "rtms-secret")
    emitted = []
    monkeypatch.setattr(rtms, "emit_transcript_line", emitted.append)
    headers = {"X-Nudge-RTMS-Secret": "rtms-secret"}

    started = client.post(
        "/rtms/events",
        json={
            "event": "meeting.started",
            "payload": {
                "object": {
                    "uuid": "zoom-http-789",
                    "topic": "HTTP RTMS Follow Up",
                }
            },
        },
        headers=headers,
    )
    first_chunk = client.post(
        "/rtms/events",
        json={
            "event_type": "transcript.chunk",
            "payload": {
                "meeting_uuid": "zoom-http-789",
                "speaker_name": "Priya",
                "text": "I'll finalize the HTTP ingress checklist",
            },
        },
        headers=headers,
    )
    second_chunk = client.post(
        "/rtms/events",
        json={
            "type": "transcript_chunk",
            "data": {
                "meeting_uuid": "zoom-http-789",
                "user_name": "Marco",
                "text": "I'll send the RTMS adapter notes",
            },
        },
        headers=headers,
    )
    ended = client.post(
        "/rtms/events",
        json={
            "event": "meeting.ended",
            "meeting_uuid": "zoom-http-789",
        },
        headers=headers,
    )

    assert started.status_code == 200
    assert started.get_json()["status"] == "started"
    assert first_chunk.status_code == 200
    assert first_chunk.get_json()["status"] == "recorded"
    assert second_chunk.status_code == 200
    assert second_chunk.get_json()["chunk_count"] == 2
    assert ended.status_code == 200
    assert ended.get_json()["status"] == "parsed"
    assert emitted == [
        {
            "meeting_id": "zoom-http-789",
            "speaker": "Priya",
            "text": "I'll finalize the HTTP ingress checklist",
            "line": "Priya: I'll finalize the HTTP ingress checklist",
        },
        {
            "meeting_id": "zoom-http-789",
            "speaker": "Marco",
            "text": "I'll send the RTMS adapter notes",
            "line": "Marco: I'll send the RTMS adapter notes",
        },
    ]

    with models.get_db() as db:
        meeting = db.execute(
            """
            SELECT *
            FROM meetings
            WHERE zoom_meeting_id = ?
            """,
            ("zoom-http-789",),
        ).fetchone()
        tasks = db.execute(
            "SELECT * FROM tasks WHERE meeting_id = ? ORDER BY id",
            (meeting["id"],),
        ).fetchall()

    assert meeting["title"] == "HTTP RTMS Follow Up"
    assert meeting["source"] == "zoom_rtms"
    assert meeting["extraction_status"] == "parsed"
    assert [task["status"] for task in tasks] == ["draft", "draft"]


def test_rtms_events_endpoint_rejects_invalid_secret(client, monkeypatch):
    monkeypatch.setenv("ZOOM_SECRET_TOKEN", "rtms-secret")

    response = client.post(
        "/rtms/events",
        json={
            "event": "meeting.started",
            "meeting_id": "unauthorized-rtms",
        },
        headers={"X-Nudge-RTMS-Secret": "wrong-secret"},
    )

    assert response.status_code == 401
    assert response.get_json()["error"] == "Invalid RTMS ingress secret"
    assert rtms.active_meeting_count() == 0


def test_rtms_events_endpoint_rejects_unsupported_event(client, monkeypatch):
    monkeypatch.setenv("ZOOM_SECRET_TOKEN", "rtms-secret")

    response = client.post(
        "/rtms/events",
        json={
            "event": "recording.completed",
            "meeting_id": "unsupported-rtms",
        },
        headers={"X-Nudge-RTMS-Secret": "rtms-secret"},
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "Unsupported RTMS event type"
    assert rtms.active_meeting_count() == 0
