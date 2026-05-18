from flask_login import UserMixin
from bson.objectid import ObjectId
from . import login_manager, mongo

class User(UserMixin):
    """Modelo de usuario para Flask-Login."""
    def __init__(self, user_data):
        self.id = str(user_data['_id'])
        self.rut = user_data['rut']
        self.nombre = user_data.get('nombre_completo', user_data.get('nombre'))
        self.email = user_data.get('email')

@login_manager.user_loader
def load_user(user_id):
    """Carga un usuario desde la base de datos para la sesión de Flask-Login."""
    user_data = mongo.db.pacientes.find_one({"_id": ObjectId(user_id)})
    return User(user_data) if user_data else None