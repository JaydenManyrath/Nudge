import json
import os
import secrets
from functools import wraps
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode, urlparse

import httpx
from flask import Blueprint, abort, redirect, render_template, request, session, url_for
from flask_login import (
    LoginManager,
    UserMixin,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from werkzeug.security import check_password_hash

from models import OAuthToken, get_db, row_to_user, upsert_oauth_token

login_manager = LoginManager()
login_manager.login_view = "auth.login"

bp = Blueprint("auth", __name__, url_prefix="/auth")

ZOOM_AUTHORIZE_URL = "https://zoom.us/oauth/authorize"
ZOOM_TOKEN_URL = "https://zoom.us/oauth/token"
DEFAULT_ZOOM_SCOPES = "meeting:read:meeting_transcript"
GOOGLE_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
DEFAULT_GOOGLE_CALENDAR_SCOPES = "https://www.googleapis.com/auth/calendar.events"


class User(UserMixin):
    def __init__(self, id, name, email, role):
        self.id = str(id)
        self.name = name
        self.email = email
        self.role = role


@login_manager.user_loader
def load_user(user_id):
    with get_db() as db:
        row = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    user = row_to_user(row)
    if user is None:
        return None
    return User(user.id, user.name, user.email, user.role)


def _safe_next(target):
    """Only allow same-site relative redirect targets (block open redirects)."""
    if not target:
        return None
    parsed = urlparse(target)
    if parsed.scheme or parsed.netloc:
        return None
    if not target.startswith("/") or target.startswith("//"):
        return None
    return target


def manager_required(view_func):
    @wraps(view_func)
    @login_required
    def wrapped_view(*args, **kwargs):
        if getattr(current_user, "role", None) != "manager":
            abort(403)
        return view_func(*args, **kwargs)

    return wrapped_view


def _public_base_url():
    value = os.environ.get("PUBLIC_BASE_URL") or os.environ.get("RENDER_EXTERNAL_URL")
    if value:
        return value.rstrip("/")

    hostname = os.environ.get("RENDER_EXTERNAL_HOSTNAME")
    if hostname:
        return f"https://{hostname.strip('/')}"

    vercel_hostname = os.environ.get("VERCEL_PROJECT_PRODUCTION_URL") or os.environ.get(
        "VERCEL_URL"
    )
    if vercel_hostname:
        return f"https://{vercel_hostname.strip('/')}"

    return None


def _external_url_for(endpoint):
    public_base_url = _public_base_url()
    if public_base_url:
        return f"{public_base_url}{url_for(endpoint)}"
    return url_for(endpoint, _external=True)


def zoom_redirect_uri():
    return os.environ.get("ZOOM_REDIRECT_URI") or _external_url_for(
        "auth.zoom_callback"
    )


def zoom_scopes():
    return os.environ.get("ZOOM_SCOPES", DEFAULT_ZOOM_SCOPES)


def google_redirect_uri():
    return os.environ.get("GOOGLE_REDIRECT_URI") or _external_url_for(
        "auth.google_callback"
    )


def google_calendar_scopes():
    return os.environ.get(
        "GOOGLE_CALENDAR_SCOPES",
        DEFAULT_GOOGLE_CALENDAR_SCOPES,
    )


def _zoom_client_config():
    client_id = os.environ.get("ZOOM_CLIENT_ID")
    client_secret = os.environ.get("ZOOM_CLIENT_SECRET")
    if not client_id or not client_secret:
        abort(500, description="Zoom OAuth client credentials are not configured.")
    return client_id, client_secret


def _google_client_config():
    client_id = os.environ.get("GOOGLE_CLIENT_ID")
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")
    if not client_id or not client_secret:
        abort(500, description="Google OAuth client credentials are not configured.")
    return client_id, client_secret


def _exchange_zoom_code(code):
    client_id, client_secret = _zoom_client_config()
    response = httpx.post(
        ZOOM_TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": zoom_redirect_uri(),
        },
        auth=(client_id, client_secret),
        timeout=10,
    )
    response.raise_for_status()
    return response.json()


def _exchange_google_code(code):
    client_id, client_secret = _google_client_config()
    response = httpx.post(
        GOOGLE_TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": google_redirect_uri(),
        },
        timeout=10,
    )
    response.raise_for_status()
    return response.json()


def _token_expires_at(token_data):
    expires_in = token_data.get("expires_in")
    if expires_in is None:
        return None
    try:
        seconds = int(expires_in)
    except (TypeError, ValueError):
        return None
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=seconds)
    return expires_at.isoformat()


def _store_zoom_token(user_id, token_data):
    access_token = token_data.get("access_token")
    if not access_token:
        abort(502, description="Zoom token response did not include an access token.")

    token = OAuthToken(
        id=None,
        user_id=int(user_id),
        provider="zoom",
        access_token=access_token,
        refresh_token=token_data.get("refresh_token"),
        token_type=token_data.get("token_type"),
        scope=token_data.get("scope") or zoom_scopes(),
        expires_at=_token_expires_at(token_data),
        raw_token=json.dumps(token_data, sort_keys=True),
    )
    with get_db() as db:
        upsert_oauth_token(db, token)


def _store_google_token(user_id, token_data):
    access_token = token_data.get("access_token")
    if not access_token:
        abort(502, description="Google token response did not include an access token.")

    token = OAuthToken(
        id=None,
        user_id=int(user_id),
        provider="google",
        access_token=access_token,
        refresh_token=token_data.get("refresh_token"),
        token_type=token_data.get("token_type"),
        scope=token_data.get("scope") or google_calendar_scopes(),
        expires_at=_token_expires_at(token_data),
        raw_token=json.dumps(token_data, sort_keys=True),
    )
    with get_db() as db:
        upsert_oauth_token(db, token)


def _demo_enabled():
    return os.environ.get("NUDGE_DEMO_MODE", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


# One-click demo accounts (no password) — only reachable when NUDGE_DEMO_MODE is on.
DEMO_ACCOUNTS = {"manager": "maya@nudge.local", "employee": "marco@nudge.local"}


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        with get_db() as db:
            row = db.execute(
                "SELECT * FROM users WHERE lower(email) = ?",
                (email,),
            ).fetchone()
        user = row_to_user(row)
        if (
            user is not None
            and user.password_hash
            and check_password_hash(user.password_hash, password)
        ):
            login_user(User(user.id, user.name, user.email, user.role))
            return redirect(
                _safe_next(request.args.get("next"))
                or url_for("dashboard.manager_dashboard")
            )
        return (
            render_template(
                "login.html",
                login_error="Invalid email or password",
                demo_enabled=_demo_enabled(),
            ),
            401,
        )

    return render_template("login.html", demo_enabled=_demo_enabled())


@bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))


@bp.route("/demo/<role>")
def demo_login(role):
    # Passwordless one-click access for demos. Gated by NUDGE_DEMO_MODE so it
    # is unavailable unless explicitly enabled. Real login + RBAC still apply.
    if not _demo_enabled():
        abort(404)
    email = DEMO_ACCOUNTS.get(role)
    if email is None:
        abort(404)
    with get_db() as db:
        row = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    user = row_to_user(row)
    if user is None:
        abort(404)
    login_user(User(user.id, user.name, user.email, user.role))
    if user.role == "manager":
        return redirect(url_for("dashboard.manager_dashboard"))
    return redirect(url_for("dashboard.employee_dashboard"))


@bp.route("/zoom/connect")
@manager_required
def zoom_connect():
    client_id, _client_secret = _zoom_client_config()
    state = secrets.token_urlsafe(32)
    session["zoom_oauth_state"] = state

    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": zoom_redirect_uri(),
        "scope": zoom_scopes(),
        "state": state,
    }
    return redirect(f"{ZOOM_AUTHORIZE_URL}?{urlencode(params)}")


@bp.route("/zoom/callback")
@manager_required
def zoom_callback():
    error = request.args.get("error")
    if error:
        return redirect(
            url_for("dashboard.manager_dashboard", zoom_error=error),
        )

    expected_state = session.pop("zoom_oauth_state", None)
    if not expected_state or request.args.get("state") != expected_state:
        abort(400, description="Invalid Zoom OAuth state.")

    code = request.args.get("code")
    if not code:
        abort(400, description="Missing Zoom OAuth authorization code.")

    token_data = _exchange_zoom_code(code)
    _store_zoom_token(current_user.id, token_data)
    return redirect(url_for("dashboard.manager_dashboard"))


@bp.route("/google/connect")
@manager_required
def google_connect():
    client_id, _client_secret = _google_client_config()
    state = secrets.token_urlsafe(32)
    session["google_oauth_state"] = state

    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": google_redirect_uri(),
        "scope": google_calendar_scopes(),
        "state": state,
        "access_type": "offline",
        "prompt": "consent",
    }
    return redirect(f"{GOOGLE_AUTHORIZE_URL}?{urlencode(params)}")


@bp.route("/google/callback")
@manager_required
def google_callback():
    error = request.args.get("error")
    if error:
        return redirect(
            url_for("dashboard.manager_dashboard", calendar_error=error),
        )

    expected_state = session.pop("google_oauth_state", None)
    if not expected_state or request.args.get("state") != expected_state:
        abort(400, description="Invalid Google OAuth state.")

    code = request.args.get("code")
    if not code:
        abort(400, description="Missing Google OAuth authorization code.")

    token_data = _exchange_google_code(code)
    _store_google_token(current_user.id, token_data)
    return redirect(url_for("dashboard.manager_dashboard"))
