import json
from dataclasses import replace

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

import sockets
from auth import manager_required
from integrations import create_calendar_event_metadata
from models import Task, get_db, row_to_meeting, row_to_task, validate_task

bp = Blueprint("review", __name__, url_prefix="/review")


@bp.route("/")
@manager_required
def list_drafts():
    with get_db() as db:
        draft_rows = db.execute(
            """
            SELECT *
            FROM tasks
            WHERE status = 'draft'
            ORDER BY created_at ASC, id ASC
            """
        ).fetchall()
        draft_tasks = [_task_view_model(row_to_task(row)) for row in draft_rows]
        meeting = _latest_draft_meeting(db)
        user_rows = db.execute(
            "SELECT id, name, email FROM users ORDER BY role DESC, name ASC"
        ).fetchall()
        users = [dict(row) for row in user_rows]

    return render_template(
        "review.html",
        draft_tasks=draft_tasks,
        meeting=meeting,
        users=users,
    )


@bp.route("/add", methods=["POST"])
@manager_required
def add_task():
    description = request.form.get("description", "").strip()
    if not description:
        flash("Task description is required.", "error")
        return redirect(url_for("review.list_drafts"))

    priority = request.form.get("priority", "normal").strip() or "normal"
    due_date = request.form.get("due_date", "").strip() or None

    with get_db() as db:
        assignee_id, assignee_name = _resolve_assignee(
            db, request.form.get("owner", "").strip()
        )
        task = Task(
            id=None,
            meeting_id=None,
            assignee_id=assignee_id,
            assignee_name=assignee_name,
            description=description,
            due_date=due_date,
            priority=priority,
            context="Added manually.",
            status="draft",
        )
        _validate_or_abort(task)
        db.execute(
            """
            INSERT INTO tasks (
                meeting_id, assignee_id, assignee_name, description,
                due_date, priority, context, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, 'draft')
            """,
            (
                task.meeting_id,
                task.assignee_id,
                task.assignee_name,
                task.description,
                task.due_date,
                task.priority,
                task.context,
            ),
        )
        db.commit()

    flash("Draft task added.", "success")
    return redirect(url_for("review.list_drafts"))


@bp.route("/<int:task_id>/approve", methods=["POST"])
@manager_required
def approve(task_id):
    sync_error = None
    with get_db() as db:
        task = _get_draft_task(db, task_id)
        updated = _task_from_form(db, task, status="pending")
        _validate_or_abort(updated)
        metadata = create_calendar_event_metadata(updated, _assignee_for_task(updated))
        if metadata["status"] == "failed":
            sync_error = metadata["error"]
        updated = replace(
            updated,
            calendar_event_id=metadata["event_id"],
            calendar_event_metadata=json.dumps(metadata, sort_keys=True),
        )
        _update_task(db, updated)
        db.commit()

    sockets.emit_task_updated(updated)
    flash("Task approved.", "success")
    if sync_error:
        flash(f"Calendar sync failed: {sync_error}. The task was still saved.", "error")
    return redirect(url_for("review.list_drafts"))


@bp.route("/<int:task_id>/edit", methods=["POST"])
@manager_required
def edit(task_id):
    with get_db() as db:
        task = _get_draft_task(db, task_id)
        updated = _task_from_form(db, task, status="draft")
        _validate_or_abort(updated)
        _update_task(db, updated)
        db.commit()

    sockets.emit_task_updated(updated)
    flash("Draft task updated.", "success")
    return redirect(url_for("review.list_drafts"))


@bp.route("/<int:task_id>/reject", methods=["POST"])
@manager_required
def reject(task_id):
    with get_db() as db:
        task = _get_draft_task(db, task_id)
        rejected = Task(
            id=task.id,
            meeting_id=task.meeting_id,
            assignee_id=task.assignee_id,
            assignee_name=task.assignee_name,
            description=task.description,
            due_date=task.due_date,
            priority=task.priority,
            context=task.context,
            status="rejected",
            calendar_event_id=task.calendar_event_id,
            calendar_event_metadata=task.calendar_event_metadata,
            created_at=task.created_at,
            updated_at=task.updated_at,
        )
        _update_task(db, rejected)
        db.commit()

    sockets.emit_task_updated(rejected)
    flash("Draft task rejected.", "info")
    return redirect(url_for("review.list_drafts"))


def _latest_draft_meeting(db):
    row = db.execute(
        """
        SELECT meetings.*
        FROM meetings
        JOIN tasks ON tasks.meeting_id = meetings.id
        WHERE tasks.status = 'draft'
        ORDER BY tasks.created_at DESC, tasks.id DESC
        LIMIT 1
        """
    ).fetchone()
    meeting = row_to_meeting(row)
    if meeting is None:
        return {
            "title": "Draft Tasks",
            "summary": "No draft tasks are waiting for review.",
            "source": "n/a",
            "extraction_status": "n/a",
            "calendar_sync_status": "n/a",
        }
    return {
        "title": meeting.title,
        "summary": meeting.summary or "No meeting summary available.",
        "source": meeting.source,
        "extraction_status": meeting.extraction_status,
        "calendar_sync_status": "Waiting for approval",
    }


def _get_draft_task(db, task_id):
    row = db.execute(
        "SELECT * FROM tasks WHERE id = ? AND status = 'draft'",
        (task_id,),
    ).fetchone()
    task = row_to_task(row)
    if task is None:
        abort(404)
    return task


def _task_from_form(db, task, *, status):
    owner = request.form.get("owner", task.assignee_name or "").strip()
    description = request.form.get("description", task.description).strip()
    due_date = request.form.get("due_date", task.due_date or "").strip() or None
    priority = request.form.get("priority", task.priority).strip()
    context = request.form.get("context", task.context or "").strip() or task.context
    assignee_id, assignee_name = _resolve_assignee(db, owner)

    return Task(
        id=task.id,
        meeting_id=task.meeting_id,
        assignee_id=assignee_id,
        assignee_name=assignee_name,
        description=description,
        due_date=due_date,
        priority=priority,
        context=context,
        status=status,
        calendar_event_id=task.calendar_event_id,
        calendar_event_metadata=task.calendar_event_metadata,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


def _resolve_assignee(db, owner):
    if not owner:
        return None, "unassigned"

    row = db.execute(
        """
        SELECT id, name
        FROM users
        WHERE lower(name) = lower(?) OR lower(email) = lower(?)
        LIMIT 1
        """,
        (owner, owner),
    ).fetchone()

    if row is None:
        return None, owner
    return int(row["id"]), row["name"]


def _assignee_for_task(task):
    return {
        "id": task.assignee_id,
        "name": task.assignee_name,
    }


def _validate_or_abort(task):
    try:
        validate_task(task)
    except ValueError as exc:
        abort(400, str(exc))


def _update_task(db, task):
    db.execute(
        """
        UPDATE tasks
        SET assignee_id = ?,
            assignee_name = ?,
            description = ?,
            due_date = ?,
            priority = ?,
            context = ?,
            status = ?,
            calendar_event_id = ?,
            calendar_event_metadata = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (
            task.assignee_id,
            task.assignee_name,
            task.description,
            task.due_date,
            task.priority,
            task.context,
            task.status,
            task.calendar_event_id,
            task.calendar_event_metadata,
            task.id,
        ),
    )


def _task_view_model(task):
    return {
        "id": task.id,
        "owner": task.owner,
        "assignee_id": task.assignee_id,
        "priority": task.priority,
        "due_date": task.due_date or "",
        "description": task.description,
        "context": task.context or "",
    }
