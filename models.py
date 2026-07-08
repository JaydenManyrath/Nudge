import os
import sqlite3
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Iterable


DB_PATH = os.environ.get("NUDGE_DB_PATH", "nudge.db")

USER_ROLES = {"manager", "employee"}
MEETING_SOURCES = {"manual_upload", "zoom_rtms"}
MEETING_STATUSES = {"pending", "parsed", "failed", "reviewed"}
TASK_PRIORITIES = {"low", "normal", "urgent"}
TASK_STATUSES = {"draft", "pending", "blocked", "done", "rejected"}


@dataclass(frozen=True)
class User:
    id: int | None
    name: str
    email: str
    role: str = "employee"
    password_hash: str | None = None
    created_at: str | None = None


@dataclass(frozen=True)
class Meeting:
    id: int | None
    title: str
    summary: str | None = None
    transcript: str | None = None
    source: str = "manual_upload"
    zoom_meeting_id: str | None = None
    extraction_status: str = "pending"
    created_at: str | None = None


@dataclass(frozen=True)
class Task:
    id: int | None
    description: str
    status: str = "draft"
    priority: str = "normal"
    meeting_id: int | None = None
    assignee_id: int | None = None
    assignee_name: str | None = None
    due_date: str | None = None
    context: str | None = None
    calendar_event_id: str | None = None
    created_at: str | None = None
    updated_at: str | None = None

    @property
    def owner(self) -> str:
        return self.assignee_name or "unassigned"


@dataclass(frozen=True)
class Comment:
    id: int | None
    task_id: int
    author_id: int | None
    body: str
    created_at: str | None = None


def get_db(path: str | os.PathLike[str] | None = None) -> sqlite3.Connection:
    db_path = Path(path or DB_PATH)
    if db_path.parent != Path("."):
        db_path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db(
    path: str | os.PathLike[str] | None = None,
    *,
    seed_demo_data: bool = True,
) -> None:
    with get_db(path) as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                role TEXT NOT NULL DEFAULT 'employee'
                    CHECK (role IN ('manager', 'employee')),
                password_hash TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS meetings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                summary TEXT,
                transcript TEXT,
                source TEXT NOT NULL DEFAULT 'manual_upload'
                    CHECK (source IN ('manual_upload', 'zoom_rtms')),
                zoom_meeting_id TEXT,
                extraction_status TEXT NOT NULL DEFAULT 'pending'
                    CHECK (extraction_status IN (
                        'pending',
                        'parsed',
                        'failed',
                        'reviewed'
                    )),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                meeting_id INTEGER REFERENCES meetings(id) ON DELETE SET NULL,
                assignee_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                assignee_name TEXT,
                description TEXT NOT NULL,
                due_date TEXT,
                priority TEXT NOT NULL DEFAULT 'normal'
                    CHECK (priority IN ('low', 'normal', 'urgent')),
                context TEXT,
                status TEXT NOT NULL DEFAULT 'draft'
                    CHECK (status IN (
                        'draft',
                        'pending',
                        'blocked',
                        'done',
                        'rejected'
                    )),
                calendar_event_id TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS comments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
                author_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                body TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
            CREATE INDEX IF NOT EXISTS idx_tasks_assignee_id ON tasks(assignee_id);
            CREATE INDEX IF NOT EXISTS idx_tasks_meeting_id ON tasks(meeting_id);
            CREATE INDEX IF NOT EXISTS idx_comments_task_id ON comments(task_id);
            """
        )

        if seed_demo_data:
            seed_demo(db)


def seed_demo(db: sqlite3.Connection) -> None:
    users = [
        ("Maya Chen", "maya@nudge.local", "manager"),
        ("Priya Shah", "priya@nudge.local", "employee"),
        ("Marco Diaz", "marco@nudge.local", "employee"),
    ]
    db.executemany(
        """
        INSERT OR IGNORE INTO users (name, email, role)
        VALUES (?, ?, ?)
        """,
        users,
    )

    meeting_id = _ensure_meeting(
        db,
        Meeting(
            id=None,
            title="Sprint Planning - Jul 6",
            summary="Team reviewed blockers, launch checklist, and assigned follow-ups.",
            transcript=(
                "Priya will finalize pricing page copy by Friday. "
                "Marco will create customer rollout notes. "
                "The checkout test needs an owner."
            ),
            source="manual_upload",
            extraction_status="parsed",
        ),
    )

    priya_id = _user_id_by_email(db, "priya@nudge.local")
    marco_id = _user_id_by_email(db, "marco@nudge.local")

    demo_tasks = [
        Task(
            id=None,
            meeting_id=meeting_id,
            assignee_id=priya_id,
            assignee_name="Priya",
            description="Finalize pricing page copy",
            due_date="2026-07-10",
            priority="urgent",
            context="Priya said she would finish pricing copy by Friday.",
            status="draft",
        ),
        Task(
            id=None,
            meeting_id=meeting_id,
            assignee_id=marco_id,
            assignee_name="Marco",
            description="Create customer rollout notes",
            due_date="2026-07-11",
            priority="normal",
            context="Marco volunteered to prepare customer rollout notes.",
            status="pending",
        ),
        Task(
            id=None,
            meeting_id=meeting_id,
            assignee_id=None,
            assignee_name="unassigned",
            description="Investigate flaky checkout test",
            due_date=None,
            priority="normal",
            context="Team mentioned flaky checkout tests but did not assign an owner.",
            status="draft",
        ),
    ]
    for task in demo_tasks:
        _ensure_task(db, task)


def row_to_user(row: sqlite3.Row | None) -> User | None:
    if row is None:
        return None
    return User(
        id=row["id"],
        name=row["name"],
        email=row["email"],
        role=row["role"],
        password_hash=row["password_hash"],
        created_at=row["created_at"],
    )


def row_to_meeting(row: sqlite3.Row | None) -> Meeting | None:
    if row is None:
        return None
    return Meeting(
        id=row["id"],
        title=row["title"],
        summary=row["summary"],
        transcript=row["transcript"],
        source=row["source"],
        zoom_meeting_id=row["zoom_meeting_id"],
        extraction_status=row["extraction_status"],
        created_at=row["created_at"],
    )


def row_to_task(row: sqlite3.Row | None) -> Task | None:
    if row is None:
        return None
    return Task(
        id=row["id"],
        meeting_id=row["meeting_id"],
        assignee_id=row["assignee_id"],
        assignee_name=row["assignee_name"],
        description=row["description"],
        due_date=row["due_date"],
        priority=row["priority"],
        context=row["context"],
        status=row["status"],
        calendar_event_id=row["calendar_event_id"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def row_to_comment(row: sqlite3.Row | None) -> Comment | None:
    if row is None:
        return None
    return Comment(
        id=row["id"],
        task_id=row["task_id"],
        author_id=row["author_id"],
        body=row["body"],
        created_at=row["created_at"],
    )


def validate_user(user: User) -> None:
    _require_text(user.name, "User.name")
    _require_text(user.email, "User.email")
    _require_choice(user.role, USER_ROLES, "User.role")


def validate_meeting(meeting: Meeting) -> None:
    _require_text(meeting.title, "Meeting.title")
    _require_choice(meeting.source, MEETING_SOURCES, "Meeting.source")
    _require_choice(
        meeting.extraction_status,
        MEETING_STATUSES,
        "Meeting.extraction_status",
    )


def validate_task(task: Task) -> None:
    _require_text(task.description, "Task.description")
    _require_choice(task.priority, TASK_PRIORITIES, "Task.priority")
    _require_choice(task.status, TASK_STATUSES, "Task.status")
    if task.due_date is not None:
        date.fromisoformat(task.due_date)


def validate_comment(comment: Comment) -> None:
    if comment.task_id is None:
        raise ValueError("Comment.task_id is required")
    _require_text(comment.body, "Comment.body")


def _ensure_meeting(db: sqlite3.Connection, meeting: Meeting) -> int:
    validate_meeting(meeting)
    existing = db.execute(
        "SELECT id FROM meetings WHERE title = ?",
        (meeting.title,),
    ).fetchone()
    if existing:
        return int(existing["id"])

    cursor = db.execute(
        """
        INSERT INTO meetings (
            title,
            summary,
            transcript,
            source,
            zoom_meeting_id,
            extraction_status
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            meeting.title,
            meeting.summary,
            meeting.transcript,
            meeting.source,
            meeting.zoom_meeting_id,
            meeting.extraction_status,
        ),
    )
    return int(cursor.lastrowid)


def _ensure_task(db: sqlite3.Connection, task: Task) -> int:
    validate_task(task)
    existing = db.execute(
        """
        SELECT id FROM tasks
        WHERE meeting_id IS ?
          AND description = ?
          AND COALESCE(assignee_name, '') = COALESCE(?, '')
        """,
        (task.meeting_id, task.description, task.assignee_name),
    ).fetchone()
    if existing:
        return int(existing["id"])

    cursor = db.execute(
        """
        INSERT INTO tasks (
            meeting_id,
            assignee_id,
            assignee_name,
            description,
            due_date,
            priority,
            context,
            status,
            calendar_event_id
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            task.meeting_id,
            task.assignee_id,
            task.assignee_name,
            task.description,
            task.due_date,
            task.priority,
            task.context,
            task.status,
            task.calendar_event_id,
        ),
    )
    return int(cursor.lastrowid)


def _user_id_by_email(db: sqlite3.Connection, email: str) -> int | None:
    row = db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    return int(row["id"]) if row else None


def _require_text(value: Any, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} is required")


def _require_choice(value: str, choices: Iterable[str], field_name: str) -> None:
    if value not in choices:
        joined = ", ".join(sorted(choices))
        raise ValueError(f"{field_name} must be one of: {joined}")
