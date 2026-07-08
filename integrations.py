import os
from datetime import date, datetime, timedelta, timezone
from uuid import NAMESPACE_URL, uuid5

from models import get_db, row_to_oauth_token

# Calendar invites, .ics, task emails, reminder emails.
# Sprint 2 stubs: these local return values keep route flows testable until
# Google Calendar OAuth and email provider wiring are implemented.


def create_calendar_invite(task, assignee):
    metadata = create_calendar_event_metadata(task, assignee)
    if metadata["status"] == "failed":
        raise RuntimeError(metadata["error"])
    return metadata["event_id"]


def create_calendar_event_metadata(task, assignee):
    if not getattr(task, "due_date", None):
        return _calendar_metadata(
            status="skipped",
            provider=None,
            calendar_id=None,
            event_id=None,
            html_link=None,
            error="missing_due_date",
        )

    try:
        token = _latest_google_calendar_token()
    except Exception as exc:
        return _calendar_metadata(
            status="failed",
            provider="google",
            calendar_id=None,
            event_id=None,
            html_link=None,
            error=str(exc),
        )
    if token is None:
        # Keep the demo/local test path working when Google is not connected.
        event_id = f"stub-calendar-{_task_key(task, assignee)}"
        return _calendar_metadata(
            status="stubbed",
            provider="stub",
            calendar_id=None,
            event_id=event_id,
            html_link=None,
            error=None,
        )

    calendar_id = "primary"
    try:
        service = _build_google_calendar_service(token)
        created_event = (
            service.events()
            .insert(
                calendarId=calendar_id,
                body=_calendar_event_body(task, assignee),
                sendUpdates="all",
            )
            .execute()
        )
        event_id = created_event.get("id")
        if not event_id:
            raise RuntimeError("Google Calendar did not return an event id.")
        return _calendar_metadata(
            status="created",
            provider="google",
            calendar_id=calendar_id,
            event_id=event_id,
            html_link=created_event.get("htmlLink"),
            error=None,
        )
    except Exception as exc:
        return _calendar_metadata(
            status="failed",
            provider="google",
            calendar_id=calendar_id,
            event_id=None,
            html_link=None,
            error=str(exc),
        )


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


def _latest_google_calendar_token():
    with get_db() as db:
        row = db.execute(
            """
            SELECT *
            FROM oauth_tokens
            WHERE provider = 'google'
            ORDER BY updated_at DESC, created_at DESC, id DESC
            LIMIT 1
            """
        ).fetchone()
    return row_to_oauth_token(row)


def _calendar_metadata(
    *,
    status,
    provider,
    calendar_id,
    event_id,
    html_link,
    error,
):
    return {
        "provider": provider,
        "calendar_id": calendar_id,
        "event_id": event_id,
        "html_link": html_link,
        "status": status,
        "synced_at": _utc_now_iso(),
        "error": error,
    }


def _build_google_calendar_service(token):
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    credentials = Credentials(
        token=token.access_token,
        refresh_token=token.refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ.get("GOOGLE_CLIENT_ID"),
        client_secret=os.environ.get("GOOGLE_CLIENT_SECRET"),
        scopes=(token.scope or "https://www.googleapis.com/auth/calendar.events").split(),
        expiry=_token_expiry(token.expires_at),
    )
    return build("calendar", "v3", credentials=credentials, cache_discovery=False)


def _calendar_event_body(task, assignee):
    due_date = _parse_due_date(task.due_date)
    end_date = due_date + timedelta(days=1)
    body = {
        "summary": getattr(task, "description", "Nudge task"),
        "description": _event_description(task),
        "start": {"date": due_date.isoformat()},
        "end": {"date": end_date.isoformat()},
    }

    attendee_email = _assignee_email(task, assignee)
    if attendee_email:
        body["attendees"] = [{"email": attendee_email}]
    return body


def _event_description(task):
    context = getattr(task, "context", None)
    parts = ["Created from a Nudge-approved meeting task."]
    if context:
        parts.append(str(context))
    return "\n\n".join(parts)


def _assignee_email(task, assignee):
    if isinstance(assignee, dict) and assignee.get("email"):
        return str(assignee["email"])
    email = getattr(assignee, "email", None)
    if email:
        return str(email)

    assignee_id = getattr(task, "assignee_id", None)
    if assignee_id is None and isinstance(assignee, dict):
        assignee_id = assignee.get("id")
    if assignee_id is None:
        return None

    with get_db() as db:
        row = db.execute(
            "SELECT email FROM users WHERE id = ?",
            (assignee_id,),
        ).fetchone()
    return row["email"] if row else None


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
    return _parse_due_date(value).strftime("%Y%m%d")


def _parse_due_date(value):
    if isinstance(value, date):
        return value
    return date.fromisoformat(value)


def _token_expiry(value):
    if not value:
        return None

    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed
    return parsed.astimezone(timezone.utc).replace(tzinfo=None)


def _utc_now_iso():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _escape_ics_text(value):
    return (
        str(value)
        .replace("\\", "\\\\")
        .replace("\n", "\\n")
        .replace(",", "\\,")
        .replace(";", "\\;")
    )
