# Sprint 1 Plan

Dates: 2026-07-03 to 2026-07-04

Sprint theme: Stubbed pipeline end-to-end.

## Sprint Goal

Build a demoable happy path where a sample transcript is parsed into structured draft tasks, a manager reviews and approves those tasks, and an employee sees assigned work on their dashboard. Live Zoom and Google Calendar authorization can remain stubbed during this sprint.

## User Stories

- As a manager, I should be able to upload or load a sample transcript, so that I can generate task drafts from a meeting.
- As a manager, I should be able to review extracted task drafts, so that AI suggestions do not become assignments without human approval.
- As a manager, I should be able to edit owner, description, deadline, and priority, so that extracted tasks match what was actually delegated.
- As an employee, I should be able to see approved tasks assigned to me, so that I know what follow-up work I own.
- As a developer, I should be able to run parser unit tests, so that malformed LLM output does not break the app.

## Dev A Tasks

Owner: AI extraction pipeline

- Build `backend/ai/schema.py` with the structured task contract.
- Build `backend/ai/parser.py` validation for summary, task list, owner, description, `due_date`, priority, and context.
- Add sample transcripts in `backend/ingestion/sample_transcripts/`.
- Stub `extraction.py` or `backend/ai/extraction.py` so sample transcripts can return predictable task JSON.
- Add `backend/tests/test_ai_parser.py`.

## Dev B Tasks

Owner: data layer and backend

- Stub or implement `models.py` with `User`, `Meeting`, `Task`, and `Comment` concepts.
- Add `init_db()` behavior needed for local demo data.
- Build `routes/review.py` manager-only draft review routes:
  - list drafts
  - approve task
  - edit task
  - reject task
- Build minimum `routes/dashboard.py` route data for manager and employee dashboards.
- Stub `integrations.py` calendar sync so approval does not fail without Google OAuth.

## Dev C Tasks

Owner: frontend

- Build `templates/base.html` shared layout.
- Build `templates/review.html` with editable draft task cards.
- Build `templates/dashboard_manager.html` showing all approved tasks.
- Build `templates/dashboard_employee.html` showing only the logged-in employee's tasks.
- Add basic styling in `static/style.css`.

## Unit Test Plan

These tests count toward the rubric requirement for at least six unit tests.

| Test file | Test function | Owner | Sprint target |
| --- | --- | --- | --- |
| `backend/tests/test_ai_parser.py` | `test_accepts_well_formed_response` | Dev A | Sprint 1 |
| `backend/tests/test_ai_parser.py` | `test_accepts_empty_task_list` | Dev A | Sprint 1 |
| `backend/tests/test_ai_parser.py` | `test_rejects_non_dict_top_level` | Dev A | Sprint 1 |
| `backend/tests/test_ai_parser.py` | `test_rejects_missing_summary` | Dev A | Sprint 1 |
| `backend/tests/test_ai_parser.py` | `test_rejects_missing_task_field` | Dev A | Sprint 1 |
| `backend/tests/test_ai_parser.py` | `test_rejects_invalid_priority` | Dev A | Sprint 1 |
| `backend/tests/test_ai_parser.py` | `test_rejects_empty_owner` | Dev A | Sprint 1 |
| `backend/tests/test_ai_parser.py` | `test_strips_whitespace_from_string_fields` | Dev A | Sprint 1 |

TODO: Add route-level tests for review approval once the database model implementation is complete.

## Sprint Review Acceptance Criteria

- A sample transcript can be loaded without Zoom.
- The transcript produces a meeting summary and at least one draft task.
- Manager review page displays draft task owner, description, due date, priority, and context.
- Manager can approve a draft task.
- Approved task appears on the employee dashboard.
- Parser tests run locally and include at least six test functions.
- Known stubs are clearly identified for Sprint 2.

## Progress Board

Use this table as the sprint kanban board. The team can copy it into a Google Sheet if required by the instructor.

| Status | Task | Owner | File(s) |
| --- | --- | --- | --- |
| To Do | Sample transcript loader | Dev A | `backend/ingestion/transcript_loader.py` |
| To Do | Parser schema and validation | Dev A | `backend/ai/schema.py`, `backend/ai/parser.py` |
| To Do | Parser unit tests | Dev A | `backend/tests/test_ai_parser.py` |
| To Do | Draft task models | Dev B | `models.py` |
| To Do | Manager approval routes | Dev B | `routes/review.py` |
| To Do | Dashboard routes | Dev B | `routes/dashboard.py` |
| Done | Shared base layout | Dev C | `templates/base.html` |
| Done | Review template | Dev C | `templates/review.html` |
| Done | Manager and employee dashboards (Trello-style board) | Dev C | `templates/dashboard_manager.html`, `templates/dashboard_employee.html` |
| Done | Base styling | Dev C | `static/style.css` |

TODO: Update statuses daily during standup.

