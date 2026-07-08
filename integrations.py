from datetime import date
from uuid import NAMESPACE_URL, uuid5

# Calendar invites, .ics, task emails, reminder emails.
# Sprint 2 stubs: these local return values keep route flows testable until
# Google Calendar OAuth and email provider wiring are implemented.


def create_calendar_invite(task, assignee):
    # Sprint 2 stub: return a deterministic local event id instead of calling
    # Google Calendar while manager approval flow is developed.
    if not getattr(task, "due_date", None):
        return None
    return f"stub-calendar-{_task_key(task, assignee)}"


def generate_ics(task):
    if not getattr(task, "due_date", None):
        return None

    event_id = f"stub-calendar-{_task_key(task, None)}"
    due_date = _format_ics_date(task.due_date)
    description = _escape_ics_text(getattr(task, "description", "Task"))
    context = _escape_ics_text(getattr(task, "context", "") or "")

    return "\n".join(
        [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//Nudge//Sprint 2 Stub//EN",
            "BEGIN:VEVENT",
            f"UID:{event_id}",
            f"DTSTART;VALUE=DATE:{due_date}",
            f"SUMMARY:{description}",
            f"DESCRIPTION:{context}",
            "END:VEVENT",
            "END:VCALENDAR",
        ]
    )


def send_task_email(task, assignee):
    return {
        "status": "skipped",
        "reason": "Sprint 2 stub: email integration is not wired yet",
        "task_id": getattr(task, "id", None),
        "assignee": _assignee_identity(assignee),
    }


def send_reminder_email(task, assignee, notification_type):
    return {
        "status": "skipped",
        "reason": "Sprint 2 stub: reminder email integration is not wired yet",
        "notification_type": notification_type,
        "task_id": getattr(task, "id", None),
        "assignee": _assignee_identity(assignee),
    }


def _task_key(task, assignee):
    raw = "|".join(
        [
            str(getattr(task, "id", "") or ""),
            getattr(task, "description", "") or "",
            getattr(task, "due_date", "") or "",
            _assignee_identity(assignee),
        ]
    )
    return uuid5(NAMESPACE_URL, raw).hex[:12]


def _assignee_identity(assignee):
    if assignee is None:
        return ""
    if isinstance(assignee, dict):
        return str(
            assignee.get("email")
            or assignee.get("name")
            or assignee.get("id")
            or ""
        )
    return str(
        getattr(assignee, "email", None)
        or getattr(assignee, "name", None)
        or getattr(assignee, "id", None)
        or ""
    )


def _format_ics_date(value):
    if isinstance(value, date):
        return value.strftime("%Y%m%d")
    return date.fromisoformat(value).strftime("%Y%m%d")


def _escape_ics_text(value):
    return (
        str(value)
        .replace("\\", "\\\\")
        .replace("\n", "\\n")
        .replace(",", "\\,")
        .replace(";", "\\;")
    )
