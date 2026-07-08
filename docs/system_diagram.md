# System Diagram

This document gives the team a text-based system diagram that renders directly in GitHub using Mermaid.

## Full Meeting-To-Task Sequence

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

## Component Architecture

```mermaid
flowchart LR
    subgraph DevA["Dev A: AI Extraction Pipeline"]
        Samples["sample transcripts"]
        Extraction["extraction.py"]
        Prompt["OpenAI prompt"]
        Parser["parser.py / schema validation"]
        ATests["backend/tests/test_ai_parser.py"]
    end

    subgraph DevB["Dev B: Backend, Data, Integrations"]
        App["app.py app factory"]
        Models["models.py: User, Meeting, Task, Comment"]
        Auth["auth.py: Flask-Login, RBAC, OAuth"]
        Review["routes/review.py"]
        API["routes/api.py"]
        RTMS["rtms.py"]
        Sockets["sockets.py"]
        Integrations["integrations.py"]
        Scheduler["scheduler.py"]
        Docker["Dockerfile / Render deploy"]
    end

    subgraph DevC["Dev C: Frontend"]
        Templates["templates/"]
        CSS["static/style.css"]
        LiveJS["static/live.js"]
        Comments["comment thread UI"]
    end

    Zoom["Zoom API / RTMS OAuth"]
    LLM["OpenAI API"]
    Google["Google Calendar API OAuth"]
    DB[("SQLite")]

    Samples --> Extraction
    Zoom --> RTMS
    RTMS --> Extraction
    Extraction --> Prompt
    Prompt --> LLM
    LLM --> Parser
    Parser --> Models
    Models --> DB

    App --> Auth
    App --> Review
    App --> API
    App --> Sockets
    Review --> Models
    API --> Models
    Scheduler --> Models
    Integrations --> Google
    Review --> Integrations
    Sockets --> LiveJS

    Templates --> Review
    Templates --> API
    LiveJS --> Sockets
    Comments --> API
```

## Authorized API Integrations

Nudge uses at least two external APIs that require authorization.

| API | Auth type | Owner | Used for | Key files |
| --- | --- | --- | --- | --- |
| Zoom API / RTMS | OAuth | Dev B | Live transcript stream and meeting handoff | `auth.py`, `rtms.py` |
| Google Calendar API | OAuth | Dev B | Calendar events for approved tasks | `auth.py`, `integrations.py` |
| OpenAI API | API key | Dev A | Transcript parsing and task extraction | `extraction.py`, `backend/ai/llm_client.py` |

TODO: Fill in exact OAuth scopes after the final Zoom and Google app configuration is created.

## Data Flow Notes

- Live transcript text can be pushed to the browser while the meeting is active, but only the final transcript should trigger task extraction.
- OpenAI output must pass parser validation before database writes.
- Manager approval is the boundary between "draft AI suggestion" and "real assigned task."
- Google Calendar sync should happen only after approval.
- SocketIO should broadcast task changes to manager and employee dashboards after approval, completion, blocker updates, and comments.

