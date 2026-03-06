# main/routes.py
# ─────────────────────────────────────────────────────────────────────────────
# Route handlers for all non-authentication pages:
#   GET       /user_dashboard
#   GET       /admin_dashboard
#   GET/POST  /profile
#
# All protected routes use the @login_required decorator from auth/helpers.py.
# ─────────────────────────────────────────────────────────────────────────────

import re  # Regex — used for password strength validation on the profile page

from flask import render_template, redirect, url_for, flash, session, request
from werkzeug.security import generate_password_hash, check_password_hash

from models import db, User, Order, OrderItem
from extensions import limiter
from auth.helpers import login_required
from auth.forms import ProfileForm
from main import main_bp


# ─────────────────────────────────────────────────────────────────────────────
# HOME PAGE  —  GET /   GET /home
# ─────────────────────────────────────────────────────────────────────────────

@main_bp.route('/')
@main_bp.route('/home')
@limiter.exempt
def home():
    """Public home / landing page."""
    return render_template('main/home.html')


@main_bp.route('/placeholder')
@limiter.exempt
def placeholder():
    """Generic placeholder page for features coming soon."""
    return render_template('main/placeholder.html')


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
# USER DASHBOARD  —  GET /user_dashboard
# ─────────────────────────────────────────────────────────────────────────────

@main_bp.route('/user_dashboard')
@login_required
def user_dashboard():
    """Standard user dashboard — shown to any logged-in, non-admin user."""
    return render_template('main/user_dashboard.html')


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

    return render_template('main/profile.html', form=form, error=error, user=user)


# ─────────────────────────────────────────────────────────────────────────────
# ACCOUNT DELETION  —  POST /account/delete
# Permanently removes the logged-in user's account and all their orders.
# Requires password confirmation so this can't be triggered by a stray link.
# ─────────────────────────────────────────────────────────────────────────────

@main_bp.route('/account/delete', methods=['POST'])
@login_required
def account_delete():
    """Permanently delete the current user's account and all their data."""
    user = User.query.get_or_404(session['user_id'])
    password = request.form.get('password', '')

    # Verify the user knows their own password before we destroy anything
    if not check_password_hash(user.password_hash, password):
        flash('Incorrect password. Your account was not deleted.', 'danger')
        return redirect(url_for('main.profile'))

    # Delete order items first (child FK), then orders (parent FK), then the user.
    # SQLite doesn't enforce FK cascades by default so we delete manually.
    for order in user.orders:
        for item in order.items:
            db.session.delete(item)
        db.session.delete(order)
    db.session.delete(user)
    db.session.commit()

    # Clear the session so the cookie no longer points to a deleted user
    session.clear()
    flash('Your account has been permanently deleted.', 'info')
    return redirect(url_for('auth.login'))

