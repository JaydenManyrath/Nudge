# Wireframe Reference

This is a written wireframe for Dev C. It describes the first build of the core pages using ASCII layout blocks. The team can attach actual screenshots or image mockups later.

TODO: Add final visual mock image once the HTML/CSS version is stable.

## Shared Layout

All authenticated pages should use `templates/base.html`.

Common regions:

- Top navigation: Nudge logo/name, current user, role, logout.
- Notification badge: count of task updates, blockers, or due-soon tasks.
- Main content area: page-specific dashboard or review UI.
- Flash/status region: upload success, approval success, sync failures.

## Manager Review Page

Route: `routes/review.py`

Template: `templates/review.html`

Purpose: Let a manager approve, edit, or reject AI-generated draft tasks before they become real assignments.

```text
+--------------------------------------------------------------------------------+
| Nudge                         Review Draft Tasks        Notifications (3) Logout |
+--------------------------------------------------------------------------------+
| Meeting: Sprint Planning - Jul 6                                                |
| Summary: Team reviewed blockers, launch checklist, and assigned follow-ups.      |
+--------------------------------------------------------------------------------+
| Draft Task 1                                                                    |
| Owner: [ Priya                         v ]  Priority: [ urgent v ]              |
| Due date: [ 2026-07-10                 ]                                        |
| Description: [ Finalize pricing page copy                                      ] |
| Context: Priya said she would finish pricing copy by Friday.                    |
|                                                                                |
| [Approve] [Save Edits] [Reject]                                                 |
+--------------------------------------------------------------------------------+
| Draft Task 2                                                                    |
| Owner: [ unassigned                    v ]  Priority: [ normal v ]              |
| Due date: [                            ]                                        |
| Description: [ Investigate flaky checkout test                                 ] |
| Context: Team mentioned flaky checkout tests but did not assign an owner.       |
|                                                                                |
| [Approve] [Save Edits] [Reject]                                                 |
+--------------------------------------------------------------------------------+
| Sidebar                                                                         |
| - Meeting source: Zoom RTMS                                                     |
| - Extraction status: Parsed                                                     |
| - Calendar sync: Waiting for approval                                           |
+--------------------------------------------------------------------------------+
```

Data populated from:

- `Meeting.summary`
- draft `Task` rows
- task fields from the extraction schema: `owner`, `description`, `due_date`, `priority`, `context`
- user list for owner reassignment

Expected interactions:

- Approve creates or updates the active task and triggers calendar sync.
- Save Edits updates the draft task without approving it.
- Reject removes the draft from the approval queue or marks it rejected.
- Validation errors should appear inline near the field.

TODO: Confirm whether owner selection is free text, a dropdown of `User` rows, or both.

## Manager Dashboard

Route: `routes/dashboard.py`

Template: `templates/dashboard_manager.html`

Purpose: Give managers a quick operational view of all active delegated tasks.

```text
+--------------------------------------------------------------------------------+
| Nudge                         Manager Dashboard         Notifications (5) Logout |
+--------------------------------------------------------------------------------+
| Metrics                                                                        |
| [ Open Tasks: 14 ] [ Due Soon: 4 ] [ Blocked: 2 ] [ Overdue: 1 ]                |
+--------------------------------------------------------------------------------+
| Filters                                                                         |
| Search [________________] Owner [All v] Status [All v] Priority [All v]          |
+--------------------------------------------------------------------------------+
| Task List                                                                       |
| +----------------------------------------------------------------------------+ |
| | Priya      Finalize pricing page copy       Due Jul 10   Urgent   Pending | |
| | Context: From Sprint Planning meeting                                      | |
| | [View Comments] [Mark Done] [Edit]                                         | |
| +----------------------------------------------------------------------------+ |
| | Marco      Create customer rollout notes    Due Jul 11   Normal   Blocked | |
| | Blocker: Waiting on customer list export                                  | |
| | [View Comments] [Resolve Blocker] [Edit]                                  | |
| +----------------------------------------------------------------------------+ |
+--------------------------------------------------------------------------------+
| Right Panel                                                                     |
| - Recent comments                                                               |
| - Calendar sync errors                                                          |
| - Upcoming deadlines                                                            |
+--------------------------------------------------------------------------------+
```

Data populated from:

- active `Task` rows across all employees
- `User` assignee records
- `Comment` rows for recent discussion
- `scheduler.py` alert states for due-soon and overdue tasks
- Google Calendar sync status from `integrations.py`

Expected interactions:

- Filter by owner, status, and priority.
- See blocked and overdue tasks at a glance.
- Open task comment thread.
- Receive live SocketIO updates when employees comment, mark done, or report blockers.

TODO: Decide whether manager can mark employee tasks done or only employees can.

## Employee Dashboard

Route: `routes/dashboard.py`

Template: `templates/dashboard_employee.html`

Purpose: Show each employee their assigned work, deadlines, comments, and blockers.

```text
+--------------------------------------------------------------------------------+
| Nudge                         My Tasks                  Notifications (2) Logout |
+--------------------------------------------------------------------------------+
| Today / Upcoming                                                               |
| [ Due Today: 1 ] [ Due This Week: 3 ] [ Blocked: 1 ]                            |
+--------------------------------------------------------------------------------+
| My Task List                                                                    |
| +----------------------------------------------------------------------------+ |
| | Finalize pricing page copy                           Due Jul 10   Urgent   | |
| | From: Sprint Planning meeting                                             | |
| | Context: Priya said she would finish pricing copy by Friday.              | |
| | [Mark Done] [Add Blocker] [Comment]                                       | |
| +----------------------------------------------------------------------------+ |
| | Draft onboarding checklist                         No due date   Normal    | |
| | From: Launch Readiness meeting                                            | |
| | [Mark Done] [Add Blocker] [Comment]                                       | |
| +----------------------------------------------------------------------------+ |
+--------------------------------------------------------------------------------+
| Comment Thread Drawer                                                           |
| Task: Finalize pricing page copy                                                |
| Manager: Please post the final copy before EOD.                                 |
| Priya: Draft is ready, waiting on legal review.                                 |
| [ Write a comment...                                      ] [Send]              |
+--------------------------------------------------------------------------------+
```

Data populated from:

- active tasks where `Task.assignee_id` matches the logged-in user
- related `Meeting` summary/context
- `Comment` rows for each task
- SocketIO events for task changes and new comments

Expected interactions:

- Mark task done.
- Add or clear a blocker.
- Comment on task.
- See real-time updates without full page refresh.

TODO: Confirm whether employees can edit descriptions/deadlines or only comment and update status.

