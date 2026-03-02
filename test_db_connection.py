# test_db_connection.py
import os
import psycopg2
import sys
import time

print("Iniciando prueba de conexión a la base de datos...")

# Leer las variables de entorno para las credenciales de la DB
# Estas variables serán inyectadas por Cloud Run desde Secret Manager
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT", "5432") # Default PostgreSQL port

# Validar que las variables de entorno están presentes
if not all([DB_USER, DB_PASSWORD, DB_NAME, DB_HOST]):
    print("ERROR: Faltan una o más variables de entorno de la base de datos (DB_USER, DB_PASSWORD, DB_NAME, DB_HOST).")
    sys.exit(1)

conn = None
try_count = 0
max_tries = 3 # Intentar varias veces por si hay latencia inicial
while try_count < max_tries:
    try_count += 1
    print(f"Intento {try_count}/{max_tries}: Conectando a {DB_HOST}:{DB_PORT}/{DB_NAME} como usuario {DB_USER}...")
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            dbname=DB_NAME,
            connect_timeout=10 # Tiempo de espera para la conexión en segundos
        )
        print("¡Conexión exitosa a la base de datos!")

        # Opcional: Ejecutar una consulta simple para verificar
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        db_version = cursor.fetchone()
        print(f"Versión de la base de datos: {db_version[0]}")
        cursor.close()
        conn.close()
        print("Conexión cerrada. Prueba completada con éxito.")
        sys.exit(0) # Salir con código de éxito
    except psycopg2.OperationalError as e:
        print(f"ERROR: Fallo operacional de la conexión: {e}")
    except Exception as e:
        print(f"ERROR: Fallo en la conexión a la base de datos: {e}")
    finally:
        print("Prueba de conexión a la base de datos finalizada.")
        if 'conn' in locals() and conn:  # Verificar si 'conn' está definido
            try:
                conn.close()
            except Exception as e:
                print(f"Error al cerrar la conexión: {e}")
