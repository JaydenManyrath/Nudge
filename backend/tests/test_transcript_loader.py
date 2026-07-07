"""
backend/tests/test_transcript_loader.py
Owner: Dev A

Unit tests for backend/ingestion/transcript_loader.py. Added in Sprint 2
to back up the "confirm parser output remains stable when transcript
text comes from Zoom RTMS instead of sample files" task -- since live
RTMS isn't wired up yet (Dev B, Sprint 2), these tests simulate the
kind of messy input RTMS or a manual paste could plausibly produce
(CRLF line endings, runs of blank lines from dropped chunks) and
confirm load_transcript_from_text() normalizes it the same way
regardless of source.
"""

import pytest

from backend.ingestion.transcript_loader import (
    list_sample_transcripts,
    load_sample_transcript,
    load_transcript_from_text,
)


def test_lists_all_sample_transcripts():
    files = list_sample_transcripts()
    assert "sprint_review.txt" in files
    assert all(f.endswith(".txt") for f in files)


def test_loads_a_known_sample_transcript():
    text = load_sample_transcript("sprint_review.txt")
    assert "Jamie" in text
    assert len(text) > 0


def test_missing_sample_raises_with_available_list():
    with pytest.raises(FileNotFoundError, match="sprint_review.txt"):
        load_sample_transcript("does_not_exist.txt")


def test_normalizes_windows_line_endings():
    raw = "Jamie: hello\r\nSam: hi there\r\n"
    result = load_transcript_from_text(raw)
    assert "\r" not in result
    assert result == "Jamie: hello\nSam: hi there"


def test_collapses_runs_of_blank_lines():
    raw = "Jamie: hello\n\n\n\n\nSam: hi there"
    result = load_transcript_from_text(raw)
    assert "\n\n\n" not in result
    assert result == "Jamie: hello\n\nSam: hi there"


def test_strips_leading_and_trailing_whitespace():
    raw = "\n\n  Jamie: hello  \n\n"
    result = load_transcript_from_text(raw)
    assert result == "Jamie: hello"


def test_empty_input_returns_empty_string():
    assert load_transcript_from_text("") == ""
    assert load_transcript_from_text(None) == ""
