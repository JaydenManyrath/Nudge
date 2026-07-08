from flask import Blueprint, abort

bp = Blueprint("api", __name__, url_prefix="/api")

SPRINT_2_STUB_MESSAGE = "Sprint 2 stub: API task mutations and polling are not wired yet."


@bp.route("/tasks/<int:task_id>/done", methods=["POST"])
def mark_done(task_id):
    abort(501, SPRINT_2_STUB_MESSAGE)


@bp.route("/tasks/<int:task_id>/blockers", methods=["POST"])
def add_blocker(task_id):
    abort(501, SPRINT_2_STUB_MESSAGE)


@bp.route("/jobs/<int:job_id>/status")
def job_status(job_id):
    abort(501, SPRINT_2_STUB_MESSAGE)


@bp.route("/notifications/badge")
def notification_badge():
    abort(501, SPRINT_2_STUB_MESSAGE)
