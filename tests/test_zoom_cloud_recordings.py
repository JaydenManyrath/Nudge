from datetime import datetime, timedelta, timezone

import models
import backend.ingestion.zoom_recordings as zoom_recordings
import routes.dashboard as dashboard
from backend.ingestion.zoom_recordings import (
    ZoomNoTranscriptError,
    ZoomPermissionError,
    ZoomRecordingError,
    ZoomTokenRefreshError,
    ZoomTranscript,
    normalize_vtt,
)


def test_vtt_normalization_preserves_speakers_and_removes_cues():
    raw_vtt = """WEBVTT

1
00:00:01.000 --> 00:00:03.000
<v Dat Nguyen>I'll send the launch notes by Friday.

2
00:00:04.000 --> 00:00:05.000
Maya: Please review the rollout plan.
"""

    assert normalize_vtt(raw_vtt) == (
        "Dat Nguyen: I'll send the launch notes by Friday.\n"
        "Maya: Please review the rollout plan."
    )


def test_live_meeting_imports_staged_zoom_cloud_transcript(
    client,
    login_as_user,
    monkeypatch,
):
    login_as_user("andrew@nudge.local")
    _store_zoom_token()
    monkeypatch.setattr(
        dashboard,
        "latest_transcript_for_user",
        lambda db, token: ZoomTranscript(
            zoom_meeting_id="zoom-cloud-123",
            title="Launch Recording",
            meeting_date="2026-07-08",
            transcript_text="Priya: I'll send the launch notes by Friday.",
        ),
    )

    response = client.get("/dashboard/live")

    assert response.status_code == 200
    assert b"Launch Recording" in response.data
    assert b"Priya: I&#39;ll send the launch notes by Friday." in response.data

    with client.session_transaction() as session:
        transcript_hash = session[dashboard.ZOOM_TRANSCRIPT_SESSION_KEY][
            "transcript_hash"
        ]
    response = client.post(
        "/dashboard/live/import",
        data={"transcript_hash": transcript_hash},
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/review/")
    with models.get_db() as db:
        meeting = db.execute(
            """
            SELECT *
            FROM meetings
            WHERE source = 'zoom_cloud_recording'
              AND zoom_meeting_id = 'zoom-cloud-123'
            """
        ).fetchone()
        tasks = db.execute(
            "SELECT * FROM tasks WHERE meeting_id = ?",
            (meeting["id"],),
        ).fetchall()
    assert meeting["title"] == "Launch Recording"
    assert meeting["transcript"] == "Priya: I'll send the launch notes by Friday."
    assert len(tasks) == 1


def test_zoom_recording_fetch_refreshes_token_after_401(monkeypatch):
    _store_zoom_token()
    monkeypatch.setenv("ZOOM_CLIENT_ID", "zoom-client")
    monkeypatch.setenv("ZOOM_CLIENT_SECRET", "zoom-secret")
    calls = {"get": 0}

    def fake_get(url, headers=None, params=None, timeout=None):
        calls["get"] += 1
        if calls["get"] == 1:
            return _FakeResponse(status_code=401)
        if "users/me/recordings" in url:
            return _FakeResponse(
                json_data={
                    "meetings": [
                        {
                            "uuid": "zoom-refresh-123",
                            "topic": "Refresh Recording",
                            "start_time": "2026-07-08T12:00:00Z",
                            "recording_files": [
                                {
                                    "file_type": "TRANSCRIPT",
                                    "download_url": "https://zoom.example/download",
                                }
                            ],
                        }
                    ]
                }
            )
        return _FakeResponse(
            text="WEBVTT\n\n00:00:01.000 --> 00:00:02.000\n<v Priya>I'll send notes."
        )

    def fake_post(url, data=None, auth=None, timeout=None):
        assert data["grant_type"] == "refresh_token"
        assert data["refresh_token"] == "zoom-refresh-token"
        assert auth == ("zoom-client", "zoom-secret")
        return _FakeResponse(
            json_data={
                "access_token": "refreshed-access-token",
                "refresh_token": "new-refresh-token",
                "expires_in": 3600,
            }
        )

    monkeypatch.setattr(zoom_recordings.httpx, "get", fake_get)
    monkeypatch.setattr(zoom_recordings.httpx, "post", fake_post)

    with models.get_db() as db:
        token = models.get_oauth_token(
            db,
            user_id=_manager_user_id(),
            provider="zoom",
        )
        transcript = zoom_recordings.latest_transcript_for_user(db, token)

    assert transcript.zoom_meeting_id == "zoom-refresh-123"
    assert transcript.transcript_text == "Priya: I'll send notes."
    with models.get_db() as db:
        refreshed = models.get_oauth_token(
            db,
            user_id=_manager_user_id(),
            provider="zoom",
        )
    assert refreshed.access_token == "refreshed-access-token"
    assert refreshed.refresh_token == "new-refresh-token"


def test_live_meeting_shows_disconnected_without_zoom_token(client, login_as_user):
    login_as_user("andrew@nudge.local")

    response = client.get("/dashboard/live")

    assert response.status_code == 200
    assert b"Zoom is not connected" in response.data
    with client.session_transaction() as session:
        assert dashboard.ZOOM_TRANSCRIPT_SESSION_KEY not in session


def test_live_meeting_shows_refresh_failure(client, login_as_user, monkeypatch):
    login_as_user("andrew@nudge.local")
    _store_zoom_token()
    monkeypatch.setattr(
        dashboard,
        "latest_transcript_for_user",
        lambda db, token: (_ for _ in ()).throw(
            ZoomTokenRefreshError("token refresh failed")
        ),
    )

    response = client.get("/dashboard/live")

    assert response.status_code == 200
    assert b"Reconnect Zoom to load cloud recording transcripts." in response.data


def test_live_meeting_shows_permission_error(client, login_as_user, monkeypatch):
    login_as_user("andrew@nudge.local")
    _store_zoom_token()
    monkeypatch.setattr(
        dashboard,
        "latest_transcript_for_user",
        lambda db, token: (_ for _ in ()).throw(
            ZoomPermissionError("raw provider detail")
        ),
    )

    response = client.get("/dashboard/live")

    assert response.status_code == 200
    assert b"Zoom did not allow access to cloud recordings" in response.data
    assert b"raw provider detail" not in response.data


def test_live_meeting_shows_no_transcript(client, login_as_user, monkeypatch):
    login_as_user("andrew@nudge.local")
    _store_zoom_token()
    monkeypatch.setattr(
        dashboard,
        "latest_transcript_for_user",
        lambda db, token: (_ for _ in ()).throw(
            ZoomNoTranscriptError("No Zoom cloud recording transcript was found.")
        ),
    )

    response = client.get("/dashboard/live")

    assert response.status_code == 200
    assert b"No Zoom cloud recording transcript was found." in response.data


def test_live_meeting_suppresses_generic_zoom_recording_error(
    client,
    login_as_user,
    monkeypatch,
):
    login_as_user("andrew@nudge.local")
    _store_zoom_token()
    monkeypatch.setattr(
        dashboard,
        "latest_transcript_for_user",
        lambda db, token: (_ for _ in ()).throw(
            ZoomRecordingError("provider unavailable")
        ),
    )

    response = client.get("/dashboard/live")

    assert response.status_code == 200
    assert b"Zoom cloud recording transcripts could not be loaded." not in response.data
    assert b"Andrew: Before we wrap, Jayden" in response.data


def test_live_meeting_does_not_stage_large_transcript(
    client,
    login_as_user,
    monkeypatch,
):
    login_as_user("andrew@nudge.local")
    _store_zoom_token()
    monkeypatch.setattr(
        dashboard,
        "latest_transcript_for_user",
        lambda db, token: ZoomTranscript(
            zoom_meeting_id="zoom-large",
            title="Large Recording",
            meeting_date="2026-07-08",
            transcript_text="Priya: " + ("follow up " * 6000),
        ),
    )

    response = client.get("/dashboard/live")

    assert response.status_code == 200
    assert b"Transcript is larger than 50 KB" in response.data
    with client.session_transaction() as session:
        assert dashboard.ZOOM_TRANSCRIPT_SESSION_KEY not in session


def test_duplicate_zoom_cloud_import_is_blocked(client, login_as_user):
    login_as_user("andrew@nudge.local")
    fetched_at = datetime.now(timezone.utc).isoformat()
    with client.session_transaction() as session:
        session[dashboard.ZOOM_TRANSCRIPT_SESSION_KEY] = {
            "zoom_meeting_id": "zoom-dupe",
            "title": "Duplicate Recording",
            "meeting_date": "2026-07-08",
            "transcript_text": "Priya: I'll send launch notes by Friday.",
            "transcript_hash": "known-hash",
            "fetched_at": fetched_at,
        }
    with models.get_db() as db:
        db.execute(
            """
            INSERT INTO meetings (
                title, summary, transcript, source, zoom_meeting_id, extraction_status
            )
            VALUES (
                'Duplicate Recording',
                'Imported already.',
                'Existing',
                'zoom_cloud_recording',
                'zoom-dupe',
                'parsed'
            )
            """
        )
        db.commit()

    response = client.post(
        "/dashboard/live/import",
        data={"transcript_hash": "known-hash"},
    )

    assert response.status_code == 302
    with models.get_db() as db:
        count = db.execute(
            """
            SELECT COUNT(*) AS total
            FROM meetings
            WHERE source = 'zoom_cloud_recording'
              AND zoom_meeting_id = 'zoom-dupe'
            """
        ).fetchone()["total"]
    assert count == 1


def test_expired_staged_zoom_transcript_is_not_imported(client, login_as_user):
    login_as_user("andrew@nudge.local")
    fetched_at = (datetime.now(timezone.utc) - timedelta(minutes=31)).isoformat()
    with client.session_transaction() as session:
        session[dashboard.ZOOM_TRANSCRIPT_SESSION_KEY] = {
            "zoom_meeting_id": "zoom-expired",
            "title": "Expired Recording",
            "meeting_date": "2026-07-08",
            "transcript_text": "Priya: I'll send launch notes by Friday.",
            "transcript_hash": "known-hash",
            "fetched_at": fetched_at,
        }

    response = client.post(
        "/dashboard/live/import",
        data={"transcript_hash": "known-hash"},
    )

    assert response.status_code == 302
    with models.get_db() as db:
        meeting = db.execute(
            "SELECT id FROM meetings WHERE zoom_meeting_id = 'zoom-expired'"
        ).fetchone()
    assert meeting is None


def _store_zoom_token():
    with models.get_db() as db:
        models.upsert_oauth_token(
            db,
            models.OAuthToken(
                id=None,
                user_id=_manager_user_id(),
                provider="zoom",
                access_token="zoom-access-token",
                refresh_token="zoom-refresh-token",
            ),
        )
        db.commit()


def _manager_user_id():
    with models.get_db() as db:
        user = db.execute(
            "SELECT id FROM users WHERE email = ?",
            ("andrew@nudge.local",),
        ).fetchone()
    return user["id"]


class _FakeResponse:
    def __init__(self, *, status_code=200, json_data=None, text=""):
        self.status_code = status_code
        self._json_data = json_data or {}
        self.text = text

    def json(self):
        return self._json_data
