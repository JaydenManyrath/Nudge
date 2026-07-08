from datetime import date, timedelta

from flask import Blueprint, render_template
from flask_login import current_user, login_required

from auth import manager_required
from models import get_db

bp = Blueprint("dashboard", __name__, url_prefix="/dashboard")

ACTIVE_STATUSES = ("pending", "blocked", "done")


@bp.route("/manager")
@manager_required
def manager_dashboard():
    with get_db() as db:
        rows = _active_task_rows(db)

    tasks = [_manager_task_view(row) for row in rows]
    metrics = _manager_metrics(tasks)

    return render_template(
        "dashboard_manager.html",
        tasks=tasks,
        metrics=metrics,
        integrations={
            "zoom": {"connected": False, "error": None},
            "calendar": {"connected": False, "error": None},
        },
        notification_count=metrics["due_soon"] + metrics["overdue"],
    )


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
