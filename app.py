from flask import Flask, request
import os
import json
import urllib.request
import urllib.error

app = Flask(__name__)

# Token de verificacion del webhook (el mismo que ya esta en Meta, NO cambiar)
VERIFY_TOKEN = "TuVozDigital2026Token"

# Datos secretos guardados en Render (Environment)
ACCESS_TOKEN = (
    os.environ.get("WHATSAPP_TOKEN")
    or os.environ.get("ACCESS_TOKEN")
    or os.environ.get("TOKEN")
)
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID")
GRAPH_URL = "https://graph.facebook.com/v23.0"


# ---------- Textos del bot ----------

MENU = (
    "¡Hola! 👋 Bienvenido a *TuVozDigital*.\n\n"
    "Ayudamos a negocios de Guatemala a atender a sus clientes "
    "por WhatsApp las 24 horas con un asistente automático.\n\n"
    "Escribe el número de la opción:\n"
    "1️⃣ ¿Qué hace un chatbot por mi negocio?\n"
    "2️⃣ Planes y precios\n"
    "3️⃣ Hablar con un asesor"
)

OPCION_1 = (
    "🤖 Un chatbot de WhatsApp:\n\n"
    "• Responde a tus clientes al instante, de día y de noche\n"
    "• Da precios, horarios y ubicación sin que tú estés pendiente\n"
    "• Toma pedidos y datos de contacto\n"
    "• Te pasa la conversación cuando el cliente quiere hablar con una persona\n\n"
    "Escribe *2* para ver planes o *3* para hablar con un asesor."
)

OPCION_2 = (
    "💼 Tenemos planes para negocios pequeños y medianos.\n\n"
    "Cada negocio es distinto, por eso un asesor te prepara una "
    "propuesta a tu medida.\n\n"
    "Escribe *3* y te contactamos."
)

OPCION_3 = (
    "🙌 ¡Con gusto! Un asesor de TuVozDigital te escribirá muy pronto "
    "a este mismo número.\n\n"
    "Si quieres, cuéntanos aquí el nombre de tu negocio y a qué se dedica."
)


def responder(texto):
    """Decide que contestar segun lo que escribio el cliente."""
    t = (texto or "").strip().lower()
    if t == "1":
        return OPCION_1
    if t == "2":
        return OPCION_2
    if t == "3":
        return OPCION_3
    return MENU


# ---------- Enviar mensajes a WhatsApp ----------

def enviar_mensaje(numero, texto):
    url = f"{GRAPH_URL}/{PHONE_NUMBER_ID}/messages"
    datos = {
        "messaging_product": "whatsapp",
        "to": numero,
        "type": "text",
        "text": {"body": texto},
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(datos).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {ACCESS_TOKEN}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            print("Mensaje enviado a", numero, "- estado", r.status, flush=True)
    except urllib.error.HTTPError as e:
        print("Error al enviar:", e.code, e.read().decode(), flush=True)
    except Exception as e:
        print("Error al enviar:", e, flush=True)


# ---------- Rutas ----------

@app.route("/", methods=["GET"])
def inicio():
    return "Bot TuVozDigital activo", 200


@app.route("/webhook", methods=["GET"])
def verify():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200
    return "Token incorrecto", 403


@app.route("/webhook", methods=["POST"])
def recibir():
    data = request.get_json(silent=True) or {}
    try:
        for entry in data.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                for msg in value.get("messages", []):
                    numero = msg.get("from")
                    if msg.get("type") == "text":
                        texto = msg.get("text", {}).get("body", "")
                    else:
                        texto = ""
                    print("Mensaje de", numero, ":", texto, flush=True)
                    enviar_mensaje(numero, responder(texto))
    except Exception as e:
        print("Error procesando mensaje:", e, flush=True)
    return "OK", 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
