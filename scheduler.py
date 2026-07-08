import json
from datetime import date, datetime, timedelta, timezone

from apscheduler.schedulers.background import BackgroundScheduler

import integrations
from models import get_db, row_to_task

scheduler = BackgroundScheduler()

DUE_SOON_DAYS = 7
NOTIFICATION_CHANNEL = "email"
ACTIVE_STATUSES = ("pending", "blocked")


def daily_sweep(today=None):
    today = _coerce_date(today) or date.today()
    due_soon_until = today + timedelta(days=DUE_SOON_DAYS)
    summary = {
        "due_soon": 0,
        "overdue": 0,
        "sent": 0,
        "skipped": 0,
        "notifications": [],
    }

    with get_db() as db:
        rows = db.execute(
            """
            SELECT
                tasks.*,
                users.id AS assignee_user_id,
                users.name AS assignee_user_name,
                users.email AS assignee_user_email,
                users.role AS assignee_user_role
            FROM tasks
            LEFT JOIN users ON users.id = tasks.assignee_id
            WHERE tasks.status IN (?, ?)
              AND tasks.due_date IS NOT NULL
            ORDER BY tasks.due_date ASC, tasks.id ASC
            """,
            ACTIVE_STATUSES,
        ).fetchall()

        for row in rows:
            due_date = _coerce_date(row["due_date"])
            if due_date is None:
                summary["skipped"] += 1
                continue

            if due_date < today:
                notification_type = "overdue"
            elif today <= due_date <= due_soon_until:
                notification_type = "due_soon"
            else:
                continue

            task = row_to_task(row)
            assignee = _assignee_from_row(row)
            if not _claim_notification(db, task, notification_type):
                summary["skipped"] += 1
                continue
            db.commit()

            result = _send_reminder_email(task, assignee, notification_type)
            _store_notification_result(db, task.id, notification_type, result)
            db.commit()

            summary[notification_type] += 1
            if result.get("status") == "failed":
                summary["skipped"] += 1
            else:
                summary["sent"] += 1
            summary["notifications"].append(
                {
                    "task_id": task.id,
                    "notification_type": notification_type,
                    "assignee": assignee,
                    "result": result,
                }
            )

    return summary


def init_scheduler():
    scheduler.add_job(
        daily_sweep,
        "cron",
        hour=8,
        minute=0,
        id="daily_sweep",
        replace_existing=True,
    )
    if not scheduler.running:
        scheduler.start()
    return scheduler


def _send_reminder_email(task, assignee, notification_type):
    try:
        return integrations.send_reminder_email(
            task,
            assignee,
            notification_type,
        )
    except Exception as exc:
        return {
            "status": "failed",
            "error": str(exc),
            "notification_type": notification_type,
            "task_id": task.id,
            "assignee": assignee,
            "failed_at": _utc_now_iso(),
        }


def _claim_notification(db, task, notification_type):
    cursor = db.execute(
        """
        INSERT OR IGNORE INTO notifications (
            task_id,
            user_id,
            notification_type,
            channel,
            metadata
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            task.id,
            task.assignee_id,
            notification_type,
            NOTIFICATION_CHANNEL,
            json.dumps({"status": "pending"}),
        ),
    )
    return cursor.rowcount == 1


def _store_notification_result(db, task_id, notification_type, result):
    db.execute(
        """
        UPDATE notifications
        SET metadata = ?
        WHERE task_id = ?
          AND notification_type = ?
          AND channel = ?
        """,
        (
            json.dumps(result, sort_keys=True),
            task_id,
            notification_type,
            NOTIFICATION_CHANNEL,
        ),
    )


def _assignee_from_row(row):
    if row["assignee_user_id"] is None:
        return None
    return {
        "id": row["assignee_user_id"],
        "name": row["assignee_user_name"],
        "email": row["assignee_user_email"],
        "role": row["assignee_user_role"],
    }


def _coerce_date(value):
    if value is None or value == "":
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def _utc_now_iso():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
