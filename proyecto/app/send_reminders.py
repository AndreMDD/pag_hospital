from app import app, mongo, mail
from flask_mail import Message
from flask import render_template
from datetime import date, timedelta

def enviar_recordatorios():
    # Configuración necesaria para generar URLs externas en el script
    if not app.config.get('SERVER_NAME'):
        app.config['SERVER_NAME'] = 'localhost:5000' # Cambiar por tu dominio en producción

    # Usamos el contexto de la aplicación para acceder a la configuración de mail y DB
    with app.app_context():
        # 1. Calcular la fecha de mañana
        hoy = date.today()
        manana = hoy + timedelta(days=1)
        fecha_str = str(manana)
        
        print(f"--- Iniciando recordatorios para fecha: {fecha_str} ---")
        
        # 2. Buscar citas programadas para esa fecha
        citas = list(mongo.db.citas.find({'fecha': fecha_str}))
        
        if not citas:
            print("No hay citas programadas para mañana.")
            return

        print(f"Se encontraron {len(citas)} citas. Enviando correos...")
        
        enviados = 0
        
        # 3. Enviar correo a cada paciente
        for cita in citas:
            try:
                msg = Message('Recordatorio de Cita - Clínica Salud',
                              sender=app.config.get('MAIL_USERNAME'),
                              recipients=[cita['email']])
                
                msg.html = render_template('email_reminder.html', cita=cita)
                mail.send(msg)
                
                print(f"[OK] Enviado a {cita['email']}")
                enviados += 1
            except Exception as e:
                print(f"[ERROR] Falló envío a {cita['email']}: {e}")

        print(f"--- Proceso finalizado. Total enviados: {enviados} ---")

if __name__ == '__main__':
    enviar_recordatorios()