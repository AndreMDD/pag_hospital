# Usamos una imagen base oficial de Python ligera
FROM python:3.13-slim

# Establecemos el directorio de trabajo dentro del contenedor
WORKDIR /app

# Evita que Python escriba archivos .pyc y fuerza que la salida de la consola no se almacene en búfer
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Copiamos los requerimientos e instalamos las dependencias
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiamos todo el código de tu proyecto al contenedor
COPY . .

# Indicamos a Flask dónde está nuestra app
ENV FLASK_APP=app/app.py

# Habilitamos el puerto 5000 para que Docker Desktop lo reconozca en la interfaz
EXPOSE 5000

# Exponemos el puerto 5000 y ejecutamos la aplicación orientada al exterior
CMD ["flask", "run", "--host=0.0.0.0"]

# Nota personal: 