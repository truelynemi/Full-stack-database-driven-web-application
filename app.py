import os
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from flask_wtf.csrf import CSRFProtect, CSRFError
from wtforms import StringField, PasswordField, SubmitField, BooleanField
from wtforms.validators import DataRequired, EqualTo, Email
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf import FlaskForm
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from flask_dance.contrib.google import make_google_blueprint, google
from flask_dance.contrib.twitter import make_twitter_blueprint, twitter
import re

from models import db, User

# -------------------------------------------------
# APP CONFIGURATION
# -------------------------------------------------
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///rza.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Flask-Mail — Gmail SMTP
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get('GMAIL_ADDRESS')
app.config['MAIL_PASSWORD'] = os.environ.get('GMAIL_APP_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('GMAIL_ADDRESS')

# Allow OAuth over HTTP in development (remove in production)
os.environ.setdefault('OAUTHLIB_INSECURE_TRANSPORT', '1')

# Initialise extensions
db.init_app(app)
csrf = CSRFProtect(app)
limiter = Limiter(app, key_func=get_remote_address)
mail = Mail(app)

# -------------------------------------------------
# OAUTH BLUEPRINTS
# -------------------------------------------------

google_bp = make_google_blueprint(
    client_id=os.environ.get('GOOGLE_CLIENT_ID'),
    client_secret=os.environ.get('GOOGLE_CLIENT_SECRET'),
    scope=['profile', 'email'],
    redirect_url='/auth/google/callback'
)
app.register_blueprint(google_bp, url_prefix='/auth')

twitter_bp = make_twitter_blueprint(
    api_key=os.environ.get('TWITTER_API_KEY'),
    api_secret=os.environ.get('TWITTER_API_SECRET'),
    redirect_url='/auth/twitter/callback'
)
app.register_blueprint(twitter_bp, url_prefix='/auth')

# Exempt OAuth redirect routes from CSRF (they use OAuth state tokens instead)
csrf.exempt(google_bp)
csrf.exempt(twitter_bp)

# -------------------------------------------------
# FORM DEFINITIONS
# -------------------------------------------------

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Sign In')


class RegistrationForm(FlaskForm):
    first_name = StringField('First Name', validators=[DataRequired()])
    last_name = StringField('Last Name', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    confirm_password = PasswordField(
        'Confirm Password',
        validators=[DataRequired(), EqualTo('password', message='Passwords must match')]
    )
    agree_terms = BooleanField('I agree to the Terms & Conditions', validators=[DataRequired()])
    submit = SubmitField('Sign Up')


class ForgotPasswordForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    submit = SubmitField('Send Reset Link')


class ResetPasswordForm(FlaskForm):
    password = PasswordField('New Password', validators=[DataRequired()])
    confirm_password = PasswordField(
        'Confirm New Password',
        validators=[DataRequired(), EqualTo('password', message='Passwords must match')]
    )
    submit = SubmitField('Reset Password')

# -------------------------------------------------
# TOKEN HELPERS
# -------------------------------------------------

def generate_token(data, salt):
    """Generate a signed, time-limited URL-safe token."""
    s = URLSafeTimedSerializer(app.secret_key)
    return s.dumps(data, salt=salt)


def verify_token(token, salt, max_age=3600):
    """Decode a token. Returns the data or raises SignatureExpired / BadSignature."""
    s = URLSafeTimedSerializer(app.secret_key)
    return s.loads(token, salt=salt, max_age=max_age)

# -------------------------------------------------
# EMAIL HELPERS
# -------------------------------------------------

def send_verification_email(user_email):
    token = generate_token(user_email, salt='email-verify')
    link = url_for('verify_email', token=token, _external=True)
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
    token = generate_token(user_email, salt='password-reset')
    link = url_for('reset_password', token=token, _external=True)
    msg = Message('Reset your password', recipients=[user_email])
    msg.body = (
        f'Hello,\n\n'
        f'You requested a password reset. Click the link below:\n\n'
        f'{link}\n\n'
        f'This link expires in 1 hour.\n\n'
        f'If you did not request this, you can ignore this email.'
    )
    mail.send(msg)

# -------------------------------------------------
# AUTHENTICATION HELPERS
# -------------------------------------------------

def login_required(f):
    """Decorator that redirects unauthenticated users to /login."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


def set_user_session(user, remember=False):
    """Write user info into the Flask session."""
    session.permanent = remember
    session['user_id'] = user.user_id
    session['user_name'] = user.full_name
    session['user_role'] = user.role


def redirect_to_dashboard(role):
    if role == 'admin':
        return redirect(url_for('admin_dashboard'))
    return redirect(url_for('user_dashboard'))

# -------------------------------------------------
# CSRF ERROR HANDLER
# -------------------------------------------------

@app.errorhandler(CSRFError)
def handle_csrf_error(e):
    flash('Your session has expired or the request was invalid. Please try again.', 'danger')
    return redirect(request.referrer or url_for('login'))

# -------------------------------------------------
# ABOUT ROUTE
# -------------------------------------------------

@app.route('/about')
@limiter.exempt
def about():
    return render_template('about.html')

# -------------------------------------------------
# LOGIN ROUTE
# -------------------------------------------------

@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def login():
    if 'user_id' in session:
        return redirect_to_dashboard(session.get('user_role'))

    error = None
    form = LoginForm()

    if request.method == 'POST':
        if form.validate_on_submit():
            email = form.email.data.strip().lower()
            password = form.password.data

            if not email or not password:
                error = "Please enter both email and password."
            else:
                user = User.query.filter_by(email=email).first()

                if user is None or user.password_hash is None:
                    error = "Incorrect email or password. Please try again."
                elif not check_password_hash(user.password_hash, password):
                    error = "Incorrect email or password. Please try again."
                elif not user.is_verified:
                    error = "Please verify your email before logging in. Check your inbox or resend below."
                else:
                    set_user_session(user, remember=form.remember_me.data)
                    flash(f"Welcome back, {user.full_name}!", "success")
                    return redirect_to_dashboard(user.role)
        else:
            flash('CSRF Token Missing or Invalid!', 'danger')

    return render_template('login.html', error=error, form=form)

# -------------------------------------------------
# LOGOUT ROUTE
# -------------------------------------------------

@app.route('/logout')
def logout():
    name = session.get('user_name', 'User')
    session.clear()
    flash(f"Goodbye, {name}! You have been logged out.", "info")
    return redirect(url_for('login'))

# -------------------------------------------------
# REGISTRATION ROUTE
# -------------------------------------------------

@app.route('/register', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def register():
    if 'user_id' in session:
        return redirect(url_for('user_dashboard'))

    error = None
    form = RegistrationForm()

    if request.method == 'POST':
        if form.validate_on_submit():
            first_name = form.first_name.data.strip()
            last_name = form.last_name.data.strip()
            email = form.email.data.strip().lower()
            password = form.password.data
            confirm_password = form.confirm_password.data

            if not first_name or not last_name or not email or not password or not confirm_password:
                error = "Please fill in all required fields."
            elif not re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", email):
                error = "Please provide a valid email address."
            elif password != confirm_password:
                error = "Passwords do not match."
            elif len(password) < 8:
                error = "Password must be at least 8 characters long."
            elif not re.search(r"\d", password):
                error = "Password must include at least one number."
            elif not re.search(r"[A-Z]", password):
                error = "Password must include at least one uppercase letter."
            elif not form.agree_terms.data:
                error = "You must agree to the Terms and Conditions."
            else:
                existing_user = User.query.filter_by(email=email).first()
                if existing_user:
                    error = "An account with that email already exists."

            if not error:
                full_name = f"{first_name} {last_name}"
                new_user = User(
                    full_name=full_name,
                    email=email,
                    password_hash=generate_password_hash(password),
                    is_verified=False
                )
                db.session.add(new_user)
                db.session.commit()

                try:
                    send_verification_email(email)
                    flash("Account created! Please check your email to verify your account.", "success")
                except Exception:
                    flash("Account created but we couldn't send the verification email. Contact support.", "warning")

                return redirect(url_for('verify_pending'))
        else:
            flash('CSRF Token Missing or Invalid!', 'danger')

    return render_template('registration.html', error=error, form=form)

# -------------------------------------------------
# EMAIL VERIFICATION ROUTES
# -------------------------------------------------

@app.route('/verify-pending')
def verify_pending():
    return render_template('verify_pending.html')


@app.route('/verify/<token>')
def verify_email(token):
    try:
        email = verify_token(token, salt='email-verify')
    except SignatureExpired:
        flash('That verification link has expired. Please register again or request a new link.', 'danger')
        return redirect(url_for('login'))
    except BadSignature:
        flash('That verification link is invalid.', 'danger')
        return redirect(url_for('login'))

    user = User.query.filter_by(email=email).first()
    if user is None:
        flash('Account not found.', 'danger')
        return redirect(url_for('login'))

    if user.is_verified:
        flash('Your email is already verified. You can log in.', 'info')
    else:
        user.is_verified = True
        db.session.commit()
        flash('Email verified! You can now log in.', 'success')

    return redirect(url_for('login'))


@app.route('/resend-verification', methods=['GET', 'POST'])
@limiter.limit("3 per hour")
def resend_verification():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        user = User.query.filter_by(email=email).first()

        # Always show the same message to prevent email enumeration
        flash('If that email exists and is unverified, a new link has been sent.', 'info')

        if user and not user.is_verified:
            try:
                send_verification_email(email)
            except Exception:
                pass  # Silent fail — message already shown

        return redirect(url_for('login'))

    return render_template('resend_verification.html')

# -------------------------------------------------
# FORGOT PASSWORD ROUTES
# -------------------------------------------------

@app.route('/forgot-password', methods=['GET', 'POST'])
@limiter.limit("5 per hour")
def forgot_password():
    form = ForgotPasswordForm()

    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        user = User.query.filter_by(email=email).first()

        # Always show same message to prevent email enumeration
        flash('If that email is registered, a password reset link has been sent.', 'info')

        if user and user.password_hash:  # only send for email/password accounts
            try:
                send_password_reset_email(email)
            except Exception:
                pass  # Silent fail — message already shown

        return redirect(url_for('login'))

    return render_template('forgot_password.html', form=form)


@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    try:
        email = verify_token(token, salt='password-reset')
    except SignatureExpired:
        flash('That password reset link has expired. Please request a new one.', 'danger')
        return redirect(url_for('forgot_password'))
    except BadSignature:
        flash('That password reset link is invalid.', 'danger')
        return redirect(url_for('forgot_password'))

    user = User.query.filter_by(email=email).first()
    if user is None:
        flash('Account not found.', 'danger')
        return redirect(url_for('login'))

    form = ResetPasswordForm()
    error = None

    if form.validate_on_submit():
        password = form.password.data
        confirm_password = form.confirm_password.data

        if password != confirm_password:
            error = "Passwords do not match."
        elif len(password) < 8:
            error = "Password must be at least 8 characters long."
        elif not re.search(r"\d", password):
            error = "Password must include at least one number."
        elif not re.search(r"[A-Z]", password):
            error = "Password must include at least one uppercase letter."
        else:
            user.password_hash = generate_password_hash(password)
            user.is_verified = True  # auto-verify if they can receive email
            db.session.commit()
            flash('Password reset successfully. You can now log in.', 'success')
            return redirect(url_for('login'))

    return render_template('reset_password.html', form=form, error=error, token=token)

# -------------------------------------------------
# GOOGLE OAUTH CALLBACK
# -------------------------------------------------

@app.route('/auth/google/callback')
def google_callback():
    if not google.authorized:
        flash('Google login failed. Please try again.', 'danger')
        return redirect(url_for('login'))

    resp = google.get('/oauth2/v2/userinfo')
    if not resp.ok:
        flash('Could not fetch your Google profile. Please try again.', 'danger')
        return redirect(url_for('login'))

    info = resp.json()
    google_id = str(info['id'])
    email = info.get('email', '').lower()
    full_name = info.get('name', email)

    # Try to find by OAuth ID first, then by email
    user = User.query.filter_by(oauth_provider='google', oauth_id=google_id).first()
    if user is None and email:
        user = User.query.filter_by(email=email).first()
        if user:
            # Link existing email account to Google
            user.oauth_provider = 'google'
            user.oauth_id = google_id
            db.session.commit()

    if user is None:
        # Create new user via Google
        user = User(
            full_name=full_name,
            email=email or None,
            oauth_provider='google',
            oauth_id=google_id,
            is_verified=True  # Google already verified the email
        )
        db.session.add(user)
        db.session.commit()
        flash(f'Account created via Google. Welcome, {full_name}!', 'success')
    else:
        flash(f'Welcome back, {user.full_name}!', 'success')

    set_user_session(user)
    return redirect_to_dashboard(user.role)

# -------------------------------------------------
# TWITTER OAUTH CALLBACK
# -------------------------------------------------

@app.route('/auth/twitter/callback')
def twitter_callback():
    if not twitter.authorized:
        flash('Twitter login failed. Please try again.', 'danger')
        return redirect(url_for('login'))

    resp = twitter.get('account/verify_credentials.json')
    if not resp.ok:
        flash('Could not fetch your Twitter profile. Please try again.', 'danger')
        return redirect(url_for('login'))

    info = resp.json()
    twitter_id = str(info['id'])
    screen_name = info.get('screen_name', f'user_{twitter_id}')
    full_name = info.get('name', screen_name)

    user = User.query.filter_by(oauth_provider='twitter', oauth_id=twitter_id).first()

    if user is None:
        user = User(
            full_name=full_name,
            oauth_provider='twitter',
            oauth_id=twitter_id,
            is_verified=True  # Twitter account considered verified
        )
        db.session.add(user)
        db.session.commit()
        flash(f'Account created via Twitter. Welcome, {full_name}!', 'success')
    else:
        flash(f'Welcome back, {user.full_name}!', 'success')

    set_user_session(user)
    return redirect_to_dashboard(user.role)

# -------------------------------------------------
# DASHBOARD ROUTES
# -------------------------------------------------

@app.route('/user_dashboard')
@login_required
def user_dashboard():
    return render_template('user_dashboard.html')


@app.route('/admin_dashboard')
@login_required
def admin_dashboard():
    if session.get('user_role') != 'admin':
        flash('You do not have permission to access that page.', 'danger')
        return redirect(url_for('user_dashboard'))
    return render_template('admin_dashboard.html')

# -------------------------------------------------
# ENTRY POINT
# -------------------------------------------------

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
