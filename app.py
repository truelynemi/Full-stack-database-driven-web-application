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

from dotenv import load_dotenv  # Loads variables from .env into os.environ
load_dotenv()                   # Must be called before os.environ.get() reads anything

from flask import Flask, redirect, url_for, flash, request
from flask_wtf.csrf import CSRFError  # So we can handle CSRF errors gracefully

from models import db             # SQLAlchemy database object
from extensions import csrf, limiter, mail  # Extension objects from extensions.py
from auth import auth_bp          # Authentication Blueprint (login, register, etc.)
from main import main_bp          # Main Blueprint (dashboards, profile, about)


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

# ── Outlook SMTP settings ─────────────────────────────────────────────────
# Flask-Mail will use these to connect to Outlook and send emails.
# The actual address and password come from your .env file.
# If you have 2FA enabled on your Microsoft account, generate an App Password at:
#   https://account.microsoft.com/security → Advanced security → App passwords
app.config['MAIL_SERVER'] = 'smtp.office365.com'  # Outlook/Office 365 outgoing mail server
app.config['MAIL_PORT'] = 587                      # Port 587 = TLS/STARTTLS (secure)
app.config['MAIL_USE_TLS'] = True                  # Encrypt the connection
app.config['MAIL_USERNAME'] = os.environ.get('OUTLOOK_ADDRESS')       # Your Outlook address
app.config['MAIL_PASSWORD'] = os.environ.get('OUTLOOK_PASSWORD')      # Your Outlook password
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('OUTLOOK_ADDRESS') # "From" address on emails


# ─────────────────────────────────────────────────────────────────────────────
# INITIALISE EXTENSIONS
# We created the extension objects in extensions.py without an app.
# Here we connect them to THIS app using init_app().
# ─────────────────────────────────────────────────────────────────────────────

db.init_app(app)       # Connect SQLAlchemy to our app (enables db.session, db.create_all, etc.)
csrf.init_app(app)     # Enable CSRF protection globally across all forms
limiter.init_app(app)  # Enable rate limiting (individual routes are limited in their blueprints)
mail.init_app(app)     # Connect Flask-Mail using the Outlook config above


# ─────────────────────────────────────────────────────────────────────────────
# REGISTER BLUEPRINTS
# ─────────────────────────────────────────────────────────────────────────────

app.register_blueprint(auth_bp)  # Auth routes: /login, /register, /logout, etc.
app.register_blueprint(main_bp)  # Main routes: /user_dashboard, /admin_dashboard, /profile, /about


# ─────────────────────────────────────────────────────────────────────────────
# CSRF ERROR HANDLER
# If a form is submitted with a missing or wrong CSRF token, show a friendly
# message instead of a raw error page.
# ─────────────────────────────────────────────────────────────────────────────

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
