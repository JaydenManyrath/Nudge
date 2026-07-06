from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

from .user import User
from .meeting import Meeting
from .task import Task
from .comment import Comment
