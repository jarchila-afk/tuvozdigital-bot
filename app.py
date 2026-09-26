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
# Numero de Jaime que recibe los avisos (se guarda en Render, sin + ni espacios)
ADMIN_NUMBER = (os.environ.get("ADMIN_NUMBER") or "").replace("+", "").replace(" ", "").strip()
GRAPH_URL = "https://graph.facebook.com/v23.0"

# Estado de cada cliente mientras el servidor esta encendido
# "esperando" = pidio asesor y esperamos sus datos
# "con_asesor" = ya mando sus datos; lo que escriba se reenvia a Jaime
estado_clientes = {}

SALUDOS = {"hola", "menu", "menú", "inicio", "buenas", "buenos dias", "buenos días",
           "buenas tardes", "buenas noches", "hi", "hello", "0"}


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

GRACIAS_DATOS = (
    "✅ ¡Gracias! Ya le pasamos tu información al asesor. "
    "Te escribirá muy pronto.\n\n"
    "Si quieres volver al menú, escribe *menu*."
)


# ---------- Enviar mensajes a WhatsApp ----------

def llamar_api(datos):
    """Envia un mensaje a Meta. Devuelve True si salio bien."""
    url = f"{GRAPH_URL}/{PHONE_NUMBER_ID}/messages"
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
            print("Mensaje enviado a", datos.get("to"), "- estado", r.status, flush=True)
            return True
    except urllib.error.HTTPError as e:
        print("Error al enviar:", e.code, e.read().decode(), flush=True)
    except Exception as e:
        print("Error al enviar:", e, flush=True)
    return False


def enviar_mensaje(numero, texto):
    return llamar_api({
        "messaging_product": "whatsapp",
        "to": numero,
        "type": "text",
        "text": {"body": texto},
    })


def enviar_plantilla(numero, nombre, parametros):
    """Plan B para avisar a Jaime cuando pasaron mas de 24 horas.
    Solo funciona cuando la plantilla exista y este aprobada en Meta."""
    limpios = [" ".join(str(p).split())[:900] for p in parametros]
    return llamar_api({
        "messaging_product": "whatsapp",
        "to": numero,
        "type": "template",
        "template": {
            "name": nombre,
            "language": {"code": "es"},
            "components": [{
                "type": "body",
                "parameters": [{"type": "text", "text": p} for p in limpios],
            }],
        },
    })


def avisar_admin(texto_aviso, numero_cliente, detalle):
    if not ADMIN_NUMBER:
        print("AVISO (sin ADMIN_NUMBER configurado):", texto_aviso, flush=True)
        return
    if not enviar_mensaje(ADMIN_NUMBER, texto_aviso):
        enviar_plantilla(ADMIN_NUMBER, "aviso_asesor", ["+" + numero_cliente, detalle])


# ---------- Logica del bot ----------

def reenviar_desde_admin(texto):
    """Jaime responde a un cliente escribiendo:  #50212345678 su mensaje"""
    partes = texto.strip()[1:].split(" ", 1)
    if len(partes) == 2 and partes[0].isdigit() and partes[1].strip():
        destino, mensaje = partes[0], partes[1].strip()
        if enviar_mensaje(destino, mensaje):
            enviar_mensaje(ADMIN_NUMBER, f"✅ Enviado a +{destino}")
        else:
            enviar_mensaje(
                ADMIN_NUMBER,
                f"❌ No se pudo enviar a +{destino}. Puede que hayan pasado más de "
                "24 horas desde su último mensaje; en ese caso escríbele desde tu WhatsApp.",
            )
    else:
        enviar_mensaje(
            ADMIN_NUMBER,
            "Para responder a un cliente escribe así:\n#50212345678 Hola, soy Jaime de TuVozDigital...",
        )


def procesar(numero, texto, tipo):
    t = (texto or "").strip().lower()

    # Jaime respondiendo a un cliente
    if numero == ADMIN_NUMBER and (texto or "").strip().startswith("#"):
        reenviar_desde_admin(texto)
        return

    estado = estado_clientes.get(numero)

    # Saludos o "menu": vuelve al inicio
    if t in SALUDOS:
        estado_clientes.pop(numero, None)
        enviar_mensaje(numero, MENU)
        return

    if t == "1":
        enviar_mensaje(numero, OPCION_1)
        return
    if t == "2":
        enviar_mensaje(numero, OPCION_2)
        return
    if t == "3":
        estado_clientes[numero] = "esperando"
        enviar_mensaje(numero, OPCION_3)
        avisar_admin(
            "🔔 *Nuevo cliente pide asesor*\n"
            f"Número: +{numero}\n"
            f"Abrir su chat: https://wa.me/{numero}\n\n"
            "Para responderle desde aquí escribe:\n"
            f"#{numero} tu mensaje",
            numero,
            "pidió hablar con un asesor",
        )
        return

    # Cliente que ya pidio asesor: reenviar lo que escriba
    if estado in ("esperando", "con_asesor"):
        contenido = texto if tipo == "text" else f"[envió un mensaje de tipo: {tipo}]"
        if estado == "esperando":
            enviar_mensaje(numero, GRACIAS_DATOS)
            estado_clientes[numero] = "con_asesor"
        avisar_admin(
            f"💬 *Mensaje de +{numero}:*\n{contenido}\n\n"
            f"Responder: #{numero} tu mensaje",
            numero,
            contenido,
        )
        return

    # Cualquier otra cosa: mostrar el menu
    enviar_mensaje(numero, MENU)


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
                    tipo = msg.get("type", "")
                    texto = msg.get("text", {}).get("body", "") if tipo == "text" else ""
                    print("Mensaje de", numero, ":", texto or f"[{tipo}]", flush=True)
                    procesar(numero, texto, tipo)
    except Exception as e:
        print("Error procesando mensaje:", e, flush=True)
    return "OK", 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
