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

## Project Structure

The app is mid-migration from a flat root layout toward a `backend/` package. AI extraction and ingestion already live in `backend/`; the Flask app, routes, and frontend are still at the repo root. Both are tracked below.

```
nudge/
├── app.py                       # Flask app factory + SocketIO init (local dev entrypoint)
├── wsgi.py                      # gunicorn/production WSGI entrypoint (imports create_app)
├── auth.py                      # flask-login setup, manager_required
├── models.py                    # SQLite schema stub (root)
├── extraction.py                # extraction stub (root; superseded by backend/ai/)
├── integrations.py              # calendar invites, .ics, task + reminder emails
├── rtms.py                      # Zoom RTMS WebSocket handlers
├── sockets.py                   # SocketIO events pushing transcript to browser
├── scheduler.py                 # daily overdue / due-soon sweep
├── routes/                      # dashboard, review, upload, api blueprints
├── templates/                   # base, login, live, review, manager/employee dashboards (Trello-style board view)
├── static/                      # style.css, live.js (SocketIO client)
├── tests/                       # placeholder unit-test stubs
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
pytest                      # 25 tests (pytest.ini collects backend/tests + tests)
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

Current tests: `backend/tests/test_ai_parser.py` and `backend/tests/test_transcript_loader.py` (Dev A, 19 assertions). Route, integration, and dashboard tests (Dev B / Dev C) are planned but not yet written; the `tests/` directory currently holds placeholder stubs.

## Timeline

Built over 8 working days (Fri Jul 3 – Fri Jul 10), split into 3 sprints plus a buffer/demo-prep block. See `docs/sprint1_plan.md` through `docs/sprint3_plan.md` and `docs/standup_notes.md` for details.
