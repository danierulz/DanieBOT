from fastapi import FastAPI, Request, Response, HTTPException
from pywa import WhatsApp
from pywa.types import Message, CallbackButton, SectionRow, SectionList, Button
import os
import json
from dataclasses import asdicts
import logging

# Configura el logging para ver todo en Cloud Run
logging.basicConfig(level=logging.INFO)



app = FastAPI()

# --- Configuración de PyWa (¡IMPORTANTE! Usa variables de entorno) ---
# Estas variables se inyectarán en Cloud Run, NO las hardcodees aquí en producción.
# Para pruebas locales, puedes definirlas directamente o usar un .env
PYWA_VERIFY_TOKEN = os.getenv("PYWA_VERIFY_TOKEN", "TU_TOKEN_DE_VERIFICACION_SECRETO")
PYWA_AUTH_TOKEN = os.getenv("PYWA_AUTH_TOKEN", "TU_TOKEN_DE_AUTENTICACION_DE_META")
# El ID del número de teléfono de WhatsApp Business
PYWA_PHONE_ID = os.getenv("PYWA_PHONE_ID", "TU_ID_DE_NUMERO_DE_TELEFONO")
APP_SECRET = os.getenv("APP_SECRET", "TU_APP_SECRET_DE_META")
APP_ID = os.getenv("APP_ID", "TU_APP_ID_DE_META")

if PYWA_PHONE_ID and PYWA_AUTH_TOKEN and PYWA_VERIFY_TOKEN:
    try:
        wa = WhatsApp(
            phone_id=PYWA_PHONE_ID,
            token=PYWA_AUTH_TOKEN,
            app_secret=APP_SECRET,
            app_id=APP_ID,
            server=app,
            webhook_endpoint="/webhook/",
            verify_token=PYWA_VERIFY_TOKEN
#            callback_url="/webhook" # Esta es la ruta donde WhatsApp enviará los mensajes
        )
        print("PyWa configurado correctamente")
    except Exception as e:
        print(f"Error al configurar PyWa: {e}")
else:
    print("Error: Asegúrate de definir las variables de entorno PYWA_VERIFY_TOKEN, PYWA_AUTH_TOKEN y PYWA_PHONE_ID")

# --- Rutas de FastAPI ---

@app.get("/")
def health_check():
    return {"status": "ok", "message": "Bot de WhatsApp funcionando en Cloud Run"}

@app.get("/webhook")
async def verify_webhook(request: Request):
    """
    Ruta para la verificación del webhook de WhatsApp.
    Meta enviará una solicitud GET a esta URL para verificarla.
    """
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    if mode == "subscribe" and token == PYWA_VERIFY_TOKEN:
        print("Webhook verificado correctamente por Meta")
        return Response(content=challenge, media_type="text/plain")
    
    print("Fallo la verificación del webhook")
    raise HTTPException(status_code=403, detail="Error de verificación")

@app.post("/webhook")
async def handle_webhook_events(request: Request):
    """
    Ruta donde WhatsApp enviará los eventos de mensajes.
    PyWa se encargará de procesarlos.
    """
    body = await request.json()
    logging.info(f"PAYLOAD RECIBIDO: {body}")
    # PyWa se encarga de procesar el JSON y disparar los handlers
    wa.handle_update(await request.json())
    return {"status": "success"}

# --- Handlers de PyWa (ejemplos) ---

@wa.on_message()
def handle_message(client: WhatsApp, message: Message):
    try:
        logging.info(f"PAYLOAD CRUDO DE META: {message}")
        """Cuando recibes un mensaje de texto"""
        try:
            logging.info(f"DETALLES DEL MENSAJE: {json.dumps(asdict(message), indent=2, default=str)}")
        except:
            logging.info(f"DICCIONARIO DEL MENSAJE: {message.__dict__}")


        print(f"Mensaje recibido de {message.from_user.name}: {message.text}")
        client.send_message(
            to=message.from_user.wa_id,
            text=f"¡Hola {message.from_user.name}! Recibí tu mensaje: '{message.text}'. ¿Cómo puedo ayudarte con tu pedido de ropa?",
            # Puedes añadir botones aquí, por ejemplo:
            buttons=[Button(title="Ver Catálogo", callback_data="CATALOGO"), Button(title="Hablar con un asesor", callback_data="ASESOR")]
        )
    except Exception as e:
        logging.error(f"Error al manejar el mensaje de {message.from_user.name}: {e}")

@wa.on_callback_button()
def handle_button_callback(client: WhatsApp, cb: CallbackButton):
    """Cuando el usuario presiona un botón"""
    print(f"Botón presionado por {cb.from_user.name}: {cb.data}")
    if cb.data == "CATALOGO":
        client.send_message(
            to=cb.from_user.wa_id,
            text="¡Claro! Aquí tienes nuestro catálogo de ropa:",
            # Aquí podrías enviar un link a un PDF o una lista de productos
        )
    elif cb.data == "ASESOR":
        client.send_message(
            to=cb.from_user.wa_id,
            text="Un asesor se pondrá en contacto contigo a la brevedad."
        )

# Agrega más handlers según necesites (on_list_response, on_reaction, etc.)
@wa.on_message()
def handle_all_messages(client, msg):
    # Esto aparecerá en los logs de Google Cloud
    logging.info(f"¡Llegó algo! De: {msg.from_user.wa_id} - Texto: {msg.text}")
    msg.reply_text(f"Hola {msg.from_user.name}, recibí tu mensaje: {msg.text}")
