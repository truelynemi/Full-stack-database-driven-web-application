# auth/__init__.py
# ─────────────────────────────────────────────────────────────────────────────
# This file turns the auth/ folder into a Python package and defines the
# Blueprint object that Flask uses to group all authentication routes together.
#
# The import at the bottom loads the routes module — this registers all the
# route functions (@auth_bp.route(...)) with the blueprint automatically.
# ─────────────────────────────────────────────────────────────────────────────

from flask import Blueprint

# Create the Blueprint.  'auth' is its registered name — used in url_for()
# calls like url_for('auth.login') to distinguish from other blueprints.
auth_bp = Blueprint('auth', __name__)

# Import routes AFTER creating auth_bp to avoid a circular import.
# (routes.py needs auth_bp to already exist when it runs @auth_bp.route())
from auth import routes  # noqa: E402, F401
