from flask import Flask
from flask_socketio import SocketIO

from auth import login_manager

socketio = SocketIO()


def create_app():
    app = Flask(__name__)

    login_manager.init_app(app)

    # register blueprints: dashboard, review, upload, api
    # from routes.dashboard import bp as dashboard_bp
    # from routes.review import bp as review_bp
    # from routes.upload import bp as upload_bp
    # from routes.api import bp as api_bp

    socketio.init_app(app)

    return app


if __name__ == "__main__":
    app = create_app()
    socketio.run(app)
