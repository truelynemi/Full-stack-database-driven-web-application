# admin/__init__.py
# ─────────────────────────────────────────────────────────────────────────────
# Dedicated admin Blueprint.
# All admin routes live here — dashboard, products, services, slots, bookings.
# ─────────────────────────────────────────────────────────────────────────────

from flask import Blueprint

admin_bp = Blueprint('admin', __name__)

# Import route modules AFTER creating admin_bp to avoid circular imports.
from admin import dashboard  # noqa: E402, F401
from admin import products  # noqa: E402, F401
from admin import bookings  # noqa: E402, F401
