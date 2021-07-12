from flask_wtf import FlaskForm, RecaptchaField
from wtforms import PasswordField, validators
from wtforms.fields.html5 import EmailField

class RegisterForm(FlaskForm):
    email = EmailField('Email Address', [validators.DataRequired(), validators.Length(min=6, max=64)])
    password = PasswordField('Password', [validators.DataRequired(),validators.Length(min=8)])
    recaptcha = RecaptchaField()
