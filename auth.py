# auth.py
# ─────────────────────────────────────────────────────────────────────────────
# This file is a Flask "Blueprint" — think of it as a mini-app that handles
# everything related to authentication:
#   • Login / logout
#   • Registration
#   • Email verification
#   • Forgot password / password reset
#
# A Blueprint lets us keep all auth logic in one place instead of cramming it
# into app.py.  app.py just registers this blueprint and everything here
# becomes part of the main app automatically.
# ─────────────────────────────────────────────────────────────────────────────

import re                          # Regular expressions — used to validate email format
from functools import wraps        # Used to build the login_required decorator cleanly

from flask import (
    Blueprint, render_template, request,
    redirect, url_for, flash, session, current_app
)
from werkzeug.security import generate_password_hash, check_password_hash  # Secure password hashing
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, BooleanField
from wtforms.validators import DataRequired, EqualTo, Email
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature  # Token generation

from models import db, User        # Database and User model
from extensions import limiter, mail  # Rate limiter and mail sender from extensions.py
from flask_mail import Message     # Email message builder

# ─────────────────────────────────────────────────────────────────────────────
# BLUEPRINT SETUP
# ─────────────────────────────────────────────────────────────────────────────

# Create the Blueprint object.  'auth' is its name — this prefix is used when
# building URLs, e.g. url_for('auth.login') instead of url_for('login').
auth_bp = Blueprint('auth', __name__)


# ─────────────────────────────────────────────────────────────────────────────
# FORM DEFINITIONS
# Each class represents one HTML form.  Flask-WTF uses these to:
#   1. Render the form fields in the template ({{ form.email() }} etc.)
#   2. Validate the submitted data automatically
#   3. Inject + check the CSRF token
# ─────────────────────────────────────────────────────────────────────────────

class LoginForm(FlaskForm):
    """Form shown on the /login page."""
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')  # Keeps the user logged in after browser closes
    submit = SubmitField('Sign In')


class RegistrationForm(FlaskForm):
    """Form shown on the /register page."""
    first_name = StringField('First Name', validators=[DataRequired()])
    last_name = StringField('Last Name', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    confirm_password = PasswordField(
        'Confirm Password',
        # EqualTo checks that this field matches the 'password' field
        validators=[DataRequired(), EqualTo('password', message='Passwords must match')]
    )
    agree_terms = BooleanField(
        'I agree to the Terms & Conditions',
        validators=[DataRequired()]  # DataRequired on a checkbox means it must be ticked
    )
    submit = SubmitField('Sign Up')


class ForgotPasswordForm(FlaskForm):
    """Form shown on the /forgot-password page — just asks for an email."""
    email = StringField('Email', validators=[DataRequired(), Email()])
    submit = SubmitField('Send Reset Link')


class ResetPasswordForm(FlaskForm):
    """Form shown on the /reset-password/<token> page — enter a new password."""
    password = PasswordField('New Password', validators=[DataRequired()])
    confirm_password = PasswordField(
        'Confirm New Password',
        validators=[DataRequired(), EqualTo('password', message='Passwords must match')]
    )
    submit = SubmitField('Reset Password')


class ProfileForm(FlaskForm):
    """Form shown on the /profile page — update name and optionally change password."""
    first_name = StringField('First Name', validators=[DataRequired()])
    last_name  = StringField('Last Name',  validators=[DataRequired()])
    # Password change fields are all optional — only validated if new_password is filled
    current_password     = PasswordField('Current Password')
    new_password         = PasswordField('New Password')
    confirm_new_password = PasswordField('Confirm New Password')
    submit = SubmitField('Save Changes')


# ─────────────────────────────────────────────────────────────────────────────
# TOKEN HELPERS
# Used to create and verify the secure links sent in emails.
# itsdangerous signs the data with the app's SECRET_KEY so tokens can't be
# faked, and they automatically expire after max_age seconds (default 1 hour).
# ─────────────────────────────────────────────────────────────────────────────

def generate_token(data, salt):
    """
    Create a signed, URL-safe token containing 'data' (usually an email address).
    'salt' makes tokens for different purposes incompatible — a password-reset
    token can't be used as an email-verification token.
    """
    s = URLSafeTimedSerializer(current_app.secret_key)
    return s.dumps(data, salt=salt)


def verify_token(token, salt, max_age=3600):
    """
    Decode a token and return the original data.
    Raises SignatureExpired if the token is older than max_age seconds (1 hour).
    Raises BadSignature if the token has been tampered with.
    """
    s = URLSafeTimedSerializer(current_app.secret_key)
    return s.loads(token, salt=salt, max_age=max_age)


# ─────────────────────────────────────────────────────────────────────────────
# EMAIL HELPERS
# These functions build and send the two types of emails the app sends.
# ─────────────────────────────────────────────────────────────────────────────

def send_verification_email(user_email):
    """
    Send an email with a link the user must click to verify their address.
    The link contains a signed token with their email baked in.
    """
    token = generate_token(user_email, salt='email-verify')
    # _external=True makes url_for produce a full URL (https://...) not just a path
    link = url_for('auth.verify_email', token=token, _external=True)

    msg = Message('Confirm your email address', recipients=[user_email])
    msg.body = (
        f'Hello,\n\n'
        f'Please click the link below to verify your email address:\n\n'
        f'{link}\n\n'
        f'This link expires in 1 hour.\n\n'
        f'If you did not create an account, you can ignore this email.'
    )
    mail.send(msg)


def send_password_reset_email(user_email):
    """
    Send an email with a link the user can use to set a new password.
    Uses a different salt ('password-reset') so it can't be confused with a
    verification token.
    """
    token = generate_token(user_email, salt='password-reset')
    link = url_for('auth.reset_password', token=token, _external=True)

    msg = Message('Reset your password', recipients=[user_email])
    msg.body = (
        f'Hello,\n\n'
        f'You requested a password reset. Click the link below:\n\n'
        f'{link}\n\n'
        f'This link expires in 1 hour.\n\n'
        f'If you did not request this, you can ignore this email.'
    )
    mail.send(msg)


# ─────────────────────────────────────────────────────────────────────────────
# AUTHENTICATION HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def login_required(f):
    """
    Decorator that protects a route — only logged-in users can access it.
    Usage:  @login_required  above any route function.
    If the user isn't logged in, they get redirected to /login instead.
    """
    @wraps(f)  # Preserves the original function's name and docstring
    def decorated(*args, **kwargs):
        if 'user_id' not in session:  # session is Flask's server-side cookie store
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated


def set_user_session(user, remember=False):
    """
    Write the logged-in user's details into the Flask session.
    The session is a secure, signed cookie stored in the browser.
    session.permanent=True means it survives after the browser is closed
    (used for the "Remember Me" feature).
    """
    session.permanent = remember
    session['user_id'] = user.user_id      # Used to identify the user on future requests
    session['user_name'] = user.full_name  # Shown in the UI ("Welcome, John!")
    session['user_role'] = user.role       # Controls which dashboard to redirect to


def redirect_to_dashboard(role):
    """Send admin users to the admin dashboard, everyone else to user dashboard."""
    if role == 'admin':
        return redirect(url_for('admin_dashboard'))
    return redirect(url_for('user_dashboard'))


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
                    # User doesn't exist, or signed up via OAuth (no password) — same vague error
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
    return render_template('login.html', error=error, form=form)


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
        return redirect(url_for('user_dashboard'))

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

            elif not form.agree_terms.data:
                error = "You must agree to the Terms and Conditions."

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

    return render_template('registration.html', error=error, form=form)


# ─────────────────────────────────────────────────────────────────────────────
# EMAIL VERIFICATION ROUTES
# ─────────────────────────────────────────────────────────────────────────────

@auth_bp.route('/verify-pending')
def verify_pending():
    """Simple page shown after registration: 'Check your inbox!'"""
    return render_template('verify_pending.html')


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

    return render_template('resend_verification.html')


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

        # Only send the email if the user exists and has a password (not OAuth-only)
        if user and user.password_hash:
            try:
                send_password_reset_email(email)
            except Exception:
                pass

        return redirect(url_for('auth.login'))

    return render_template('forgot_password.html', form=form)


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

    return render_template('reset_password.html', form=form, error=error, token=token)
