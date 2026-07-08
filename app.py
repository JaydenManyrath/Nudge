import os

from flask import Flask

from auth import bp as auth_bp
from auth import login_manager
from extensions import socketio
from models import get_db


def _is_truthy(value):
    return str(value).strip().lower() not in {"", "0", "false", "no", "off"}


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key")

    @app.get("/healthz")
    def healthz():
        with get_db() as db:
            db.execute("SELECT 1").fetchone()
        return {"status": "ok"}

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
