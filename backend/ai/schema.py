"""
backend/ai/schema.py
Owner: Dev A

Defines the structured contract for LLM-extracted tasks. This is the
schema the whole team builds against -- Dev B's models/routes and
Dev C's review UI all assume this shape. Any change here must be
communicated to Dev B and Dev C.

Expected top-level LLM response shape:
{
  "summary": str,
  "tasks": [
    {
      "owner": str,               # name as it appears in the transcript, or "unassigned"
      "description": str,
      "due_date": str | None,     # ISO 8601 date, e.g. "2026-07-10", or null if unspecified
      "priority": "low" | "normal" | "urgent",
      "context": str              # short paraphrase of the transcript moment this came from
    },
    ...
  ]
}
"""

REQUIRED_TASK_FIELDS = {
    "owner": str,
    "description": str,
    "due_date": (str, type(None)),
    "priority": str,
    "context": str,
}

VALID_PRIORITIES = {"low", "normal", "urgent"}

REQUIRED_TOP_LEVEL_FIELDS = {
    "summary": str,
    "tasks": list,
}


def get_json_schema() -> dict:
    """
    Returns an OpenAI-compatible JSON schema (for use with
    response_format={"type": "json_schema", "json_schema": ...}, i.e.
    structured outputs) describing the expected extraction output.
    Keep this in sync with the REQUIRED_*/VALID_* constants above --
    parser.py validates against those, not against this dict directly.
    """
    return {
        "name": "meeting_extraction",
        "schema": {
            "type": "object",
            "properties": {
                "summary": {"type": "string"},
                "tasks": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "owner": {"type": "string"},
                            "description": {"type": "string"},
                            "due_date": {"type": ["string", "null"]},
                            "priority": {
                                "type": "string",
                                "enum": sorted(VALID_PRIORITIES),
                            },
                            "context": {"type": "string"},
                        },
                        "required": [
                            "owner",
                            "description",
                            "due_date",
                            "priority",
                            "context",
                        ],
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["summary", "tasks"],
            "additionalProperties": False,
        },
        "strict": True,
    }
