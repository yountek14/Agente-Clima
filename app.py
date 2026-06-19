import os
import traceback
import time
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
from herramientas.monitoreo import (
    logger_global as logger,
    recolector_global as recolector,
    sistema_trazas_global as sistema_trazas,
    AnalizadorTrazas,
)
from herramientas.seguridad import (
    validador_entrada_global as validador,
    filtro_etico_global as filtro_etico,
    limitador_tasa_global as limitador,
    sanitizador_salida_global as sanitizador,
)

# Inicialización de la aplicación Flask
app = Flask(__name__, static_folder="static", template_folder="templates")
CORS(app)

# ==========================================
# ESTRUCTURAS EN MEMORIA (VOLÁTILES)
# ==========================================
CACHE_CLIMA = {}       # Guarda datos de Open-Meteo por comuna_id para evitar saturar la API
HISTORIAL_CHAT = {}    # Guarda los mensajes del chat indexados por session_id (Memoria Efímera)
METRICAS_HTTP = []     # Métricas de requests HTTP
VIOLACIONES_POR_SESION = {}  # Contador de violaciones de seguridad para autodestruct
TOKEN_BUDGET_POR_SESION = {}  # Contador acumulativo de tokens por sesión (prompt + completion)
MAX_MENSAJES_HISTORIAL = 20   # Máximo de mensajes (human + ai) en el historial de chat (10 intercambios)
TOKEN_BUDGET_MAX = 50000      # Presupuesto máximo de tokens por sesión

# Inicialización segura del Agente Meteorológico de Inteligencia Artificial
try:
    agente = AgenteMeteorologicoSimple()
    logger.info("agente_inicializado", modelo="gpt-4o")
except Exception as e:
    logger.error("agente_inicializacion_fallida", error=str(e))
    traceback.print_exc()
    agente = None


# ==========================================
# MIDDLEWARE DE MÉTRICAS HTTP
# ==========================================
@app.before_request
def antes_de_peticion():
    request._inicio = time.perf_counter()
    request._trace_id = str(uuid.uuid4())[:8]

@app.after_request
def despues_de_peticion(response):
    duracion = (time.perf_counter() - request._inicio) * 1000
    METRICAS_HTTP.append({
        "timestamp": datetime.utcnow().isoformat(),
        "method": request.method,
        "path": request.path,
        "status": response.status_code,
        "duracion_ms": round(duracion, 2),
        "trace_id": getattr(request, "_trace_id", ""),
    })
    logger.info("http_request", trace_id=request._trace_id,
                method=request.method, path=request.path,
                status=response.status_code, duracion_ms=round(duracion, 2))
    return response


# ==========================================
# ENRUTAMIENTO Y VISTAS (FRONTEND)
# ==========================================
@app.route('/')
def index():
    """Sirve la interfaz gráfica principal renderizada desde la carpeta templates."""
    return render_template("index.html")

@app.route('/metricas')
def metricas():
    """Sirve el dashboard de métricas y monitoreo."""
    return render_template("metricas.html")


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
            logger.debug("cache_hit", comuna_id=comuna_id)
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
        logger.info("open_meteo_ok", comuna_id=comuna_id)
        return jsonify(data)

    except Exception as e:
        logger.error("open_meteo_error", comuna_id=comuna_id, error=str(e))
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

    # --- EASTER EGG: Activar/desactivar autodestruct por chat ---
    PALABRAS_ACTIVAR = ["!boom", "/boom", "activar autodestruct", "activar explosión",
                        "activar explosion", "explosión!", "explosion!", "boom!",
                        "detonar", "autodestrucción", "autodestruccion"]
    PALABRAS_CANCELAR = ["!noboom", "/noboom", "cancelar autodestruct",
                         "desactivar autodestruct", "desactivar explosión",
                         "abortar autodestruct", "cancelar explosión"]

    msg_lower = mensaje_usuario.lower()
    if any(p in msg_lower for p in PALABRAS_ACTIVAR):
        logger.info("autodestruct_activado_por_comando", session_id=session_id)
        return jsonify({"autodestruct": True})
    if any(p in msg_lower for p in PALABRAS_CANCELAR):
        VIOLACIONES_POR_SESION[session_id] = 0
        logger.info("autodestruct_cancelado_por_comando", session_id=session_id)
        return jsonify({"respuesta": "🔒 Autodestruct desactivado. Contador de violaciones reiniciado.", "autodestruct_cancelado": True})

    # --- SEGURIDAD: Contador de violaciones ---
    def _violacion(mensaje_error):
        VIOLACIONES_POR_SESION[session_id] = VIOLACIONES_POR_SESION.get(session_id, 0) + 1
        if VIOLACIONES_POR_SESION[session_id] >= 3:
            logger.warning("autodestruct_activado", session_id=session_id)
            return jsonify({"autodestruct": True})
        return jsonify({"error": mensaje_error}), 400

    # --- SEGURIDAD: Rate limiting por sesión ---
    permitido, restantes = limitador.permitir(f"chat:{session_id}")
    if not permitido:
        logger.warning("rate_limit_excedido", session_id=session_id)
        return _violacion("Demasiadas peticiones. Intenta nuevamente en un minuto.")

    # --- SEGURIDAD: Validación de entrada ---
    validacion = validador.validar(mensaje_usuario)
    if not validacion["es_seguro"]:
        logger.warning("entrada_bloqueada", session_id=session_id,
                       riesgo=validacion["riesgo_maximo"],
                       razon=validacion["validaciones"]["inyeccion"].mensaje)
        if validacion["riesgo_maximo"] in ("alto", "critico"):
            return _violacion("Tu mensaje contiene contenido no permitido.")

    # --- SEGURIDAD: Filtro ético ---
    etico = filtro_etico.evaluar(mensaje_usuario)
    if not etico["es_seguro"]:
        logger.warning("filtro_etico_bloqueo", session_id=session_id,
                       categorias=etico["categorias"])
        return _violacion("No puedo procesar esa solicitud.")
        
    if comuna_id not in COMUNAS_DE_LOS_LAGOS:
        return jsonify({"error": "La comuna provista no se encuentra registrada."}), 404
        
    comuna = COMUNAS_DE_LOS_LAGOS[comuna_id]
    
    # Inicializar el historial en la memoria efímera de Flask si es una sesión nueva
    if session_id not in HISTORIAL_CHAT:
        HISTORIAL_CHAT[session_id] = []
        
    # Extraer el contexto del clima en tiempo real desde nuestra caché interna
    ahora = datetime.now()

    def _fetch_clima_data():
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": comuna["latitud"],
            "longitude": comuna["longitud"],
            "current": ["temperature_2m", "rain", "wind_speed_10m", "weather_code"],
            "daily": ["weather_code", "temperature_2m_max", "temperature_2m_min"],
            "timezone": "auto"
        }
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        CACHE_CLIMA[comuna_id] = {"timestamp": ahora, "data": data}
        return data

    clima_contexto = "Información meteorológica instantánea no disponible en este momento."
    pronostico_contexto = "No hay pronóstico disponible."

    if comuna_id in CACHE_CLIMA and ahora - CACHE_CLIMA[comuna_id]["timestamp"] < timedelta(minutes=10):
        data = CACHE_CLIMA[comuna_id]["data"]
    else:
        try:
            data = _fetch_clima_data()
        except Exception:
            data = CACHE_CLIMA.get(comuna_id, {}).get("data") if comuna_id in CACHE_CLIMA else None

    if data:
        curr = data.get("current", {})
        clima_contexto = (
            f"Temperatura Actual: {curr.get('temperature_2m')}°C, "
            f"Precipitación: {curr.get('rain')}mm, "
            f"Velocidad del Viento: {curr.get('wind_speed_10m')}km/h, "
            f"Código de Condición WMO: {curr.get('weather_code')}."
        )
        daily = data.get("daily", {})
        if daily.get("time"):
            dias = []
            for i, fecha in enumerate(daily["time"]):
                dias.append(
                    f"{fecha}: Máx {daily['temperature_2m_max'][i]}°C, "
                    f"Mín {daily['temperature_2m_min'][i]}°C, "
                    f"Código WMO {daily['weather_code'][i]}"
                )
            pronostico_contexto = "Pronóstico 7 días:\n" + "\n".join(dias)

    # Inyección dinámica del prompt del sistema estructurado por ubicación
    system_prompt = (
        f"Eres Agente-Clima, un chatbot meteorológico altamente capacitado, divertido y con un estilo de personalidad cercano.\n"
        f"Te encuentras conversando con un usuario situado geográficamente en la comuna de {comuna['nombre']}.\n"
        f"Datos climáticos actuales en vivo para {comuna['nombre']}: {clima_contexto}\n\n"
        f"{pronostico_contexto}\n\n"
        f"Utiliza rigurosamente estos datos si te consultan sobre el clima actual o próximos días (incluyendo mañana). "
        f"Responde siempre en español, de forma carismática, concisa y fluida."
    )
    
    # Construcción de la cola de mensajes adaptada para LangChain (System Prompt + Historial + Input)
    messages = [("system", system_prompt)]
    
    # Adjuntar la memoria conversacional previa de esta pestaña
    for msg in HISTORIAL_CHAT[session_id]:
        messages.append((msg["role"], msg["content"]))
        
    # Añadir la nueva consulta enviada por el frontend
    messages.append(("human", mensaje_usuario))
    
    traza_chat = sistema_trazas.iniciar_traza("chat", session_id=session_id, comuna_id=comuna_id)
    trace_id = traza_chat.trace_id
    span_chat = sistema_trazas.iniciar_span("llm_invoke")
    inicio_llm = time.perf_counter()
    try:
        # Ejecutar la inferencia llamando al LLM a través de tu clase Agente
        respuesta_ia = agente.llm.invoke(messages)
        duracion_llm = (time.perf_counter() - inicio_llm) * 1000
        contenido_respuesta = respuesta_ia.content if hasattr(respuesta_ia, 'content') else str(respuesta_ia)

        # Registrar métricas del LLM
        tokens_prompt = respuesta_ia.usage.prompt_tokens if hasattr(respuesta_ia, 'usage') and respuesta_ia.usage else 0
        tokens_completion = respuesta_ia.usage.completion_tokens if hasattr(respuesta_ia, 'usage') and respuesta_ia.usage else 0
        recolector.registrar("chat_llm", duracion_llm,
                             tokens_prompt=tokens_prompt,
                             tokens_completion=tokens_completion,
                             trace_id=trace_id, modelo="gpt-4o")

        # --- SEGURIDAD: Validación de salida ---
        pii_salida = sanitizador.verificar_pii(contenido_respuesta)
        if not pii_salida.es_valido:
            logger.warning("pii_en_salida", session_id=session_id, detalles=pii_salida.detalles)
            contenido_respuesta = sanitizador.sanitizar_pii(contenido_respuesta)

        # Registrar y persistir secuencialmente el intercambio de mensajes en la memoria de Flask
        HISTORIAL_CHAT[session_id].append({"role": "human", "content": mensaje_usuario})
        HISTORIAL_CHAT[session_id].append({"role": "ai", "content": contenido_respuesta})

        # --- DEFENSA: Ventana deslizante del historial (previene crecimiento ilimitado) ---
        while len(HISTORIAL_CHAT[session_id]) > MAX_MENSAJES_HISTORIAL:
            HISTORIAL_CHAT[session_id].pop(0)

        # --- DEFENSA: Presupuesto de tokens por sesión ---
        tokens_gastados = tokens_prompt + tokens_completion
        TOKEN_BUDGET_POR_SESION[session_id] = TOKEN_BUDGET_POR_SESION.get(session_id, 0) + tokens_gastados
        if TOKEN_BUDGET_POR_SESION[session_id] > TOKEN_BUDGET_MAX:
            logger.warning("token_budget_excedido", session_id=session_id,
                           tokens_acumulados=TOKEN_BUDGET_POR_SESION[session_id])
            HISTORIAL_CHAT[session_id] = []
            TOKEN_BUDGET_POR_SESION[session_id] = 0
            contenido_respuesta += "\n\n⚠️ Has alcanzado el límite de tokens de esta sesión. El historial ha sido reiniciado."

        sistema_trazas.finalizar_span(span_chat)
        sistema_trazas.finalizar_traza()
        
        return jsonify({"respuesta": contenido_respuesta})
        
    except Exception as e:
        duracion_llm = (time.perf_counter() - inicio_llm) * 1000
        recolector.registrar("chat_llm", duracion_llm, exitoso=False,
                             tipo_error=type(e).__name__, trace_id=trace_id)
        sistema_trazas.finalizar_span(span_chat, estado="ERROR", error=str(e))
        sistema_trazas.finalizar_traza(estado="ERROR")
        logger.error("chat_llm_error", trace_id=trace_id, error=str(e))
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
        
    # --- SEGURIDAD: Rate limiting para reportes ---
    ip = request.remote_addr or "unknown"
    permitido, _ = limitador.permitir(f"reporte:{ip}")
    if not permitido:
        logger.warning("rate_limit_reporte_excedido", ip=ip)
        return jsonify({"error": "Demasiados reportes solicitados. Intenta más tarde."}), 429

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
            
        logger.info("pipeline_iniciado", comuna_id=comuna_id, correo=correo)
        
        comuna = COMUNAS_DE_LOS_LAGOS[comuna_id]
        # Invocar la rutina síncrona original de tu arquitectura académica (agente.py)
        resultado = agente.generar_reporte(email=correo, comuna_id=comuna_id, nombre_comuna=comuna["nombre"], latitud=comuna["latitud"], longitud=comuna["longitud"])
        
        if not resultado or not resultado.get("exito", False):
            mensaje_error = resultado.get("error", "Fallo no especificado durante el flujo analítico.")
            return jsonify({"error": f"El pipeline del agente se detuvo: {mensaje_error}"}), 500
            
        logger.info("pipeline_exitoso", comuna_id=comuna_id)
        
        # Retorna el estado e inyecta la vista previa en crudo para renderizar dentro del iframe
        return jsonify({
            "status": "success",
            "mensaje": "¡Reporte meteorológico enviado de forma exitosa a su casilla de correo!",
            "html_preview": resultado.get("html_reporte", "<h1>Reporte Generado de Forma Exitosa</h1>"),
            "pasos_ejecutados": resultado.get("pasos_ejecutados", [])
        })
        
    except Exception as e:
        logger.error("pipeline_error", error=str(e))
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
        logger.error("tts_error", error=str(e))
        return jsonify({"error": f"Error en síntesis de voz: {str(e)}"}), 500


# ==========================================
# ENDPOINT DE MÉTRICAS Y MONITOREO
# ==========================================
@app.route('/api/metricas', methods=['GET'])
def api_metricas():
    """Devuelve métricas de rendimiento del sistema y del agente."""
    resumen_recolector = recolector.resumen()
    resumen_trazas = AnalizadorTrazas.resumir(sistema_trazas.trazas)

    duraciones_http = [m["duracion_ms"] for m in METRICAS_HTTP]
    http_resumen = {
        "total_peticiones": len(METRICAS_HTTP),
        "tiempo_promedio_ms": round(sum(duraciones_http) / len(duraciones_http), 2) if duraciones_http else 0,
        "tiempo_maximo_ms": round(max(duraciones_http), 2) if duraciones_http else 0,
    }

    return jsonify({
        "agente": resumen_recolector,
        "trazabilidad": resumen_trazas,
        "http": http_resumen,
    })


@app.route('/api/metricas/detalle', methods=['GET'])
def api_metricas_detalle():
    """Devuelve el detalle completo de métricas y trazas."""
    return jsonify({
        "metricas": recolector.a_diccionarios(),
        "trazas": [
            {
                "trace_id": t.trace_id,
                "nombre": t.nombre,
                "estado": t.estado,
                "duracion_total_ms": t.duracion_total_ms,
                "timestamp_inicio": t.timestamp_inicio,
                "spans": [
                    {"nombre": s.nombre, "duracion_ms": s.duracion_ms,
                     "estado": s.estado, "parent_span_id": s.parent_span_id}
                    for s in t.spans
                ],
            }
            for t in sistema_trazas.trazas
        ],
        "http": METRICAS_HTTP[-100:],
    })


# ==========================================
# ARRANQUE DE LA APLICACIÓN
# ==========================================
if __name__ == '__main__':
    # Configuración de puerto dinámica para adaptabilidad local y de nube
    port = int(os.getenv("PORT", 5000))
    logger.info("servidor_iniciado", puerto=port, url=f"http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=True)