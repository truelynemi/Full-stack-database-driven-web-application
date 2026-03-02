# main/__init__.py
# ─────────────────────────────────────────────────────────────────────────────
# This file turns the main/ folder into a Python package and defines the
# Blueprint for all non-authentication pages:
#   • About page (public)
#   • User dashboard
#   • Admin dashboard
#   • Profile page
#
# Routes here use url_for('main.user_dashboard') etc.
# ─────────────────────────────────────────────────────────────────────────────

from flask import Blueprint

# Create the Blueprint.  'main' is its registered name.
main_bp = Blueprint('main', __name__)

# Import routes AFTER creating main_bp to avoid a circular import.
from main import routes  # noqa: E402, F401
