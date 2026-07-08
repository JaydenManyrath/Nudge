from flask_login import current_user
from flask_socketio import join_room

from extensions import socketio
from models import get_db

MANAGERS_ROOM = "managers"


def _user_room(user_id):
    return f"user:{user_id}"


@socketio.on("connect")
def handle_connect():
    # Scope realtime pushes: an employee joins only their own room; a manager
    # joins the managers room plus every user's room, so managers observe all
    # task streams while employees only receive their own. current_user is
    # available because Flask-SocketIO shares the Flask login session.
    if not getattr(current_user, "is_authenticated", False):
        return None

    if getattr(current_user, "role", None) == "manager":
        join_room(MANAGERS_ROOM)
        with get_db() as db:
            for row in db.execute("SELECT id FROM users").fetchall():
                join_room(_user_room(row["id"]))
    else:
        join_room(_user_room(current_user.id))
    return None


def _scoped_room(assignee_id):
    # Assigned tasks go to the assignee's room (managers are members too);
    # unassigned tasks go to managers only.
    return _user_room(assignee_id) if assignee_id is not None else MANAGERS_ROOM


def emit_transcript_line(line):
    # Live meeting transcript is a manager-facing view.
    socketio.emit("transcript_line", line, to=MANAGERS_ROOM)
    return line


def emit_task_updated(task):
    payload = task_payload(task)
    socketio.emit("task_updated", payload, to=_scoped_room(task.assignee_id))
    return payload


def emit_comment_added(task, comment):
    payload = {
        "task_id": task.id,
        "comment": comment_payload(comment),
    }
    socketio.emit("comment_added", payload, to=_scoped_room(task.assignee_id))
    return payload


def emit_blocker_updated(task, description=None):
    payload = {
        "task_id": task.id,
        "status": task.status,
        "description": description,
    }
    socketio.emit("blocker_updated", payload, to=_scoped_room(task.assignee_id))
    return payload


def task_payload(task):
    return {
        "id": task.id,
        "status": task.status,
        "priority": task.priority,
        "due_date": _format_due_date(task.due_date),
        "due_date_iso": task.due_date,
        "description": task.description,
        "owner": task.owner,
    }


def comment_payload(comment):
    if isinstance(comment, dict):
        return {
            "author": comment.get("author") or "Unknown",
            "role": comment.get("role") or "",
            "body": comment.get("body") or "",
            "created_at": comment.get("created_at"),
        }

    return {
        "author": comment["author"] or "Unknown",
        "role": comment["role"] or "",
        "body": comment["body"],
        "created_at": comment["created_at"],
    }


def _format_due_date(value):
    if not value:
        return "No due date"
    return value
