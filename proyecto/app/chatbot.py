from flask import request, jsonify
from flask_login import login_required, current_user
from bson.objectid import ObjectId
from datetime import date
import os
import random
from langchain_groq import ChatGroq
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import tool
from .. import app, mongo
from ..utils import agendar_cita_bot, obtener_memoria_sesion, SYSTEM_PROMPT

@app.route('/chat_endpoint', methods=['POST'])
@login_required
def chat_endpoint():
    data = request.get_json()
    mensaje = data.get('message', '').lower()
    user_id = str(current_user.id)
    memoria_chat = obtener_memoria_sesion(user_id)
    
    emergencias = ['infarto', 'hemorragia', 'inconsciencia', 'ahogo', 'pecho', 'sangre']
    if any(palabra in mensaje for palabra in emergencias):
        alerta = "🚨 <strong>ALERTA DE EMERGENCIA: DIRÍJASE A URGENCIAS INMEDIATAMENTE.</strong><br>Sus síntomas indican un riesgo vital."
        return jsonify({"response": alerta, "agent": "Medical Matcher"})
        
    if any(p in mensaje for p in ['olvida', 'me equivoqué', 'cambio de síntoma', 'distinto']):
        memoria_chat.clear()
        respuesta_reset = "🔄 He borrado el contexto. Por favor, descríbeme tus nuevos síntomas."
        memoria_chat.chat_memory.add_ai_message(respuesta_reset)
        return jsonify({"response": respuesta_reset, "agent": "Triage Matcher"})

    paciente = mongo.db.pacientes.find_one({'_id': ObjectId(current_user.id)})
    citas_pasadas = paciente.get('atenciones', {}).get('consultas_agendadas', [])
    futuras = [c for c in citas_pasadas if c.get('fecha') and c['fecha'] >= str(date.today())]
    futuras.sort(key=lambda x: (x['fecha'], x['hora']))
    futuras_str = "Ninguna." if not futuras else f"{futuras[0]['fecha']} a las {futuras[0]['hora']} con {futuras[0]['doctor']}"
    
    todos_medicos = list(mongo.db.medicos.find({}, {'_id': 0, 'nombre': 1, 'especialidad': 1}))
    random.shuffle(todos_medicos)
    medicos_str = ", ".join([f"{m['nombre']} ({m['especialidad']})" for m in todos_medicos])
    
    contexto_sistema = f"{SYSTEM_PROMPT}\n\nCONTEXTO:\n- Nombre: {current_user.nombre.split()[0]}\n- Próxima Cita: {futuras_str}\n\nMÉDICOS:\n{medicos_str}"
    
    try:
        @tool
        def agendar_cita(especialidad: str, doctor: str, fecha: str, hora: str) -> str:
            """Escribe en la BD para agendar una cita. Formatos: YYYY-MM-DD, HH:MM."""
            return agendar_cita_bot(especialidad, doctor, fecha, hora, current_user.rut, current_user.nombre, current_user.email, user_id)
            
        @tool
        def consultar_doctores(especialidad: str) -> str:
            """Consulta en la BD los doctores disponibles."""
            medicos = list(mongo.db.medicos.find({"especialidad": {"$regex": especialidad, "$options": "i"}}))
            return "Doctores disponibles: " + ", ".join([f"{m['nombre']} ({m['especialidad']})" for m in medicos]) if medicos else "No encontrados."

        tools = [agendar_cita, consultar_doctores]
        llm = ChatGroq(api_key=os.environ.get('GROQ_API_KEY'), model="llama-3.3-70b-versatile", temperature=0.3)
        prompt = ChatPromptTemplate.from_messages([("system", contexto_sistema), MessagesPlaceholder(variable_name="chat_history"), ("human", "{input}"), MessagesPlaceholder(variable_name="agent_scratchpad")])
        agent_executor = AgentExecutor(agent=create_tool_calling_agent(llm, tools, prompt), tools=tools)
        response = agent_executor.invoke({"input": mensaje, "chat_history": memoria_chat.chat_memory.messages})
        memoria_chat.chat_memory.add_user_message(mensaje); memoria_chat.chat_memory.add_ai_message(response["output"])
        return jsonify({"response": response["output"], "agent": "Agente LangChain"})
    except Exception as e:
        return jsonify({"response": "Error de conexión con el IA.", "agent": "Sistema"})