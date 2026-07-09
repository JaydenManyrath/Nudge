import hashlib
from datetime import date, datetime, timedelta, timezone

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required

from auth import manager_required
from backend.ingestion.zoom_recordings import (
    ZoomNoTranscriptError,
    ZoomPermissionError,
    ZoomRecordingError,
    ZoomTokenRefreshError,
    latest_transcript_for_user,
)
from extraction import ExtractionError, create_draft_tasks_from_transcript
from models import get_db, get_oauth_token

bp = Blueprint("dashboard", __name__, url_prefix="/dashboard")

ACTIVE_STATUSES = ("pending", "blocked", "done")
ZOOM_TRANSCRIPT_SESSION_KEY = "zoom_cloud_recording_transcript"
ZOOM_TRANSCRIPT_MAX_BYTES = 50 * 1024
ZOOM_TRANSCRIPT_SESSION_TTL = timedelta(minutes=30)


@bp.route("/manager")
@manager_required
def manager_dashboard():
    with get_db() as db:
        rows = _active_task_rows(db)
        zoom_connected = _zoom_connected(db)
        google_token = get_oauth_token(
            db,
            user_id=int(current_user.id),
            provider="google",
        )

    tasks = [_manager_task_view(row) for row in rows]
    metrics = _manager_metrics(tasks)

    return render_template(
        "dashboard_manager.html",
        tasks=tasks,
        metrics=metrics,
        integrations={
            "zoom": {
                "connected": zoom_connected,
                "error": request.args.get("zoom_error"),
            },
            "calendar": {
                "connected": google_token is not None,
                "error": request.args.get("calendar_error"),
            },
        },
        notification_count=metrics["due_soon"] + metrics["overdue"],
    )


@bp.route("/live")
@manager_required
def live_meeting():
    session.pop(ZOOM_TRANSCRIPT_SESSION_KEY, None)
    zoom_transcript = None
    zoom_error = None
    transcript_too_large = False

    with get_db() as db:
        zoom_token = get_oauth_token(
            db,
            user_id=int(current_user.id),
            provider="zoom",
        )
        zoom_connected = zoom_token is not None
        if zoom_token is not None:
            try:
                zoom_transcript = latest_transcript_for_user(db, zoom_token)
            except ZoomTokenRefreshError:
                zoom_error = "Reconnect Zoom to load cloud recording transcripts."
            except ZoomPermissionError:
                zoom_error = (
                    "Zoom did not allow access to cloud recordings. Reconnect Zoom "
                    "with recording permissions."
                )
            except ZoomNoTranscriptError as exc:
                zoom_error = str(exc)
            except ZoomRecordingError:
                zoom_error = "Zoom cloud recording transcripts could not be loaded."

    staged_transcript = None
    if zoom_transcript is not None:
        staged_transcript = _zoom_transcript_session_payload(zoom_transcript)
        transcript_too_large = (
            len(staged_transcript["transcript_text"].encode("utf-8"))
            > ZOOM_TRANSCRIPT_MAX_BYTES
        )
        if not transcript_too_large:
            session[ZOOM_TRANSCRIPT_SESSION_KEY] = staged_transcript

    return render_template(
        "live.html",
        zoom_connected=zoom_connected,
        zoom_transcript=staged_transcript,
        zoom_error=zoom_error,
        zoom_transcript_too_large=transcript_too_large,
        zoom_transcript_max_kb=ZOOM_TRANSCRIPT_MAX_BYTES // 1024,
    )


@bp.route("/live/import", methods=["POST"])
@manager_required
def import_live_meeting():
    staged = session.get(ZOOM_TRANSCRIPT_SESSION_KEY)
    if not staged or _staged_transcript_expired(staged):
        session.pop(ZOOM_TRANSCRIPT_SESSION_KEY, None)
        flash("Zoom transcript staging expired. Reload the live meeting page.", "error")
        return redirect(url_for("dashboard.live_meeting"))

    if request.form.get("transcript_hash") != staged.get("transcript_hash"):
        flash("Zoom transcript changed before import. Reload the live meeting page.", "error")
        return redirect(url_for("dashboard.live_meeting"))

    zoom_meeting_id = staged.get("zoom_meeting_id")
    with get_db() as db:
        duplicate = db.execute(
            """
            SELECT id
            FROM meetings
            WHERE source = 'zoom_cloud_recording'
              AND zoom_meeting_id = ?
            LIMIT 1
            """,
            (zoom_meeting_id,),
        ).fetchone()
    if duplicate:
        session.pop(ZOOM_TRANSCRIPT_SESSION_KEY, None)
        flash("That Zoom cloud recording has already been imported.", "error")
        return redirect(url_for("review.list_drafts"))

    try:
        result = create_draft_tasks_from_transcript(
            staged.get("title"),
            staged.get("transcript_text"),
            source="zoom_cloud_recording",
            zoom_meeting_id=zoom_meeting_id,
            meeting_date=staged.get("meeting_date"),
        )
    except ExtractionError:
        flash("Zoom transcript import failed. Review the transcript and try again.", "error")
        return redirect(url_for("dashboard.live_meeting"))

    session.pop(ZOOM_TRANSCRIPT_SESSION_KEY, None)
    task_count = len(result["tasks"])
    flash(
        f"Created {task_count} draft task{'s' if task_count != 1 else ''} "
        f"from {result['meeting'].title}.",
        "success",
    )
    if result["extraction_warning"]:
        flash(result["extraction_warning"], "error")
    return redirect(url_for("review.list_drafts"))


@bp.route("/employee")
@login_required
def employee_dashboard():
    with get_db() as db:
        rows = _active_task_rows(db, assignee_id=int(current_user.id))

    tasks = [_employee_task_view(row) for row in rows]
    summary = _employee_summary(tasks)

    return render_template(
        "dashboard_employee.html",
        tasks=tasks,
        summary=summary,
        notification_count=summary["due_today"] + summary["blocked"],
    )


def _zoom_connected(db):
    return (
        get_oauth_token(
            db,
            user_id=int(current_user.id),
            provider="zoom",
        )
        is not None
    )


def _active_task_rows(db, *, assignee_id=None):
    params = list(ACTIVE_STATUSES)
    assignee_filter = ""
    if assignee_id is not None:
        assignee_filter = "AND tasks.assignee_id = ?"
        params.append(assignee_id)

    return db.execute(
        f"""
        SELECT
            tasks.*,
            meetings.title AS meeting_title,
            meetings.summary AS meeting_summary
        FROM tasks
        LEFT JOIN meetings ON meetings.id = tasks.meeting_id
        WHERE tasks.status IN (?, ?, ?)
          {assignee_filter}
        ORDER BY
            CASE WHEN tasks.due_date IS NULL THEN 1 ELSE 0 END,
            tasks.due_date ASC,
            tasks.created_at ASC,
            tasks.id ASC
        """,
        params,
    ).fetchall()


def _manager_task_view(row):
    return {
        "id": row["id"],
        "owner": row["assignee_name"] or "unassigned",
        "description": row["description"],
        "due_date": _format_due_date(row["due_date"]),
        "due_date_iso": row["due_date"],
        "priority": row["priority"],
        "status": row["status"],
        "context": row["context"] or _meeting_context(row),
    }


def _employee_task_view(row):
    return {
        "id": row["id"],
        "description": row["description"],
        "due_date": _format_due_date(row["due_date"]),
        "due_date_iso": row["due_date"],
        "priority": row["priority"],
        "status": row["status"],
        "from_meeting": row["meeting_title"] or "Unlinked meeting",
        "context": row["context"] or _meeting_context(row),
    }


def _manager_metrics(tasks):
    return {
        "open": sum(1 for task in tasks if task["status"] in {"pending", "blocked"}),
        "due_soon": sum(1 for task in tasks if _is_due_this_week(task)),
        "blocked": sum(1 for task in tasks if task["status"] == "blocked"),
        "overdue": sum(1 for task in tasks if _is_overdue(task)),
    }


def _employee_summary(tasks):
    today = date.today()
    return {
        "due_today": sum(1 for task in tasks if _task_due_date(task) == today),
        "due_this_week": sum(1 for task in tasks if _is_due_this_week(task)),
        "blocked": sum(1 for task in tasks if task["status"] == "blocked"),
    }


def _meeting_context(row):
    if row["meeting_title"]:
        return f"From {row['meeting_title']}"
    if row["meeting_summary"]:
        return row["meeting_summary"]
    return "No context available."


def _format_due_date(value):
    due_date = _parse_due_date(value)
    if due_date is None:
        return "No due date"
    return f"{due_date.strftime('%b')} {due_date.day}"


def _is_due_this_week(task):
    due_date = _task_due_date(task)
    if due_date is None or task["status"] == "done":
        return False
    today = date.today()
    return today <= due_date <= today + timedelta(days=7)


def _is_overdue(task):
    due_date = _task_due_date(task)
    return due_date is not None and task["status"] != "done" and due_date < date.today()


def _task_due_date(task):
    return _parse_due_date(task.get("due_date_iso"))


def _parse_due_date(value):
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _zoom_transcript_session_payload(zoom_transcript):
    transcript_hash = hashlib.sha256(
        zoom_transcript.transcript_text.encode("utf-8")
    ).hexdigest()
    return {
        "zoom_meeting_id": zoom_transcript.zoom_meeting_id,
        "title": zoom_transcript.title,
        "meeting_date": zoom_transcript.meeting_date,
        "transcript_text": zoom_transcript.transcript_text,
        "transcript_hash": transcript_hash,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


def _staged_transcript_expired(staged):
    fetched_at = staged.get("fetched_at")
    if not fetched_at:
        return True
    try:
        parsed = datetime.fromisoformat(fetched_at)
    except ValueError:
        return True
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - parsed > ZOOM_TRANSCRIPT_SESSION_TTL
