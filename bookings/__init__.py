# bookings/__init__.py
# Creates the bookings Blueprint.
# Routes are imported after the Blueprint is defined to avoid circular imports.

from flask import Blueprint

bookings_bp = Blueprint('bookings', __name__)

from bookings import routes  # noqa — must be imported after bookings_bp is defined
