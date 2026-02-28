# Usa una imagen base de Python ligera
FROM python:3.10-slim

# Establece el directorio de trabajo dentro del contenedor
WORKDIR /app

# Copia el archivo de requisitos e instala las dependencias
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia el resto de tu aplicación al directorio de trabajo
# Asegúrate de que tu archivo principal de FastAPI se llame main.py
# o ajusta el comando CMD según el nombre de tu archivo.
COPY . .

# Expone el puerto 8080 (Cloud Run espera que tu app escuche en este puerto)
EXPOSE 8080

# Comando para iniciar la aplicación con Uvicorn
# main:app asume que tienes un archivo main.py y una instancia de FastAPI llamada app
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
