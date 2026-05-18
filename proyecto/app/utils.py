from . import mongo, chat_memories
from pymongo.errors import DuplicateKeyError
from bson.objectid import ObjectId
from datetime import datetime
from langchain.memory import ConversationBufferWindowMemory

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

def agendar_cita_bot(especialidad, doctor, fecha, hora, rut, nombre, email, user_id):
    """Inserta una reserva en MongoDB, llamada indirectamente por el LLM."""
    cita_existente = mongo.db.citas.find_one({
        'doctor': doctor, 'fecha': fecha, 'hora': hora
    })
    if cita_existente:
        return "Error: El horario ya está ocupado. Dile al paciente que elija otra hora o fecha."
        
    cita = {
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
    
    try:
        mongo.db.citas.insert_one(cita)
        cita_paciente = {'especialidad': especialidad, 'fecha': fecha, 'hora': hora, 'doctor': doctor}
        mongo.db.pacientes.update_one({'_id': ObjectId(user_id)}, {'$push': {'atenciones.consultas_agendadas': cita_paciente}})
        return f"Éxito: Cita agendada para el {fecha} a las {hora}."
    except DuplicateKeyError:
        return "Error: Colisión detectada, el horario acaba de ser ocupado."
    except Exception as e:
        return f"Error interno de base de datos: {str(e)}"

def obtener_memoria_sesion(user_id):
    """Retorna la memoria de conversación para un usuario, creándola si no existe."""
    if user_id not in chat_memories:
        # Memoria a corto plazo adaptativa: retiene los últimos 5 intercambios
        chat_memories[user_id] = ConversationBufferWindowMemory(k=5, return_messages=True, memory_key="chat_history")
    return chat_memories[user_id]

SYSTEM_PROMPT = """Eres una IA Orquestadora de 3 agentes de salud (Triage, Record Keeper y Scheduler) operando bajo LangChain.
Tienes a tu disposición herramientas para consultar doctores, revisar el historial del paciente (Memoria a Largo Plazo) y agendar citas.

Usa tus herramientas para planificar y adaptarte a lo que pide el paciente. Antes de tomar una decisión de reserva, verifica siempre la disponibilidad y el historial si es relevante.

REGLA DE EXTENSIÓN: Tus respuestas deben ser MUY BREVES y directas (máximo 2-3 líneas).
REGLA DE AGENDAMIENTO: Cuando pidas confirmación para agendar, agrega EXACTAMENTE este HTML: <div class='mt-2'><button class='btn btn-sm btn-success chat-btn-reply' data-reply='Sí'>Sí</button> <button class='btn btn-sm btn-outline-danger chat-btn-reply' data-reply='No'>No</button></div>. Si el paciente dice 'Sí', DEBES usar la función 'agendar_cita'.
"""