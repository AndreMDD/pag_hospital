from flask import request, jsonify, abort
from functools import wraps
from bson import json_util
import json

from . import app, mongo

def require_api_key(f):
    """
    Decorador para proteger rutas con una clave de API.
    La clave debe ser enviada en la cabecera 'X-API-KEY'.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = app.config.get('POWERBI_API_KEY')
        # Comprobar que la clave de la app existe y que el request la incluye
        if not api_key or request.headers.get('X-API-KEY') != api_key:
            abort(401, description="Acceso no autorizado. Se requiere una clave de API válida.")
        return f(*args, **kwargs)
    return decorated_function

@app.route('/api/dashboard/citas', methods=['GET'])
@require_api_key
def get_citas_dashboard():
    """
    Endpoint protegido que retorna todas las citas de la base de datos.
    Ideal para ser consumido por herramientas de BI como Power BI.
    """
    try:
        # Obtenemos todas las citas de la colección
        citas = list(mongo.db.citas.find({}))
        
        # Usamos json_util de BSON para serializar correctamente los datos de MongoDB (como ObjectId y fechas)
        response_data = json.loads(json_util.dumps(citas))
        
        return jsonify(response_data)
    except Exception as e:
        return jsonify({"error": "Ocurrió un error al consultar los datos", "detalle": str(e)}), 500

@app.route('/api/dashboard/stats', methods=['GET'])
@require_api_key
def get_dashboard_stats():
    """
    Endpoint protegido que retorna datos agregados sobre las citas usando un pipeline de MongoDB.
    Agrupa las citas por especialidad y estado para obtener un conteo.
    """
    try:
        # Pipeline de agregación para contar citas por especialidad y estado
        pipeline = [
            {
                # Agrupar por la combinación de especialidad y estado
                "$group": {
                    "_id": {
                        "especialidad": "$especialidad",
                        "estado": "$estado"
                    },
                    "count": { "$sum": 1 }
                }
            },
            {
                # Re-agrupar por especialidad para anidar los resultados de estado
                "$group": {
                    "_id": "$_id.especialidad",
                    "estadisticas_estado": {
                        "$push": {
                            "estado": "$_id.estado",
                            "cantidad": "$count"
                        }
                    },
                    "total_citas": { "$sum": "$count" }
                }
            },
            { "$sort": { "total_citas": -1 } } # Ordenar por las especialidades con más citas
        ]
        stats_data = list(mongo.db.citas.aggregate(pipeline))
        return jsonify(json.loads(json_util.dumps(stats_data)))
    except Exception as e:
        return jsonify({"error": "Ocurrió un error al procesar la agregación", "detalle": str(e)}), 500