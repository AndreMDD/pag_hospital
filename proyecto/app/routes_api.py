from flask import request, jsonify
from flask_login import login_required, current_user
from bson.objectid import ObjectId
from datetime import datetime, timedelta
from . import app, mongo

@app.route('/api/medicos')
def api_medicos():
    especialidad = request.args.get('especialidad')
    mapa = {'medicina_general': 'Medicina General', 'cardiologia': 'Cardiología', 'dermatologia': 'Dermatología', 'pediatria': 'Pediatría'}
    query = {'especialidad': mapa[especialidad]} if especialidad in mapa else {}
    medicos = list(mongo.db.medicos.find(query).sort('nombre', 1))
    return jsonify([m['nombre'] for m in medicos])

@app.route('/api/horarios-disponibles')
def api_horarios():
    doctor, fecha_str = request.args.get('doctor'), request.args.get('fecha')
    if not doctor or not fecha_str: return jsonify([])
    try: fecha_obj = datetime.strptime(fecha_str, '%Y-%m-%d').date()
    except ValueError: return jsonify([])
    medico_db = mongo.db.medicos.find_one({'nombre': doctor})
    grupo = medico_db.get('grupo_turno', 1) if medico_db else 1
    inicio_str, fin_str = ("08:00", "14:00") if (fecha_obj.isocalendar()[1] + grupo) % 2 == 0 else ("14:00", "20:00")
    bloques = []
    inicio, fin = datetime.strptime(inicio_str, "%H:%M"), datetime.strptime(fin_str, "%H:%M")
    while inicio < fin:
        bloques.append(inicio.strftime("%H:%M"))
        inicio += timedelta(minutes=30)
    horas_ocupadas = {c['hora'] for c in mongo.db.citas.find({'doctor': doctor, 'fecha': fecha_str})}
    return jsonify([hora for hora in bloques if hora not in horas_ocupadas])

@app.route('/get_history')
@login_required
def get_history():
    paciente = mongo.db.pacientes.find_one({'_id': ObjectId(current_user.id)})
    atenciones = paciente.get('atenciones', {})
    citas = atenciones.get('consultas_agendadas', [])
    inmediatas = atenciones.get('atenciones_inmediatas', [])
    citas.sort(key=lambda x: (x.get('fecha', ''), x.get('hora', '')), reverse=True)
    inmediatas.sort(key=lambda x: x.get('fecha_registro', ''), reverse=True)
    return jsonify({'citas': citas, 'inmediatas': inmediatas})