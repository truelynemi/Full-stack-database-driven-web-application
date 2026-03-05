# app.py
# ─────────────────────────────────────────────────────────────────────────────
# Main entry point — kept intentionally lean.
# Responsibilities:
#   1. Create the Flask app and set configuration
#   2. Connect all extensions (database, CSRF, rate limiter, mail)
#   3. Register Blueprints (auth routes + main/dashboard routes)
#   4. Handle CSRF errors gracefully
#   5. Start the dev server when run directly with  python app.py
#
# Business logic lives in:
#   auth/     — login, register, email verification, password reset
#   main/     — dashboards, profile page, about page
# ─────────────────────────────────────────────────────────────────────────────

import os  # Used to read environment variables from the .env file
from datetime import timedelta  # Used to set the Remember Me session lifetime

from dotenv import load_dotenv  # Loads variables from .env into os.environ
load_dotenv()                   # Must be called before os.environ.get() reads anything

from flask import Flask, redirect, url_for, flash, request
from flask_wtf.csrf import CSRFError  # So we can handle CSRF errors gracefully

from models import db             # SQLAlchemy database object
from extensions import csrf, limiter, mail  # Extension objects from extensions.py
from auth import auth_bp          # Authentication Blueprint (login, register, etc.)
from main import main_bp          # Main Blueprint (dashboards, profile, about)
from shop import shop_bp          # Shop Blueprint (catalogue, cart, checkout, orders)


# ─────────────────────────────────────────────────────────────────────────────
# APP CREATION & CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────

app = Flask(__name__)  # Create the Flask application

# SECRET_KEY is used to sign cookies and tokens — keep it secret!
# We read it from the .env file; if it's not set, use a fallback for development.
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

# Tell SQLAlchemy where to store the database file (SQLite = a single local file)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'

# Disable a SQLAlchemy feature we don't need (saves memory/warnings)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# How long a "Remember Me" session lasts before the cookie expires.
# Only applies when session.permanent=True (set in auth/helpers.py set_user_session).
# Without this, Flask defaults to 31 days — setting it explicitly makes it clear.
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)

# ── Gmail SMTP settings ───────────────────────────────────────────────────
# Flask-Mail will use these to connect to Gmail and send emails.
# The actual address and App Password come from your .env file.
# To get a Gmail App Password:
#   1. Enable 2-Step Verification at myaccount.google.com/security
#   2. Go to myaccount.google.com/apppasswords → create one for "Mail"
app.config['MAIL_SERVER'] = 'smtp.gmail.com'   # Gmail's outgoing mail server
app.config['MAIL_PORT'] = 587                   # Port 587 = TLS/STARTTLS (secure)
app.config['MAIL_USE_TLS'] = True               # Encrypt the connection
app.config['MAIL_USERNAME'] = os.environ.get('GMAIL_ADDRESS')       # Your Gmail address
app.config['MAIL_PASSWORD'] = os.environ.get('GMAIL_APP_PASSWORD')  # Your Gmail App Password
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('GMAIL_ADDRESS') # "From" address on emails

# ── Stripe settings ───────────────────────────────────────────────────────────
# The publishable key is safe to expose in HTML (used by client-side Stripe.js if needed).
# The secret key must NEVER be exposed — it stays server-side only.
app.config['STRIPE_PUBLISHABLE_KEY'] = os.environ.get('STRIPE_PUBLISHABLE_KEY')


# ─────────────────────────────────────────────────────────────────────────────
# INITIALISE EXTENSIONS
# We created the extension objects in extensions.py without an app.
# Here we connect them to THIS app using init_app().
# ─────────────────────────────────────────────────────────────────────────────

db.init_app(app)       # Connect SQLAlchemy to our app (enables db.session, db.create_all, etc.)
csrf.init_app(app)     # Enable CSRF protection globally across all forms
limiter.init_app(app)  # Enable rate limiting (individual routes are limited in their blueprints)
mail.init_app(app)     # Connect Flask-Mail using the Gmail config above


# ─────────────────────────────────────────────────────────────────────────────
# REGISTER BLUEPRINTS
# ─────────────────────────────────────────────────────────────────────────────

app.register_blueprint(auth_bp)   # Auth routes: /login, /register, /logout, etc.
app.register_blueprint(main_bp)   # Main routes: /user_dashboard, /admin_dashboard, /profile, /about
app.register_blueprint(shop_bp)   # Shop routes: /shop, /cart, /checkout/*, /orders


# ─────────────────────────────────────────────────────────────────────────────
# CSRF ERROR HANDLER
# If a form is submitted with a missing or wrong CSRF token, show a friendly
# message instead of a raw error page.
# ─────────────────────────────────────────────────────────────────────────────

@app.context_processor
def inject_consent():
    """Pass the cookie_consent cookie value to all templates as 'consent'."""
    consent = request.cookies.get('cookie_consent')
    return dict(consent=consent)


@app.errorhandler(CSRFError)
def handle_csrf_error(e):
    flash('Your session has expired or the request was invalid. Please try again.', 'danger')
    # Send the user back to where they came from, or to /login if unknown
    return redirect(request.referrer or url_for('auth.login'))


# ─────────────────────────────────────────────────────────────────────────────
# ENTRY POINT
# This block only runs when you execute  python app.py  directly.
# It won't run if the file is imported as a module (e.g. by a test runner).
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    with app.app_context():
        # Create all database tables defined in models.py if they don't exist yet.
        # Safe to run every time — it skips tables that already exist.
        db.create_all()
    app.run(debug=True)  # debug=True enables auto-reload and detailed error pages
    