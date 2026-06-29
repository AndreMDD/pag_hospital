from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from bson.objectid import ObjectId
from pymongo.errors import DuplicateKeyError, WriteError
from datetime import date, datetime
from flask_mail import Message

from . import app, mongo, mail
from .forms import ReservaForm

@app.route('/reservar', methods=['GET', 'POST'])
@login_required
def reservar():
    form = ReservaForm()
    if form.validate_on_submit():
        if form.fecha.data < date.today():
            flash('Error: No se pueden reservar horas en fechas pasadas.', 'danger')
            return redirect(url_for('reservar'))

        # 1. Refactorización: Usar datos del usuario autenticado en lugar del formulario para mayor seguridad.
        # 2. Refactorización: La validación de RUT, nombre y email ya no es necesaria aquí si usamos current_user.
        cita_data = {
            'rut': current_user.rut,
            'nombre': current_user.nombre,
            'email': current_user.email,
            'especialidad': dict(form.especialidad.choices).get(form.especialidad.data),
            'doctor': form.doctor.data,
            'fecha': form.fecha.data.strftime('%Y-%m-%d'),
            'hora': form.hora.data,
            'estado': 'Reservada',
            'resultados': [],
            'created_at': datetime.now()
        }

        # 3. Seguridad y Refactorización: Se elimina la comprobación manual previa (find_one).
        # Se confía en un índice único en la BD (`doctor`, `fecha`, `hora`) y se captura el error.
        # Esto previene "race conditions" de forma robusta.
        cita_id = None
        try:
            result = mongo.db.citas.insert_one(cita_data)
            cita_id = result.inserted_id
            # 4. Integridad de datos: Se intenta actualizar el historial del paciente.
            mongo.db.pacientes.update_one({'_id': ObjectId(current_user.id)}, {'$push': {'atenciones.consultas_agendadas': {'especialidad': cita_data['especialidad'], 'fecha': cita_data['fecha'], 'hora': cita_data['hora'], 'doctor': cita_data['doctor']}}})
            try:
                msg = Message('Confirmación de Reserva', sender=app.config.get('MAIL_USERNAME'), recipients=[cita_data['email']])
                msg.html = render_template('email_confirmation.html', cita=cita_data)
                mail.send(msg)
                flash(f'Reserva agendada con éxito.', 'success')
            except Exception: flash(f'Reserva agendada, pero hubo un error enviando el correo.', 'warning')
            return redirect(url_for('mis_citas'))
        except DuplicateKeyError:
            flash('Lo sentimos, el horario seleccionado acaba de ser ocupado. Por favor, elija otro.', 'warning')
        except WriteError as e:
            # 5. Integridad de datos: Si falla la escritura en el historial del paciente, se borra la cita creada (rollback manual).
            if cita_id: mongo.db.citas.delete_one({'_id': cita_id})
            flash(f'Error al asociar la cita a tu historial. Inténtalo de nuevo. Detalle: {e}', 'danger')
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