from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import RLock

from extraction import ExtractionError, create_draft_tasks_from_transcript
from models import Meeting, get_db, row_to_meeting, validate_meeting
from sockets import emit_transcript_line


@dataclass
class RtmsMeetingBuffer:
    meeting_id: str
    title: str
    chunks: list[str] = field(default_factory=list)
    started_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    @property
    def transcript(self):
        return "\n".join(self.chunks).strip()


_ACTIVE_MEETINGS = {}
_ACTIVE_MEETINGS_LOCK = RLock()
_DEFAULT_MEETING_ID = "unknown"


def handle_meeting_started(payload):
    meeting_id = _meeting_id(payload)
    title = _meeting_title(payload, meeting_id)
    buffer = RtmsMeetingBuffer(meeting_id=meeting_id, title=title)
    with _ACTIVE_MEETINGS_LOCK:
        _ACTIVE_MEETINGS[meeting_id] = buffer

    return {
        "status": "started",
        "meeting_id": buffer.meeting_id,
        "title": buffer.title,
        "started_at": buffer.started_at,
    }


def handle_transcript_chunk(payload):
    meeting_id = _meeting_id(payload)
    text = _transcript_text(payload)
    if not text:
        return {
            "status": "skipped",
            "meeting_id": meeting_id,
            "reason": "empty transcript chunk",
        }

    speaker = _speaker(payload)
    line = _format_line(text, speaker)
    with _ACTIVE_MEETINGS_LOCK:
        buffer = _ACTIVE_MEETINGS.get(meeting_id)
        if buffer is None:
            buffer = RtmsMeetingBuffer(
                meeting_id=meeting_id,
                title=_meeting_title(payload, meeting_id),
            )
            _ACTIVE_MEETINGS[meeting_id] = buffer
        buffer.chunks.append(line)
        chunk_count = len(buffer.chunks)

    event = {
        "meeting_id": meeting_id,
        "speaker": speaker,
        "text": text,
        "line": line,
    }
    emit_transcript_line(event)

    return {
        "status": "recorded",
        "meeting_id": meeting_id,
        "line": line,
        "chunk_count": chunk_count,
    }


def handle_meeting_ended(payload):
    meeting_id = _meeting_id(payload)
    with _ACTIVE_MEETINGS_LOCK:
        buffer = _ACTIVE_MEETINGS.pop(meeting_id, None)
    if buffer is None:
        buffer = RtmsMeetingBuffer(
            meeting_id=meeting_id,
            title=_meeting_title(payload, meeting_id),
        )

    transcript = buffer.transcript
    if not transcript:
        meeting = _persist_failed_meeting(
            title=buffer.title,
            zoom_meeting_id=meeting_id,
            transcript=None,
            reason="No transcript chunks were received before the meeting ended.",
        )
        return {
            "status": "failed",
            "meeting": meeting,
            "tasks": [],
            "error": "transcript_text is empty",
        }

    try:
        result = create_draft_tasks_from_transcript(
            buffer.title,
            transcript,
            source="zoom_rtms",
            zoom_meeting_id=meeting_id,
            meeting_date=buffer.started_at[:10],
        )
    except ExtractionError as exc:
        meeting = _persist_failed_meeting(
            title=buffer.title,
            zoom_meeting_id=meeting_id,
            transcript=transcript,
            reason=str(exc),
        )
        return {
            "status": "failed",
            "meeting": meeting,
            "tasks": [],
            "error": str(exc),
        }

    return {
        "status": "parsed",
        "meeting": result["meeting"],
        "tasks": result["tasks"],
        "extraction": result["extraction"],
    }


def reset_active_meetings():
    with _ACTIVE_MEETINGS_LOCK:
        _ACTIVE_MEETINGS.clear()


def active_meeting_count():
    with _ACTIVE_MEETINGS_LOCK:
        return len(_ACTIVE_MEETINGS)


def _persist_failed_meeting(title, zoom_meeting_id, transcript, reason):
    meeting = Meeting(
        id=None,
        title=title,
        summary=f"Zoom RTMS extraction failed: {reason}",
        transcript=transcript,
        source="zoom_rtms",
        zoom_meeting_id=zoom_meeting_id,
        extraction_status="failed",
    )
    validate_meeting(meeting)

    with get_db() as db:
        cursor = db.execute(
            """
            INSERT INTO meetings (
                title,
                summary,
                transcript,
                source,
                zoom_meeting_id,
                extraction_status
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                meeting.title,
                meeting.summary,
                meeting.transcript,
                meeting.source,
                meeting.zoom_meeting_id,
                meeting.extraction_status,
            ),
        )
        db.commit()
        return row_to_meeting(
            db.execute(
                "SELECT * FROM meetings WHERE id = ?",
                (cursor.lastrowid,),
            ).fetchone()
        )


def _meeting_id(payload):
    return str(
        _payload_value(
            payload,
            (
                "meeting_uuid",
                "meeting_id",
                "zoom_meeting_id",
                "uuid",
                "id",
                "payload.object.uuid",
                "payload.object.id",
                "payload.meeting_uuid",
                "payload.meeting_id",
                "payload.zoom_meeting_id",
            ),
        )
        or _DEFAULT_MEETING_ID
    )


def _meeting_title(payload, meeting_id):
    title = _payload_value(
        payload,
        (
            "topic",
            "title",
            "meeting_title",
            "payload.object.topic",
            "payload.object.title",
            "payload.topic",
            "payload.title",
        ),
    )
    return str(title or f"Zoom Meeting {meeting_id}").strip()


def _transcript_text(payload):
    text = _payload_value(
        payload,
        (
            "text",
            "transcript",
            "sentence",
            "content",
            "payload.text",
            "payload.transcript",
            "payload.sentence",
            "payload.content",
            "payload.object.text",
            "payload.object.transcript",
            "payload.object.sentence",
            "payload.object.content",
        ),
    )
    return str(text or "").strip()


def _speaker(payload):
    speaker = _payload_value(
        payload,
        (
            "speaker",
            "speaker_name",
            "user_name",
            "participant_name",
            "name",
            "payload.speaker",
            "payload.speaker_name",
            "payload.user_name",
            "payload.participant_name",
            "payload.object.speaker",
            "payload.object.speaker_name",
            "payload.object.user_name",
            "payload.object.participant_name",
        ),
    )
    if not speaker:
        return None
    return str(speaker).strip() or None


def _format_line(text, speaker):
    if speaker:
        return f"{speaker}: {text}"
    return text


def _payload_value(payload, paths):
    if not isinstance(payload, dict):
        return None

    for path in paths:
        value = payload
        for part in path.split("."):
            if not isinstance(value, dict) or part not in value:
                value = None
                break
            value = value[part]
        if value not in (None, ""):
            return value
    return None
