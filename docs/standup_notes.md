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

## Standup: 2026-07-08

**Sprint:** Sprint 3

**Attendees:** Dev A

**Sprint Goal Reminder:** Finish the collaborative task-tracking experience: real-time updates, comments, reminders, deployment, and edge case handling.

### Dev A

- Yesterday: Sprint 2 prompt tuning, `reference_date` hallucination fix, transcript_loader hardening, Docker/wsgi fix (see prior sprint2 notes).
- Today:
  - Found that `routes/upload.py` -> root `extraction.py` was never actually calling the OpenAI-backed pipeline in `backend/ai/extraction.py` -- it only ran the deterministic regex extractor, so nothing in the running app exercised OpenAI at all (only `backend/tests` did, directly). Fixed by making `extraction.extract_tasks()` call the real OpenAI pipeline first when `OPENAI_API_KEY` is set, and fall back to the deterministic extractor on missing key or OpenAI failure, with a warning surfaced to the manager either way. See `docs/task_schema.md#extraction-failure-handling-sprint-3-addition`.
  - Added the two remaining Sprint 3 edge-case sample transcripts: `urgent_priority.txt` (explicit urgency + resolvable near-term deadline) and `task_no_deadline.txt` (real, clearly-owned task with zero timing language). Sprint 2's "multiple tasks assigned to one person" case was already covered by `sprint_review.txt`.
  - Added `tests/test_extraction_fallback.py` (OpenAI-first/fallback selection logic, monkeypatched, no network) and extended `tests/test_extraction.py` with end-to-end coverage for both new samples. Full suite: 38/38 passing.
  - Updated `docs/task_schema.md`: filled in the Sprint 3 TODO, added the new samples to the coverage table, documented the fallback-path date-resolution limitation, and added the new tests to the Test Coverage Map.
- Blockers: `rtms.py` is still a full stub (all three handlers `return None`) -- live Zoom meeting-end handoff to extraction still doesn't exist. Manual upload is therefore still the only real extraction entry point for demo day; team should confirm we're leading the demo with manual upload rather than live RTMS.

### Decisions

- Root `extraction.py` is no longer "deterministic-only" -- it now prefers the real OpenAI pipeline and only falls back to the deterministic extractor when needed. The deterministic path is kept exactly as-is (still credential-free for CI/local dev), just demoted to a fallback rather than the only path.

### Action Items

- [ ] Team - Decide and rehearse whether the demo leads with live RTMS or manual-upload fallback, given RTMS is still fully stubbed.
- [ ] Dev B - When `rtms.py`'s meeting-end handoff lands, call `backend.ai.extraction.extract_tasks` (or route through root `extraction.extract_tasks`, which now already prefers it) rather than reimplementing extraction dispatch.
- [x] Dev A - Add remaining Sprint 2/3 edge-case sample transcripts.
- [x] Dev A - Add extraction failure handling documentation and user-facing error examples.


