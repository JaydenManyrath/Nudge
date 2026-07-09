import json
import os
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

import httpx

from models import OAuthToken, upsert_oauth_token

ZOOM_API_BASE_URL = "https://api.zoom.us/v2"
ZOOM_TOKEN_URL = "https://zoom.us/oauth/token"
TRANSCRIPT_FILE_TYPES = {"TRANSCRIPT", "VTT", "CC"}


class ZoomRecordingError(Exception):
    """Base class for user-safe Zoom recording fetch errors."""


class ZoomTokenRefreshError(ZoomRecordingError):
    pass


class ZoomPermissionError(ZoomRecordingError):
    def __init__(self, message: str, *, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class ZoomNoTranscriptError(ZoomRecordingError):
    pass


@dataclass(frozen=True)
class ZoomTranscript:
    zoom_meeting_id: str
    title: str
    meeting_date: str | None
    transcript_text: str


def latest_transcript_for_user(db, token: OAuthToken) -> ZoomTranscript:
    access_token = _valid_access_token(db, token)
    try:
        return _latest_transcript_with_access_token(access_token)
    except ZoomPermissionError as exc:
        if exc.status_code != 401:
            raise
        access_token = refresh_zoom_token(db, token).access_token
        return _latest_transcript_with_access_token(access_token)


def _latest_transcript_with_access_token(access_token: str) -> ZoomTranscript:
    recordings = _list_recent_recordings(access_token)
    recording, transcript_file = _newest_recording_with_transcript(recordings)
    if recording is None or transcript_file is None:
        raise ZoomNoTranscriptError(
            "No Zoom cloud recording transcript was found from the last 30 days."
        )

    raw_vtt = _download_transcript(access_token, transcript_file)
    transcript_text = normalize_vtt(raw_vtt)
    if not transcript_text:
        raise ZoomNoTranscriptError("The latest Zoom transcript was empty.")

    return ZoomTranscript(
        zoom_meeting_id=str(
            recording.get("uuid") or recording.get("id") or recording.get("meeting_id")
        ),
        title=(recording.get("topic") or "Zoom Cloud Recording").strip(),
        meeting_date=_meeting_date(recording),
        transcript_text=transcript_text,
    )


def refresh_zoom_token(db, token: OAuthToken) -> OAuthToken:
    if not token.refresh_token:
        raise ZoomTokenRefreshError("Reconnect Zoom to refresh recording access.")

    client_id = os.environ.get("ZOOM_CLIENT_ID")
    client_secret = os.environ.get("ZOOM_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise ZoomTokenRefreshError("Zoom OAuth is not configured.")

    response = httpx.post(
        ZOOM_TOKEN_URL,
        data={
            "grant_type": "refresh_token",
            "refresh_token": token.refresh_token,
        },
        auth=(client_id, client_secret),
        timeout=10,
    )
    if response.status_code >= 400:
        raise ZoomTokenRefreshError("Reconnect Zoom to refresh recording access.")

    token_data = response.json()
    access_token = token_data.get("access_token")
    if not access_token:
        raise ZoomTokenRefreshError("Zoom did not return a refreshed access token.")

    refreshed = OAuthToken(
        id=token.id,
        user_id=token.user_id,
        provider="zoom",
        access_token=access_token,
        refresh_token=token_data.get("refresh_token") or token.refresh_token,
        token_type=token_data.get("token_type") or token.token_type,
        scope=token_data.get("scope") or token.scope,
        expires_at=_token_expires_at(token_data),
        raw_token=json.dumps(token_data, sort_keys=True),
    )
    upsert_oauth_token(db, refreshed)
    db.commit()
    return refreshed


def normalize_vtt(vtt_text: str) -> str:
    lines = (vtt_text or "").replace("\ufeff", "").replace("\r\n", "\n").split("\n")
    normalized = []
    pending_speaker = None
    skip_block = False

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            skip_block = False
            pending_speaker = None
            continue
        if line == "WEBVTT" or line.startswith("WEBVTT "):
            continue
        if line in {"NOTE", "STYLE", "REGION"} or line.startswith(("NOTE ", "STYLE ", "REGION ")):
            skip_block = True
            continue
        if skip_block:
            continue
        if re.fullmatch(r"\d+", line):
            continue
        if "-->" in line:
            pending_speaker = _speaker_from_voice_tag(line)
            continue

        speaker = _speaker_from_voice_tag(line) or pending_speaker
        line = re.sub(r"<v\s+([^>]+)>", "", line)
        line = re.sub(r"</v>", "", line)
        line = re.sub(r"<[^>]+>", "", line)
        line = re.sub(r"\s+", " ", line).strip()
        if not line:
            continue
        if speaker and ":" not in line.split(" ", 2)[0]:
            line = f"{speaker}: {line}"
        normalized.append(line)

    return "\n".join(normalized).strip()


def _valid_access_token(db, token: OAuthToken) -> str:
    if _is_expired(token.expires_at):
        return refresh_zoom_token(db, token).access_token
    return token.access_token


def _is_expired(expires_at: str | None) -> bool:
    if not expires_at:
        return False
    try:
        parsed = datetime.fromisoformat(expires_at)
    except ValueError:
        return False
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed <= datetime.now(timezone.utc) + timedelta(seconds=60)


def _list_recent_recordings(access_token: str) -> list[dict]:
    today = date.today()
    params = {
        "from": (today - timedelta(days=30)).isoformat(),
        "to": today.isoformat(),
        "page_size": 30,
    }
    recordings = []
    next_page_token = None

    for _page in range(3):
        if next_page_token:
            params["next_page_token"] = next_page_token
        response = _zoom_get(
            f"{ZOOM_API_BASE_URL}/users/me/recordings",
            access_token,
            params=params,
        )
        data = response.json()
        recordings.extend(data.get("meetings", []))
        next_page_token = data.get("next_page_token")
        if not next_page_token:
            break

    return recordings


def _newest_recording_with_transcript(recordings: list[dict]) -> tuple[dict | None, dict | None]:
    sorted_recordings = sorted(
        recordings,
        key=lambda item: item.get("start_time") or item.get("recording_start") or "",
        reverse=True,
    )
    for recording in sorted_recordings:
        transcript_file = _transcript_file(recording.get("recording_files") or [])
        if transcript_file is not None:
            return recording, transcript_file
    return None, None


def _transcript_file(files: list[dict]) -> dict | None:
    for recording_file in files:
        file_type = str(recording_file.get("file_type") or "").upper()
        if file_type in TRANSCRIPT_FILE_TYPES and recording_file.get("download_url"):
            return recording_file
    return None


def _download_transcript(access_token: str, transcript_file: dict) -> str:
    response = _zoom_get(transcript_file["download_url"], access_token)
    return response.text


def _zoom_get(url: str, access_token: str, *, params: dict | None = None):
    try:
        response = httpx.get(
            url,
            headers={"Authorization": f"Bearer {access_token}"},
            params=params,
            timeout=15,
        )
    except httpx.HTTPError as exc:
        raise ZoomRecordingError("Zoom recording data could not be loaded.") from exc
    if response.status_code in {401, 403}:
        raise ZoomPermissionError(
            "Zoom did not allow access to cloud recordings.",
            status_code=response.status_code,
        )
    if response.status_code >= 400:
        raise ZoomRecordingError("Zoom recording data could not be loaded.")
    return response


def _meeting_date(recording: dict) -> str | None:
    value = recording.get("start_time") or recording.get("recording_start")
    if not value:
        return None
    return str(value)[:10]


def _speaker_from_voice_tag(line: str) -> str | None:
    match = re.search(r"<v\s+([^>]+)>", line)
    if not match:
        return None
    return re.sub(r"\s+", " ", match.group(1)).strip()


def _token_expires_at(token_data: dict) -> str | None:
    expires_in = token_data.get("expires_in")
    if expires_in is None:
        return None
    try:
        seconds = int(expires_in)
    except (TypeError, ValueError):
        return None
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat()
