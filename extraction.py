import re

from backend.ai.parser import ExtractionValidationError, validate_extraction
from backend.ingestion.transcript_loader import load_transcript_from_text
from models import Meeting, Task, get_db, row_to_meeting, row_to_task, validate_meeting, validate_task


class ExtractionError(Exception):
    """Raised when transcript extraction cannot produce valid draft data."""


def extract_tasks(transcript_text, job_id=None):
    """
    Deterministic sample/demo extraction path.

    The OpenAI-backed extractor under backend/ai/ is still available for the
    live pipeline, but this root adapter is used by manual/sample upload so
    local development and tests do not require network credentials.
    """
    normalized = load_transcript_from_text(transcript_text)
    if not normalized:
        raise ExtractionError(f"job_id={job_id}: transcript_text is empty")

    raw_result = {
        "summary": _build_summary(normalized),
        "tasks": _extract_candidate_tasks(normalized),
    }

    try:
        return validate_extraction(raw_result)
    except ExtractionValidationError as exc:
        raise ExtractionError(f"job_id={job_id}: extraction failed validation: {exc}") from exc


def create_draft_tasks_from_transcript(title, transcript_text):
    """
    Creates one manual-upload meeting and draft task rows from transcript text.

    Returns {"meeting": Meeting, "tasks": [Task], "extraction": dict}.
    """
    normalized = load_transcript_from_text(transcript_text)
    if not normalized:
        raise ExtractionError("transcript_text is empty")

    meeting_title = (title or _transcript_heading(normalized) or "Uploaded Transcript").strip()
    extraction = extract_tasks(normalized)

    with get_db() as db:
        meeting = Meeting(
            id=None,
            title=meeting_title,
            summary=extraction["summary"],
            transcript=normalized,
            source="manual_upload",
            extraction_status="parsed",
        )
        validate_meeting(meeting)
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
        meeting_id = int(cursor.lastrowid)

        task_ids = []
        for candidate in extraction["tasks"]:
            assignee_id, assignee_name = _resolve_assignee(db, candidate["owner"])
            task = Task(
                id=None,
                meeting_id=meeting_id,
                assignee_id=assignee_id,
                assignee_name=assignee_name,
                description=candidate["description"],
                due_date=candidate["due_date"],
                priority=candidate["priority"],
                context=candidate["context"],
                status="draft",
            )
            validate_task(task)
            cursor = db.execute(
                """
                INSERT INTO tasks (
                    meeting_id,
                    assignee_id,
                    assignee_name,
                    description,
                    due_date,
                    priority,
                    context,
                    status,
                    calendar_event_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task.meeting_id,
                    task.assignee_id,
                    task.assignee_name,
                    task.description,
                    task.due_date,
                    task.priority,
                    task.context,
                    task.status,
                    task.calendar_event_id,
                ),
            )
            task_ids.append(int(cursor.lastrowid))

        db.commit()

        saved_meeting = row_to_meeting(
            db.execute("SELECT * FROM meetings WHERE id = ?", (meeting_id,)).fetchone()
        )
        saved_tasks = [
            row_to_task(db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone())
            for task_id in task_ids
        ]

    return {
        "meeting": saved_meeting,
        "tasks": saved_tasks,
        "extraction": extraction,
    }


def _extract_candidate_tasks(transcript_text):
    tasks = []
    lines = [line.strip() for line in transcript_text.splitlines() if line.strip()]

    for line in lines:
        if line.startswith("[") and line.endswith("]"):
            continue
        if ":" not in line:
            continue

        speaker, utterance = [part.strip() for part in line.split(":", 1)]
        task = _task_from_utterance(speaker, utterance, line)
        if task is not None:
            tasks.append(task)

    return _dedupe_tasks(tasks)


def _task_from_utterance(speaker, utterance, context):
    lower = utterance.lower()
    priority = _priority_for(utterance)

    request_match = re.search(
        r"^(?P<owner>[A-Z][A-Za-z .'-]+),\s+can you\s+(?P<action>.+)",
        utterance,
    )
    if request_match:
        return _candidate(
            owner=request_match.group("owner"),
            action=request_match.group("action"),
            priority=priority,
            context=context,
        )

    if lower.startswith("someone should "):
        return _candidate(
            owner="unassigned",
            action=utterance[len("Someone should ") :],
            priority=priority,
            context=context,
        )

    if lower.startswith("someone needs to "):
        return _candidate(
            owner="unassigned",
            action=utterance[len("Someone needs to ") :],
            priority=priority,
            context=context,
        )

    pledge_match = re.search(
        r"\b(?:i'll|i will|i can)\s+(?P<action>.+)",
        utterance,
        flags=re.IGNORECASE,
    )
    if pledge_match:
        return _candidate(
            owner=speaker,
            action=pledge_match.group("action"),
            priority=priority,
            context=context,
        )

    return None


def _candidate(owner, action, priority, context):
    description = _clean_description(action)
    if not description:
        return None

    return {
        "owner": owner.strip() or "unassigned",
        "description": description,
        "due_date": None,
        "priority": priority,
        "context": context,
    }


def _clean_description(action):
    cleaned = action.strip()
    cleaned = re.split(r"\s+(?:actually|though)[,.]?\s*", cleaned, maxsplit=1)[0]
    cleaned = cleaned.rstrip(" .?!")
    cleaned = re.sub(r"^(?:to\s+)", "", cleaned, flags=re.IGNORECASE)
    if not cleaned:
        return ""
    return cleaned[0].upper() + cleaned[1:]


def _priority_for(text):
    lower = text.lower()
    if any(term in lower for term in ("urgent", "high priority", "blocking", "blocker")):
        return "urgent"
    if any(term in lower for term in ("low priority", "no rush", "eventually")):
        return "low"
    return "normal"


def _build_summary(transcript_text):
    title = _transcript_heading(transcript_text) or "Uploaded transcript"
    task_count = len(_extract_candidate_tasks(transcript_text))
    if task_count == 0:
        return f"{title}: no clear action items were identified."
    suffix = "task" if task_count == 1 else "tasks"
    return f"{title}: identified {task_count} draft {suffix} for manager review."


def _transcript_heading(transcript_text):
    for line in transcript_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            return stripped.strip("[]").replace("\u2014", "-")
    return None


def _dedupe_tasks(tasks):
    seen = set()
    deduped = []
    for task in tasks:
        key = (task["owner"].lower(), task["description"].lower())
        if key in seen:
            continue
        seen.add(key)
        deduped.append(task)
    return deduped


def _resolve_assignee(db, owner):
    if not owner or owner.lower() == "unassigned":
        return None, "unassigned"

    normalized_owner = owner.strip().lower()
    rows = db.execute("SELECT id, name, email FROM users").fetchall()
    for row in rows:
        name = row["name"].strip().lower()
        first_name = name.split()[0] if name else ""
        email = row["email"].strip().lower()
        if normalized_owner in {name, first_name, email}:
            return int(row["id"]), row["name"]

    return None, owner.strip()
