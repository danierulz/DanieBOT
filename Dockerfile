# Usa una imagen base de Python ligera
FROM python:3.10-slim

WORKDIR /DANIEBOT

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8080

# Migraciones + uvicorn (PORT lo define Cloud Run, por defecto 8080)
ENTRYPOINT ["python", "/DANIEBOT/scripts/docker_entrypoint.py"]
