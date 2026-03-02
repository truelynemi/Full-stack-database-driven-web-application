# auth/forms.py
# ─────────────────────────────────────────────────────────────────────────────
# All WTForms form classes used in the authentication system.
# Flask-WTF uses these to:
#   1. Render form fields in templates ({{ form.email() }} etc.)
#   2. Validate submitted data automatically
#   3. Inject and verify CSRF tokens on every form
# ─────────────────────────────────────────────────────────────────────────────

from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, BooleanField  # BooleanField used for remember_me
from wtforms.validators import DataRequired, EqualTo, Email


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
