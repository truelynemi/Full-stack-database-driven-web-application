# auth/routes.py
# ─────────────────────────────────────────────────────────────────────────────
# All authentication route handlers.
# Each function is decorated with @auth_bp.route() to register it with the
# auth Blueprint defined in auth/__init__.py.
#
# Routes handled here:
#   GET/POST  /login
#   GET       /logout
#   GET/POST  /register
#   GET       /verify-pending
#   GET       /verify/<token>
#   GET/POST  /resend-verification
#   GET/POST  /forgot-password
#   GET/POST  /reset-password/<token>
# ─────────────────────────────────────────────────────────────────────────────

import re  # Regular expressions — used to validate password strength

from flask import render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import SignatureExpired, BadSignature

from models import db, User
from extensions import limiter
from auth import auth_bp
from auth.forms import LoginForm, RegistrationForm, ForgotPasswordForm, ResetPasswordForm
from auth.helpers import (
    verify_token, send_verification_email, send_password_reset_email,
    set_user_session, redirect_to_dashboard
)


# ─────────────────────────────────────────────────────────────────────────────
# LOGIN ROUTE  —  GET /login  and  POST /login
# ─────────────────────────────────────────────────────────────────────────────

@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute")  # Block brute-force: max 5 login attempts per minute per IP
def login():
    # If the user is already logged in, skip the form and send them to their dashboard
    if 'user_id' in session:
        return redirect_to_dashboard(session.get('user_role'))

    error = None       # Will hold any error message to show in the template
    form = LoginForm()

    if request.method == 'POST':
        if form.validate_on_submit():  # Checks CSRF token + WTForms validators
            email = form.email.data.strip().lower()  # Normalise email (trim spaces, lowercase)
            password = form.password.data

            if not email or not password:
                error = "Please enter both email and password."
            else:
                # Look up user by email in the database
                user = User.query.filter_by(email=email).first()

                if user is None or user.password_hash is None:
                    # User doesn't exist — same vague error to prevent email enumeration
                    error = "Incorrect email or password. Please try again."
                elif not check_password_hash(user.password_hash, password):
                    # check_password_hash compares the input against the stored hash securely
                    error = "Incorrect email or password. Please try again."
                elif not user.is_verified:
                    # Account exists and password is correct but email not yet verified
                    error = "Please verify your email before logging in. Check your inbox or resend below."
                else:
                    # Everything checks out — log the user in
                    set_user_session(user, remember=form.remember_me.data)
                    flash(f"Welcome back, {user.full_name}!", "success")
                    return redirect_to_dashboard(user.role)
        else:
            # validate_on_submit() failed — most likely the CSRF token was missing or wrong
            flash('CSRF Token Missing or Invalid!', 'danger')

    # Render the login form (on GET, or if there was a validation error)
    return render_template('auth/login.html', error=error, form=form)


# ─────────────────────────────────────────────────────────────────────────────
# LOGOUT ROUTE  —  GET /logout
# ─────────────────────────────────────────────────────────────────────────────

@auth_bp.route('/logout')
def logout():
    """Clear the session (log the user out) and redirect to the login page."""
    name = session.get('user_name', 'User')
    session.clear()  # Wipes all session data — user is now anonymous
    flash(f"Goodbye, {name}! You have been logged out.", "info")
    return redirect(url_for('auth.login'))


# ─────────────────────────────────────────────────────────────────────────────
# REGISTRATION ROUTE  —  GET /register  and  POST /register
# ─────────────────────────────────────────────────────────────────────────────

@auth_bp.route('/register', methods=['GET', 'POST'])
@limiter.limit("5 per minute")  # Prevent mass account creation
def register():
    # Already logged in? No need to register again
    if 'user_id' in session:
        return redirect(url_for('main.user_dashboard'))

    error = None
    form = RegistrationForm()

    if request.method == 'POST':
        if form.validate_on_submit():
            # Strip whitespace and normalise the email to lowercase
            first_name = form.first_name.data.strip()
            last_name = form.last_name.data.strip()
            email = form.email.data.strip().lower()
            password = form.password.data
            confirm_password = form.confirm_password.data

            # ── Server-side validation chain ──────────────────────────────
            # Each check returns an error message; we stop at the first failure.

            if not first_name or not last_name or not email or not password or not confirm_password:
                error = "Please fill in all required fields."

            # Regex check: must look like a real email address
            elif not re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", email):
                error = "Please provide a valid email address."

            elif password != confirm_password:
                error = "Passwords do not match."

            elif len(password) < 8:
                error = "Password must be at least 8 characters long."

            # re.search looks for at least one digit anywhere in the password
            elif not re.search(r"\d", password):
                error = "Password must include at least one number."

            # re.search looks for at least one uppercase letter
            elif not re.search(r"[A-Z]", password):
                error = "Password must include at least one uppercase letter."

            else:
                # Check the database — is this email already taken?
                existing_user = User.query.filter_by(email=email).first()
                if existing_user:
                    error = "An account with that email already exists."

            # ── Create the account if no errors ──────────────────────────
            if not error:
                full_name = f"{first_name} {last_name}"

                new_user = User(
                    full_name=full_name,
                    email=email,
                    # generate_password_hash creates a secure one-way hash — the raw
                    # password is never stored in the database
                    password_hash=generate_password_hash(password),
                    is_verified=False  # Account is inactive until email is clicked
                )
                db.session.add(new_user)    # Stage the new row
                db.session.commit()         # Write it to the database file

                # Try to send the verification email
                try:
                    send_verification_email(email)
                    flash("Account created! Please check your email to verify your account.", "success")
                except Exception:
                    # Email failed (e.g. bad credentials) but account was created — don't crash
                    flash("Account created but we couldn't send the verification email. Contact support.", "warning")

                return redirect(url_for('auth.verify_pending'))
        else:
            flash('CSRF Token Missing or Invalid!', 'danger')

    return render_template('auth/registration.html', error=error, form=form)


# ─────────────────────────────────────────────────────────────────────────────
# EMAIL VERIFICATION ROUTES
# ─────────────────────────────────────────────────────────────────────────────

@auth_bp.route('/verify-pending')
def verify_pending():
    """Simple page shown after registration: 'Check your inbox!'"""
    return render_template('auth/verify_pending.html')


@auth_bp.route('/verify/<token>')
def verify_email(token):
    """
    The user clicks the link in their email.  The URL contains a signed token.
    We decode it to get their email, find them in the DB, and mark them verified.
    """
    try:
        email = verify_token(token, salt='email-verify')
    except SignatureExpired:
        flash('That verification link has expired. Please register again or request a new link.', 'danger')
        return redirect(url_for('auth.login'))
    except BadSignature:
        # Token was tampered with or just invalid
        flash('That verification link is invalid.', 'danger')
        return redirect(url_for('auth.login'))

    user = User.query.filter_by(email=email).first()
    if user is None:
        flash('Account not found.', 'danger')
        return redirect(url_for('auth.login'))

    if user.is_verified:
        flash('Your email is already verified. You can log in.', 'info')
    else:
        user.is_verified = True
        db.session.commit()
        flash('Email verified! You can now log in.', 'success')

    return redirect(url_for('auth.login'))


@auth_bp.route('/resend-verification', methods=['GET', 'POST'])
@limiter.limit("3 per hour")  # Prevent spam — max 3 resend requests per hour per IP
def resend_verification():
    """Let a user request a fresh verification email if their old link expired."""
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        user = User.query.filter_by(email=email).first()

        # Always show the same message regardless of whether the email exists.
        # This prevents attackers from figuring out which emails are registered
        # (called "email enumeration").
        flash('If that email exists and is unverified, a new link has been sent.', 'info')

        if user and not user.is_verified:
            try:
                send_verification_email(email)
            except Exception:
                pass  # Fail silently — the flash message has already been shown

        return redirect(url_for('auth.login'))

    return render_template('auth/resend_verification.html')


# ─────────────────────────────────────────────────────────────────────────────
# FORGOT PASSWORD ROUTES
# ─────────────────────────────────────────────────────────────────────────────

@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
@limiter.limit("5 per hour")  # Prevent reset-link spam
def forgot_password():
    """Show a form asking for the user's email, then send them a reset link."""
    form = ForgotPasswordForm()

    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        user = User.query.filter_by(email=email).first()

        # Same anti-enumeration trick as resend_verification — vague message always
        flash('If that email is registered, a password reset link has been sent.', 'info')

        # Only send the email if the user exists and has a password
        if user and user.password_hash:
            try:
                send_password_reset_email(email)
            except Exception:
                pass

        return redirect(url_for('auth.login'))

    return render_template('auth/forgot_password.html', form=form)


@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    """
    The user clicks the reset link in their email.
    We verify the token, then let them choose a new password.
    """
    try:
        email = verify_token(token, salt='password-reset')
    except SignatureExpired:
        flash('That password reset link has expired. Please request a new one.', 'danger')
        return redirect(url_for('auth.forgot_password'))
    except BadSignature:
        flash('That password reset link is invalid.', 'danger')
        return redirect(url_for('auth.forgot_password'))

    user = User.query.filter_by(email=email).first()
    if user is None:
        flash('Account not found.', 'danger')
        return redirect(url_for('auth.login'))

    form = ResetPasswordForm()
    error = None

    if form.validate_on_submit():
        password = form.password.data
        confirm_password = form.confirm_password.data

        # Re-run password strength checks (same rules as registration)
        if password != confirm_password:
            error = "Passwords do not match."
        elif len(password) < 8:
            error = "Password must be at least 8 characters long."
        elif not re.search(r"\d", password):
            error = "Password must include at least one number."
        elif not re.search(r"[A-Z]", password):
            error = "Password must include at least one uppercase letter."
        else:
            # Hash and save the new password
            user.password_hash = generate_password_hash(password)
            # If they could receive the email, their address is clearly valid — verify it
            user.is_verified = True
            db.session.commit()
            flash('Password reset successfully. You can now log in.', 'success')
            return redirect(url_for('auth.login'))

    return render_template('auth/reset_password.html', form=form, error=error, token=token)
