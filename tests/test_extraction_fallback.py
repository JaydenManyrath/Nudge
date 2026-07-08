"""
tests/test_extraction_fallback.py
Owner: Dev A

Covers the extraction-path selection logic in root extraction.py:
extract_tasks() should prefer the real OpenAI-backed pipeline
(backend/ai/extraction.py) whenever OPENAI_API_KEY is configured, and
fall back to the deterministic, network-free extractor when the key is
missing or the OpenAI call fails outright. These tests never hit the
network -- the OpenAI path is monkeypatched, not exercised for real.
"""

import pytest

import extraction
from backend.ai.extraction import ExtractionError as OpenAIExtractionError

SAMPLE_TRANSCRIPT = (
    "[Standup]\n\nAlex: I'll update the deployment docs by Friday.\n"
)


def test_no_api_key_uses_fallback_and_warns(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    result = extraction.extract_tasks(SAMPLE_TRANSCRIPT, job_id=1)

    assert result["extraction_method"] == "fallback"
    assert "OPENAI_API_KEY" in result["extraction_warning"]
    assert result["summary"]


def test_openai_success_path_is_used_when_key_present(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-real")

    canned = {
        "summary": "Alex will update deployment docs.",
        "tasks": [
            {
                "owner": "Alex",
                "description": "Update the deployment docs",
                "due_date": "2026-07-10",
                "priority": "normal",
                "context": "Alex committed to updating docs by Friday.",
            }
        ],
    }

    def fake_openai_extract(transcript_text, job_id, meeting_date=None):
        return canned

    monkeypatch.setattr(extraction, "openai_extract_tasks", fake_openai_extract)

    result = extraction.extract_tasks(SAMPLE_TRANSCRIPT, job_id=2)

    assert result["extraction_method"] == "openai"
    assert result["extraction_warning"] is None
    assert result["summary"] == canned["summary"]
    assert result["tasks"] == canned["tasks"]


def test_openai_failure_falls_back_with_warning(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-real")

    def failing_openai_extract(transcript_text, job_id, meeting_date=None):
        raise OpenAIExtractionError(f"job_id={job_id}: LLM call failed: rate limited")

    monkeypatch.setattr(extraction, "openai_extract_tasks", failing_openai_extract)

    result = extraction.extract_tasks(SAMPLE_TRANSCRIPT, job_id=3)

    assert result["extraction_method"] == "fallback"
    assert "OpenAI extraction failed" in result["extraction_warning"]
    assert "rate limited" in result["extraction_warning"]
    # The fallback should still have produced a usable draft task.
    assert len(result["tasks"]) >= 1


def test_empty_transcript_raises_regardless_of_api_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-real")

    with pytest.raises(extraction.ExtractionError):
        extraction.extract_tasks("   ", job_id=4)
