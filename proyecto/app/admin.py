from flask import render_template, redirect, url_for, flash, request, session
from bson.objectid import ObjectId
from datetime import date
from .. import app, mongo

@app.route('/admin')
def admin_dashboard():
    if not session.get('admin_logged_in'):
        flash('Acceso denegado. Por favor inicie sesión.', 'warning')
        return redirect(url_for('login'))
    query = request.args.get('q')
    if query:
        citas = list(mongo.db.citas.find({"$or": [{"rut": {"$regex": query, "$options": "i"}}, {"nombre": {"$regex": query, "$options": "i"}}]}).sort('fecha', 1))
        titulo = f"Resultados de búsqueda para: '{query}'"
    else:
        citas = list(mongo.db.citas.find({'fecha': str(date.today())}).sort('hora', 1))
        titulo = f"Citas programadas para hoy: {date.today()}"
    return render_template('admin.html', citas=citas, titulo=titulo)

@app.route('/admin/cancelar/<cita_id>')
def cancelar_cita(cita_id):
    if not session.get('admin_logged_in'): return redirect(url_for('login'))
    mongo.db.citas.delete_one({'_id': ObjectId(cita_id)})
    flash('La cita ha sido cancelada.', 'success')
    return redirect(url_for('admin_dashboard'))