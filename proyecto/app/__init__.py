# Este archivo actúa como un agrupador de los controladores (rutas) subdivididos.
# Permite mantener la estructura original sin romper los "url_for" de los templates.
from . import main
from . import auth
from . import citas
from . import admin
from . import api
from . import chatbot