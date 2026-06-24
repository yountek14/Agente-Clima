import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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
from herramientas.auth import gestor_usuarios_global as gestor_usuarios

# Inicialización de la aplicación Flask
# Las carpetas static y templates están en la raíz del proyecto, no en src/
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
app = Flask(__name__, 
            static_folder=os.path.join(BASE_DIR, "static"), 
            template_folder=os.path.join(BASE_DIR, "templates"))
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

# ==========================================
# AUTENTICACIÓN Y CONTADOR DE VISITANTES
# ==========================================
VISITAS_POR_VISITANTE = {}    # Contador de consultas por visitante (IP + cookie)
MAX_CONSULTAS_VISITANTE = 4   # Máximo de consultas gratuitas para visitantes

# Inicialización segura del Agente Meteorológico de Inteligencia Artificial
try:
    agente = AgenteMeteorologicoSimple()
    logger.info("agente_inicializado", modelo="gpt-4o")
except Exception as e:
    logger.error("agente_inicializacion_fallida", error=str(e))
    traceback.print_exc()
    agente = None


# ==========================================
# MIDDLEWARE DE MÉTRICAS HTTP Y SESIÓN
# ==========================================
@app.before_request
def antes_de_peticion():
    request._inicio = time.perf_counter()
    request._trace_id = str(uuid.uuid4())[:8]
    
    # Verificar sesión de usuario autenticado
    token = request.cookies.get('session_token')
    request.usuario_actual = gestor_usuarios.validar_sesion(token) if token else None
    
    # Manejar cookie de visitante para conteo de consultas
    request.visitante_id = request.cookies.get('visitante_id')
    if not request.visitante_id:
        request.visitante_id = str(uuid.uuid4())
        request._nueva_cookie_visitante = True
    else:
        request._nueva_cookie_visitante = False

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
    
    # Setear cookie de visitante si es nueva
    if getattr(request, '_nueva_cookie_visitante', False):
        response.set_cookie('visitante_id', request.visitante_id, 
                          max_age=60*60*24*30, httponly=True, samesite='Lax')
    
    return response


def obtener_clave_visitante():
    """Genera una clave única para el visitante combinando IP y cookie."""
    ip = request.remote_addr or "unknown"
    return f"{ip}:{request.visitante_id}"


def contar_consulta_visitante():
    """Incrementa el contador de consultas del visitante y retorna el total."""
    clave = obtener_clave_visitante()
    VISITAS_POR_VISITANTE[clave] = VISITAS_POR_VISITANTE.get(clave, 0) + 1
    return VISITAS_POR_VISITANTE[clave]


def obtener_consultas_visitante():
    """Retorna el número de consultas realizadas por el visitante actual."""
    clave = obtener_clave_visitante()
    return VISITAS_POR_VISITANTE.get(clave, 0)


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

@app.route('/perfil')
def perfil():
    """Sirve la página de perfil del usuario."""
    if not request.usuario_actual:
        return render_template("index.html")
    return render_template("perfil.html", usuario=request.usuario_actual)

@app.route('/quienes-somos')
def quienes_somos():
    """Sirve la página informativa del proyecto."""
    return render_template("quienes_somos.html")

@app.route('/stand')
def stand():
    """Sirve la página de exhibición para el stand (Summit IA)."""
    return render_template("stand.html")


# ==========================================
# ENDPOINTS DE LA API (BACKEND)
# ==========================================

# ==========================================
# ENDPOINTS DE AUTENTICACIÓN
# ==========================================
@app.route('/api/auth/registro', methods=['POST'])
def api_auth_registro():
    """Registro de nuevo usuario."""
    data = request.get_json()
    if not data:
        return jsonify({"exito": False, "error": "Datos inválidos"}), 400
    
    nombre = data.get('nombre', '').strip()
    email = data.get('email', '').strip()
    password = data.get('password', '')
    
    if not nombre or not email or not password:
        return jsonify({"exito": False, "error": "Todos los campos son obligatorios"}), 400
    
    resultado = gestor_usuarios.registrar(nombre, email, password)
    
    if resultado["exito"]:
        response = jsonify(resultado)
        response.set_cookie('session_token', resultado["token"],
                          max_age=60*60*24*7, httponly=True, samesite='Lax')
        return response
    
    return jsonify(resultado), 400


@app.route('/api/auth/login', methods=['POST'])
def api_auth_login():
    """Inicio de sesión de usuario."""
    data = request.get_json()
    if not data:
        return jsonify({"exito": False, "error": "Datos inválidos"}), 400
    
    email = data.get('email', '').strip()
    password = data.get('password', '')
    
    if not email or not password:
        return jsonify({"exito": False, "error": "Email y contraseña son obligatorios"}), 400
    
    resultado = gestor_usuarios.login(email, password)
    
    if resultado["exito"]:
        response = jsonify(resultado)
        response.set_cookie('session_token', resultado["token"],
                          max_age=60*60*24*7, httponly=True, samesite='Lax')
        return response
    
    return jsonify(resultado), 401


@app.route('/api/auth/logout', methods=['POST'])
def api_auth_logout():
    """Cierre de sesión de usuario."""
    token = request.cookies.get('session_token')
    if token:
        gestor_usuarios.logout(token)
    
    response = jsonify({"exito": True})
    response.delete_cookie('session_token')
    return response


@app.route('/api/auth/estado', methods=['GET'])
def api_auth_estado():
    """Verifica si hay una sesión activa y retorna datos del usuario."""
    if request.usuario_actual:
        return jsonify({
            "logueado": True,
            "user": request.usuario_actual,
            "consultas_visitante": 0,
            "max_consultas": 0
        })
    else:
        return jsonify({
            "logueado": False,
            "consultas_visitante": obtener_consultas_visitante(),
            "max_consultas": MAX_CONSULTAS_VISITANTE
        })


@app.route('/api/auth/perfil', methods=['GET'])
def api_auth_perfil_get():
    """Obtiene el perfil del usuario autenticado."""
    if not request.usuario_actual:
        return jsonify({"exito": False, "error": "No autenticado"}), 401
    
    perfil = gestor_usuarios.obtener_perfil(request.usuario_actual["id"])
    if perfil:
        return jsonify({"exito": True, "user": perfil})
    return jsonify({"exito": False, "error": "Usuario no encontrado"}), 404


@app.route('/api/auth/perfil', methods=['PUT'])
def api_auth_perfil_put():
    """Actualiza el perfil del usuario autenticado."""
    if not request.usuario_actual:
        return jsonify({"exito": False, "error": "No autenticado"}), 401
    
    data = request.get_json()
    if not data:
        return jsonify({"exito": False, "error": "Datos inválidos"}), 400
    
    cambios = {}
    if 'nombre' in data:
        cambios['nombre'] = data['nombre']
    if 'email' in data:
        cambios['email'] = data['email']
    
    resultado = gestor_usuarios.actualizar_perfil(request.usuario_actual["id"], cambios)
    return jsonify(resultado)


@app.route('/api/auth/perfil/password', methods=['PUT'])
def api_auth_perfil_password():
    """Cambia la contraseña del usuario autenticado."""
    if not request.usuario_actual:
        return jsonify({"exito": False, "error": "No autenticado"}), 401
    
    data = request.get_json()
    if not data:
        return jsonify({"exito": False, "error": "Datos inválidos"}), 400
    
    password_actual = data.get('password_actual', '')
    password_nueva = data.get('password_nueva', '')
    
    if not password_actual or not password_nueva:
        return jsonify({"exito": False, "error": "Contraseñas requeridas"}), 400
    
    resultado = gestor_usuarios.cambiar_password(
        request.usuario_actual["id"], 
        password_actual, 
        password_nueva
    )
    return jsonify(resultado)


@app.route('/api/auth/perfil/foto', methods=['POST'])
def api_auth_perfil_foto():
    """Sube una nueva foto de perfil."""
    if not request.usuario_actual:
        return jsonify({"exito": False, "error": "No autenticado"}), 401
    
    if 'foto' not in request.files:
        return jsonify({"exito": False, "error": "No se proporcionó imagen"}), 400
    
    archivo = request.files['foto']
    if archivo.filename == '':
        return jsonify({"exito": False, "error": "Archivo vacío"}), 400
    
    extension = os.path.splitext(archivo.filename)[1]
    archivo_bytes = archivo.read()
    
    resultado = gestor_usuarios.guardar_foto(
        request.usuario_actual["id"],
        archivo_bytes,
        extension
    )
    return jsonify(resultado)

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
    Si WeatherAPI está configurada, fusiona datos de ambas fuentes (estrategia conservadora).
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
            
    # 2. SI NO ESTÁ EN CACHÉ O EXPIRÓ, CONSULTAR APIs
    comuna = COMUNAS_DE_LOS_LAGOS[comuna_id]
    
    # Consultar Open-Meteo (siempre)
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": comuna["latitud"],
        "longitude": comuna["longitud"],
        "current": ["temperature_2m", "precipitation", "rain", "showers", "wind_speed_10m", "weather_code"],
        "daily": ["weather_code", "temperature_2m_max", "temperature_2m_min", "precipitation_sum", "precipitation_probability_max"],
        "timezone": "auto"
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        # Si WeatherAPI está configurada, intentar fusionar datos actuales
        weatherapi_key = os.getenv("WEATHERAPI_KEY")
        if weatherapi_key:
            try:
                data = fusionar_con_weatherapi(data, comuna, weatherapi_key)
                logger.info("pronostico_fusionado", comuna_id=comuna_id)
            except Exception as e:
                logger.warning("weatherapi_fusion_error", comuna_id=comuna_id, error=str(e))
                # Continuar con datos de Open-Meteo si falla la fusión
        
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


def fusionar_con_weatherapi(data_open_meteo: dict, comuna: dict, api_key: str) -> dict:
    """
    Fusiona datos de Open-Meteo con WeatherAPI usando estrategia conservadora.
    Solo fusiona los datos actuales (current), el pronóstico diario se mantiene de Open-Meteo.
    """
    # Consultar WeatherAPI
    url = "http://api.weatherapi.com/v1/current.json"
    params = {
        "key": api_key,
        "q": f"{comuna['latitud']},{comuna['longitud']}",
        "aqi": "no"
    }
    
    response = requests.get(url, params=params, timeout=10)
    response.raise_for_status()
    data_wa = response.json()
    
    current_wa = data_wa.get("current", {})
    current_om = data_open_meteo.get("current", {})
    
    # PRECIPITACIÓN: Conservador - si cualquiera reporta lluvia, hay lluvia
    precip_om = current_om.get("precipitation") or 0
    precip_wa = current_wa.get("precip_mm") or 0
    precip_final = max(precip_om, precip_wa)
    
    # TEMPERATURA: Promedio
    temp_om = current_om.get("temperature_2m")
    temp_wa = current_wa.get("temp_c")
    if temp_om is not None and temp_wa is not None:
        temp_final = round((temp_om + temp_wa) / 2, 1)
    elif temp_om is not None:
        temp_final = temp_om
    else:
        temp_final = temp_wa
    
    # VIENTO: Promedio
    viento_om = current_om.get("wind_speed_10m")
    viento_wa = current_wa.get("wind_kph")
    if viento_om is not None and viento_wa is not None:
        viento_final = round((viento_om + viento_wa) / 2, 1)
    elif viento_om is not None:
        viento_final = viento_om
    else:
        viento_final = viento_wa
    
    # CÓDIGO WMO: El más severo
    wmo_om = current_om.get("weather_code") or 0
    wmo_wa = weatherapi_code_to_wmo(current_wa.get("condition", {}).get("code", 1000), current_wa.get("cloud", 0))
    
    # Determinar severidad
    def wmo_severity(code):
        if code >= 95: return 10
        elif code >= 71: return 9
        elif code >= 61: return 8
        elif code >= 51: return 7
        elif code >= 45: return 6
        elif code >= 3: return 5
        elif code >= 1: return 3
        else: return 1
    
    wmo_final = wmo_om if wmo_severity(wmo_om) >= wmo_severity(wmo_wa) else wmo_wa
    
    # Actualizar datos de Open-Meteo con valores fusionados
    data_fusionado = data_open_meteo.copy()
    data_fusionado["current"] = {
        "temperature_2m": temp_final,
        "precipitation": precip_final,
        "rain": precip_final if precip_final > 0 else 0,
        "showers": 0,
        "wind_speed_10m": viento_final,
        "weather_code": wmo_final
    }
    data_fusionado["fusionado"] = True
    
    return data_fusionado


def weatherapi_code_to_wmo(condition_code: int, cloud: int) -> int:
    """
    Mapea código de condición WeatherAPI a código WMO aproximado.
    """
    # Lluvia
    if condition_code in [1063, 1072, 1087, 1180, 1183, 1186, 1189, 1192, 1195, 1198, 1201]:
        return 61  # Lluvia ligera
    if condition_code in [1273, 1276, 1279, 1282]:
        return 95  # Tormenta
    
    # Nieve
    if condition_code in [1066, 1069, 1114, 1117, 1204, 1207, 1210, 1213, 1216, 1219, 1222, 1225, 1237]:
        return 71  # Nieve ligera
    
    # Niebla
    if condition_code in [1030, 1135, 1147]:
        return 45  # Niebla
    
    # Nublado/Parcialmente nublado
    if cloud > 80:
        return 3  # Nublado
    elif cloud > 50:
        return 2  # Parcialmente nublado
    elif cloud > 20:
        return 1  # Principalmente despejado
    else:
        return 0  # Despejado


@app.route('/api/chat', methods=['POST'])
def api_chat():
    """
    Endpoint del Chatbot interactivo volátil.
    Mantiene un historial conversacional temporal indexado por sesión
    e inyecta dinámicamente las condiciones meteorológicas vivas como contexto.
    
    Lógica de acceso:
    - Usuario logueado: acceso ilimitado (sujeto a rate limit de 30/min)
    - Visitante: máximo 4 consultas gratuitas
    """
    if agente is None:
        return jsonify({"error": "El agente meteorológico inteligente no está disponible."}), 500
    
    # ==========================================
    # VERIFICACIÓN DE ACCESO (LOGIN vs VISITANTE)
    # ==========================================
    if request.usuario_actual:
        # Usuario logueado: verificar rate limit por sesión
        session_id = request.get_json().get('session_id', '') if request.get_json() else ''
        permitido, restantes = limitador.permitir(f"chat:{session_id}")
        if not permitido:
            logger.warning("rate_limit_excedido", session_id=session_id)
            return jsonify({"error": "Demasiadas peticiones. Intenta nuevamente en un minuto."}), 429
    else:
        # Visitante: verificar límite de consultas gratuitas
        consultas = obtener_consultas_visitante()
        if consultas >= MAX_CONSULTAS_VISITANTE:
            logger.info("limite_visitante_alcanzado", 
                       visitante_id=request.visitante_id,
                       consultas=consultas)
            return jsonify({
                "error": "Has alcanzado el límite de consultas gratuitas.",
                "requiere_login": True,
                "consultas_realizadas": consultas,
                "max_consultas": MAX_CONSULTAS_VISITANTE
            }), 403
    
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
            "current": ["temperature_2m", "precipitation", "rain", "showers", "wind_speed_10m", "weather_code"],
            "daily": ["weather_code", "temperature_2m_max", "temperature_2m_min", "precipitation_sum", "precipitation_probability_max"],
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
        precipitacion = curr.get('precipitation') or 0
        lluvia = curr.get('rain') or 0
        chubascos = curr.get('showers') or 0
        
        # Determinar tipo de precipitación
        if precipitacion > 0:
            if chubascos > 0:
                tipo_precip = f"Chubascos ({chubascos}mm)"
            elif lluvia > 0:
                tipo_precip = f"Lluvia ({lluvia}mm)"
            else:
                tipo_precip = f"Precipitación ({precipitacion}mm)"
        else:
            tipo_precip = "Sin precipitación"
        
        clima_contexto = (
            f"Temperatura Actual: {curr.get('temperature_2m')}°C, "
            f"Precipitación: {tipo_precip}, "
            f"Velocidad del Viento: {curr.get('wind_speed_10m')}km/h, "
            f"Código de Condición WMO: {curr.get('weather_code')}."
        )
        daily = data.get("daily", {})
        if daily.get("time"):
            dias = []
            for i, fecha in enumerate(daily["time"]):
                precip_sum = daily['precipitation_sum'][i] if daily.get('precipitation_sum') else 0
                prob_precip = daily['precipitation_probability_max'][i] if daily.get('precipitation_probability_max') else 0
                dias.append(
                    f"{fecha}: Máx {daily['temperature_2m_max'][i]}°C, "
                    f"Mín {daily['temperature_2m_min'][i]}°C, "
                    f"Código WMO {daily['weather_code'][i]}, "
                    f"Precipitación: {precip_sum}mm ({prob_precip}% prob.)"
                )
            pronostico_contexto = "Pronóstico 7 días:\n" + "\n".join(dias)

    # Inyección dinámica del prompt del sistema estructurado por ubicación
    # Usar zona horaria de Chile (America/Santiago)
    from zoneinfo import ZoneInfo
    ahora_fecha = datetime.now(ZoneInfo("America/Santiago"))
    fecha_actual = ahora_fecha.strftime("%A %d de %B de %Y")
    hora_actual = ahora_fecha.strftime("%H:%M")
    
    system_prompt = (
        f"Eres Agente-Clima, un chatbot meteorológico altamente capacitado, divertido y con un estilo de personalidad cercano.\n"
        f"Fecha y hora actual: {fecha_actual} a las {hora_actual} (hora de Chile).\n"
        f"Te encuentras conversando con un usuario situado geográficamente en la comuna de {comuna['nombre']}.\n"
        f"Datos climáticos actuales en vivo para {comuna['nombre']}: {clima_contexto}\n\n"
        f"{pronostico_contexto}\n\n"
        f"Utiliza rigurosamente estos datos si te consultan sobre el clima actual o próximos días. "
        f"Cuando te pregunten por 'mañana' o días específicos, usa los datos del pronóstico de 7 días proporcionados arriba. "
        f"Responde siempre en español, de forma carismática, concisa y fluida."
    )
    
    # Personalización para usuarios registrados
    if request.usuario_actual:
        nombre_usuario = request.usuario_actual['nombre']
        system_prompt += f"\n\nEl usuario se llama {nombre_usuario}. Úsalo para personalizar tus respuestas de forma cercana."
    
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
        
        # Si es visitante, incrementar contador de consultas
        if not request.usuario_actual:
            nuevas_consultas = contar_consulta_visitante()
            logger.info("consulta_visitante_contabilizada",
                       visitante_id=request.visitante_id,
                       total_consultas=nuevas_consultas,
                       restantes=MAX_CONSULTAS_VISITANTE - nuevas_consultas)
        
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
    
    - Usuario logueado: usa su correo de cuenta, guarda en historial
    - Visitante: usa correo proporcionado, no guarda historial
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
            
        comuna_id = data.get('comuna_id', '').strip()
        
        # Determinar correo y user_id según si está logueado
        if request.usuario_actual:
            correo = request.usuario_actual['email']
            user_id = request.usuario_actual['id']
        else:
            correo = data.get('correo', '').strip()
            user_id = None
            
        if not correo:
            return jsonify({"error": "Falta el correo electrónico."}), 400
            
        if not comuna_id:
            return jsonify({"error": "Falta la comuna."}), 400
            
        if comuna_id not in COMUNAS_DE_LOS_LAGOS:
            return jsonify({"error": f"La comuna '{comuna_id}' consultada no figura en los registros de Los Lagos."}), 404
            
        logger.info("pipeline_iniciado", comuna_id=comuna_id, correo=correo, user_id=user_id)
        
        comuna = COMUNAS_DE_LOS_LAGOS[comuna_id]
        # Invocar la rutina síncrona con user_id opcional
        resultado = agente.generar_reporte(
            email=correo, 
            comuna_id=comuna_id, 
            nombre_comuna=comuna["nombre"], 
            latitud=comuna["latitud"], 
            longitud=comuna["longitud"],
            user_id=user_id
        )
        
        if not resultado or not resultado.get("exito", False):
            mensaje_error = resultado.get("error", "Fallo no especificado durante el flujo analítico.")
            return jsonify({"error": f"El pipeline del agente se detuvo: {mensaje_error}"}), 500
            
        logger.info("pipeline_exitoso", comuna_id=comuna_id)
        
        # Retorna el estado e inyecta la vista previa en crudo para renderizar dentro del iframe
        return jsonify({
            "status": "success",
            "mensaje": "¡Reporte meteorológico enviado de forma exitosa a su casilla de correo!",
            "html_preview": resultado.get("html_reporte", "<h1>Reporte Generado de Forma Exitosa</h1>"),
            "pasos_ejecutados": resultado.get("pasos_ejecutados", []),
            "es_usuario": user_id is not None
        })
        
    except Exception as e:
        logger.error("pipeline_error", error=str(e))
        traceback.print_exc()
        return jsonify({"error": f"Fallo interno en el backend del servidor: {str(e)}"}), 500


# ==========================================
# ENDPOINTS DE HISTORIAL DE REPORTES (USUARIOS)
# ==========================================
@app.route('/historial')
def pagina_historial():
    """Página de historial de reportes (solo para usuarios logueados)."""
    if not request.usuario_actual:
        return render_template("index.html")
    return render_template("historial.html", usuario=request.usuario_actual)


@app.route('/api/historial', methods=['GET'])
def api_historial():
    """Obtiene el historial de reportes del usuario logueado."""
    if not request.usuario_actual:
        return jsonify({"exito": False, "error": "No autenticado"}), 401
    
    from herramientas.historial_usuario import obtener_todos_reportes_usuario
    reportes = obtener_todos_reportes_usuario(request.usuario_actual['id'])
    
    # Retornar sin el HTML completo para ahorrar datos
    reportes_resumen = [
        {
            "fecha": r.get("fecha"),
            "comuna_id": r.get("comuna_id"),
            "comuna_nombre": r.get("comuna_nombre"),
            "datos_clima": r.get("datos_clima"),
            "timestamp": r.get("timestamp")
        }
        for r in reportes
    ]
    
    return jsonify({"exito": True, "reportes": list(reversed(reportes_resumen))})


@app.route('/api/historial/<int:index>', methods=['GET'])
def api_historial_reporte(index):
    """Obtiene un reporte específico del historial del usuario."""
    if not request.usuario_actual:
        return jsonify({"exito": False, "error": "No autenticado"}), 401
    
    from herramientas.historial_usuario import obtener_reporte_usuario
    reporte = obtener_reporte_usuario(request.usuario_actual['id'], index)
    
    if not reporte:
        return jsonify({"exito": False, "error": "Reporte no encontrado"}), 404
    
    return jsonify({"exito": True, "reporte": reporte})


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