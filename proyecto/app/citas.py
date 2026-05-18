from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from bson.objectid import ObjectId
from pymongo.errors import DuplicateKeyError
from datetime import date, time, datetime
from flask_mail import Message

from .. import app, mongo, mail
from ..forms import ReservaForm
from ..utils import validar_rut

@app.route('/reservar', methods=['GET', 'POST'])
@login_required
def reservar():
    form = ReservaForm()
    if form.validate_on_submit():
        if form.fecha.data < date.today():
            flash('Error: No se pueden reservar horas en fechas pasadas.', 'danger')
            return render_template('reservar.html', form=form)
        try:
            hora_obj = datetime.strptime(form.hora.data, '%H:%M').time()
            if not (time(8, 0) <= hora_obj <= time(20, 0)):
                flash('Error: El horario de atención es de 08:00 a 20:00 hrs.', 'danger')
                return render_template('reservar.html', form=form)
        except (ValueError, TypeError):
            flash('Error: Formato de hora inválido.', 'danger')
            return render_template('reservar.html', form=form)
        if not validar_rut(form.rut.data):
            flash('El RUT ingresado no es válido.', 'danger')
            return render_template('reservar.html', form=form)
            
        if mongo.db.citas.find_one({'doctor': form.doctor.data, 'fecha': str(form.fecha.data), 'hora': form.hora.data}):
            flash('Lo sentimos, ese horario acaba de ser ocupado. Por favor elija otro.', 'warning')
            return render_template('reservar.html', form=form)

        cita = {
            'rut': form.rut.data.replace(".", "").upper(), 'nombre': form.nombre.data,
            'email': form.email.data, 'especialidad': dict(form.especialidad.choices).get(form.especialidad.data),
            'doctor': form.doctor.data, 'fecha': str(form.fecha.data), 'hora': form.hora.data,
            'estado': 'Reservada', 'resultados': [], 'created_at': datetime.now()
        }
        try:
            mongo.db.citas.insert_one(cita)
            mongo.db.pacientes.update_one({'_id': ObjectId(current_user.id)}, {'$push': {'atenciones.consultas_agendadas': {'especialidad': cita['especialidad'], 'fecha': cita['fecha'], 'hora': cita['hora'], 'doctor': cita['doctor']}}})
            try:
                msg = Message('Confirmación de Reserva', sender=app.config.get('MAIL_USERNAME'), recipients=[cita['email']])
                msg.html = render_template('email_confirmation.html', cita=cita)
                mail.send(msg)
                flash(f'Reserva agendada con éxito.', 'success')
            except Exception: flash(f'Reserva agendada, pero hubo un error enviando el correo.', 'warning')
            return redirect(url_for('mis_citas'))
        except DuplicateKeyError:
            flash('El horario seleccionado acaba de ser reservado.', 'danger')
    return render_template('reservar.html', form=form)

@app.route('/mis-citas')
@login_required
def mis_citas(): return render_template('mis_citas.html')

@app.route('/buscar-medico', methods=['GET', 'POST'])
@login_required
def buscar_medico():
    medicos = []
    query = request.form.get('query', '')
    if query:
        medicos = list(mongo.db.medicos.find({"$or": [{"nombre": {"$regex": query, "$options": "i"}}, {"especialidad": {"$regex": query, "$options": "i"}}]}))
    return render_template('buscar_medico.html', medicos=medicos, query=query)

@app.route('/resultados')
@login_required
def resultados():
    flash('Sistema de resultados en mantenimiento.', 'warning')
    return redirect(url_for('index'))

@app.route('/cita/confirmar/<cita_id>')
def confirmar_asistencia(cita_id):
    mongo.db.citas.update_one({'_id': ObjectId(cita_id)}, {'$set': {'estado': 'Confirmada'}})
    flash('¡Gracias! Tu asistencia ha sido confirmada.', 'success')
    return redirect(url_for('index'))

@app.route('/cita/cancelar/<cita_id>')
def cancelar_asistencia(cita_id):
    # ... lógica de cancelación ...
    return redirect(url_for('index'))