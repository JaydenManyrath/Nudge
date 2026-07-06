"""
backend/ai/llm_client.py
Owner: Dev A

Thin wrapper around the OpenAI API for structured task extraction.
Uses JSON schema / structured outputs (see schema.get_json_schema())
so the raw response is shaped correctly by construction -- parser.py
is the actual safety net that validates it before anything touches
the database.

NOTE ON NAMING: earlier planning docs called this "claude_client.py"
in the sprint plan. The team decided to stay on OpenAI (matches the
existing requirements.txt), so this file is named llm_client.py
instead to avoid a misleading filename. If routes/upload.py or
extraction.py were written against a "claude_client" import, update
that import to `from backend.ai.llm_client import call_extraction`.
"""

import json
import os

from openai import OpenAI

from .prompts import SYSTEM_PROMPT, build_user_prompt
from .schema import get_json_schema

_MODEL = os.environ.get("OPENAI_EXTRACTION_MODEL", "gpt-4o-mini")


def _get_client() -> OpenAI:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set -- check your .env")
    return OpenAI(api_key=api_key)


def call_extraction(transcript_text: str) -> dict:
    """
    Sends the transcript to OpenAI and returns the parsed JSON response
    as a Python dict. Raises on network/API errors -- callers
    (backend/ai/extraction.py) are responsible for catching and
    handling failures (e.g. marking the job as failed) so a bad LLM
    call can't crash the request or the background worker.

    NOTE: this function does NOT validate the response against
    schema.py -- that's parser.py's job, kept deliberately separate so
    validation logic is unit-testable without hitting the network
    (see backend/tests/test_ai_parser.py).
    """
    client = _get_client()

    response = client.chat.completions.create(
        model=_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_prompt(transcript_text)},
        ],
        response_format={
            "type": "json_schema",
            "json_schema": get_json_schema(),
        },
    )

    raw_content = response.choices[0].message.content
    return json.loads(raw_content)
