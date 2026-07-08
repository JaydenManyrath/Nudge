# Sprint 2 Plan

Dates: 2026-07-05 to 2026-07-06

Sprint theme: Real Zoom RTMS and Google Calendar OAuth integration.

## Sprint Goal

Replace Sprint 1 stubs with authorized Zoom RTMS transcript ingestion and Google Calendar sync for approved tasks.

## User Stories

- As a manager, I should be able to connect Zoom, so that Nudge can receive live meeting transcript data.
- As a manager, I should be able to use manual transcript upload as a fallback, so that the app still works if live RTMS fails.
- As a manager, I should be able to connect Google Calendar, so that approved task deadlines become calendar events.
- As an employee, I should receive calendar events for approved assigned tasks, so that deadlines appear in my existing schedule.
- As a developer, I should be able to test OAuth-dependent code paths with stubs or mocks, so that CI does not require real credentials.

## Dev A Tasks

Owner: AI extraction pipeline

- Tune the OpenAI/LLM prompt in `backend/ai/prompts.py` or `extraction.py`.
- Confirm parser output remains stable when transcript text comes from Zoom RTMS instead of sample files.
- Add edge case sample transcripts:
  - no action items
  - unclear owner
  - vague deadline
  - multiple tasks assigned to one person
- Document any prompt/schema changes in `docs/task_schema.md`.

## Dev B Tasks

Owner: backend, OAuth, integrations

- Implement Zoom OAuth handshake in `auth.py`.
- Implement Zoom RTMS WebSocket handlers in `rtms.py`.
- Add meeting-end handoff from `rtms.py` to `extraction.py`.
- Keep `routes/upload.py` available as a manual transcript fallback.
- Implement Google Calendar OAuth handshake in `auth.py`.
- Implement event creation in `integrations.py`.
- Store calendar event metadata on approved tasks.
- Update `Dockerfile` and environment variables for Render deployment.

## Dev C Tasks

Owner: frontend

- Add Zoom connection state to manager dashboard.
- Add Google Calendar connection state to manager dashboard.
- Build manual upload UI in `templates/live.html` or upload page template.
- Add user-facing error states for:
  - Zoom not connected
  - Google Calendar not connected
  - transcript upload failure
  - calendar sync failure
- Update `static/style.css` for OAuth buttons, status banners, and upload controls.

## Authorized API Requirements

| API | Authorization | Sprint 2 acceptance |
| --- | --- | --- |
| Zoom API / RTMS | OAuth | Manager can authorize Zoom and receive or simulate a live transcript stream. |
| Google Calendar API | OAuth | Manager can authorize Google and create events from approved tasks. |

Configured local callback URLs and scopes:

- Zoom callback: `http://localhost:5000/auth/zoom/callback`
- Zoom scope: `meeting:read:meeting_transcript`
- Google callback: `http://localhost:5000/auth/google/callback`
- Google Calendar scope: `https://www.googleapis.com/auth/calendar.events`

On Render, callback URLs resolve from `RENDER_EXTERNAL_URL` unless
`PUBLIC_BASE_URL`, `ZOOM_REDIRECT_URI`, or `GOOGLE_REDIRECT_URI` is set.

## Unit Test Plan

Add tests around integration boundaries without requiring live external network calls.

| Test file | Test function | Owner | Sprint target |
| --- | --- | --- | --- |
| `tests/test_auth.py` | `test_zoom_oauth_callback_stores_token` | Dev B | Sprint 2 |
| `tests/test_auth.py` | `test_google_oauth_callback_stores_token` | Dev B | Sprint 2 |
| `tests/test_extraction.py` | `test_pasted_transcript_upload_creates_manual_upload_draft` | Dev B | Sprint 2 |
| `tests/test_extraction.py` | `test_uploaded_transcript_file_creates_manual_upload_draft` | Dev B | Sprint 2 |
| `tests/test_review.py` | `test_approving_a_draft_moves_it_to_pending` | Dev B | Sprint 2 |
| `tests/test_rtms.py` | `test_rtms_events_endpoint_dispatches_lifecycle_events` | Dev B | Sprint 2 |
| `tests/test_integrations.py` | `test_create_calendar_invite_uses_google_calendar_when_token_exists` | Dev B | Sprint 2 |

## Sprint Review Acceptance Criteria

- Zoom OAuth flow can be started from the app.
- RTMS handler can accept live or simulated transcript chunks.
- Manual transcript upload still works as a fallback.
- OpenAI/LLM extraction receives the final transcript after meeting end when `NUDGE_EXTRACTION_BACKEND=openai`; tests and sample uploads may use deterministic extraction.
- Google Calendar OAuth flow can be started from the app.
- Approved task with a due date creates or simulates a calendar event.
- Calendar sync failure does not delete or lose the approved task.
- Required env vars are listed in `.env.example`.

## Progress Board

| Status | Task | Owner | File(s) |
| --- | --- | --- | --- |
| Done | Zoom OAuth routes | Dev B | `auth.py` |
| Done | Zoom RTMS stream handler | Dev B | `rtms.py`, `routes/rtms_ingress.py` |
| Done | Manual upload fallback | Dev B | `routes/upload.py` |
| Done | Google OAuth routes | Dev B | `auth.py` |
| Done | Calendar event creation | Dev B | `integrations.py` |
| Done | OAuth status UI | Dev C | `templates/dashboard_manager.html` |
| Done | Upload UI | Dev C | `templates/live.html` |
| Done | Prompt tuning / OpenAI handoff for real transcripts | Dev A | `extraction.py`, `backend/ai/prompts.py` |
| Done | Integration boundary tests | Dev B | `tests/test_auth.py`, `tests/test_review.py`, `tests/test_rtms.py`, `tests/test_integrations.py` |
