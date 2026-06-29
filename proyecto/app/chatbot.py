from flask import request, jsonify
from flask_login import login_required, current_user
from bson.objectid import ObjectId
from datetime import date
import os
import random
from typing import Annotated, Sequence, TypedDict, Literal
import operator
from langchain_groq import ChatGroq
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_core.tools import tool
from langgraph.graph import StateGraph, END, START
from langgraph.prebuilt import create_react_agent
from . import app, mongo
from .utils import agendar_cita_bot, obtener_memoria_sesion, TRIAGE_PROMPT, SCHEDULER_PROMPT

class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]

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
    
    contexto_sistema = f"CONTEXTO PACIENTE:\n- Nombre: {current_user.nombre.split()[0]}\n- Próxima Cita: {futuras_str}\n\nMÉDICOS DISPONIBLES:\n{medicos_str}"
    
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

        # --- NODOS DEL GRAFO MULTI-AGENTE ---
        def triage_node(state: AgentState):
            sys_msg = SystemMessage(content=f"{TRIAGE_PROMPT}\n\n{contexto_sistema}")
            response = llm.invoke([sys_msg] + state["messages"])
            response.name = "Triage"
            return {"messages": [response]}

        scheduler_agent = create_react_agent(
            llm,
            tools=tools,
            # El system_message se inyectará directamente en el nodo.
        )

        def scheduler_node(state: AgentState):
            sys_msg = SystemMessage(content=f"{SCHEDULER_PROMPT}\n\n{contexto_sistema}")
            result = scheduler_agent.invoke({"messages": [sys_msg] + state["messages"]})
            new_messages = result["messages"][1:] # Excluimos el system message que acabamos de añadir
            if new_messages and isinstance(new_messages[-1], AIMessage):
                new_messages[-1].name = "Scheduler"
            return {"messages": new_messages[len(state["messages"]):]}

        def supervisor_router(state: AgentState) -> Literal["triage", "scheduler"]:
            router_prompt = "Eres el orquestador. Si el paciente menciona síntomas o pide recomendación médica, responde 'triage'. Si el paciente explícitamente quiere agendar, cancelar, consultar doctores, o responde 'Sí'/'No' a una reserva, responde 'scheduler'. Responde SOLO con la palabra 'triage' o 'scheduler'."
            sys_msg = SystemMessage(content=router_prompt)
            res = llm.invoke([sys_msg] + state["messages"])
            return "scheduler" if "scheduler" in res.content.strip().lower() else "triage"

        # --- CONSTRUCCIÓN DEL GRAFO ---
        workflow = StateGraph(AgentState)
        workflow.add_node("triage", triage_node)
        workflow.add_node("scheduler", scheduler_node)
        workflow.add_conditional_edges(START, supervisor_router)
        workflow.add_edge("triage", END)
        workflow.add_edge("scheduler", END)
        app_graph = workflow.compile()

        # --- EJECUCIÓN CON MEMORIA ---
        langchain_msgs = memoria_chat.chat_memory.messages.copy()
        langchain_msgs.append(HumanMessage(content=mensaje))
        final_state = app_graph.invoke({"messages": langchain_msgs})
        final_message = final_state["messages"][-1]
        
        memoria_chat.chat_memory.add_user_message(mensaje)
        memoria_chat.chat_memory.add_ai_message(final_message.content)
        
        agent_name = final_message.name if final_message.name else "Orquestador"
        return jsonify({"response": final_message.content, "agent": agent_name})
    except Exception as e:
        return jsonify({"response": f"Error del sistema multi-agente: {str(e)}", "agent": "Sistema"})