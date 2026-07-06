from flask import Blueprint

bp = Blueprint("api", __name__, url_prefix="/api")


@bp.route("/tasks/<int:task_id>/done", methods=["POST"])
def mark_done(task_id):
    pass


@bp.route("/tasks/<int:task_id>/blockers", methods=["POST"])
def add_blocker(task_id):
    pass


@bp.route("/jobs/<int:job_id>/status")
def job_status(job_id):
    pass


@bp.route("/notifications/badge")
def notification_badge():
    pass
