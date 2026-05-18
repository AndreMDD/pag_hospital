from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, SelectField, DateField, TimeField
from wtforms.validators import DataRequired, Email, EqualTo

class LoginForm(FlaskForm):
    username = StringField('Usuario o RUT', validators=[DataRequired()])
    password = PasswordField('Contraseña', validators=[DataRequired()])
    submit = SubmitField('Ingresar')

class RegistroForm(FlaskForm):
    rut = StringField('RUT', validators=[DataRequired()])
    nombre = StringField('Nombre Completo', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    nameUser = StringField('Nombre de Usuario', validators=[DataRequired()])
    celular = StringField('Teléfono Celular', validators=[DataRequired(message='El teléfono es obligatorio')])
    password = PasswordField('Contraseña', validators=[DataRequired(), EqualTo('confirm_password', message='Las contraseñas deben coincidir')])
    confirm_password = PasswordField('Confirmar Contraseña', validators=[DataRequired()])
    submit = SubmitField('Registrarse')

class ReservaForm(FlaskForm):
    rut = StringField('RUT (ej: 12345678-9)', validators=[DataRequired()])
    nombre = StringField('Nombre Completo', validators=[DataRequired()])
    email = StringField('Correo Electrónico', validators=[DataRequired(), Email()])
    especialidad = SelectField('Especialidad', choices=[
        ('medicina_general', 'Medicina General'),
        ('cardiologia', 'Cardiología'),
        ('dermatologia', 'Dermatología'),
        ('pediatria', 'Pediatría')
    ], validators=[DataRequired()])
    doctor = SelectField('Doctor de Preferencia', choices=[], validate_choice=False)
    fecha = DateField('Fecha', validators=[DataRequired()])
    hora = SelectField('Hora Disponible', choices=[], validate_choice=False)
    submit = SubmitField('Confirmar Reserva')

class RecuperarPasswordForm(FlaskForm):
    email = StringField('Correo Electrónico', validators=[DataRequired(), Email()])
    submit = SubmitField('Enviar Código')

class ValidarCodigoForm(FlaskForm):
    codigo = StringField('Código de Verificación', validators=[DataRequired()])
    submit = SubmitField('Validar')

class NuevaPasswordForm(FlaskForm):
    password = PasswordField('Nueva Contraseña', validators=[DataRequired(), EqualTo('confirm_password', message='Las contraseñas deben coincidir')])
    confirm_password = PasswordField('Confirmar Nueva Contraseña', validators=[DataRequired()])
    submit = SubmitField('Actualizar Contraseña')