# Task Extraction Schema

This document is the contract between `extraction.py` / `backend/ai/extraction.py`, the LLM response parser, and the database layer in `models.py`.

Nudge uses meeting transcripts to produce a meeting summary and a list of draft tasks. These tasks are not final until a manager reviews them in `routes/review.py`.

TODO: The project overview uses the word `deadline`, while the current parser contract in `backend/ai/schema.py` uses `due_date`. For now, this document treats `due_date` as the code-facing field and "deadline" as the product-facing label.

## Canonical Payload Shape

```json
{
  "summary": "string",
  "tasks": [
    {
      "owner": "string",
      "description": "string",
      "due_date": "YYYY-MM-DD or null",
      "priority": "low | normal | urgent",
      "context": "string"
    }
  ]
}
```

## JSON Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "NudgeParsedMeeting",
  "type": "object",
  "additionalProperties": false,
  "required": ["summary", "tasks"],
  "properties": {
    "summary": {
      "type": "string",
      "description": "Short plain-language summary of the meeting."
    },
    "tasks": {
      "type": "array",
      "description": "Draft delegated tasks extracted from the transcript.",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": [
          "owner",
          "description",
          "due_date",
          "priority",
          "context"
        ],
        "properties": {
          "owner": {
            "type": "string",
            "description": "Person assigned to the task, using the name from the transcript. Use \"unassigned\" if unclear."
          },
          "description": {
            "type": "string",
            "description": "Specific action item written as a clear task."
          },
          "due_date": {
            "type": ["string", "null"],
            "format": "date",
            "description": "Task deadline in ISO date format, or null if the transcript does not specify one."
          },
          "priority": {
            "type": "string",
            "enum": ["low", "normal", "urgent"],
            "description": "Estimated urgency based on transcript language and deadline."
          },
          "context": {
            "type": "string",
            "description": "Short explanation of the transcript moment that produced this task."
          }
        }
      }
    }
  }
}
```

## Valid Example

```json
{
  "summary": "The team reviewed launch readiness, assigned pricing page follow-ups, and flagged a flaky checkout test.",
  "tasks": [
    {
      "owner": "Priya",
      "description": "Finalize the pricing page copy",
      "due_date": "2026-07-10",
      "priority": "urgent",
      "context": "Priya said she would have pricing copy done by Friday before the launch review."
    },
    {
      "owner": "unassigned",
      "description": "Investigate the flaky checkout test",
      "due_date": null,
      "priority": "normal",
      "context": "The team mentioned the checkout test has been failing intermittently, but no owner was assigned."
    }
  ]
}
```

## Malformed Example

```json
{
  "summary": "Team talked about launch tasks.",
  "tasks": [
    {
      "owner": "",
      "description": "Fix the calendar sync issue",
      "deadline": "Friday",
      "priority": "super urgent"
    }
  ]
}
```

## Expected Parser Handling

`backend/ai/parser.py` should reject the malformed payload before any database writes happen.

Expected validation failures:

- `owner` is empty after trimming whitespace.
- `due_date` is missing because the payload uses `deadline` instead.
- `deadline` uses natural language instead of ISO `YYYY-MM-DD`.
- `priority` is not one of `low`, `normal`, or `urgent`.
- `context` is missing.

The parser should raise `ExtractionValidationError` with a useful message and the calling code should mark extraction as failed or requiring manual review.

TODO: Decide whether `parser.py` should support a backward-compatible alias from `deadline` to `due_date`, or whether Claude should always be prompted to emit only `due_date`.

## Mapping To Database Models

The intended SQLAlchemy models are `Meeting`, `Task`, `User`, and `Comment`.

### Meeting

One parsed payload maps to one `Meeting` row.

Suggested fields:

| Schema field | Model field | Notes |
| --- | --- | --- |
| `summary` | `Meeting.summary` | Stored after parser validation. |
| transcript source | `Meeting.source` | `zoom_rtms` or `manual_upload`. TODO: confirm exact enum values. |
| meeting identity | `Meeting.zoom_meeting_id` | Nullable for manual uploads. TODO: confirm field name. |
| extraction state | `Meeting.extraction_status` | Example values: `pending`, `parsed`, `failed`, `reviewed`. TODO: confirm final states. |

### Task

Each item in `tasks` maps to one draft `Task` row.

| Schema field | Model field | Notes |
| --- | --- | --- |
| `owner` | `Task.assignee_name` or `Task.assignee_id` | If the user exists, link to `User.id`; otherwise keep the raw name for manager review. TODO: confirm final field split. |
| `description` | `Task.description` | Main task text visible on dashboards. |
| `due_date` | `Task.due_date` | Product label is "deadline." |
| `priority` | `Task.priority` | Should match `low`, `normal`, or `urgent`. |
| `context` | `Task.context` | Used by manager review to explain why the task was extracted. |
| generated draft state | `Task.status` | Draft tasks should start as `draft`; approved tasks move to `pending` or `open`. TODO: confirm exact status names. |
| meeting link | `Task.meeting_id` | Foreign key to `Meeting.id`. |

## Review And Approval Rules

- `extraction.py` writes draft tasks only.
- Draft tasks should not sync to Google Calendar.
- Draft tasks should not appear as active employee work until approved.
- `routes/review.py` is manager-only.
- On approval, `Task.status` changes from `draft` to an active state and `integrations.py` creates a Google Calendar event if `due_date` is present.
- On edit, manager changes should override LLM output but keep the original `context` unless the manager updates it.
- On reject, the task should either be deleted or moved to `rejected`.

TODO: Decide whether rejected tasks are hard-deleted or retained for audit/demo purposes.

## Test Coverage Map

The parser contract is covered by `backend/tests/test_ai_parser.py`.

| Test | Contract behavior |
| --- | --- |
| `test_accepts_well_formed_response` | Valid summary and tasks are accepted. |
| `test_accepts_empty_task_list` | Meetings with no extracted tasks are allowed. |
| `test_rejects_non_dict_top_level` | Top-level response must be an object. |
| `test_rejects_missing_summary` | `summary` is required. |
| `test_rejects_missing_task_field` | Every task must include required fields. |
| `test_rejects_invalid_priority` | Priority enum is enforced. |
| `test_rejects_empty_owner` | Owner cannot be blank. |
| `test_strips_whitespace_from_string_fields` | Parser normalizes strings before database use. |

