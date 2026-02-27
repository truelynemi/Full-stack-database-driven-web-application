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
import re

# Import the shared db object and the User model from models.py
from models import db, User

# -------------------------------------------------
# APP CONFIGURATION
# -------------------------------------------------
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///rza.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialise the database with the app
db.init_app(app)

# Enable CSRF protection globally
csrf = CSRFProtect(app)

# Set up rate limiter: limit by IP address
limiter = Limiter(app, key_func=get_remote_address)

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
@limiter.exempt  # This route is exempt from rate limiting
def about():
    return render_template('about.html')

# -------------------------------------------------
# LOGIN ROUTE
# -------------------------------------------------

@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute")  # Limit this route to 5 requests per minute
def login():
    # Redirect already-logged-in users straight to their dashboard
    if 'user_id' in session:
        if session.get('user_role') == 'admin':
            return redirect(url_for('admin_dashboard'))
        return redirect(url_for('user_dashboard'))

    error = None
    form = LoginForm()

    if request.method == 'POST':
        if form.validate_on_submit():
            email = form.email.data.strip().lower()
            password = form.password.data

            # 1. Server-side basic validation
            if not email or not password:
                error = "Please enter both email and password."
            else:
                # 2. Look for a user with this email in the database
                user = User.query.filter_by(email=email).first()

                if user is None:
                    # No user found — keep error message vague for security
                    error = "Incorrect email or password. Please try again."
                else:
                    # 3. Check the entered password against the stored hash
                    if check_password_hash(user.password_hash, password):
                        # 4. Password correct — configure session
                        session.permanent = form.remember_me.data  # persist if "remember me"
                        session['user_id'] = user.user_id
                        session['user_name'] = user.full_name
                        session['user_role'] = user.role

                        flash(f"Welcome back, {user.full_name}!", "success")

                        # 5. Redirect based on role
                        if user.role == "admin":
                            return redirect(url_for('admin_dashboard'))
                        return redirect(url_for('user_dashboard'))
                    else:
                        error = "Incorrect email or password. Please try again."
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
@limiter.limit("5 per minute")  # Limit this route to 5 requests per minute
def register():
    # Redirect already-logged-in users
    if 'user_id' in session:
        return redirect(url_for('user_dashboard'))

    error = None
    form = RegistrationForm()

    if request.method == 'POST':
        if form.validate_on_submit():
            first_name = form.first_name.data.strip()
            last_name = form.last_name.data.strip()
            email = form.email.data.strip().lower()  # lowercase to avoid duplicate emails
            password = form.password.data
            confirm_password = form.confirm_password.data

            # 1. Server-side validation chain

            # Required fields
            if not first_name or not last_name or not email or not password or not confirm_password:
                error = "Please fill in all required fields."
            # Email format
            elif not re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", email):
                error = "Please provide a valid email address."
            # Passwords match
            elif password != confirm_password:
                error = "Passwords do not match."
            # Minimum length
            elif len(password) < 8:
                error = "Password must be at least 8 characters long."
            # Must contain a digit
            elif not re.search(r"\d", password):
                error = "Password must include at least one number."
            # Must contain an uppercase letter
            elif not re.search(r"[A-Z]", password):
                error = "Password must include at least one uppercase letter."
            # Terms and conditions
            elif not form.agree_terms.data:
                error = "You must agree to the Terms and Conditions."
            else:
                # 2. Check email uniqueness in database
                existing_user = User.query.filter_by(email=email).first()
                if existing_user:
                    error = "An account with that email already exists."

            # 3. If no errors, create the user
            if not error:
                full_name = f"{first_name} {last_name}"
                password_hash = generate_password_hash(password)

                new_user = User(
                    full_name=full_name,
                    email=email,
                    password_hash=password_hash
                    # join_date defaults to datetime.utcnow via the model
                )

                db.session.add(new_user)
                db.session.commit()

                flash("Account created successfully. You can now log in.", "success")
                return redirect(url_for('login'))
        else:
            flash('CSRF Token Missing or Invalid!', 'danger')

    return render_template('registration.html', error=error, form=form)

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
        db.create_all()  # Create tables if they don't already exist
    app.run(debug=True)
