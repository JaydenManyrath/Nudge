import os

from flask import Flask, redirect, render_template, url_for
from flask_login import current_user

from auth import bp as auth_bp
from auth import login_manager
from extensions import socketio
from models import get_db


def _is_truthy(value):
    return str(value).strip().lower() not in {"", "0", "false", "no", "off"}


def _error_home():
    # A safe "get me out of here" destination based on who is signed in.
    if getattr(current_user, "is_authenticated", False):
        if getattr(current_user, "role", None) == "manager":
            return url_for("dashboard.manager_dashboard"), "Back to dashboard"
        return url_for("dashboard.employee_dashboard"), "Back to my tasks"
    return url_for("auth.login"), "Go to sign in"


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key")

    @app.get("/")
    def index():
        # Landing on the bare domain should go to the app, not 404.
        return redirect(url_for("auth.login"))

    @app.get("/healthz")
    def healthz():
        with get_db() as db:
            db.execute("SELECT 1").fetchone()
        return {"status": "ok"}

    @app.errorhandler(403)
    def forbidden(error):
        home_url, home_label = _error_home()
        return (
            render_template(
                "error.html",
                code=403,
                title="Access denied",
                message="You do not have permission to view that page. Some pages are limited to managers.",
                home_url=home_url,
                home_label=home_label,
            ),
            403,
        )

    @app.errorhandler(404)
    def not_found(error):
        home_url, home_label = _error_home()
        return (
            render_template(
                "error.html",
                code=404,
                title="Page not found",
                message="We could not find the page you were looking for.",
                home_url=home_url,
                home_label=home_label,
            ),
            404,
        )

    @app.errorhandler(500)
    def server_error(error):
        home_url, home_label = _error_home()
        return (
            render_template(
                "error.html",
                code=500,
                title="Something went wrong",
                message="An unexpected error occurred on our end. Please try again.",
                home_url=home_url,
                home_label=home_label,
            ),
            500,
        )

    @app.context_processor
    def inject_notifications():
        # Feeds the top-bar bell dropdown: the current user's overdue and
        # due-soon tasks (managers see everyone's, employees see their own).
        from datetime import date, timedelta

        if not getattr(current_user, "is_authenticated", False):
            return {"notifications": []}

        items = []
        try:
            with get_db() as db:
                params = ["pending", "blocked"]
                assignee_filter = ""
                if getattr(current_user, "role", None) != "manager":
                    assignee_filter = "AND tasks.assignee_id = ?"
                    params.append(int(current_user.id))
                rows = db.execute(
                    f"""
                    SELECT description, due_date, assignee_name
                    FROM tasks
                    WHERE status IN (?, ?) AND due_date IS NOT NULL {assignee_filter}
                    ORDER BY due_date ASC
                    """,
                    params,
                ).fetchall()

            today = date.today()
            soon = today + timedelta(days=2)
            for row in rows:
                try:
                    due = date.fromisoformat(row["due_date"])
                except (TypeError, ValueError):
                    continue
                if due < today:
                    items.append({"type": "overdue", "text": row["description"], "due": row["due_date"]})
                elif due <= soon:
                    items.append({"type": "due_soon", "text": row["description"], "due": row["due_date"]})
        except Exception:
            items = []

        return {"notifications": items}

    login_manager.init_app(app)

    from routes.api import bp as api_bp
    from routes.dashboard import bp as dashboard_bp
    from routes.review import bp as review_bp
    from routes.rtms_ingress import bp as rtms_ingress_bp
    from routes.upload import bp as upload_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(review_bp)
    app.register_blueprint(upload_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(rtms_ingress_bp)

    async_mode = os.environ.get("SOCKETIO_ASYNC_MODE")
    if async_mode:
        socketio.init_app(app, async_mode=async_mode)
    else:
        socketio.init_app(app)

    # Start the daily reminder sweep. Off by default under pytest (which sets
    # NUDGE_START_SCHEDULER=false) so tests don't spawn a background thread.
    if _is_truthy(os.environ.get("NUDGE_START_SCHEDULER", "true")):
        from scheduler import init_scheduler

        init_scheduler()

    return app


if __name__ == "__main__":
    app = create_app()
    socketio.run(app)
