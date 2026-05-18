from flask import render_template, redirect, url_for, flash, request, session, Response
from .. import app

@app.after_request
def add_header(response: Response) -> Response:
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

@app.before_request
def check_session():
    session.permanent = True

@app.route('/')
def index():
    return render_template('index.html', title="Inicio")

@app.route('/consultar', methods=['POST'])
def consultar():
    rut = request.form.get('rut_consulta')
    if rut:
        flash('Por seguridad, debes iniciar sesión para ver tus citas.', 'info')
        return redirect(url_for('login'))
    return redirect(url_for('index'))

@app.route('/especialidades')
def especialidades(): return redirect(url_for('index'))

@app.route('/servicios')
def servicios(): return redirect(url_for('index'))