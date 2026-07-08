import hmac
import os

from flask import Blueprint, jsonify, request

import rtms


bp = Blueprint("rtms_ingress", __name__, url_prefix="/rtms")

_SECRET_HEADER = "X-Nudge-RTMS-Secret"
_EVENT_ALIASES = {
    "meeting.start": "meeting.started",
    "meeting.started": "meeting.started",
    "meeting_started": "meeting.started",
    "started": "meeting.started",
    "transcript.chunk": "transcript.chunk",
    "transcript_chunk": "transcript.chunk",
    "chunk": "transcript.chunk",
    "meeting.end": "meeting.ended",
    "meeting.ended": "meeting.ended",
    "meeting_ended": "meeting.ended",
    "ended": "meeting.ended",
}
_EVENT_HANDLERS = {
    "meeting.started": rtms.handle_meeting_started,
    "transcript.chunk": rtms.handle_transcript_chunk,
    "meeting.ended": rtms.handle_meeting_ended,
}


@bp.route("/events", methods=["POST"])
def rtms_events():
    secret = os.environ.get("ZOOM_SECRET_TOKEN")
    if not secret:
        return jsonify({"error": "RTMS ingress secret is not configured"}), 503

    provided_secret = request.headers.get(_SECRET_HEADER, "")
    if not hmac.compare_digest(provided_secret, secret):
        return jsonify({"error": "Invalid RTMS ingress secret"}), 401

    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify({"error": "Expected JSON object payload"}), 400

    event_type = _canonical_event_type(body)
    handler = _EVENT_HANDLERS.get(event_type)
    if handler is None:
        return (
            jsonify(
                {
                    "error": "Unsupported RTMS event type",
                    "event": _raw_event_type(body),
                    "supported_events": sorted(_EVENT_HANDLERS.keys()),
                }
            ),
            400,
        )

    return jsonify(handler(_handler_payload(body)))


def _canonical_event_type(body):
    raw_event = _raw_event_type(body)
    if not raw_event:
        return None
    event_key = str(raw_event).strip().lower()
    return _EVENT_ALIASES.get(event_key, event_key)


def _raw_event_type(body):
    for key in ("event", "event_type", "type"):
        value = body.get(key)
        if value:
            return value
    return None


def _handler_payload(body):
    if "payload" in body or not isinstance(body.get("data"), dict):
        return body

    payload = dict(body)
    payload["payload"] = body["data"]
    return payload
