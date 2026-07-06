"""
backend/ai/parser.py
Owner: Dev A

Validates the LLM's JSON response against the contract in schema.py
before it's allowed anywhere near the database. LLM output isn't
always perfectly structured, even with JSON schema mode on -- this is
the safety net so a malformed response can't crash routes/review.py
or corrupt the tasks table.

validate_extraction() either returns a cleaned/normalized dict, or
raises ExtractionValidationError with a human-readable reason.
"""

from .schema import (
    REQUIRED_TOP_LEVEL_FIELDS,
    REQUIRED_TASK_FIELDS,
    VALID_PRIORITIES,
)


class ExtractionValidationError(Exception):
    """Raised when the LLM's response doesn't match the expected schema."""


def validate_extraction(data: dict) -> dict:
    if not isinstance(data, dict):
        raise ExtractionValidationError(
            f"Top-level response must be an object, got {type(data).__name__}"
        )

    for field, expected_type in REQUIRED_TOP_LEVEL_FIELDS.items():
        if field not in data:
            raise ExtractionValidationError(f"Missing required field: '{field}'")
        if not isinstance(data[field], expected_type):
            raise ExtractionValidationError(
                f"Field '{field}' should be {expected_type.__name__}, "
                f"got {type(data[field]).__name__}"
            )

    cleaned_tasks = [_validate_task(task, i) for i, task in enumerate(data["tasks"])]

    return {"summary": data["summary"].strip(), "tasks": cleaned_tasks}


def _validate_task(task: dict, index: int) -> dict:
    if not isinstance(task, dict):
        raise ExtractionValidationError(
            f"tasks[{index}] must be an object, got {type(task).__name__}"
        )

    for field, expected_type in REQUIRED_TASK_FIELDS.items():
        if field not in task:
            raise ExtractionValidationError(
                f"tasks[{index}] missing required field: '{field}'"
            )
        if not isinstance(task[field], expected_type):
            raise ExtractionValidationError(
                f"tasks[{index}].{field} has the wrong type "
                f"(got {type(task[field]).__name__})"
            )

    if task["priority"] not in VALID_PRIORITIES:
        raise ExtractionValidationError(
            f"tasks[{index}].priority must be one of {sorted(VALID_PRIORITIES)}, "
            f"got '{task['priority']}'"
        )

    if not task["owner"].strip():
        raise ExtractionValidationError(f"tasks[{index}].owner cannot be empty")

    if not task["description"].strip():
        raise ExtractionValidationError(f"tasks[{index}].description cannot be empty")

    return {
        "owner": task["owner"].strip(),
        "description": task["description"].strip(),
        "due_date": task["due_date"],
        "priority": task["priority"],
        "context": task["context"].strip(),
    }
