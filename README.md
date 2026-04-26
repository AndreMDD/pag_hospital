# 🏥 Clínica Salud - Sistema de Gestión Hospitalaria con IA

Plataforma web integral para la gestión de pacientes y reserva de citas médicas de "Clínica Salud". Construida con **Flask** y **MongoDB**, esta aplicación destaca por integrar un asistente virtual inteligente basado en **IA (LLaMA 3 vía Groq)** capaz de realizar triage médico y agendar citas de forma conversacional.

## ✨ Características Principales

- 🔐 **Autenticación Completa:** Registro, inicio de sesión seguro, y recuperación de contraseñas mediante códigos de verificación de un solo uso enviados por correo (OTP).
- 📅 **Reserva de Citas Dinámica:** Sistema de agendamiento con validación de disponibilidad en tiempo real (evita colisiones de horarios) y turnos rotativos para médicos.
- 🤖 **Agente Inteligente de Salud (IA):** Chatbot orquestador (Triage, Record Keeper, Scheduler) que evalúa síntomas, recuerda el contexto del paciente y agenda horas directamente en la base de datos usando *Function Calling*.
- 👨‍💻 **Panel de Administración:** Interfaz dedicada para que los administradores puedan buscar, ver y cancelar citas médicas.
- 📧 **Notificaciones por Correo:** Envío automatizado de confirmaciones de reserva, recuperación de cuentas y un script automatizado (`send_reminders.py`) para recordar citas del día siguiente.
- 🇨🇱 **Validación Local:** Formateo y validación estricta de RUT chileno integrada tanto en Frontend (JavaScript) como en Backend (Python).

## 🛠️ Tecnologías Utilizadas

- **Backend:** Python 3, Flask, Flask-Login, Flask-WTF, Flask-Mail.
- **Base de Datos:** MongoDB (PyMongo), BSON.
- **Inteligencia Artificial:** Groq API (modelo `llama-3.3-70b-versatile`), LangChain Classic.
- **Frontend:** HTML5, CSS3, JavaScript, Jinja2 (Templates).

## 🚀 Requisitos Previos

Asegúrate de tener instalado en tu sistema local:
- Python 3.8+
- Git
- Cuenta en MongoDB Atlas o servidor local de MongoDB.
- Cuenta en GroqCloud para obtener la API Key de los modelos de IA.

## ⚙️ Instalación y Configuración

1. **Clonar el repositorio:**
   ```bash
   git clone https://github.com/tu-usuario/proyecto.git
   cd proyecto
   ```

2. **Crear y activar un entorno virtual:**
   ```bash
   # En Windows
   python -m venv venv
   venv\Scripts\activate
   
   # En macOS/Linux
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Instalar dependencias:**
   ```bash
   pip install -r app/requirements.txt
   ```

4. **Configurar las Variables de Entorno:**
   Crea un archivo llamado `.env` en la carpeta `app/` y añade las siguientes variables con tus credenciales:

   ```env
   # Seguridad de Flask
   SECRET_KEY=tu_clave_secreta_aleatoria
   ADMIN_PASSWORD=contraseña_para_el_panel_admin

   # Base de Datos
   MONGO_URI=mongodb+srv://<usuario>:<password>@cluster.mongodb.net/hospital_central

   # Configuración de Correo (Ejemplo con Gmail)
   MAIL_SERVER=smtp.gmail.com
   MAIL_PORT=587
   MAIL_USE_TLS=True
   MAIL_USERNAME=tu_correo@gmail.com
   MAIL_PASSWORD=tu_contraseña_de_aplicacion

   # API Key para el Asistente IA
   GROQ_API_KEY=tu_api_key_de_groq
   ```

## 🏃‍♂️ Ejecución de la Aplicación

Para iniciar el servidor de desarrollo, ejecuta el siguiente comando desde la raíz:

```bash
python app/app.py
```

La aplicación estará disponible en: `http://localhost:5000`

### Recordatorios de Citas
Para enviar correos a los pacientes que tienen cita al día siguiente, puedes configurar una tarea programada (Cron Job o Programador de Tareas) para que ejecute el script a diario:
```bash
python app/send_reminders.py
```

---
*Desarrollado para Clínica Salud.*
