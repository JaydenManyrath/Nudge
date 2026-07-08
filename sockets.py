from extensions import socketio


@socketio.on("connect")
def handle_connect():
    return None


def emit_transcript_line(line):
    socketio.emit("transcript_line", line)
    return line


def emit_task_updated(task):
    payload = task_payload(task)
    socketio.emit("task_updated", payload)
    return payload


def emit_comment_added(task_id, comment):
    payload = {
        "task_id": task_id,
        "comment": comment_payload(comment),
    }
    socketio.emit("comment_added", payload)
    return payload


def emit_blocker_updated(task, description=None):
    payload = {
        "task_id": task.id,
        "status": task.status,
        "description": description,
    }
    socketio.emit("blocker_updated", payload)
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
