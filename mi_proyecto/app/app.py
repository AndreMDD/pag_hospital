from flask import Flask, render_template, redirect, url_for, flash, request, session, jsonify
from flask_pymongo import PyMongo
from flask_wtf import FlaskForm
from flask_mail import Mail, Message
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from wtforms import StringField, PasswordField, SubmitField, SelectField, DateField, TimeField
from wtforms.validators import DataRequired, Email, EqualTo
import os
from dotenv import load_dotenv
from datetime import date, time, datetime, timedelta
from bson.objectid import ObjectId
from pymongo.errors import DuplicateKeyError
import certifi
from langchain_classic.memory import ConversationBufferMemory
import random
from groq import Groq

# Cargar variables de entorno
load_dotenv()

app = Flask(__name__)

memory = ConversationBufferMemory()
# Configuración segura (en producción usar variables de entorno)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', os.urandom(24).hex())
app.config['ADMIN_PASSWORD'] = os.environ.get('ADMIN_PASSWORD') # Definir obligatoriamente en el archivo .env

# Seguridad de Sesión: Evitar acceso prolongado sin uso
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30) # La sesión expira tras 30 min de inactividad
app.config['SESSION_COOKIE_HTTPONLY'] = True # Protege las cookies de ataques XSS (robo de sesión por JS)

# Configuración MongoDB
# Tomamos la URI directamente de las variables de entorno. 
# Si no se provee, por defecto usará la base de datos 'hospital_central'
app.config['MONGO_URI'] = os.environ.get('MONGO_URI', 'mongodb://localhost:27017/hospital_central')

# Configuración Flask-Mail
app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = os.environ.get('MAIL_USE_TLS', 'True') == 'True'
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')

mail = Mail(app)

if 'mongodb+srv' in app.config['MONGO_URI']:
    mongo = PyMongo(app, tlsCAFile=certifi.where())
else:
    mongo = PyMongo(app)

# Crear índice único para evitar duplicados (Doctor + Fecha + Hora)
with app.app_context():
    try:
        mongo.db.citas.create_index([("doctor", 1), ("fecha", 1), ("hora", 1)], unique=True)
    except Exception as e:
        print(f"⚠️ Advertencia: No se pudo conectar a MongoDB al iniciar. Revisa tu MONGO_URI y conexión a internet. Detalles: {e}")

# Configuración Flask-Login
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# --- Interceptores (Hooks) de Seguridad ---
@app.after_request
def add_header(response):
    """
    Evita que el navegador guarde en caché las páginas.
    Previene el bug donde el usuario cierra sesión, presiona 'Atrás' y ve los datos de nuevo.
    """
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

@app.before_request
def check_session():
    # Habilita el tiempo límite (30 min) y lo renueva con cada clic/interacción que haga el usuario
    session.permanent = True

class User(UserMixin):
    def __init__(self, user_data):
        self.id = str(user_data['_id'])
        self.rut = user_data['rut']
        self.nombre = user_data.get('nombre_completo', user_data.get('nombre'))
        self.email = user_data.get('contacto', {}).get('email') if 'contacto' in user_data else user_data.get('email')

@login_manager.user_loader
def load_user(user_id):
    user_data = mongo.db.pacientes.find_one({"_id": ObjectId(user_id)})
    return User(user_data) if user_data else None

# --- Helpers ---
def validar_rut(rut):
    """Valida el formato y dígito verificador del RUT chileno."""
    rut = rut.replace(".", "").replace("-", "").upper()
    if len(rut) < 2: return False
    cuerpo, dv = rut[:-1], rut[-1]
    try:
        reverso = map(int, reversed(str(cuerpo)))
        factors = [2, 3, 4, 5, 6, 7]
        s = sum(d * factors[i % 6] for i, d in enumerate(reverso))
        res = 11 - (s % 11)
        expected_dv = 'K' if res == 10 else '0' if res == 11 else str(res)
        return dv == expected_dv
    except ValueError:
        return False

# --- Formularios (Flask-WTF) ---
class LoginForm(FlaskForm):
    username = StringField('Usuario o RUT', validators=[DataRequired()])
    password = PasswordField('Contraseña', validators=[DataRequired()])
    submit = SubmitField('Ingresar')

class RegistroForm(FlaskForm):
    rut = StringField('RUT', validators=[DataRequired()])
    nombre = StringField('Nombre Completo', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    nameUser = StringField('Nombre de Usuario', validators=[DataRequired()])
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

# --- Rutas ---

@app.route('/')
def index():
    return render_template('index.html', title="Inicio")

@app.route('/reservar', methods=['GET', 'POST'])
@login_required
def reservar():
    form = ReservaForm()
    if form.validate_on_submit():
        # 0. Validaciones de Negocio (Fecha y Hora)
        if form.fecha.data < date.today():
            flash('Error: No se pueden reservar horas en fechas pasadas.', 'danger')
            return render_template('reservar.html', form=form)
        
        # Horario laboral: 08:00 a 20:00
        try:
            hora_obj = datetime.strptime(form.hora.data, '%H:%M').time()
            if not (time(8, 0) <= hora_obj <= time(20, 0)):
                flash('Error: El horario de atención es de 08:00 a 20:00 hrs.', 'danger')
                return render_template('reservar.html', form=form)
        except (ValueError, TypeError):
            flash('Error: Formato de hora inválido.', 'danger')
            return render_template('reservar.html', form=form)

        # 1. Validar RUT
        if not validar_rut(form.rut.data):
            flash('El RUT ingresado no es válido. Verifique el formato y dígito verificador.', 'danger')
            return render_template('reservar.html', form=form)
        
        # Validar disponibilidad real en base de datos (doble chequeo)
        cita_existente = mongo.db.citas.find_one({
            'doctor': form.doctor.data,
            'fecha': str(form.fecha.data),
            'hora': form.hora.data
        })
        if cita_existente:
            flash('Lo sentimos, ese horario acaba de ser ocupado. Por favor elija otro.', 'warning')
            return render_template('reservar.html', form=form)

        # 2. Crear documento para MongoDB
        cita = {
            'rut': form.rut.data.replace(".", "").upper(), # Guardamos limpio
            'nombre': form.nombre.data,
            'email': form.email.data,
            'especialidad': dict(form.especialidad.choices).get(form.especialidad.data),
            'doctor': form.doctor.data,
            'fecha': str(form.fecha.data),
            'hora': form.hora.data,
            'estado': 'Reservada',
            'resultados': [],
            'created_at': datetime.now() # Timestamp automático
        }
        
        # 3. Insertar en colección 'citas'
        try:
            mongo.db.citas.insert_one(cita)
            
            # Actualizar documento del paciente con la nueva estructura
            cita_paciente = {
                'especialidad': dict(form.especialidad.choices).get(form.especialidad.data),
                'fecha': str(form.fecha.data),
                'hora': form.hora.data,
                'doctor': form.doctor.data
            }
            mongo.db.pacientes.update_one({'_id': ObjectId(current_user.id)}, {'$push': {'atenciones.consultas_agendadas': cita_paciente}})
            
            # 4. Enviar correo de confirmación
            try:
                msg = Message('Confirmación de Reserva - Clínica Salud',
                              sender=app.config.get('MAIL_USERNAME'),
                              recipients=[cita['email']])
                # Renderizamos el HTML del correo
                msg.html = render_template('email_confirmation.html', cita=cita)
                mail.send(msg)
                flash(f'Reserva agendada con éxito. Se ha enviado un correo de confirmación a {cita["email"]}.', 'success')
            except Exception as e:
                print(f"Error enviando correo: {e}")
                flash(f'Reserva agendada, pero hubo un error enviando el correo de confirmación.', 'warning')
                
            return redirect(url_for('mis_citas'))
        except DuplicateKeyError:
            flash('Lo sentimos, el horario seleccionado acaba de ser reservado por otra persona. Por favor intente con otro horario.', 'danger')
            return render_template('reservar.html', form=form)
        except Exception as e:
            flash('Error al conectar con la base de datos.', 'danger')
            print(e)
            
    return render_template('reservar.html', form=form)

# API para obtener médicos por especialidad
@app.route('/api/medicos')
def api_medicos():
    especialidad = request.args.get('especialidad')
    
    # Mapa para traducir del valor del formulario a la BD
    mapa_especialidades = {
        'medicina_general': 'Medicina General',
        'cardiologia': 'Cardiología',
        'dermatologia': 'Dermatología',
        'pediatria': 'Pediatría'
    }
    
    query = {}
    if especialidad and especialidad in mapa_especialidades:
        query['especialidad'] = mapa_especialidades[especialidad]
    
    medicos = list(mongo.db.medicos.find(query).sort('nombre', 1))
    return jsonify([m['nombre'] for m in medicos])

# API para obtener horarios disponibles dinámicamente
@app.route('/api/horarios-disponibles')
def api_horarios():
    doctor = request.args.get('doctor')
    fecha_str = request.args.get('fecha')
    
    if not doctor or not fecha_str:
        return jsonify([])

    try:
        fecha_obj = datetime.strptime(fecha_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify([])

    # 1. Obtener el grupo del doctor y calcular el turno rotativo
    medico_db = mongo.db.medicos.find_one({'nombre': doctor})
    grupo = medico_db.get('grupo_turno', 1) if medico_db else 1
    
    # isocalendar()[1] devuelve el número de semana del año (las semanas empiezan el lunes).
    # Esto hace que el domingo en la madrugada cambie automáticamente al nuevo turno.
    semana_del_anio = fecha_obj.isocalendar()[1]
    
    # Si la suma es par, turno mañana (08:00 a 14:00). Si es impar, turno tarde (14:00 a 20:00).
    if (semana_del_anio + grupo) % 2 == 0:
        inicio_str, fin_str = "08:00", "14:00"
    else:
        inicio_str, fin_str = "14:00", "20:00"

    # 2. Generar todos los bloques horarios para el turno correspondiente
    bloques = []
    inicio = datetime.strptime(inicio_str, "%H:%M")
    fin = datetime.strptime(fin_str, "%H:%M")
    delta = timedelta(minutes=30)
    
    while inicio < fin:
        bloques.append(inicio.strftime("%H:%M"))
        inicio += delta

    # 3. Buscar horas ocupadas en BD
    citas_ocupadas = mongo.db.citas.find({'doctor': doctor, 'fecha': fecha_str})
    horas_ocupadas = [c['hora'] for c in citas_ocupadas]

    # 4. Filtrar disponibles
    disponibles = [hora for hora in bloques if hora not in horas_ocupadas]
    
    return jsonify(disponibles)

# Ruta para procesar el formulario de búsqueda del Home
@app.route('/consultar', methods=['POST'])
def consultar():
    rut = request.form.get('rut_consulta')
    if rut:
        # Redirigir al login si intenta consultar (ahora es privado)
        flash('Por seguridad, debes iniciar sesión para ver tus citas.', 'info')
        return redirect(url_for('login'))
    return redirect(url_for('index'))

@app.route('/mis-citas')
@login_required
def mis_citas():
    # Ahora solo renderizamos la vista. El JS se encargará de pedir los datos.
    return render_template('mis_citas.html')

@app.route('/get_history')
@login_required
def get_history():
    # API para alimentar la columna visual (Historial)
    paciente = mongo.db.pacientes.find_one({'_id': ObjectId(current_user.id)})
    atenciones = paciente.get('atenciones', {})
    
    citas = atenciones.get('consultas_agendadas', [])
    inmediatas = atenciones.get('atenciones_inmediatas', [])
    
    citas.sort(key=lambda x: x.get('fecha', '') + x.get('hora', ''), reverse=True)
    inmediatas.sort(key=lambda x: x.get('fecha_registro', ''), reverse=True)
    
    return jsonify({'citas': citas, 'inmediatas': inmediatas})

# --- MEMORIA Y PROMPT DE SISTEMA ---
chat_memories = {}

def obtener_memoria_sesion(user_id):
    # Short-term memory: Retiene todas las interacciones de la sesión
    if user_id not in chat_memories:
        chat_memories[user_id] = ConversationBufferMemory(return_messages=True)
    return chat_memories[user_id]

SYSTEM_PROMPT = """Eres una IA Orquestadora de 3 agentes de salud. Sigue estas reglas estrictamente para EVITAR SESGOS:

1. TRIAGE (Neutralidad): No asumas diagnósticos pasados. Si el paciente menciona un síntoma nuevo, descarta tu análisis anterior y evalúa desde cero (Evita Sesgo de Anclaje).
2. RECORD KEEPER (Validación): Usa el historial del paciente solo como REFERENCIA. Pregunta siempre si desean mantener sus preferencias previas o cambiarlas.
3. SCHEDULER (Diversidad): Sugiere doctores de forma rotativa. NO ofrezcas siempre al mismo médico solo por estar de primero en la lista (Evita Sesgo de Disponibilidad).

REGLA DE EXTENSIÓN: Tus respuestas deben ser MUY BREVES, genéricas y directas al grano (máximo 2-3 líneas). No des explicaciones largas.
REGLA DE CONFIRMACIÓN: Cuando le preguntes al paciente para confirmar una acción (ej: "¿Estás seguro de agendar con el Dr. Pérez?"), DEBES agregar OPCIONES INTERACTIVAS usando EXACTAMENTE este bloque HTML al final de tu respuesta: <div class='mt-2'><button class='btn btn-sm btn-success chat-btn-reply' data-reply='Sí'>Sí</button> <button class='btn btn-sm btn-outline-danger chat-btn-reply' data-reply='No'>No</button></div>

Recuerda: Cuestiona tus propias suposiciones antes de emitir tu respuesta final.
"""

@app.route('/chat_endpoint', methods=['POST'])
@login_required
def chat_endpoint():
    data = request.get_json()
    mensaje = data.get('message', '').lower()
    user_id = str(current_user.id)
    
    # Cargar Memoria de Sesión (Short-term)
    memoria = obtener_memoria_sesion(user_id)
    
    # ==========================================
    # REGLA DE ORO: Alerta inmediata ante palabras de emergencia (Determinista)
    # ==========================================
    emergencias = ['infarto', 'hemorragia', 'inconsciencia', 'ahogo', 'pecho', 'sangre']
    if any(palabra in mensaje for palabra in emergencias):
        alerta = "🚨 <strong>ALERTA DE EMERGENCIA: DIRÍJASE A URGENCIAS INMEDIATAMENTE.</strong><br>Sus síntomas indican un riesgo vital. No espere por una cita."
        return jsonify({"response": alerta, "agent": "Medical Matcher"})
        
    # ==========================================
    # RESET DE CONTEXTO MÉDICO (Mitigación Sesgo de Anclaje)
    # ==========================================
    palabras_reset = ['olvida', 'me equivoqué', 'cambio de síntoma', 'ahora siento', 'distinto']
    if any(p in mensaje for p in palabras_reset):
        memoria.clear()
        respuesta_reset = "🔄 <strong>Triage:</strong> He borrado el contexto clínico anterior de mi memoria para mantener una evaluación neutral. Por favor, descríbeme tus nuevos síntomas desde cero."
        memoria.chat_memory.add_ai_message(respuesta_reset)
        return jsonify({"response": respuesta_reset, "agent": "Triage Matcher"})

    # Añadir mensaje del usuario a la memoria ANTES de llamar a Groq
    memoria.chat_memory.add_user_message(mensaje)

    # Extraer contexto Long-Term de MongoDB para pasárselo al LLM (RAG Básico)
    paciente = mongo.db.pacientes.find_one({'_id': ObjectId(current_user.id)})
    seguro = paciente.get('convenio', 'Fonasa / Isapre (Asociado)')
    
    citas = paciente.get('atenciones', {}).get('consultas_agendadas', [])
    futuras = [c for c in citas if c['fecha'] >= str(date.today())]
    futuras.sort(key=lambda x: x['fecha'] + x['hora'])
    futuras_str = "Ninguna cita agendada." if not futuras else f"{futuras[0]['fecha']} a las {futuras[0]['hora']} con el {futuras[0]['doctor']} para {futuras[0]['especialidad'].replace('_', ' ')}"
    
    # Obtener catálogo de doctores (Mitigación de sesgo de disponibilidad)
    todos_medicos = list(mongo.db.medicos.find({}, {'_id': 0, 'nombre': 1, 'especialidad': 1}))
    random.shuffle(todos_medicos)
    medicos_str = ", ".join([f"{m['nombre']} ({m['especialidad']})" for m in todos_medicos])
    
    # ==========================================
    # PROCESAMIENTO DEL LLM VIA GROQ
    # ==========================================
    contexto_sistema = f"{SYSTEM_PROMPT}\n\n"
    contexto_sistema += f"CONTEXTO RESTRINGIDO DEL PACIENTE (SOLO USA ESTO SI TE LO PREGUNTA):\n"
    contexto_sistema += f"- Nombre: {current_user.nombre.split()[0]}\n"
    contexto_sistema += f"- Convenio/Seguro Activo: {seguro}\n"
    contexto_sistema += f"- Próxima Cita Médica: {futuras_str}\n\n"
    contexto_sistema += f"CATÁLOGO DE MÉDICOS (DISPONIBILIDAD ACTUAL):\n{medicos_str}\n\n"
    contexto_sistema += "INSTRUCCIONES DE FORMATO:\n- Responde de forma MUY CORTA.\n- Usa etiquetas HTML básicas (<strong>, <br>).\n- Firma tu respuesta indicando qué agente eres (ej: '<em>- Atte. Triage</em>').\n- Si pides confirmación, SIEMPRE incluye los botones HTML indicados en el prompt."
    
    mensajes_llm = [{"role": "system", "content": contexto_sistema}]
    
    # Inyectar el historial de chat (Ventana de memoria)
    for msg in memoria.chat_memory.messages:
        role = "user" if msg.type == "human" else "assistant"
        mensajes_llm.append({"role": role, "content": msg.content})

    try:
        # Inicializar cliente Groq
        groq_client = Groq(api_key=os.environ.get('GROQ_API_KEY'))
        
        chat_completion = groq_client.chat.completions.create(
            messages=mensajes_llm,
            model="llama-3.3-70b-versatile", # Modelo de Meta actualizado
            temperature=0.3, # Temperatura baja para que no alucine información médica
            max_tokens=800
        )
        respuesta_ia = chat_completion.choices[0].message.content
        
        # Guardar la respuesta en la memoria de la IA
        memoria.chat_memory.add_ai_message(respuesta_ia)
        return jsonify({"response": respuesta_ia, "agent": "Red de Agentes IA (Groq)"})
        
    except Exception as e:
        print(f"Error procesando LLM Groq: {e}")
        fallback = "Lo siento, la conexión con mi modelo de lenguaje está fallando. Verifica tu GROQ_API_KEY y conexión."
        return jsonify({"response": fallback, "agent": "Sistema Central"})

@app.route('/resultados')
@login_required
def resultados():
    # Aquí iría la lógica de visualización de exámenes
    flash('Sistema de resultados en mantenimiento.', 'warning')
    return redirect(url_for('index'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        # Validación simple de administrador (Usuario: admin)
        if form.username.data == "admin" and app.config.get('ADMIN_PASSWORD') and form.password.data == app.config['ADMIN_PASSWORD']:
            session['admin_logged_in'] = True
            flash('Bienvenido al Panel de Administración.', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            # Lógica de Login Paciente
            rut_limpio = form.username.data.replace(".", "").replace("-", "").upper()
            user_data = mongo.db.pacientes.find_one({'rut': rut_limpio})
            
            if user_data and check_password_hash(user_data['password'], form.password.data):
                user = User(user_data)
                login_user(user)
                flash('Has iniciado sesión correctamente.', 'success')
                return redirect(url_for('mis_citas'))
            else:
                flash('RUT o contraseña incorrectos.', 'danger')
    
    return render_template('login.html', form=form, title="Inicio de Sesión Clínica Salud")

@app.route('/registro', methods=['GET', 'POST'])
def registro():
    form = RegistroForm()
    if form.validate_on_submit():
        rut_limpio = form.rut.data.replace(".", "").replace("-", "").upper()
        
        # Verificar si ya existe
        if mongo.db.pacientes.find_one({'rut': rut_limpio}):
            flash('El RUT ya está registrado.', 'warning')
        else:
            hashed_password = generate_password_hash(form.password.data)
            new_user_data = {
                'rut': rut_limpio,
                'nombre_completo': form.nombre.data,
                'nameUser': form.nameUser.data,
                'contacto': {
                    'email': form.email.data,
                    'celular': '' # Se puede agregar al formulario posteriormente
                },
                'password': hashed_password,
                'atenciones': {
                    'consultas_agendadas': [],
                    'atenciones_inmediatas': []
                },
                'examenes_disponibles': []
            }
            result = mongo.db.pacientes.insert_one(new_user_data)
            new_user_data['_id'] = result.inserted_id
            login_user(User(new_user_data))
            flash('Cuenta creada exitosamente. Bienvenido.', 'success')
            return redirect(url_for('mis_citas'))
            
    return render_template('registro.html', form=form)

@app.route('/buscar-medico', methods=['GET', 'POST'])
@login_required
def buscar_medico():
    medicos = []
    query = request.form.get('query', '')
    if query:
        # Búsqueda insensible a mayúsculas/minúsculas por nombre o especialidad
        regex_query = {"$regex": query, "$options": "i"}
        medicos = list(mongo.db.medicos.find({
            "$or": [{"nombre": regex_query}, {"especialidad": regex_query}]
        }))
    return render_template('buscar_medico.html', medicos=medicos, query=query)

@app.route('/admin')
def admin_dashboard():
    if not session.get('admin_logged_in'):
        flash('Acceso denegado. Por favor inicie sesión.', 'warning')
        return redirect(url_for('login'))
    
    query = request.args.get('q')
    if query:
        # Búsqueda por RUT o Nombre (insensible a mayúsculas)
        regex_query = {"$regex": query, "$options": "i"}
        citas = list(mongo.db.citas.find({
            "$or": [{"rut": regex_query}, {"nombre": regex_query}]
        }).sort('fecha', 1))
        titulo = f"Resultados de búsqueda para: '{query}'"
    else:
        # Por defecto: Buscar citas de HOY
        citas = list(mongo.db.citas.find({'fecha': str(date.today())}).sort('hora', 1))
        titulo = f"Citas programadas para hoy: {date.today()}"

    return render_template('admin.html', citas=citas, titulo=titulo)

@app.route('/admin/cancelar/<cita_id>')
def cancelar_cita(cita_id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('login'))
    
    # Eliminar la cita por su ID
    mongo.db.citas.delete_one({'_id': ObjectId(cita_id)})
    flash('La cita ha sido cancelada exitosamente.', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/cita/confirmar/<cita_id>')
def confirmar_asistencia(cita_id):
    try:
        mongo.db.citas.update_one(
            {'_id': ObjectId(cita_id)},
            {'$set': {'estado': 'Confirmada'}}
        )
        flash('¡Gracias! Tu asistencia ha sido confirmada exitosamente.', 'success')
    except Exception as e:
        flash('Ocurrió un error al confirmar la cita.', 'danger')
    return redirect(url_for('index'))

@app.route('/cita/cancelar/<cita_id>')
def cancelar_asistencia(cita_id):
    try:
        cita = mongo.db.citas.find_one({'_id': ObjectId(cita_id)})
        if cita:
            # Eliminar de la colección de citas para liberar el horario
            mongo.db.citas.delete_one({'_id': ObjectId(cita_id)})
            # Opcional: Eliminar también del historial del paciente si se desea mantener sincronizado
            mongo.db.pacientes.update_one({'rut': cita['rut']}, {'$pull': {'atenciones.consultas_agendadas': {'fecha': cita['fecha'], 'hora': cita['hora']}}})
            flash('Tu cita ha sido cancelada correctamente.', 'info')
        else:
            flash('La cita no existe o ya fue cancelada.', 'warning')
    except Exception as e:
        flash('Ocurrió un error al cancelar la cita.', 'danger')
    return redirect(url_for('index'))

@app.route('/logout')
def logout():
    logout_user()
    session.pop('admin_logged_in', None)
    flash('Sesión cerrada correctamente.', 'info')
    return redirect(url_for('index'))

# Rutas adicionales del menú para evitar errores 404
@app.route('/especialidades')
@login_required
def especialidades(): return redirect(url_for('index'))

@app.route('/servicios')
@login_required
def servicios(): return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)