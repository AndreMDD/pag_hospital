from flask import render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime
import random
from flask_mail import Message

from . import app, mongo, mail
from .forms import LoginForm, RegistroForm, RecuperarPasswordForm, ValidarCodigoForm, NuevaPasswordForm
from .models import User

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        if form.username.data == "admin" and app.config.get('ADMIN_PASSWORD') and form.password.data == app.config['ADMIN_PASSWORD']:
            session['admin_logged_in'] = True
            flash('Bienvenido al Panel de Administración.', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            rut_limpio = form.username.data.replace(".", "").replace("-", "").upper()
            user_data = mongo.db.pacientes.find_one({'rut': rut_limpio})
            if user_data and check_password_hash(user_data['password'], form.password.data):
                user = User(user_data)
                login_user(user)
                flash('Has iniciado sesión correctamente.', 'success')
                return redirect(url_for('mis_citas'))
            else:
                flash('RUT o contraseña incorrectos.', 'danger')
    return render_template('login.html', form=form, title="Inicio de Sesión")

@app.route('/registro', methods=['GET', 'POST'])
def registro():
    form = RegistroForm()
    if form.validate_on_submit():
        rut_limpio = form.rut.data.replace(".", "").replace("-", "").upper()
        if mongo.db.pacientes.find_one({'rut': rut_limpio}):
            flash('El RUT ya está registrado.', 'warning')
        elif mongo.db.pacientes.find_one({'email': form.email.data}):
            flash('El correo electrónico ya está en uso.', 'warning')
        else:
            hashed_password = generate_password_hash(form.password.data)
            new_user_data = {
                'rut': rut_limpio, 'nombre_completo': form.nombre.data,
                'email': form.email.data, 'nameUser': form.nameUser.data,
                'celular': form.celular.data, 'password': hashed_password,
                'atenciones': {'consultas_agendadas': [], 'atenciones_inmediatas': []},
                'examenes_disponibles': []
            }
            mongo.db.pacientes.insert_one(new_user_data)
            flash('¡Registro exitoso! Por favor, inicia sesión.', 'success')
            return redirect(url_for('login'))
    elif request.method == 'POST':
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"{getattr(form, field).label.text}: {error}", 'danger')
    return render_template('registro.html', form=form)

@app.route('/recuperar-password', methods=['GET', 'POST'])
def recuperar_password():
    form = RecuperarPasswordForm()
    if form.validate_on_submit():
        paciente = mongo.db.pacientes.find_one({'email': form.email.data})
        if paciente:
            codigo = str(random.randint(100000, 999999))
            session.update({'reset_code': codigo, 'reset_email': form.email.data, 'last_resend_time': datetime.now().timestamp()})
            try:
                msg = Message('Código de Recuperación - Clínica Salud', sender=app.config.get('MAIL_USERNAME'), recipients=[form.email.data])
                msg.body = f"Tu código de verificación es: {codigo}"
                mail.send(msg)
                flash('Se ha enviado un código a tu correo.', 'info')
                return redirect(url_for('validar_codigo'))
            except Exception:
                flash('Hubo un error al enviar el correo. Inténtalo más tarde.', 'danger')
        else: flash('No se encontró una cuenta con ese correo.', 'danger')
    return render_template('solicitar_recuperacion.html', form=form)

@app.route('/validar-codigo', methods=['GET', 'POST'])
def validar_codigo():
    if 'reset_email' not in session or 'reset_code' not in session:
        flash('La sesión de recuperación ha expirado.', 'warning')
        return redirect(url_for('recuperar_password'))
    form = ValidarCodigoForm()
    if form.validate_on_submit():
        if form.codigo.data == session['reset_code']:
            session['codigo_validado'] = True
            return redirect(url_for('recuperacion'))
        else: flash('El código es incorrecto.', 'danger')
    return render_template('validar_codigo.html', form=form)

@app.route('/reenviar-codigo')
def reenviar_codigo():
    if 'reset_email' not in session: return redirect(url_for('recuperar_password'))
    if 'last_resend_time' in session and (datetime.now().timestamp() - session['last_resend_time']) < 60:
        flash(f"Espera antes de reenviar.", 'warning')
        return redirect(url_for('validar_codigo'))
    session.update({'last_resend_time': datetime.now().timestamp(), 'reset_code': str(random.randint(100000, 999999))})
    try:
        msg = Message('Nuevo Código', sender=app.config.get('MAIL_USERNAME'), recipients=[session['reset_email']])
        msg.body = f"Tu nuevo código es: {session['reset_code']}"
        mail.send(msg)
    except Exception: pass
    return redirect(url_for('validar_codigo'))

@app.route('/recuperacion', methods=['GET', 'POST'])
def recuperacion():
    if not session.get('codigo_validado') or 'reset_email' not in session: return redirect(url_for('recuperar_password'))
    form = NuevaPasswordForm()
    if form.validate_on_submit():
        mongo.db.pacientes.update_one({'email': session['reset_email']}, {'$set': {'password': generate_password_hash(form.password.data)}})
        [session.pop(k, None) for k in ['reset_email', 'reset_code', 'codigo_validado', 'last_resend_time']]
        flash('¡Contraseña actualizada! Ya puedes iniciar sesión.', 'success')
        return redirect(url_for('login'))
    return render_template('recuperacion.html', form=form)

@app.route('/logout')
def logout():
    logout_user()
    session.pop('admin_logged_in', None)
    flash('Sesión cerrada correctamente.', 'info')
    return redirect(url_for('index'))