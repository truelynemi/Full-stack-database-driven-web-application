# main/routes.py
# ─────────────────────────────────────────────────────────────────────────────
# Route handlers for all non-authentication pages:
#   GET       /about
#   GET       /user_dashboard
#   GET       /admin_dashboard
#   GET/POST  /profile
#
# All protected routes use the @login_required decorator from auth/helpers.py.
# ─────────────────────────────────────────────────────────────────────────────

import re  # Regex — used for password strength validation on the profile page

from flask import render_template, redirect, url_for, flash, session, request
from werkzeug.security import generate_password_hash, check_password_hash

from models import db, User
from extensions import limiter
from auth.helpers import login_required
from auth.forms import ProfileForm
from main import main_bp


# ─────────────────────────────────────────────────────────────────────────────
# ABOUT PAGE  —  GET /about
# ─────────────────────────────────────────────────────────────────────────────

@main_bp.route('/about')
@limiter.exempt  # This page is public info — no need to rate-limit it
def about():
    """Public about page — no login required."""
    return render_template('main/about.html')


@main_bp.route('/privacy')
@limiter.exempt
def privacy():
    """Public privacy policy page."""
    return render_template('main/privacy.html')


@main_bp.route('/terms')
@limiter.exempt
def terms():
    """Public terms of service page."""
    return render_template('main/terms.html')


# ─────────────────────────────────────────────────────────────────────────────
# DASHBOARD ROUTES
# These are the pages users land on after logging in.
# Both are protected by @login_required — unauthenticated users are redirected
# to /login before they can see any content.
# ─────────────────────────────────────────────────────────────────────────────

@main_bp.route('/user_dashboard')
@login_required  # Must be logged in to access this page
def user_dashboard():
    """Standard user dashboard — shown to any logged-in, non-admin user."""
    return render_template('main/user_dashboard.html')


@main_bp.route('/admin_dashboard')
@login_required  # Must be logged in first...
def admin_dashboard():
    """Admin dashboard — only accessible to users with role='admin'."""
    if session.get('user_role') != 'admin':
        # Logged in but not an admin — redirect with a warning
        flash('You do not have permission to access that page.', 'danger')
        return redirect(url_for('main.user_dashboard'))
    return render_template('main/admin_dashboard.html')


# ─────────────────────────────────────────────────────────────────────────────
# PROFILE ROUTE  —  GET/POST /profile
# Lets a logged-in user update their name and optionally change their password.
# ─────────────────────────────────────────────────────────────────────────────

@main_bp.route('/profile', methods=['GET', 'POST'])
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
            return redirect(url_for('main.profile'))

    elif request.method == 'GET':
        # On a GET request, pre-fill the name fields with the current values
        form.first_name.data = first
        form.last_name.data  = last

    return render_template('main/profile.html', form=form, error=error)
