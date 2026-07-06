# Problem Statement

## Problem

Small organizations rely on meetings to make decisions and delegate work, but action items often get lost after the call ends. Someone may write notes, someone may remember a deadline, and someone may send a follow-up message, but the process is inconsistent. The result is missed handoffs, unclear ownership, and managers spending extra time chasing updates.

Nudge helps solve this by turning meeting transcripts into structured, reviewable task assignments.

## Why It Matters

Meetings are expensive because they use team time, but the bigger problem is what happens afterward. If action items are not captured with an owner and deadline, the meeting's decisions do not reliably turn into completed work.

TODO: Insert at least one real citable statistic here before submission. Good options include:

- A statistic about time spent in meetings per week.
- A statistic about employees or managers losing time to follow-up and coordination.
- A statistic about missed action items or unclear ownership after meetings.

Example citation format:

> According to [source name], [specific statistic]. This matters for Nudge because [one sentence connecting the statistic to task follow-through].

TODO: Add the full URL, publication date, and access date for the chosen source.

## Target Users

Nudge is designed for small organizations where one person often coordinates a team but does not have a heavy project-management process.

Primary users:

- Managers who run meetings and delegate work.
- Employees who need a clear list of assigned follow-ups.
- Small teams that already use Zoom and Google Calendar.

## Current Pain Points

- Meeting notes are unstructured.
- Action items may not include an owner.
- Deadlines may be mentioned verbally but not tracked.
- Follow-up tasks are scattered across chat, calendar, email, and memory.
- Managers must manually remind people about overdue work.
- Employees may not know whether a comment or blocker was seen.

## Proposed Solution

Nudge captures a Zoom meeting transcript through RTMS or manual upload, sends the transcript to Claude, extracts a meeting summary and structured draft tasks, and lets a manager review those tasks before they become real assignments.

Approved tasks are then:

- saved in the database,
- shown on manager and employee dashboards,
- synced to Google Calendar,
- updated in real time with SocketIO,
- connected to task-level comments and blockers.

## What Makes Nudge Different

Existing tools such as Otter.ai and Fireflies.ai are strong at recording, transcribing, and summarizing meetings. Nudge focuses on the next step: turning the transcript into delegated, trackable work.

Key differences:

- Nudge requires manager approval before AI-generated tasks become assignments.
- Nudge stores each task with owner, description, due date, priority, and context.
- Nudge syncs approved deadlines to Google Calendar.
- Nudge gives employees a dashboard for their assigned work.
- Nudge supports task-level comments and blockers after the meeting.
- Nudge uses real-time updates so managers and employees see changes quickly.

TODO: Add a brief comparison table with the exact features offered by Otter.ai and Fireflies.ai after checking their current product pages.

## Success Criteria

Nudge is successful if the demo can show this complete flow:

1. A Zoom RTMS transcript or uploaded transcript enters the system.
2. Claude extracts a meeting summary and draft tasks.
3. The parser validates the structured output.
4. A manager reviews, edits, approves, or rejects each draft task.
5. Approved tasks appear on manager and employee dashboards.
6. Task updates and comments appear in real time.
7. Approved tasks with due dates sync to Google Calendar.

## Assumptions

- The first version uses SQLite because the project scope is small and student-demo focused.
- Managers are responsible for reviewing AI output before employees see final assignments.
- The team will use OAuth for Zoom and Google Calendar.
- Claude is the LLM used for the final project write-up.

TODO: The current repository README mentions OpenAI in a few places. Update README or this document after the team confirms whether the final LLM provider is Claude or OpenAI.

