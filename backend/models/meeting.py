from . import db


class Meeting(db.Model):
    __tablename__ = "meetings"

    id = db.Column(db.Integer, primary_key=True)
    transcript = db.Column(db.Text)
    status = db.Column(db.String, nullable=False, default="pending")
    created_at = db.Column(db.DateTime, server_default=db.func.now())
