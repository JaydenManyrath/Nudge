from flask import Blueprint, abort, jsonify, request
from flask_login import current_user, login_required

import sockets
from models import Comment, get_db, row_to_task, validate_comment

bp = Blueprint("api", __name__, url_prefix="/api")

ACTIVE_STATUSES = ("pending", "blocked", "done")
SPRINT_2_STUB_MESSAGE = "Sprint 2 stub: this API endpoint is not wired yet."


@bp.route("/tasks/<int:task_id>/done", methods=["POST"])
@login_required
def mark_done(task_id):
    with get_db() as db:
        task = _get_accessible_task(db, task_id)
        if task.status != "done":
            _update_task_status(db, task.id, "done")
            task = _task_by_id(db, task.id)
            db.commit()

    payload = sockets.emit_task_updated(task)
    return jsonify({"task": payload})


@bp.route("/tasks/<int:task_id>/reopen", methods=["POST"])
@login_required
def reopen(task_id):
    # Move a completed task back to pending ("mark undone").
    with get_db() as db:
        task = _get_accessible_task(db, task_id)
        if task.status == "done":
            _update_task_status(db, task.id, "pending")
            task = _task_by_id(db, task.id)
            db.commit()

    payload = sockets.emit_task_updated(task)
    return jsonify({"task": payload})


@bp.route("/tasks/<int:task_id>/blockers", methods=["POST"])
@login_required
def add_blocker(task_id):
    body = _json_body()
    description = str(body.get("description") or "").strip()
    if not description:
        abort(400, "Blocker description is required.")

    with get_db() as db:
        task = _get_accessible_task(db, task_id)
        if task.status == "done":
            abort(409, "Done tasks cannot be blocked.")

        _update_task_status(db, task.id, "blocked")
        comment = _insert_comment(db, task.id, f"Blocker: {description}")
        task = _task_by_id(db, task.id)
        db.commit()

    task_payload = sockets.emit_task_updated(task)
    blocker_payload = sockets.emit_blocker_updated(task, description)
    comment_payload = sockets.emit_comment_added(task, comment)
    return jsonify(
        {
            "task": task_payload,
            "blocker": blocker_payload,
            "comment": comment_payload["comment"],
        }
    )


@bp.route("/tasks/<int:task_id>/blockers/resolve", methods=["POST"])
@login_required
def resolve_blocker(task_id):
    with get_db() as db:
        task = _get_accessible_task(db, task_id)
        if task.status == "blocked":
            _update_task_status(db, task.id, "pending")
            comment = _insert_comment(db, task.id, "Blocker resolved.")
            task = _task_by_id(db, task.id)
            db.commit()
        else:
            comment = None

    task_payload = sockets.emit_task_updated(task)
    blocker_payload = sockets.emit_blocker_updated(task, None)
    response = {
        "task": task_payload,
        "blocker": blocker_payload,
    }
    if comment is not None:
        response["comment"] = sockets.emit_comment_added(task, comment)["comment"]
    return jsonify(response)


@bp.route("/tasks/<int:task_id>/comments")
@login_required
def list_comments(task_id):
    with get_db() as db:
        _get_accessible_task(db, task_id)
        rows = db.execute(
            """
            SELECT
                comments.body,
                comments.created_at,
                COALESCE(users.name, 'Unknown') AS author,
                COALESCE(users.role, '') AS role
            FROM comments
            LEFT JOIN users ON users.id = comments.author_id
            WHERE comments.task_id = ?
            ORDER BY comments.created_at ASC, comments.id ASC
            """,
            (task_id,),
        ).fetchall()

    return jsonify({"comments": [sockets.comment_payload(row) for row in rows]})


@bp.route("/tasks/<int:task_id>/comments", methods=["POST"])
@login_required
def add_comment(task_id):
    body = str(_json_body().get("body") or "").strip()
    if not body:
        abort(400, "Comment body is required.")

    with get_db() as db:
        task = _get_accessible_task(db, task_id)
        comment = _insert_comment(db, task.id, body)
        db.commit()

    payload = sockets.emit_comment_added(task, comment)
    return jsonify({"comment": payload["comment"]}), 201


@bp.route("/jobs/<int:job_id>/status")
@login_required
def job_status(job_id):
    abort(501, SPRINT_2_STUB_MESSAGE)


@bp.route("/notifications/badge")
@login_required
def notification_badge():
    abort(501, SPRINT_2_STUB_MESSAGE)


def _json_body():
    return request.get_json(silent=True) or {}


def _get_accessible_task(db, task_id):
    task = _task_by_id(db, task_id)
    if task is None or task.status not in ACTIVE_STATUSES:
        abort(404)
    if getattr(current_user, "role", None) == "manager":
        return task
    if task.assignee_id != int(current_user.id):
        abort(403)
    return task


def _task_by_id(db, task_id):
    row = db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    return row_to_task(row)


def _update_task_status(db, task_id, status):
    db.execute(
        """
        UPDATE tasks
        SET status = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (status, task_id),
    )


def _insert_comment(db, task_id, body):
    comment = Comment(
        id=None,
        task_id=task_id,
        author_id=int(current_user.id),
        body=body,
    )
    try:
        validate_comment(comment)
    except ValueError as exc:
        abort(400, str(exc))

    cursor = db.execute(
        """
        INSERT INTO comments (task_id, author_id, body)
        VALUES (?, ?, ?)
        """,
        (comment.task_id, comment.author_id, comment.body),
    )
    return _comment_by_id(db, int(cursor.lastrowid))


def _comment_by_id(db, comment_id):
    return db.execute(
        """
        SELECT
            comments.body,
            comments.created_at,
            COALESCE(users.name, 'Unknown') AS author,
            COALESCE(users.role, '') AS role
        FROM comments
        LEFT JOIN users ON users.id = comments.author_id
        WHERE comments.id = ?
        """,
        (comment_id,),
    ).fetchone()
