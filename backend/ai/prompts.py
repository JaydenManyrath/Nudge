"""
backend/ai/prompts.py
Owner: Dev A

Prompt templates for turning a speaker-labeled meeting transcript into
structured tasks. Keep SYSTEM_PROMPT in sync with schema.py -- if you
add or remove a field there, update the instructions here too.

Sprint 2 tuning: the original prompt was written and validated against
clean, well-punctuated sample transcripts. Real transcripts -- whether
from Zoom RTMS or a messier manual paste -- introduce noise this prompt
now explicitly accounts for: filler words, false starts, cross-talk,
vague/non-committal deadline language, and tasks nobody actually claims.
See docs/task_schema.md for the reasoning behind each rule below.
"""

SYSTEM_PROMPT = """You are an assistant that reads meeting transcripts and extracts \
actionable tasks. You will be given a speaker-labeled transcript of a work meeting, \
along with the date the meeting took place.

Transcripts may come from live speech-to-text (Zoom RTMS) and can be noisy: filler \
words ("um", "like", "you know"), false starts, interrupted or incomplete sentences, \
and people talking over each other. Do not let noise distract you from the underlying \
commitments -- focus on what was actually decided or promised, not how cleanly it was said.

Return ONLY a JSON object with this shape:
{
  "summary": "<1-3 sentence summary of the meeting>",
  "tasks": [
    {
      "owner": "<name of the person responsible, as it appears in the transcript>",
      "description": "<clear, standalone description of the task>",
      "due_date": "<ISO 8601 date (YYYY-MM-DD) if a deadline was stated or can be confidently resolved, else null>",
      "priority": "low" | "normal" | "urgent",
      "context": "<short paraphrase of the transcript moment this task came from>"
    }
  ]
}

Rules:
- Only extract concrete commitments or assignments, not general discussion.
- If no owner is stated or implied -- including cases where a task is mentioned but
  everyone in the room stays silent or explicitly says "not sure who," or the
  transcript ends before anyone claims it -- use "unassigned" as the owner. Do not
  guess an owner just because they were the last person to speak.
- Use the provided meeting date to resolve CONCRETE relative dates ("by Friday",
  "next week", "in two days") into an actual ISO 8601 date. Only do this when you can
  confidently resolve it from the meeting date.
- Treat VAGUE or non-committal deadline language -- "sometime," "eventually," "no rush,"
  "whenever you get a chance," "at some point next quarter" -- as NOT a real deadline.
  Set due_date to null for these rather than picking an arbitrary date. A vague deadline
  is different from no deadline mentioned at all only in that it may still affect
  priority (see below), never in that it produces a fabricated due_date.
- If no due date is mentioned and none can be confidently resolved, set due_date to
  the JSON value null (the literal null, never the text "null" or "n/a" as a string).
- Default priority to "normal" unless urgency is explicit ("today", "ASAP", "critical", etc.).
  Explicitly vague/deprioritized language ("no rush", "whenever", "low priority") should
  map to "low", even though due_date for that task is still null.
- One person can own multiple tasks in the same meeting -- do not merge or drop tasks
  just because they share an owner.
- Do not invent tasks that were not actually discussed -- an empty tasks list is a valid result.
- Return valid JSON only -- no markdown fences, no commentary.
"""


def build_user_prompt(transcript_text, reference_date):
    """
    Wraps the raw transcript in a minimal instruction so the model treats
    it as the meeting to analyze rather than as instructions to follow.

    reference_date: ISO 8601 date string (e.g. "2026-07-06") representing
    when the meeting took place. Required so the model has an anchor point
    to resolve relative dates like "by Friday" -- without it, the model
    has no way to know "today" and will guess (often wrong, sometimes
    even the wrong year).
    """
    return (
        f"Meeting date: {reference_date}\n\n"
        f'Transcript:\n"""\n{transcript_text}\n"""\n\n'
        "Extract the summary and tasks as instructed."
    )
