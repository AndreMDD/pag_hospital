from flask import Flask
from flask_pymongo import PyMongo
from flask_mail import Mail
from flask_login import LoginManager
from .config import Config

# 1. Inicializar la aplicación
app = Flask(__name__)
app.config.from_object(Config)

# 2. Inicializar extensiones
mongo = PyMongo(app)
mail = Mail(app)

login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'

# 3. Importar los controladores al final para evitar importaciones circulares
# (Asegúrate de importar solo los archivos que conservaste al limpiar los duplicados)
from . import main, auth, chatbot, citas, admin, api