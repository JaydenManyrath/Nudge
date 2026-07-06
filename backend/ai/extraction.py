"""
backend/ai/extraction.py
Owner: Dev A

Orchestrates the AI extraction pipeline: transcript text in, validated
task list out. This is the module the job pipeline / routes/review.py
actually calls -- it never writes to the database and never triggers
distribution itself. Per models.py's task lifecycle: extraction only
ever produces "draft" candidates; draft -> pending happens exclusively
on manager approval in routes/review.py.

Sprint 1 acceptance criteria: given a sample transcript (see
backend/ingestion/sample_transcripts/), extract_tasks() returns a
valid structured task list matching schema.py -- no live Zoom needed.
"""

from .llm_client import call_extraction
from .parser import validate_extraction, ExtractionValidationError


class ExtractionError(Exception):
    """Raised when extraction fails outright (API error or unrecoverable bad output)."""


def extract_tasks(transcript_text: str, job_id: int) -> dict:
    """
    Runs the full extraction pipeline for a single job:
      1. Call the LLM                (llm_client.call_extraction)
      2. Validate + normalize output (parser.validate_extraction)

    Returns a dict shaped:
      {"summary": str, "tasks": [{owner, description, due_date, priority, context}, ...]}

    Does NOT write to the database. The caller (job pipeline /
    routes/upload.py) is responsible for persisting each task as a
    draft row and flipping the job status to awaiting_review. Kept
    this way so extraction stays a pure, independently testable
    function (see backend/tests/test_ai_parser.py).

    Raises ExtractionError if the LLM call fails, or if the response
    can't be validated even after the model was asked for structured
    JSON output.
    """
    if not transcript_text or not transcript_text.strip():
        raise ExtractionError(f"job_id={job_id}: transcript_text is empty")

    try:
        raw_response = call_extraction(transcript_text)
    except Exception as exc:
        raise ExtractionError(f"job_id={job_id}: LLM call failed: {exc}") from exc

    try:
        return validate_extraction(raw_response)
    except ExtractionValidationError as exc:
        raise ExtractionError(f"job_id={job_id}: response failed validation: {exc}") from exc
