# auth/helpers.py
# ─────────────────────────────────────────────────────────────────────────────
# Shared helper functions used by auth routes and the main blueprint.
# Kept in a separate file so they can be imported by multiple modules without
# pulling in the blueprint or route definitions.
# ─────────────────────────────────────────────────────────────────────────────

from functools import wraps  # Used to build the login_required decorator cleanly

from flask import session, redirect, url_for, flash, current_app
from itsdangerous import URLSafeTimedSerializer  # Token generation and verification
from flask_mail import Message

from extensions import mail  # Mail sender from extensions.py


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


def send_otp_email(user_email, code):
    """
    Send a 6-digit one-time password to the user for 2FA login verification.
    The code expires in 10 minutes (enforced server-side via otp_expires).
    """
    msg = Message('Your login verification code', recipients=[user_email])
    msg.body = (
        f'Your one-time login code is:\n\n'
        f'    {code}\n\n'
        f'This code expires in 10 minutes.\n\n'
        f'If you did not attempt to log in, please change your password immediately.'
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
        return redirect(url_for('admin.admin_dashboard'))
    return redirect(url_for('main.user_dashboard'))
