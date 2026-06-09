import os
import traceback
from datetime import datetime, timedelta
import requests
from flask import Flask, request, jsonify, render_template, send_file
from flask_cors import CORS
import tempfile
import asyncio
import edge_tts
import uuid

# Importaciones de tus módulos locales obligatorios
from agente import AgenteMeteorologicoSimple
from comunas import COMUNAS_DE_LOS_LAGOS

# Inicialización de la aplicación Flask
app = Flask(__name__, static_folder="static", template_folder="templates")
CORS(app)

# ==========================================
# ESTRUCTURAS EN MEMORIA (VOLÁTILES)
# ==========================================
CACHE_CLIMA = {}       # Guarda datos de Open-Meteo por comuna_id para evitar saturar la API
HISTORIAL_CHAT = {}    # Guarda los mensajes del chat indexados por session_id (Memoria Efímera)

# Inicialización segura del Agente Meteorológico de Inteligencia Artificial
try:
    agente = AgenteMeteorologicoSimple()
    print("🤖 [SISTEMA] AgenteMeteorologicoSimple inicializado correctamente.")
except Exception as e:
    print(f"❌ [CRÍTICO] Error al inicializar el agente de IA: {e}")
    traceback.print_exc()
    agente = None


# ==========================================
# ENRUTAMIENTO Y VISTAS (FRONTEND)
# ==========================================
@app.route('/')
def index():
    """Sirve la interfaz gráfica principal renderizada desde la carpeta templates."""
    return render_template("index.html")


# ==========================================
# ENDPOINTS DE LA API (BACKEND)
# ==========================================

@app.route('/api/comunas', methods=['GET'])
def api_comunas():
    """Devuelve la lista estructurada de comunas con su ID y Nombre para el dropdown."""
    comunas_lista = [
        {"id": key, "nombre": val["nombre"]}
        for key, val in COMUNAS_DE_LOS_LAGOS.items()
    ]
    return jsonify(comunas_lista)


@app.route('/api/pronostico', methods=['GET'])
def api_pronostico():
    """
    Gestiona el pronóstico actual y semanal de 7 días.
    Implementa un sistema de caché de 10 minutos para optimizar las peticiones.
    """
    comuna_id = request.args.get('comuna_id', '').strip()
    
    if comuna_id not in COMUNAS_DE_LOS_LAGOS:
        return jsonify({"error": "La comuna especificada no es válida"}), 404
        
    ahora = datetime.now()
    
    # 1. VERIFICAR SI EXISTE EN CACHÉ VALIDA (Menos de 10 minutos de antigüedad)
    if comuna_id in CACHE_CLIMA:
        cache = CACHE_CLIMA[comuna_id]
        if ahora - cache["timestamp"] < timedelta(minutes=10):
            print(f"⚡ [CACHÉ] Usando datos temporales en memoria para: {comuna_id}")
            return jsonify(cache["data"])
            
    # 2. SI NO ESTÁ EN CACHÉ O EXPIRÓ, CONSULTAR OPEN-METEO API
    comuna = COMUNAS_DE_LOS_LAGOS[comuna_id]
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": comuna["latitud"],
        "longitude": comuna["longitud"],
        "current": ["temperature_2m", "rain", "wind_speed_10m", "weather_code"],
        "daily": ["weather_code", "temperature_2m_max", "temperature_2m_min"],
        "timezone": "auto"
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        # Guardar el resultado en la caché global con su marca de tiempo
        CACHE_CLIMA[comuna_id] = {
            "timestamp": ahora,
            "data": data
        }
        print(f"🌐 [API EXTERNA] Consulta exitosa a Open-Meteo para {comuna_id}. Nueva caché almacenada.")
        return jsonify(data)
        
    except Exception as e:
        print(f"❌ [ERROR] Fallo al invocar Open-Meteo: {str(e)}")
        return jsonify({"error": f"Error al consultar la API meteorológica: {str(e)}"}), 500


@app.route('/api/chat', methods=['POST'])
def api_chat():
    """
    Endpoint del Chatbot interactivo volátil.
    Mantiene un historial conversacional temporal indexado por sesión
    e inyecta dinámicamente las condiciones meteorológicas vivas como contexto.
    """
    if agente is None:
        return jsonify({"error": "El agente meteorológico inteligente no está disponible."}), 500
        
    data = request.get_json()
    if not data:
        return jsonify({"error": "No se recibieron parámetros en formato válido."}), 400
        
    session_id = data.get('session_id', '').strip()
    mensaje_usuario = data.get('mensaje', '').strip()
    comuna_id = data.get('comuna_id', '').strip()
    
    if not session_id or not mensaje_usuario or not comuna_id:
        return jsonify({"error": "Faltan parámetros críticos obligatorios: session_id, mensaje o comuna_id."}), 400
        
    if comuna_id not in COMUNAS_DE_LOS_LAGOS:
        return jsonify({"error": "La comuna provista no se encuentra registrada."}), 404
        
    comuna = COMUNAS_DE_LOS_LAGOS[comuna_id]
    
    # Inicializar el historial en la memoria efímera de Flask si es una sesión nueva
    if session_id not in HISTORIAL_CHAT:
        HISTORIAL_CHAT[session_id] = []
        
    # Extraer el contexto del clima en tiempo real desde nuestra caché interna
    clima_contexto = "Información meteorológica instantánea no disponible en este momento."
    if comuna_id in CACHE_CLIMA:
        curr = CACHE_CLIMA[comuna_id]["data"].get("current", {})
        clima_contexto = (
            f"Temperatura Actual: {curr.get('temperature_2m')}°C, "
            f"Precipitación: {curr.get('rain')}mm, "
            f"Velocidad del Viento: {curr.get('wind_speed_10m')}km/h, "
            f"Código de Condición WMO: {curr.get('weather_code')}."
        )

    # Inyección dinámica del prompt del sistema estructurado por ubicación
    system_prompt = (
        f"Eres Agente-Clima, un chatbot meteorológico altamente capacitado, divertido y con un estilo de personalidad cercano.\n"
        f"Te encuentras conversando con un usuario situado geográficamente en la comuna de {comuna['nombre']}.\n"
        f"Datos climáticos reales recopilados en vivo para {comuna['nombre']}: {clima_contexto}.\n"
        f"Utiliza rigurosamente este bloque de datos si te consultan sobre el estado actual del día, ropa sugerida o actividades recomendadas. "
        f"Responde siempre en español, de forma carismática, concisa y fluida."
    )
    
    # Construcción de la cola de mensajes adaptada para LangChain (System Prompt + Historial + Input)
    messages = [("system", system_prompt)]
    
    # Adjuntar la memoria conversacional previa de esta pestaña
    for msg in HISTORIAL_CHAT[session_id]:
        messages.append((msg["role"], msg["content"]))
        
    # Añadir la nueva consulta enviada por el frontend
    messages.append(("human", mensaje_usuario))
    
    try:
        # Ejecutar la inferencia llamando al LLM a través de tu clase Agente
        respuesta_ia = agente.llm.invoke(messages)
        contenido_respuesta = respuesta_ia.content if hasattr(respuesta_ia, 'content') else str(respuesta_ia)
        
        # Registrar y persistir secuencialmente el intercambio de mensajes en la memoria de Flask
        HISTORIAL_CHAT[session_id].append({"role": "human", "content": mensaje_usuario})
        HISTORIAL_CHAT[session_id].append({"role": "ai", "content": contenido_respuesta})
        
        return jsonify({"respuesta": contenido_respuesta})
        
    except Exception as e:
        print(f"❌ [ERROR CHAT] Ocurrió una anomalía en la inferencia del modelo LLM: {str(e)}")
        return jsonify({"error": f"Error interno al procesar el flujo conversacional de la IA: {str(e)}"}), 500


# ==========================================
# ENDPOINT ORIGINAL: GENERACIÓN DE REPORTE COMPLETO (6 PASOS)
# ==========================================
@app.route('/generar-reporte', methods=['POST'])
def generar_reporte():
    """
    Módulo del planificador formal de correos.
    Dispara de forma integrada las tareas automatizadas para redactar,
    formatear y despachar el informe meteorológico HTML de la comuna elegida.
    """
    if agente is None:
        return jsonify({"error": "El Agente Meteorológico no se encuentra inicializado en el servidor."}), 500
        
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No se recibieron datos legibles en la petición corporativa."}), 400
            
        correo = data.get('correo', '').strip()
        comuna_id = data.get('comuna_id', '').strip()
        
        if not correo or not comuna_id:
            return jsonify({"error": "Faltan parámetros requeridos de envío: 'correo' y 'comuna_id'."}), 400
            
        if comuna_id not in COMUNAS_DE_LOS_LAGOS:
            return jsonify({"error": f"La comuna '{comuna_id}' consultada no figura en los registros de Los Lagos."}), 404
            
        print(f"\n🚀 [PIPELINE] Iniciando orquestación completa de 6 pasos para la comuna: {comuna_id}...")
        print(f"📧 [PIPELINE] Destinatario del correo HTML: {correo}")
        
        comuna = COMUNAS_DE_LOS_LAGOS[comuna_id]
        # Invocar la rutina síncrona original de tu arquitectura académica (agente.py)
        resultado = agente.generar_reporte(email=correo, comuna_id=comuna_id, nombre_comuna=comuna["nombre"], latitud=comuna["latitud"], longitud=comuna["longitud"])
        
        if not resultado or not resultado.get("exito", False):
            mensaje_error = resultado.get("error", "Fallo no especificado durante el flujo analítico.")
            return jsonify({"error": f"El pipeline del agente se detuvo: {mensaje_error}"}), 500
            
        print("✅ [SISTEMA] ¡Pipeline de correo culminado con éxito! Despachando datos al Frontend.")
        
        # Retorna el estado e inyecta la vista previa en crudo para renderizar dentro del iframe
        return jsonify({
            "status": "success",
            "mensaje": "¡Reporte meteorológico enviado de forma exitosa a su casilla de correo!",
            "html_preview": resultado.get("html_reporte", "<h1>Reporte Generado de Forma Exitosa</h1>"),
            "pasos_ejecutados": resultado.get("pasos_ejecutados", [])
        })
        
    except Exception as e:
        print("❌ [CRÍTICO] Error general atrapado en la ruta /generar-reporte:")
        traceback.print_exc()
        return jsonify({"error": f"Fallo interno en el backend del servidor: {str(e)}"}), 500


# ==========================================
# ENDPOINT DE SÍNTESIS DE VOZ (TTS)
# ==========================================
@app.route('/api/tts', methods=['POST'])
def api_tts():
    """
    Endpoint para convertir texto a voz usando Edge TTS.
    Genera un archivo MP3 temporal y lo envía al cliente para que suene como humano.
    """
    data = request.get_json()
    if not data or 'texto' not in data:
        return jsonify({"error": "No se proporcionó texto"}), 400
        
    texto = data['texto'].strip()
    if not texto:
        return jsonify({"error": "El texto está vacío"}), 400
        
    # Voz femenina en español muy natural (Dalia - México)
    VOICE = "es-MX-DaliaNeural"
    
    temp_dir = tempfile.gettempdir()
    unique_id = uuid.uuid4().hex
    output_file = os.path.join(temp_dir, f"tts_{unique_id}.mp3")
    
    async def generar_audio():
        communicate = edge_tts.Communicate(texto, VOICE)
        await communicate.save(output_file)
        
    try:
        asyncio.run(generar_audio())
        return send_file(output_file, mimetype="audio/mpeg")
    except Exception as e:
        print(f"❌ [ERROR TTS] Fallo al generar audio con Edge TTS: {str(e)}")
        return jsonify({"error": f"Error en síntesis de voz: {str(e)}"}), 500


# ==========================================
# ARRANQUE DE LA APLICACIÓN
# ==========================================
if __name__ == '__main__':
    # Configuración de puerto dinámica para adaptabilidad local y de nube
    port = int(os.getenv("PORT", 5000))
    print(f"\n📡 [ Flask Server Listo ] Escuchando localmente en: http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=True)