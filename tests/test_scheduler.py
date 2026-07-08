from datetime import date, timedelta

import models
import scheduler


def test_daily_sweep_does_not_double_notify(app, monkeypatch):
    today = date(2026, 7, 8)
    sent = []

    def fake_send_reminder_email(task, assignee, notification_type):
        sent.append((task.id, assignee["email"], notification_type))
        return {
            "status": "sent",
            "task_id": task.id,
            "notification_type": notification_type,
        }

    monkeypatch.setattr(
        scheduler.integrations,
        "send_reminder_email",
        fake_send_reminder_email,
    )

    with models.get_db() as db:
        db.execute("DELETE FROM notifications")
        db.execute("DELETE FROM tasks")
        assignee = db.execute(
            "SELECT id FROM users WHERE email = ?",
            ("marco@nudge.local",),
        ).fetchone()
        task_ids = [
            _insert_task(
                db,
                assignee["id"],
                "Due soon reminder",
                today + timedelta(days=1),
                "pending",
            ),
            _insert_task(
                db,
                assignee["id"],
                "Overdue reminder",
                today - timedelta(days=1),
                "blocked",
            ),
            _insert_task(
                db,
                assignee["id"],
                "Future reminder",
                today + timedelta(days=30),
                "pending",
            ),
            _insert_task(
                db,
                assignee["id"],
                "Completed reminder",
                today,
                "done",
            ),
        ]
        db.commit()

    first = scheduler.daily_sweep(today=today)
    second = scheduler.daily_sweep(today=today)

    assert first["due_soon"] == 1
    assert first["overdue"] == 1
    assert first["sent"] == 2
    assert second["sent"] == 0
    assert sorted(sent) == [
        (task_ids[0], "marco@nudge.local", "due_soon"),
        (task_ids[1], "marco@nudge.local", "overdue"),
    ]

    with models.get_db() as db:
        rows = db.execute(
            """
            SELECT task_id, notification_type, channel, metadata
            FROM notifications
            ORDER BY task_id
            """
        ).fetchall()

    assert len(rows) == 2
    assert [row["task_id"] for row in rows] == task_ids[:2]
    assert {row["notification_type"] for row in rows} == {"due_soon", "overdue"}
    assert {row["channel"] for row in rows} == {"email"}
    assert all('"status": "sent"' in row["metadata"] for row in rows)


def test_daily_sweep_allows_one_reminder_per_stage(app, monkeypatch):
    today = date(2026, 7, 8)
    sent = []

    def fake_send_reminder_email(task, assignee, notification_type):
        sent.append((task.id, assignee["email"], notification_type))
        return {
            "status": "sent",
            "task_id": task.id,
            "notification_type": notification_type,
        }

    monkeypatch.setattr(
        scheduler.integrations,
        "send_reminder_email",
        fake_send_reminder_email,
    )

    with models.get_db() as db:
        db.execute("DELETE FROM notifications")
        db.execute("DELETE FROM tasks")
        assignee = db.execute(
            "SELECT id FROM users WHERE email = ?",
            ("marco@nudge.local",),
        ).fetchone()
        task_id = _insert_task(
            db,
            assignee["id"],
            "Stage transition reminder",
            today + timedelta(days=1),
            "pending",
        )
        db.commit()

    due_soon = scheduler.daily_sweep(today=today)
    duplicate_due_soon = scheduler.daily_sweep(today=today)
    overdue = scheduler.daily_sweep(today=today + timedelta(days=2))
    duplicate_overdue = scheduler.daily_sweep(today=today + timedelta(days=2))

    assert due_soon["sent"] == 1
    assert due_soon["due_soon"] == 1
    assert duplicate_due_soon["sent"] == 0
    assert overdue["sent"] == 1
    assert overdue["overdue"] == 1
    assert duplicate_overdue["sent"] == 0
    assert sent == [
        (task_id, "marco@nudge.local", "due_soon"),
        (task_id, "marco@nudge.local", "overdue"),
    ]

    with models.get_db() as db:
        rows = db.execute(
            """
            SELECT notification_type, channel
            FROM notifications
            WHERE task_id = ?
            ORDER BY notification_type
            """,
            (task_id,),
        ).fetchall()

    assert [row["notification_type"] for row in rows] == ["due_soon", "overdue"]
    assert {row["channel"] for row in rows} == {"email"}


def test_daily_sweep_dedupes_failed_provider_attempts(app, monkeypatch):
    today = date(2026, 7, 8)
    attempts = []

    def fake_send_reminder_email(task, assignee, notification_type):
        attempts.append((task.id, assignee["email"], notification_type))
        raise RuntimeError("provider timeout")

    monkeypatch.setattr(
        scheduler.integrations,
        "send_reminder_email",
        fake_send_reminder_email,
    )

    with models.get_db() as db:
        db.execute("DELETE FROM notifications")
        db.execute("DELETE FROM tasks")
        assignee = db.execute(
            "SELECT id FROM users WHERE email = ?",
            ("marco@nudge.local",),
        ).fetchone()
        task_id = _insert_task(
            db,
            assignee["id"],
            "Provider failure reminder",
            today,
            "pending",
        )
        db.commit()

    first = scheduler.daily_sweep(today=today)
    second = scheduler.daily_sweep(today=today)

    assert first["sent"] == 0
    assert first["skipped"] == 1
    assert second["sent"] == 0
    assert attempts == [(task_id, "marco@nudge.local", "due_soon")]

    with models.get_db() as db:
        row = db.execute(
            """
            SELECT notification_type, metadata
            FROM notifications
            WHERE task_id = ?
            """,
            (task_id,),
        ).fetchone()

    assert row["notification_type"] == "due_soon"
    assert '"status": "failed"' in row["metadata"]
    assert "provider timeout" in row["metadata"]


def _insert_task(db, assignee_id, description, due_date, status):
    cursor = db.execute(
        """
        INSERT INTO tasks (
            assignee_id,
            assignee_name,
            description,
            due_date,
            priority,
            status
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            assignee_id,
            "Marco",
            description,
            due_date.isoformat(),
            "normal",
            status,
        ),
    )
    return int(cursor.lastrowid)
