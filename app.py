from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from flask_wtf.csrf import CSRFProtect, CSRFError, FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, EqualTo, Email
from flask_limiter import Limiter
import re

# Import the shared db object and the User model from models.py
from models import db, User

# -------------------------------------------------
# APP CONFIGURATION
# -------------------------------------------------
app = Flask(__name__)
csrf = CSRFProtect(app)  # Enable CSRF protection globally

# Set up rate limiter: limit to 5 requests per minute per IP address for certain routes
limiter = Limiter(app, key_func=get_remote_address)

# Creating a FlaskForm to manage CSRF properly
class NameForm(FlaskForm):
    first_name = StringField('First Name', validators=[DataRequired()])
    last_name = StringField('Last Name', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])  # Email validation
    password = PasswordField('Password', validators=[DataRequired()])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password', message='Passwords must match')])
    agree_terms = BooleanField('I agree to the Terms & Conditions', validators=[DataRequired()])
    submit = SubmitField('Submit')

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
    error = None  # This will hold any error message to display in the template
    form = NameForm()

    if request.method == 'POST':
        if form.validate_on_submit():
            email = form.email.data
            password = form.password.data
        else:
            flash('CSRF Token Missing or Invalid!', 'danger')

        # 1. Server-side basic validation (ensure email and password are not empty)
        if not email or not password:
            error = "Please enter both email and password."
        else:
            # 2. Look for a user with this email in the database
            user = User.query.filter_by(email=email).first()

            if user is None:
                # No user found with that email
                error = "Incorrect email or password. Please try again."
            else:
                # 3. Check the entered password against the stored password hash
                if check_password_hash(user.password_hash, password):
                    # 4. Password is correct -> log the user in using session
                    session['user_id'] = user.user_id
                    session['user_name'] = user.full_name  # from Users table
                    session['user_role'] = user.role  # store role for dashboard
                    
                    flash(f"Welcome back, {user.full_name}!", "success")

                    # 5. Redirect to home or a dashboard page
                    if user.role == "admin":
                        return redirect(url_for('admin_dashboard'))
                    else:
                        return redirect(url_for('user_dashboard'))
                else:
                    # Password is incorrect
                    error = "Incorrect email or password. Please try again."

    # For GET requests or if there was an error, show the login form again
    # 'error' is passed to the template so {{ error }} can display it
    return render_template('login.html', error=error, form=form)

# -------------------------------------------------
# REGISTRATION ROUTE
# -------------------------------------------------
@app.route('/register', methods=['GET', 'POST'])
@limiter.limit("5 per minute")  # Limit this route to 5 requests per minute
def register():
    error = None  # This will hold any validation error message
    form = NameForm()

    if request.method == 'POST':
        if form.validate_on_submit():
            first_name = form.first_name.data
            last_name = form.last_name.data
            email = form.email.data.strip().lower()  # Convert to lowercase to avoid duplicate emails
            password = form.password.data
            confirm_password = form.confirm_password.data
        else:
            flash('CSRF Token Missing or Invalid!', 'danger')

        # 1. Server-side validation (required fields, email format, password match, etc.)
        
        # Make sure required fields are not empty
        if not first_name or not last_name or not email or not password or not confirm_password:
            error = "Please fill in all required fields."
        # Validate email format
        elif not re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", email):
            error = "Please provide a valid email address."
        # Check passwords match
        elif password != confirm_password:
            error = "Passwords do not match."
        # Password strength: Check for a minimum length of 8 characters, a number, and an uppercase letter
        elif len(password) < 8:
            error = "Password must be at least 8 characters long."
        elif not re.search(r"\d", password):
            error = "Password must include at least one number."
        elif not re.search(r"[A-Z]", password):
            error = "Password must include at least one uppercase letter."
        else:
            # 2. Check if the email already exists in the database
            existing_user = User.query.filter_by(email=email).first()
            if existing_user:
                error = "An account with that email already exists."

        # **Terms and Conditions Validation**: Ensure the user agrees to the terms
        if not form.agree_terms.data:
            error = "You must agree to the Terms and Conditions."

        # 3. If no errors, create the user
        if not error:
            # Join first and last name for 'full_name' field
            full_name = f"{first_name} {last_name}"

            # Hash the raw password using Werkzeug (pbkdf2 is default)
            password_hash = generate_password_hash(password)

            # Create a new User object (in memory only for now)
            new_user = User(
                full_name=full_name,
                email=email,
                password_hash=password_hash
                # join_date is set automatically by default=datetime.utcnow
            )

            # Stage the new user to be saved
            db.session.add(new_user)

            # Permanently save to the database file rza.db
            db.session.commit()

            # Give user feedback and redirect them to the login page
            flash("Account created successfully. You can now log in.", "success")
            return redirect(url_for('login'))

        # If we reached here and error is not None, fall through to re-render form

    # For GET requests OR when validation fails, show the form again.
    # 'error' is passed into the template so it can display a message.
    return render_template('registration.html', error=error, form=form)
