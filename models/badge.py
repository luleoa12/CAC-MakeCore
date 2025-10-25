from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Badge(db.Model):
    __tablename__ = 'badge'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False)
    description = db.Column(db.String(256))
    image_path = db.Column(db.String(256))
    unobtained_image_path = db.Column(db.String(256))
    requirement_type = db.Column(db.String(64))  # e.g., 'comments', 'projects', 'upvotes'
    requirement_value = db.Column(db.Integer)    # e.g., 5, 15, 10, etc.

class UserBadge(db.Model):
    __tablename__ = 'user_badge'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    badge_id = db.Column(db.Integer, db.ForeignKey('badge.id'))
    date_awarded = db.Column(db.DateTime, default=datetime.utcnow)
    badge = db.relationship('Badge', backref='user_badges')
