from urllib.parse import parse_qs, urlparse

import auth
import models


def test_login_required_routes_redirect_when_unauthenticated(client):
    response = client.get("/review/")

    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]


def test_zoom_oauth_connect_redirects_to_zoom(client, login_as_user, monkeypatch):
    login_as_user("maya@nudge.local")
    monkeypatch.setenv("ZOOM_CLIENT_ID", "zoom-client")
    monkeypatch.setenv("ZOOM_CLIENT_SECRET", "zoom-secret")
    monkeypatch.setenv(
        "ZOOM_REDIRECT_URI",
        "https://nudge.example.com/auth/zoom/callback",
    )
    monkeypatch.setenv("ZOOM_SCOPES", "meeting:read:meeting_transcript")

    response = client.get("/auth/zoom/connect")

    assert response.status_code == 302
    location = response.headers["Location"]
    parsed = urlparse(location)
    query = parse_qs(parsed.query)
    assert f"{parsed.scheme}://{parsed.netloc}{parsed.path}" == auth.ZOOM_AUTHORIZE_URL
    assert query["response_type"] == ["code"]
    assert query["client_id"] == ["zoom-client"]
    assert query["redirect_uri"] == ["https://nudge.example.com/auth/zoom/callback"]
    assert query["scope"] == ["meeting:read:meeting_transcript"]
    assert query["state"][0]

    with client.session_transaction() as session:
        assert session["zoom_oauth_state"] == query["state"][0]


def test_zoom_oauth_callback_stores_token(client, login_as_user, monkeypatch):
    login_as_user("maya@nudge.local")
    monkeypatch.setenv("ZOOM_CLIENT_ID", "zoom-client")
    monkeypatch.setenv("ZOOM_CLIENT_SECRET", "zoom-secret")
    monkeypatch.setenv("ZOOM_SCOPES", "meeting:read:meeting_transcript")
    monkeypatch.setattr(
        auth,
        "_exchange_zoom_code",
        lambda code: {
            "access_token": "zoom-access-token",
            "refresh_token": "zoom-refresh-token",
            "token_type": "bearer",
            "scope": "meeting:read:meeting_transcript",
            "expires_in": 3600,
        },
    )
    with client.session_transaction() as session:
        session["zoom_oauth_state"] = "known-state"

    response = client.get("/auth/zoom/callback?code=abc123&state=known-state")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/dashboard/manager")
    with models.get_db() as db:
        user = db.execute(
            "SELECT id FROM users WHERE email = ?",
            ("maya@nudge.local",),
        ).fetchone()
        token = models.get_oauth_token(
            db,
            user_id=user["id"],
            provider="zoom",
        )
    assert token is not None
    assert token.access_token == "zoom-access-token"
    assert token.refresh_token == "zoom-refresh-token"
    assert token.scope == "meeting:read:meeting_transcript"
    assert token.expires_at is not None


def test_zoom_oauth_state_mismatch_is_rejected(client, login_as_user):
    login_as_user("maya@nudge.local")
    with client.session_transaction() as session:
        session["zoom_oauth_state"] = "known-state"

    response = client.get("/auth/zoom/callback?code=abc123&state=wrong-state")

    assert response.status_code == 400


def test_zoom_redirect_uri_uses_render_external_url(client, monkeypatch):
    monkeypatch.delenv("ZOOM_REDIRECT_URI", raising=False)
    monkeypatch.setenv("RENDER_EXTERNAL_URL", "https://nudge.onrender.com/")

    with client.application.test_request_context():
        redirect_uri = auth.zoom_redirect_uri()

    assert redirect_uri == "https://nudge.onrender.com/auth/zoom/callback"


def test_google_oauth_connect_redirects_to_google(client, login_as_user, monkeypatch):
    login_as_user("maya@nudge.local")
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "google-client")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "google-secret")
    monkeypatch.setenv(
        "GOOGLE_REDIRECT_URI",
        "https://nudge.example.com/auth/google/callback",
    )
    monkeypatch.setenv(
        "GOOGLE_CALENDAR_SCOPES",
        "https://www.googleapis.com/auth/calendar.events",
    )

    response = client.get("/auth/google/connect")

    assert response.status_code == 302
    location = response.headers["Location"]
    parsed = urlparse(location)
    query = parse_qs(parsed.query)
    assert f"{parsed.scheme}://{parsed.netloc}{parsed.path}" == auth.GOOGLE_AUTHORIZE_URL
    assert query["response_type"] == ["code"]
    assert query["client_id"] == ["google-client"]
    assert query["redirect_uri"] == ["https://nudge.example.com/auth/google/callback"]
    assert query["scope"] == ["https://www.googleapis.com/auth/calendar.events"]
    assert query["access_type"] == ["offline"]
    assert query["prompt"] == ["consent"]
    assert query["state"][0]

    with client.session_transaction() as session:
        assert session["google_oauth_state"] == query["state"][0]


def test_google_oauth_callback_stores_token(client, login_as_user, monkeypatch):
    login_as_user("maya@nudge.local")
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "google-client")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "google-secret")
    monkeypatch.setenv(
        "GOOGLE_CALENDAR_SCOPES",
        "https://www.googleapis.com/auth/calendar.events",
    )
    monkeypatch.setattr(
        auth,
        "_exchange_google_code",
        lambda code: {
            "access_token": "google-access-token",
            "refresh_token": "google-refresh-token",
            "token_type": "Bearer",
            "scope": "https://www.googleapis.com/auth/calendar.events",
            "expires_in": 3600,
        },
    )
    with client.session_transaction() as session:
        session["google_oauth_state"] = "known-state"

    response = client.get("/auth/google/callback?code=abc123&state=known-state")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/dashboard/manager")
    with models.get_db() as db:
        user = db.execute(
            "SELECT id FROM users WHERE email = ?",
            ("maya@nudge.local",),
        ).fetchone()
        token = models.get_oauth_token(
            db,
            user_id=user["id"],
            provider="google",
        )
    assert token is not None
    assert token.access_token == "google-access-token"
    assert token.refresh_token == "google-refresh-token"
    assert token.scope == "https://www.googleapis.com/auth/calendar.events"
    assert token.expires_at is not None


def test_google_oauth_state_mismatch_is_rejected(client, login_as_user):
    login_as_user("maya@nudge.local")
    with client.session_transaction() as session:
        session["google_oauth_state"] = "known-state"

    response = client.get("/auth/google/callback?code=abc123&state=wrong-state")

    assert response.status_code == 400


def test_google_redirect_uri_uses_public_base_url(client, monkeypatch):
    monkeypatch.delenv("GOOGLE_REDIRECT_URI", raising=False)
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://nudge.example.com/")

    with client.application.test_request_context():
        redirect_uri = auth.google_redirect_uri()

    assert redirect_uri == "https://nudge.example.com/auth/google/callback"
