from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'

    user_id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True)   # nullable for Twitter OAuth (no email guaranteed)
    password_hash = db.Column(db.String(256), nullable=True)        # nullable for OAuth users (no password)
    role = db.Column(db.String(20), nullable=False, default='user')
    join_date = db.Column(db.DateTime, default=datetime.utcnow)

    # Email verification
    is_verified = db.Column(db.Boolean, nullable=False, default=False)

    # OAuth (Google / Twitter)
    oauth_provider = db.Column(db.String(20), nullable=True)   # 'google', 'twitter', or None
    oauth_id = db.Column(db.String(100), nullable=True)        # provider's user ID

    def __repr__(self):
        return f'<User {self.email or self.oauth_id}>'
