# Sprint 3 Plan

Dates: 2026-07-07 to 2026-07-08

Sprint theme: Real-time updates, comments, deployment, and edge case handling.

## Sprint Goal

Finish the collaborative task-tracking experience: real-time SocketIO dashboard updates, task-level comments, reminder scheduling, deployment to Render, and handling for common failure cases.

## User Stories

- As a manager, I should see task status changes in real time, so that I can track team follow-through without refreshing.
- As an employee, I should receive task updates and comments in real time, so that I do not miss manager changes.
- As a manager or employee, I should be able to comment on a task, so that follow-up discussion stays attached to the assignment.
- As an employee, I should be able to report a blocker, so that the manager can help resolve it.
- As a manager, I should see due-soon and overdue alerts, so that delegated tasks do not get forgotten.
- As a stakeholder, I should be able to access the deployed app on Render, so that the final demo is not limited to one local machine.

## Dev A Tasks

Owner: AI extraction pipeline

- Add extraction failure handling documentation and user-facing error examples.
- Review edge-case transcripts and confirm parser behavior.
- Help Dev B seed demo data that shows multiple owners, no owner, no deadline, and urgent priority.
- Confirm `docs/task_schema.md` still matches parser behavior.

## Dev B Tasks

Owner: realtime backend, scheduler, deployment

- Implement SocketIO events in `sockets.py`.
- Emit real-time events from `routes/review.py` and `routes/api.py`.
- Implement comment creation and retrieval in `routes/api.py`.
- Implement blocker update endpoint in `routes/api.py`.
- Implement scheduler daily sweep in `scheduler.py`.
- Deduplicate reminder emails/notifications.
- Build or finalize Docker deployment using `Dockerfile`.
- Deploy to Render.

## Dev C Tasks

Owner: frontend realtime and comments

- Implement SocketIO client behavior in `static/live.js`.
- Update manager dashboard when task status, blockers, or comments change.
- Update employee dashboard when a task is approved, edited, completed, or commented on.
- Build comment thread UI.
- Add visual states for pending, done, blocked, overdue, and due soon.
- Polish responsive layout and demo data presentation.

## Unit Test Plan

These tests cover the final non-AI task workflow and scheduler behavior.

| Test file | Test function | Owner | Sprint target |
| --- | --- | --- | --- |
| `tests/test_rbac.py` | TODO: `test_employee_cannot_access_manager_review` | Dev B | Sprint 3 |
| `tests/test_review.py` | `test_approving_a_draft_moves_it_to_pending` | Dev B | Sprint 3 |
| `tests/test_drafts.py` | TODO: `test_rejected_draft_does_not_show_on_dashboard` | Dev B | Sprint 3 |
| `tests/test_api.py` | TODO: `test_employee_can_mark_task_done` | Dev B | Sprint 3 |
| `tests/test_api.py` | TODO: `test_comment_is_attached_to_task` | Dev B / Dev C | Sprint 3 |
| `tests/test_scheduler.py` | `test_daily_sweep_does_not_double_notify` | Dev B | Sprint 3 |

TODO: Some current test files contain placeholder functions. Replace placeholder `pass` tests with assertions before final submission.

## Sprint Review Acceptance Criteria

- Approved tasks appear on manager and employee dashboards.
- SocketIO pushes task updates without manual refresh.
- Comment thread works for at least one task.
- Employee can mark a task done.
- Employee can report a blocker.
- Manager can see blocked, due-soon, and overdue tasks.
- Scheduler avoids duplicate due-soon or overdue reminders.
- App runs from Docker.
- App is deployed on Render or has a documented Render deployment command.
- Demo script covers Zoom/manual transcript, OpenAI extraction, manager approval, employee dashboard, comments, and calendar sync.

## Progress Board

| Status | Task | Owner | File(s) |
| --- | --- | --- | --- |
| To Do | SocketIO backend events | Dev B | `sockets.py`, `routes/api.py`, `routes/review.py` |
| Done | SocketIO browser client | Dev C | `static/realtime.js`, `static/live.js` |
| To Do | Comment endpoints | Dev B | `routes/api.py`, `models.py` |
| Done | Comment thread UI | Dev C | `templates/_comment_drawer.html`, dashboard templates |
| In Progress | Blocker workflow | Dev B / Dev C | `routes/api.py`, dashboard templates (frontend done; backend endpoint pending) |
| To Do | Scheduler reminders | Dev B | `scheduler.py`, `integrations.py` |
| To Do | Render deployment | Dev B | `Dockerfile`, Render settings |
| To Do | Edge case demo data | Dev A | sample transcripts, seeded data |
| Done | Final responsive polish | Dev C | `static/style.css` |

Dev C frontend note: the realtime client and comment UI are built against a
documented contract (see the header of `static/realtime.js`). They stay inert
until Dev B emits the matching SocketIO events and implements the comment /
blocker / done endpoints in `routes/api.py` and `sockets.py`.

TODO: Update statuses daily during standup.

## Demo Checklist

- [ ] Manager logs in.
- [ ] Manager connects or shows Zoom integration.
- [ ] Manager uploads fallback transcript if live RTMS is unavailable.
- [ ] OpenAI extraction produces summary and draft tasks.
- [ ] Manager approves one task and edits another.
- [ ] Approved task appears on employee dashboard.
- [ ] Employee comments on the task.
- [ ] Manager sees the comment update in real time.
- [ ] Employee marks one task done or blocked.
- [ ] Calendar event is created or shown as successfully simulated.

