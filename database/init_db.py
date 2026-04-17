from contextlib import contextmanager
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker


import sys
import os
#from database.models.Order import Order
#from database.models.OrderItem import OrderItem
#from database.models.Products import Products
#from database.models.ProductImages import ProductImages

# Print sys.path to debug module search paths
#print("sys.path:", sys.path)

# Add the project root directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
#print("Updated sys.path:", sys.path)

# Load environment variables
load_dotenv()

# Database connection parameters
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")
###############################################################################
# Para pruebas con main.py ya que se despliega con docker.compose para conectarse a la base de datos,
#  se levanta whatsapp-bot y el index para pruebas local
DB_HOST_DOCKER = os.getenv("DB_HOST_DOCKER")  # For Docker connectivity
###############################################################################

###############################################################################################
# Para pruebas con scraper_core.py el HOST debe ser
#127.0.0.1:5433 -- para probar con .\cloud-sql-proxy.exe --port 5433 laslocaswhatsapp:us-central1:whatsapp-bot-db
# ya que esa configuracion es para conectarse al proxy local, no a la base directamente.
###############################################################################################
# Create the database URL
#   Para pruebas con scraper_core.py el HOST debe ser
# #DATABASE_URL = f"postgresql+pg8000://{DB_USER}:{DB_PASSWORD}@127.0.0.1:5433/{DB_NAME}"
#  Para pruebas con main.py y docker-compose, el HOST debe ser el definido en DB_HOST_DOCKER
# y lanzar docker compose up --build en terminal
DATABASE_URL = f"postgresql+pg8000://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
engine = create_engine(DATABASE_URL, echo=True, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def initialize_database():
    print(f"DEBUG: Conectando  base init_db con datos : {DATABASE_URL} ")
    try:

        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            print(result.fetchone())
        # Create the database engine
        print(f"DEBUG: Conectando con usuario: {DB_USER} a la base {DB_NAME} ")
        print("Create_engine init_db.py")

        # Create all tables based on the models
        Base.metadata.create_all(engine)
        print("Database and tables created successfully.")

    except Exception as e:
         print(f"Error initializing database: {e}")

@contextmanager
def get_db_session():
        """Generador de sesiones que se cierran solas."""
        session = SessionLocal()
        try:
            yield session
            session.commit() # Si todo sale bien, guarda
        except Exception as e:
            session.rollback() # Si hay error, deshace
            print(f"❌ Error en la DB get_db_session: {e}")
            raise
        finally:
            session.close() # Siempre cierra la conexión

# 5. Función de ayuda (Dependency) para usar en las rutas de FastAPI
def get_db_fastApi():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()

if __name__ == "__main__":
    initialize_database()