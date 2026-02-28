# models.py
# ─────────────────────────────────────────────────────────────────────────────
# This file defines the database structure using SQLAlchemy.
#
# SQLAlchemy is an "ORM" (Object-Relational Mapper) — it lets us work with
# database rows as Python objects instead of writing raw SQL.
#
# Example:
#   Instead of:  SELECT * FROM users WHERE email = 'bob@example.com'
#   We write:    User.query.filter_by(email='bob@example.com').first()
# ─────────────────────────────────────────────────────────────────────────────

from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

# Create the SQLAlchemy object.
# This is NOT connected to any app yet — that happens in app.py via db.init_app(app).
db = SQLAlchemy()


class User(db.Model):
    """
    Represents a single registered user.
    Each attribute decorated with db.Column becomes a column in the 'users' table.
    """

    __tablename__ = 'users'  # The actual name of the table in the database file

    # ── Primary key ────────────────────────────────────────────────────────
    # Every row needs a unique identifier.  SQLAlchemy auto-increments this.
    user_id = db.Column(db.Integer, primary_key=True)

    # ── Basic user info ─────────────────────────────────────────────────────
    # nullable=False means this column MUST have a value — it can't be left empty.
    full_name = db.Column(db.String(120), nullable=False)

    # unique=True means no two users can share the same email address.
    email = db.Column(db.String(120), unique=True, nullable=False)

    # We never store the raw password — only a one-way hash of it.
    # See generate_password_hash / check_password_hash in auth.py.
    password_hash = db.Column(db.String(256), nullable=False)

    # ── Role ────────────────────────────────────────────────────────────────
    # Controls which dashboard the user sees after login.
    # 'user' = standard access,  'admin' = admin dashboard access.
    # default='user' means new accounts are regular users unless changed manually.
    role = db.Column(db.String(20), nullable=False, default='user')

    # ── Join date ───────────────────────────────────────────────────────────
    # Automatically set to the current UTC time when a new user is created.
    # datetime.utcnow (without parentheses) passes the function itself so
    # SQLAlchemy calls it fresh each time — not once at import time.
    join_date = db.Column(db.DateTime, default=datetime.utcnow)

    # ── Email verification ──────────────────────────────────────────────────
    # Newly registered users start as is_verified=False.
    # They can't log in until they click the link in their verification email,
    # which sets this to True.
    is_verified = db.Column(db.Boolean, nullable=False, default=False)

    def __repr__(self):
        """How this object displays in logs and the Python shell."""
        return f'<User {self.email}>'
