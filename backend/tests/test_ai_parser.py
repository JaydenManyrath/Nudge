"""
backend/tests/test_ai_parser.py
Owner: Dev A

Unit tests for backend/ai/parser.py. Counts toward the 6+ required
unit tests -- extraction is the least deterministic part of the app
(LLM output), so it gets the heaviest coverage.

These tests never call the network / OpenAI -- they feed
validate_extraction() hand-built dicts that simulate good and bad LLM
responses, so they run fast and deterministically in CI.
"""

import pytest

from backend.ai.parser import validate_extraction, ExtractionValidationError


GOOD_RESPONSE = {
    "summary": "Team discussed Q3 launch blockers and assigned follow-ups.",
    "tasks": [
        {
            "owner": "Priya",
            "description": "Finalize the pricing page copy",
            "due_date": "2026-07-10",
            "priority": "urgent",
            "context": "Priya said she'd have pricing copy done by Friday",
        },
        {
            "owner": "unassigned",
            "description": "Investigate flaky checkout test",
            "due_date": None,
            "priority": "normal",
            "context": "Someone mentioned the checkout test has been flaky",
        },
    ],
}


def test_accepts_well_formed_response():
    result = validate_extraction(GOOD_RESPONSE)
    assert result["summary"] == GOOD_RESPONSE["summary"]
    assert len(result["tasks"]) == 2
    assert result["tasks"][0]["owner"] == "Priya"


def test_accepts_empty_task_list():
    data = {"summary": "Quick sync, no action items.", "tasks": []}
    result = validate_extraction(data)
    assert result["tasks"] == []


def test_rejects_non_dict_top_level():
    with pytest.raises(ExtractionValidationError):
        validate_extraction(["not", "a", "dict"])


def test_rejects_missing_summary():
    data = {"tasks": []}
    with pytest.raises(ExtractionValidationError, match="summary"):
        validate_extraction(data)


def test_rejects_missing_task_field():
    data = {
        "summary": "ok",
        "tasks": [
            {
                "owner": "Sam",
                "description": "Do the thing",
                "priority": "normal",
                "context": "...",
                # due_date deliberately omitted
            }
        ],
    }
    with pytest.raises(ExtractionValidationError, match="due_date"):
        validate_extraction(data)


def test_rejects_invalid_priority():
    data = {
        "summary": "ok",
        "tasks": [
            {
                "owner": "Sam",
                "description": "Do the thing",
                "due_date": None,
                "priority": "super-urgent",
                "context": "...",
            }
        ],
    }
    with pytest.raises(ExtractionValidationError, match="priority"):
        validate_extraction(data)


def test_rejects_empty_owner():
    data = {
        "summary": "ok",
        "tasks": [
            {
                "owner": "   ",
                "description": "Do the thing",
                "due_date": None,
                "priority": "normal",
                "context": "...",
            }
        ],
    }
    with pytest.raises(ExtractionValidationError, match="owner"):
        validate_extraction(data)


def test_strips_whitespace_from_string_fields():
    data = {
        "summary": "  Trimmed summary.  ",
        "tasks": [
            {
                "owner": "  Jamie  ",
                "description": "  Ship the report  ",
                "due_date": "2026-07-15",
                "priority": "low",
                "context": "  said at the end of the call  ",
            }
        ],
    }
    result = validate_extraction(data)
    assert result["summary"] == "Trimmed summary."
    assert result["tasks"][0]["owner"] == "Jamie"
    assert result["tasks"][0]["description"] == "Ship the report"
