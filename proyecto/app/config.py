import os
from dotenv import load_dotenv
from datetime import timedelta

# El README indica que el archivo .env se encuentra en la carpeta 'app/'
load_dotenv()

class Config:
    """
    Clase de configuración para la aplicación Flask.
    Carga las variables desde un archivo .env o usa valores por defecto seguros.
    """
    # Clave secreta para proteger sesiones, cookies y otros datos de seguridad
    SECRET_KEY = os.environ.get('SECRET_KEY', os.urandom(24).hex())
    
    # Contraseña para el panel de administración (debe estar en .env)
    ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD')

    # Configuración de seguridad y duración de la sesión de usuario
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=30) # Cierra sesión tras 30 min de inactividad
    SESSION_COOKIE_HTTPONLY = True # Previene acceso a la cookie de sesión desde JavaScript (ataques XSS)

    # URI de conexión para la base de datos MongoDB
    MONGO_URI = os.environ.get('MONGO_URI', 'mongodb://localhost:27017/hospital_central')

    # Configuración de Flask-Mail para el envío de correos (ej. con Gmail)
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'True') == 'True'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD') # Se recomienda usar una contraseña de aplicación

    # API Key para el servicio de IA (Groq)
    GROQ_API_KEY = os.environ.get('GROQ_API_KEY')