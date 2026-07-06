"""
backend/ingestion/transcript_loader.py
Owner: Dev A

Loads transcript text for a meeting job. Sprint 1: reads from the local
sample_transcripts/ folder so Dev B and Dev C can build against
real-shaped data without waiting on live Zoom OAuth (zoom_client.py
lands in Sprint 2). This module is meant to become the shared entry
point regardless of whether the transcript came from Zoom RTMS, a
manual upload (routes/upload.py), or a sample file.
"""

import os

_SAMPLE_DIR = os.path.join(os.path.dirname(__file__), "sample_transcripts")


def list_sample_transcripts() -> list:
    """Returns the available sample transcript filenames, sorted."""
    if not os.path.isdir(_SAMPLE_DIR):
        return []
    return sorted(f for f in os.listdir(_SAMPLE_DIR) if f.endswith(".txt"))


def load_sample_transcript(filename: str) -> str:
    """
    Loads a single sample transcript by filename (e.g. "sprint_review.txt")
    from backend/ingestion/sample_transcripts/. Raises FileNotFoundError
    with a clear message if it doesn't exist, so a typo fails loudly
    rather than silently feeding extraction an empty string.
    """
    path = os.path.join(_SAMPLE_DIR, filename)
    if not os.path.isfile(path):
        available = ", ".join(list_sample_transcripts()) or "(none found)"
        raise FileNotFoundError(
            f"No sample transcript named '{filename}'. Available: {available}"
        )

    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def load_transcript_from_text(raw_text: str) -> str:
    """
    Normalizes transcript text coming from a manual upload (routes/upload.py)
    or any other future source (e.g. full Zoom RTMS transcript, once
    zoom_client.py lands in Sprint 2). Currently just strips leading/
    trailing whitespace -- kept as its own function so upload/Zoom code
    has one shared place to route through before extraction.py sees it.
    """
    return raw_text.strip()
