# app.py
# ─────────────────────────────────────────────────────────────────────────────
# This is the main entry point of the application.
# Its job is deliberately kept small:
#   1. Create the Flask app and configure it
#   2. Connect all the extensions (database, CSRF, rate limiter, mail)
#   3. Register the auth Blueprint (which handles all login/register/etc. routes)
#   4. Define the dashboard pages (the pages users land on after logging in)
#   5. Start the server when run directly with  python app.py
# ─────────────────────────────────────────────────────────────────────────────

import os  # Used to read environment variables from the .env file

from flask import Flask, render_template, redirect, url_for, flash, session, request
from flask_wtf.csrf import CSRFError  # So we can handle CSRF errors gracefully

from models import db, User        # SQLAlchemy database object + User model
from extensions import csrf, limiter, mail  # Extension objects from extensions.py
from auth import auth_bp, login_required, ProfileForm  # Blueprint, decorator, profile form
from werkzeug.security import generate_password_hash, check_password_hash  # Password handling
import re                                  # Regex — used for password strength validation


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

# ── Gmail SMTP settings ───────────────────────────────────────────────────
# Flask-Mail will use these to connect to Gmail and send emails.
# The actual address and App Password come from your .env file.
app.config['MAIL_SERVER'] = 'smtp.gmail.com'   # Gmail's outgoing mail server
app.config['MAIL_PORT'] = 587                   # Port 587 = TLS/STARTTLS (secure)
app.config['MAIL_USE_TLS'] = True               # Encrypt the connection
app.config['MAIL_USERNAME'] = os.environ.get('GMAIL_ADDRESS')       # Your Gmail address
app.config['MAIL_PASSWORD'] = os.environ.get('GMAIL_APP_PASSWORD')  # Your Gmail App Password
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('GMAIL_ADDRESS') # "From" address on emails


# ─────────────────────────────────────────────────────────────────────────────
# INITIALISE EXTENSIONS
# We created the extension objects in extensions.py without an app.
# Here we connect them to THIS app using init_app().
# ─────────────────────────────────────────────────────────────────────────────

db.init_app(app)       # Connect SQLAlchemy to our app (enables db.session, db.create_all, etc.)
csrf.init_app(app)     # Enable CSRF protection globally across all forms
limiter.init_app(app)  # Enable rate limiting (individual routes are limited in auth.py)
mail.init_app(app)     # Connect Flask-Mail using the Gmail config above


# ─────────────────────────────────────────────────────────────────────────────
# REGISTER BLUEPRINTS
# Blueprints are like plug-in modules.  Registering auth_bp adds all the routes
# defined in auth.py (/login, /register, /logout, etc.) to this app.
# ─────────────────────────────────────────────────────────────────────────────

app.register_blueprint(auth_bp)  # All routes in auth.py are now live


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
# ABOUT PAGE
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/about')
@limiter.exempt  # This page is public info — no need to rate-limit it
def about():
    return render_template('about.html')


# ─────────────────────────────────────────────────────────────────────────────
# DASHBOARD ROUTES
# These are the pages users land on after logging in.
# Both are protected by @login_required — unauthenticated users are redirected
# to /login before they can see any content.
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/user_dashboard')
@login_required  # Must be logged in to access this page
def user_dashboard():
    """Standard user dashboard — shown to any logged-in, non-admin user."""
    return render_template('user_dashboard.html')


@app.route('/admin_dashboard')
@login_required  # Must be logged in first...
def admin_dashboard():
    """Admin dashboard — only accessible to users with role='admin'."""
    if session.get('user_role') != 'admin':
        # Logged in but not an admin — redirect with a warning
        flash('You do not have permission to access that page.', 'danger')
        return redirect(url_for('user_dashboard'))
    return render_template('admin_dashboard.html')


# ─────────────────────────────────────────────────────────────────────────────
# PROFILE ROUTE
# Lets a logged-in user update their name and optionally change their password.
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/profile', methods=['GET', 'POST'])
@login_required  # Must be logged in — unauthenticated users go to /login
def profile():
    # Look up the current user in the database using their session ID
    user = User.query.get(session['user_id'])

    # Pre-fill first/last name by splitting the stored full_name on the first space
    # e.g. "John Smith" → first="John", last="Smith"
    name_parts = user.full_name.split(' ', 1)
    first = name_parts[0]
    last  = name_parts[1] if len(name_parts) > 1 else ''

    form = ProfileForm()
    error = None

    if form.validate_on_submit():
        # ── Update name ───────────────────────────────────────────────────
        new_first = form.first_name.data.strip()
        new_last  = form.last_name.data.strip()
        user.full_name = f"{new_first} {new_last}"

        # Update the session so the dashboard greeting reflects the new name immediately
        session['user_name'] = user.full_name

        # ── Optional password change ──────────────────────────────────────
        new_password = form.new_password.data
        if new_password:
            current_password     = form.current_password.data
            confirm_new_password = form.confirm_new_password.data

            # Step 1: Verify the user knows their current password
            if not current_password or not check_password_hash(user.password_hash, current_password):
                error = "Current password is incorrect."
            elif new_password != confirm_new_password:
                error = "New passwords do not match."
            elif len(new_password) < 8:
                error = "New password must be at least 8 characters long."
            elif not re.search(r"\d", new_password):
                error = "New password must include at least one number."
            elif not re.search(r"[A-Z]", new_password):
                error = "New password must include at least one uppercase letter."
            else:
                # All checks pass — hash and save the new password
                user.password_hash = generate_password_hash(new_password)

        if not error:
            db.session.commit()  # Save name (and password if changed) to the database
            flash("Profile updated successfully.", "success")
            return redirect(url_for('profile'))

    elif request.method == 'GET':
        # On a GET request, pre-fill the name fields with the current values
        form.first_name.data = first
        form.last_name.data  = last

    return render_template('profile.html', form=form, error=error)


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
