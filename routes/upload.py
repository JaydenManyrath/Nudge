from flask import Blueprint

bp = Blueprint("upload", __name__, url_prefix="/upload")


@bp.route("/", methods=["GET"])
def upload_form():
    pass


@bp.route("/", methods=["POST"])
def upload_transcript():
    pass
