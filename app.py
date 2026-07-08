import os

from flask import Flask
from flask_socketio import SocketIO

from auth import bp as auth_bp
from auth import login_manager

socketio = SocketIO()


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key")

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

    return app


if __name__ == "__main__":
    app = create_app()
    socketio.run(app)
