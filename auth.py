from flask_login import LoginManager, UserMixin

login_manager = LoginManager()


class User(UserMixin):
    pass


@login_manager.user_loader
def load_user(user_id):
    pass


def manager_required(view_func):
    pass
