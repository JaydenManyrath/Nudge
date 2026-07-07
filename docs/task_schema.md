# Task Extraction Schema

This document is the contract between `extraction.py` / `backend/ai/extraction.py`, the LLM response parser, and the database layer in `models.py`.

Nudge uses meeting transcripts to produce a meeting summary and a list of draft tasks. These tasks are not final until a manager reviews them in `routes/review.py`.

**Note on model choice:** earlier planning docs referred to "Claude" throughout. The team decided in Sprint 1 to use OpenAI (`backend/ai/llm_client.py`) instead, since that matched the dependencies already in `requirements.txt`. This document uses "the LLM" or "OpenAI" from here on; treat any remaining "Claude" references elsewhere in the repo's docs as stale terminology from before that decision, not a second model in play.

**Resolved:** `parser.py` does NOT support a backward-compatible `deadline` alias. The LLM is always prompted (via `backend/ai/prompts.py` and the strict JSON schema in `backend/ai/schema.py`) to emit `due_date` only. A payload using `deadline` instead of `due_date` is treated as malformed and rejected -- see the Malformed Example below, which is exactly this case.

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

## Reference Date (Sprint 2 addition)

The LLM is not told "today's date" implicitly -- it has no way to know when the
meeting happened unless told explicitly. Without an anchor, relative language
like "by Friday" gets guessed, and guesses have been observed to land on the
wrong date *and* the wrong year.

`backend/ai/llm_client.call_extraction(transcript_text, reference_date=None)`
accepts a `reference_date` (ISO 8601 string) representing when the meeting took
place, and `backend/ai/prompts.build_user_prompt()` includes it as `Meeting date: ...`
in the prompt sent to the LLM. If no `reference_date` is supplied, it defaults to
today's date at call time.

`backend/ai/extraction.extract_tasks(transcript_text, job_id, meeting_date=None)`
threads this through as `meeting_date`. **Once `models.py` / `backend/models/`
has a real `Meeting.created_at` or similar field, callers should pass that value
in as `meeting_date`** rather than relying on the "defaults to today" fallback,
so relative dates resolve against the actual meeting, not whenever extraction
happens to run (which matters if a job is retried or processed hours later).

## Null-Like String Normalization (Sprint 2 addition)

Even with strict JSON schema mode, the LLM has been observed returning the
*string* `"null"` for `due_date` instead of the JSON value `null`. `parser.py`'s
`_normalize_due_date()` treats the strings `"null"`, `"none"`, `"n/a"`, `"na"`,
`"unknown"`, and `""` (case-insensitive, whitespace-trimmed) as equivalent to
`None`, so a literal `"null"` string can never reach the database as a fake
deadline.

Any other non-empty `due_date` string is validated against real ISO 8601 date
parsing (`datetime.date.fromisoformat`). A value like `"next Friday"` slipping
through as literal text is rejected with `ExtractionValidationError`, not
silently stored -- a malformed date is treated as worse than no date.



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

## Sample Transcript Coverage

`backend/ingestion/sample_transcripts/` covers a deliberate spread of shapes so
extraction can be exercised without live Zoom RTMS:

| File | Edge case exercised |
| --- | --- |
| `sprint_review.txt` | Clear owners, concrete relative deadlines ("by Friday"), one person owning multiple tasks |
| `project_kickoff.txt` | Ambiguous-but-eventually-claimed ownership, no explicit deadlines |
| `standup_no_actions.txt` | No action items at all -- extraction must return an empty `tasks` list, not invent any |
| `vague_deadline.txt` | Non-committal deadline language ("no rush," "sometime next quarter," "whenever") -- must resolve to `due_date: null`, not a guessed date |
| `unclear_owner.txt` | A real task is raised but nobody claims it and the conversation moves on -- must resolve to `owner: "unassigned"`, not the last speaker |

TODO (Sprint 3): add a sample with explicit urgency language ("ASAP," "critical") and a sample combining "has a real task" with "no deadline mentioned" as a single case, to directly back the Sprint 3 demo-data requirement (multiple owners, no owner, no deadline, urgent priority all represented).

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
| `test_normalizes_string_null_to_none` | LLM returning the string `"null"` is treated as no deadline, not stored literally. |
| `test_normalizes_other_null_like_strings` | Same for `"none"`, `"n/a"`, and empty string. |
| `test_rejects_non_iso_due_date` | A due_date that isn't a real ISO date (e.g. `"next Friday"`) is rejected, not stored. |
| `test_accepts_valid_iso_due_date` | A well-formed ISO date passes through unchanged. |
| `test_strips_whitespace_from_string_fields` | Parser normalizes strings before database use. |

`backend/tests/test_transcript_loader.py` (added Sprint 2) covers the transcript
normalization layer that both sample files and any future live/manual transcript
text pass through:

| Test | Contract behavior |
| --- | --- |
| `test_lists_all_sample_transcripts` | Sample directory is discoverable. |
| `test_loads_a_known_sample_transcript` | A named sample loads correctly. |
| `test_missing_sample_raises_with_available_list` | Bad filename fails loudly, not silently. |
| `test_normalizes_windows_line_endings` | CRLF input (e.g. from browser paste) is normalized to `\n`. |
| `test_collapses_runs_of_blank_lines` | Long blank-line runs (e.g. from dropped RTMS chunks) don't bloat the transcript. |
| `test_strips_leading_and_trailing_whitespace` | Consistent trimming regardless of source. |
| `test_empty_input_returns_empty_string` | Empty/`None` input doesn't crash the loader. |

