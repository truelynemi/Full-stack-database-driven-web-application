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

    # Relationship to orders — lets us do user.orders to get all their orders
    orders = db.relationship('Order', backref='user', lazy=True)

    def __repr__(self):
        """How this object displays in logs and the Python shell."""
        return f'<User {self.email}>'


# ─────────────────────────────────────────────────────────────────────────────
# SHOP MODELS
# ─────────────────────────────────────────────────────────────────────────────

class Product(db.Model):
    """A product available for purchase in the shop."""
    __tablename__ = 'products'

    id          = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=False)
    # Price stored in pence/cents to avoid floating-point issues. e.g. 999 = £9.99
    price       = db.Column(db.Integer, nullable=False)
    image_url   = db.Column(db.String(300), nullable=True)
    is_active   = db.Column(db.Boolean, default=True, nullable=False)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

    items = db.relationship('OrderItem', backref='product', lazy=True)

    def __repr__(self):
        return f'<Product {self.name}>'


class Order(db.Model):
    """A completed (or pending) purchase by a user."""
    __tablename__ = 'orders'

    id                         = db.Column(db.Integer, primary_key=True)
    user_id                    = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False)
    stripe_checkout_session_id = db.Column(db.String(200), unique=True)
    # Total in pence/cents, e.g. 1998 = £19.98
    amount_total               = db.Column(db.Integer, nullable=False)
    # 'pending' → created, 'paid' → Stripe confirmed payment, 'failed' → error
    status                     = db.Column(db.String(20), default='pending', nullable=False)
    created_at                 = db.Column(db.DateTime, default=datetime.utcnow)

    items = db.relationship('OrderItem', backref='order', lazy=True)

    def __repr__(self):
        return f'<Order {self.id} status={self.status}>'


class OrderItem(db.Model):
    """One line item within an Order (which product, how many, at what price)."""
    __tablename__ = 'order_items'

    id         = db.Column(db.Integer, primary_key=True)
    order_id   = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    quantity   = db.Column(db.Integer, nullable=False)
    # Snapshot of price at the moment of purchase so historical orders stay accurate
    unit_price = db.Column(db.Integer, nullable=False)

    def __repr__(self):
        return f'<OrderItem order={self.order_id} product={self.product_id} qty={self.quantity}>'
