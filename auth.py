from functools import wraps

from flask import Blueprint, abort, redirect, render_template, request, url_for
from flask_login import (
    LoginManager,
    UserMixin,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from werkzeug.security import check_password_hash

from models import get_db, row_to_user

login_manager = LoginManager()
login_manager.login_view = "auth.login"

bp = Blueprint("auth", __name__, url_prefix="/auth")


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


def manager_required(view_func):
    @wraps(view_func)
    @login_required
    def wrapped_view(*args, **kwargs):
        if getattr(current_user, "role", None) != "manager":
            abort(403)
        return view_func(*args, **kwargs)

    return wrapped_view


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
                request.args.get("next") or url_for("dashboard.manager_dashboard")
            )
        return render_template("login.html", login_error="Invalid email or password"), 401

    return render_template("login.html")


@bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))
