from flask import Blueprint

bp = Blueprint("review", __name__, url_prefix="/review")


@bp.route("/")
def list_drafts():
    pass


@bp.route("/<int:task_id>/approve", methods=["POST"])
def approve(task_id):
    pass


@bp.route("/<int:task_id>/edit", methods=["POST"])
def edit(task_id):
    pass


@bp.route("/<int:task_id>/reject", methods=["POST"])
def reject(task_id):
    pass
