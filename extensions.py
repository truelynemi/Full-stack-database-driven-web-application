# extensions.py
# ─────────────────────────────────────────────────────────────────────────────
# This file creates the Flask extension objects (csrf, limiter, mail) WITHOUT
# binding them to a specific app yet.
#
# Why do it this way?
#   Both app.py and auth.py need to use these extensions.
#   If we created them inside app.py, auth.py would have to import from app.py,
#   and app.py imports from auth.py — that's a "circular import" which crashes
#   Python.  By putting the extensions here, both files can import from this
#   neutral file with no circular dependency.
#
#   The actual app is connected later by calling  .init_app(app)  in app.py.
# ─────────────────────────────────────────────────────────────────────────────

from flask_wtf.csrf import CSRFProtect        # Protects forms from CSRF attacks
from flask_limiter import Limiter              # Rate-limits routes (brute-force protection)
from flask_limiter.util import get_remote_address  # Helper that returns the caller's IP address
from flask_mail import Mail                    # Sends emails (verification, password reset)

# Create the CSRF protection object.
# It will be attached to the app in app.py via csrf.init_app(app).
csrf = CSRFProtect()

# Create the rate limiter.
# get_remote_address tells the limiter to track limits per IP address.
limiter = Limiter(get_remote_address)

# Create the mail object.
# Gmail SMTP settings are configured in app.py and connected via mail.init_app(app).
mail = Mail()
