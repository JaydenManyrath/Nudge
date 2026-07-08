# Nudge

Nudge turns Zoom meeting transcripts into tracked, assigned tasks. It pulls a transcript from Zoom, sends it to OpenAI for structured extraction, lets a manager review and approve what gets created, then syncs deadlines to Google Calendar and keeps everyone's dashboard up to date in real time.

## How It Works

1. **Ingest** — `zoom_client.py` authenticates with Zoom (OAuth) and fetches a meeting transcript, or a sample transcript is loaded locally for dev/demo.
2. **Extract** — the transcript is sent to OpenAI, which returns structured task candidates (owner, description, due date) following the contract in `docs/task_schema.md`.
3. **Review** — a manager reviews extracted tasks on the review screen and approves, edits, or rejects each one.
4. **Sync** — approved tasks are written to the database and pushed to Google Calendar (OAuth) as events with deadlines.
5. **Track** — manager and employee dashboards show task status as a Trello-style board (Pending / Blocked / Done columns), with real-time updates over WebSockets and threaded comments on individual tasks.

## Stack

- **Backend:** Flask, SQLAlchemy, SQLite
- **AI:** OpenAI API (key-based, no OAuth)
- **Integrations:** Zoom API (OAuth), Google Calendar API (OAuth)
- **Frontend:** Jinja templates, vanilla CSS/JS, WebSockets for realtime
- **Deployment:** Docker (gunicorn + eventlet via `wsgi:app`), Render
- **Local dev:** `docker-compose.yml` (Flask + SQLite volume)

## Architecture

![Nudge architecture: live transcript capture through manager-approved distribution](docs/architecture.svg)

### Meeting-to-task sequence

```mermaid
sequenceDiagram
    autonumber
    participant Zoom as Zoom RTMS
    participant Upload as Manual Upload
    participant RTMS as rtms.py
    participant Extract as extraction.py
    participant LLM as OpenAI API
    participant Parser as parser.py validation
    participant DB as SQLite via SQLAlchemy
    participant Review as routes/review.py
    participant SocketIO as Flask-SocketIO
    participant Employee as Employee Dashboard
    participant Calendar as Google Calendar API
    participant Integrations as integrations.py

    alt Live Zoom meeting
        Zoom->>RTMS: Stream transcript chunks
        RTMS->>SocketIO: Push live transcript text to browser
        RTMS->>Extract: Handoff final transcript at meeting end
    else Manual fallback
        Upload->>Extract: Submit uploaded transcript file
    end

    Extract->>LLM: Send transcript and structured extraction prompt
    LLM-->>Extract: Return meeting summary and draft task JSON
    Extract->>Parser: Validate JSON contract

    alt Valid extraction
        Parser-->>Extract: Clean parsed meeting payload
        Extract->>DB: Create Meeting row
        Extract->>DB: Create draft Task rows
        Review->>DB: Load draft tasks for manager review
        Review->>DB: Approve, edit, or reject each draft
        Review->>SocketIO: Broadcast approved task update
        SocketIO->>Employee: Refresh task list and notification badge
        Review->>Integrations: Request calendar sync for approved tasks
        Integrations->>Calendar: Create calendar event using OAuth token
        Calendar-->>Integrations: Return event id/link
        Integrations->>DB: Store calendar sync metadata
    else Invalid extraction
        Parser-->>Extract: Raise validation error
        Extract->>DB: Mark extraction failed or needs manual review
    end
```

## Project Structure

The app is mid-migration from a flat root layout toward a `backend/` package. AI extraction and ingestion already live in `backend/`; the Flask app, routes, and frontend are still at the repo root. Both are tracked below.

```
nudge/
├── app.py                       # Flask app factory + SocketIO init (local dev entrypoint)
├── wsgi.py                      # gunicorn/production WSGI entrypoint (imports create_app)
├── auth.py                      # flask-login setup, manager_required
├── models.py                    # SQLite schema and seed/demo data
├── extraction.py                # sample/manual transcript extraction + draft persistence
├── integrations.py              # Sprint 2 stubs for calendar invites, .ics, task + reminder emails
├── rtms.py                      # Sprint 2 stub for Zoom RTMS WebSocket handlers
├── sockets.py                   # Sprint 2 stub for SocketIO transcript streaming
├── scheduler.py                 # Sprint 2 stub for daily overdue / due-soon sweep
├── routes/                      # dashboard, review, upload, api blueprints
├── templates/                   # base, login, live, review, manager/employee dashboards (Trello-style board view)
├── static/                      # style.css, live.js (SocketIO client)
├── tests/                       # route, dashboard, auth, draft, extraction persistence tests
├── backend/                     # package-style modules (newer layout)
│   ├── config.py
│   ├── ai/                      # OpenAI client, prompts, schema, parser, extraction
│   ├── ingestion/               # transcript_loader + sample_transcripts/
│   ├── models/                  # SQLAlchemy models: user, meeting
│   └── tests/                   # test_ai_parser.py, test_transcript_loader.py
├── docs/                        # problem statement, sprint plans, task schema, wireframe, architecture.svg
├── Dockerfile                   # gunicorn + eventlet, binds $PORT, runs wsgi:app
├── docker-compose.yml           # local dev convenience (docker compose up)
├── pytest.ini                   # scopes test collection to backend/tests + tests
├── requirements.txt
└── .env.example
```

## Setup

```bash
git clone <repo-url>
cd nudge
cp .env.example .env        # fill in Zoom, OpenAI, Google Calendar keys/secrets
```

**Local (venv):**

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python app.py               # or: flask --app app run
```

**Local (Docker):**

```bash
docker compose up           # builds the Dockerfile, serves on :5000
```

Required env vars (see `.env.example`): Zoom OAuth client ID/secret, OpenAI API key, Google Calendar OAuth client ID/secret.

Production builds the `Dockerfile` (gunicorn `wsgi:app`, binds `$PORT`) and deploys to Render. A `render.yaml` is not committed yet — Render is configured against the Dockerfile directly.

## Tests

```bash
pytest                      # 32 tests (pytest.ini collects backend/tests + tests)
```

## Authentication

Two OAuth-authorized integrations:

- **Zoom** — authorizes transcript retrieval (`ingestion/zoom_client.py`)
- **Google Calendar** — authorizes pushing task deadlines as events (`calendar_integration/google_client.py`)

OpenAI API access is key-based rather than OAuth, so it sits outside the "APIs with authorization" bucket but remains the core AI differentiator for task extraction.

## Team Ownership

| Owner | Responsible for |
|---|---|
| **Dev A** | Ingestion (`ingestion/`) and AI extraction (`ai/`) |
| **Dev B** | Models, routes, Google Calendar integration, and realtime sockets |
| **Dev C** | Frontend — templates, CSS/JS, dashboard rendering |

Current tests cover backend AI parser validation, transcript loading, authentication guards, review approvals/edits/rejections, manager and employee dashboard filtering, calendar stub IDs on approval, draft rejection behavior, and the no-Zoom sample transcript path that creates a meeting summary plus draft task rows.

Remaining intentional Sprint 2 stubs:

- `routes/api.py` task mutation, blocker, job status, and notification badge endpoints.
- `rtms.py` live Zoom RTMS meeting lifecycle handlers.
- `sockets.py` realtime transcript/client update emission.
- `scheduler.py` overdue and due-soon notification sweep.
- `integrations.py` Google Calendar OAuth calls and task/reminder email delivery.

## Timeline

Built over 8 working days (Fri Jul 3 – Fri Jul 10), split into 3 sprints plus a buffer/demo-prep block. See `docs/sprint1_plan.md` through `docs/sprint3_plan.md` and `docs/standup_notes.md` for details.
