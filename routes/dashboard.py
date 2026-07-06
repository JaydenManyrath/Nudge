from flask import Blueprint

bp = Blueprint("dashboard", __name__, url_prefix="/dashboard")


@bp.route("/manager")
def manager_dashboard():
    pass


@bp.route("/employee")
def employee_dashboard():
    pass
