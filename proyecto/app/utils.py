from . import mongo
from pymongo.errors import DuplicateKeyError
from bson.objectid import ObjectId
from datetime import datetime, timedelta
from langchain_core.messages import HumanMessage, AIMessage

chat_memories = {}

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

# --- FUNCIONES PARA EL CHATBOT ---

def obtener_horarios_disponibles_doctor(doctores, fecha_str):
    """
    Retorna una lista de horarios (HH:MM) disponibles para un doctor en una fecha específica.
    Esta función ahora está optimizada para manejar un solo doctor.
    """
    medico_db = mongo.db.medicos.find_one({'nombre': doctores[0]})
    if not medico_db: return []
    try: fecha_obj = datetime.strptime(fecha_str, '%Y-%m-%d').date()
    except (ValueError, TypeError): return []

    grupo = medico_db.get('grupo_turno', 1)
    inicio_h, fin_h = (8, 14) if (fecha_obj.isocalendar()[1] + grupo) % 2 == 0 else (14, 20)
    
    bloques_turno = set()
    hora_actual = datetime.min.replace(hour=inicio_h)
    while hora_actual.hour < fin_h:
        bloques_turno.add(hora_actual.strftime("%H:%M"))
        hora_actual += timedelta(minutes=30)

    citas_ocupadas = mongo.db.citas.find({'doctor': doctores[0], 'fecha': fecha_str}, {'hora': 1})
    horas_ocupadas = {c['hora'] for c in citas_ocupadas}
    
    return sorted(list(bloques_turno - horas_ocupadas))

def agendar_cita_bot(especialidad, doctor, fecha, hora, rut, nombre, email, user_id):
    """Inserta una reserva en MongoDB, llamada indirectamente por el LLM."""
    # Se elimina la comprobación previa (find_one) para evitar race conditions.
    cita_data = {
        'rut': rut.replace(".", "").upper(),
        'nombre': nombre,
        'email': email,
        'especialidad': especialidad,
        'doctor': doctor,
        'fecha': fecha,
        'hora': hora,
        'estado': 'Reservada',
        'resultados': [],
        'created_at': datetime.now()
    }
    
    cita_id = None
    try:
        # 1. Intentar insertar la cita. Falla si el índice único detecta un duplicado.
        result = mongo.db.citas.insert_one(cita_data)
        cita_id = result.inserted_id
        
        # 2. Actualizar el historial del paciente.
        cita_paciente = {'especialidad': especialidad, 'fecha': fecha, 'hora': hora, 'doctor': doctor, 'cita_id': str(cita_id)}
        mongo.db.pacientes.update_one({'_id': ObjectId(user_id)}, {'$push': {'atenciones.consultas_agendadas': cita_paciente}})
        
        return f"Éxito: Cita agendada para el {fecha} a las {hora}."
    except DuplicateKeyError:
        return "Error: El horario ya no está disponible. Por favor, pide al paciente que elija otra hora o fecha."
    except Exception as e:
        # 3. Rollback manual: si la actualización del paciente falla, se borra la cita creada.
        if cita_id:
            mongo.db.citas.delete_one({'_id': cita_id})
        return f"Error interno de base de datos: {str(e)}"

class CustomChatMemory:
    def __init__(self, k=5):
        self.k = k
        self.messages = []
    
    def add_user_message(self, msg):
        self.messages.append(HumanMessage(content=msg))
        self._trim()
        
    def add_ai_message(self, msg):
        self.messages.append(AIMessage(content=msg))
        self._trim()
        
    def _trim(self):
        if len(self.messages) > self.k * 2:
            self.messages = self.messages[-(self.k * 2):]

class SessionMemory:
    def __init__(self, k=5):
        self.chat_memory = CustomChatMemory(k)
        
    def clear(self):
        self.chat_memory.messages = []

def obtener_memoria_sesion(user_id):
    """Retorna la memoria de conversación para un usuario, creándola si no existe."""
    if user_id not in chat_memories:
        chat_memories[user_id] = SessionMemory(k=5)
    return chat_memories[user_id]

EVALUADOR_PROMPT = """Eres el Agente Evaluador de Síntomas de Clínica Salud.
Tu objetivo es escuchar los síntomas del paciente y recomendar a qué especialidad médica debería acudir.
IMPORTANTE: NO agendas citas. Si el paciente quiere agendar, responde algo como "Claro, te derivo con mi colega para agendar tu cita." y finaliza tu turno.
REGLA DE EXTENSIÓN: Tus respuestas deben ser MUY BREVES y directas (máximo 2-3 líneas)."""

SCHEDULER_PROMPT = """Eres el Agente de Agendamiento (Scheduler) de Clínica Salud.
Tienes a tu disposición herramientas para consultar doctores, consultar disponibilidad por especialidad y agendar citas.
Antes de tomar una decisión de reserva, verifica siempre la disponibilidad.

REGLA DE ERROR DE AGENDAMIENTO: Si la herramienta 'agendar_cita' devuelve un error de que el horario no está disponible, DEBES informar al paciente y preguntarle si desea elegir otra hora o buscar disponibilidad en otra fecha.

REGLA DE EXTENSIÓN: Tus respuestas deben ser MUY BREVES y directas (máximo 2-3 líneas).
REGLA DE AGENDAMIENTO: Cuando pidas confirmación para agendar, agrega EXACTAMENTE este HTML: <div class='mt-2'><button class='btn btn-sm btn-success chat-btn-reply' data-reply='Sí'>Sí</button> <button class='btn btn-sm btn-outline-danger chat-btn-reply' data-reply='No'>No</button></div>.
Si el paciente dice 'Sí' o confirma, DEBES usar la función 'agendar_cita'."""