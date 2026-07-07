# Standup Notes

Use this file to record daily Scrum updates and sprint planning notes. Keep entries short and concrete.

## Standup Template

```markdown
## Standup: YYYY-MM-DD

**Sprint:** Sprint number or buffer day

**Attendees:** Dev A, Dev B, Dev C, other names

**Sprint Goal Reminder:** One sentence describing the sprint goal.

### Dev A
- Yesterday:
- Today:
- Blockers:

### Dev B
- Yesterday:
- Today:
- Blockers:

### Dev C
- Yesterday:
- Today:
- Blockers:

### Decisions
- Decision:

### Action Items
- [ ] Owner - action item
```

## Standup: 2026-07-03

**Sprint:** Sprint 1 kickoff

**Attendees:** Dev A, Dev B, Dev C

**Sprint Goal Reminder:** Build a stubbed end-to-end flow where a sample transcript becomes draft tasks, a manager approves them, and an employee can see assigned work.

### Dev A

- Yesterday: Set up sample transcript ideas and reviewed the task extraction contract needed by the rest of the team.
- Today: Create `backend/ai/schema.py`, `backend/ai/parser.py`, sample transcripts, and tests for valid and invalid LLM outputs.
- Blockers: Need final agreement on whether the task deadline field is called `due_date` or `deadline`.

### Dev B

- Yesterday: Sketched the Flask app structure, route boundaries, and database model names.
- Today: Stub `models.py`, `routes/review.py`, `routes/api.py`, and the manager-only approval route.
- Blockers: OAuth credentials are not ready yet, so Zoom and Google will be stubbed in Sprint 1.

### Dev C

- Yesterday: Reviewed dashboard requirements and core templates.
- Today: Build basic `templates/review.html`, `templates/dashboard_manager.html`, `templates/dashboard_employee.html`, and `static/style.css`.
- Blockers: Needs test data from Dev A and field names from Dev B to wire templates cleanly.

### Decisions

- Sprint 1 will prioritize a demoable happy path over live integrations.
- Draft tasks must be reviewed by a manager before appearing as active employee work.
- Google Calendar sync is stubbed in Sprint 1 and implemented for real in Sprint 2.
- SocketIO can be simulated or lightly stubbed in Sprint 1 if full real-time work does not fit.

### Action Items

- [ ] Dev A - Commit parser schema and at least six parser tests.
- [ ] Dev B - Create draft task approval route and task status transition.
- [x] Dev C - Create the manager review screen using editable task cards.
- [ ] Team - Add a real citation/statistic to `docs/problem_statement.md`.

## Standup: 2026-07-07

**Sprint:** Sprint 1

**Attendees:** Dev A, Dev B, Dev C

**Sprint Goal Reminder:** Build a stubbed end-to-end flow where a sample transcript becomes draft tasks, a manager approves them, and an employee can see assigned work.

### Dev A

- Yesterday:
- Today:
- Blockers:

### Dev B

- Yesterday:
- Today:
- Blockers:

### Dev C

- Yesterday: Reviewed dashboard requirements and wireframe.
- Today: Built `templates/base.html` shared layout, `templates/review.html` editable draft task cards, and the manager/employee dashboards as a Trello-style board (Pending/Blocked/Done columns), plus light styling in `static/style.css`. Templates render standalone with mock data until Dev B's routes land.
- Blockers: Waiting on Dev B for final field names and route context to swap mock data for live template variables.

### Decisions

- Dashboards use a Trello-style Kanban board (Pending / Blocked / Done) instead of a flat task list.

### Action Items

- [ ] Dev B - Share final `Task` field names and route context objects so Dev C can wire templates to live data.

