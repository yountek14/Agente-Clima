"""
Módulo de fusión de datos climáticos desde múltiples fuentes.
Implementa estrategia conservadora: si cualquier API detecta lluvia, se reporta lluvia.
"""

import re
from typing import Dict, Optional, Tuple

def parse_clima_response(respuesta: str) -> Dict:
    """
    Parsea la respuesta de texto de una herramienta de clima a un diccionario.
    """
    datos = {}
    
    # Extraer temperatura
    match = re.search(r"Temperatura:\s*([\d.]+)°C", respuesta)
    if match:
        datos['temperatura'] = float(match.group(1))
    
    # Extraer precipitacion (soporta "Precipitación total:", "Precipitación:", "Lluvia:")
    match = re.search(r"(?:Precipitaci[oó]n\s*(?:total)?|Lluvia):\s*([\d.]+)\s*mm", respuesta)
    if match:
        datos['precipitacion'] = float(match.group(1))
    
    # Extraer viento
    match = re.search(r"Velocidad del Viento:\s*([\d.]+)\s*km/h", respuesta)
    if match:
        datos['viento'] = float(match.group(1))
    
    # Extraer código WMO (soporta formatos: "Código del Clima (WMO): X", "Código WMO aproximado: X", "Código WMO: X")
    match = re.search(r"WMO.*?(\d+)", respuesta)
    if match:
        datos['wmo_code'] = int(match.group(1))
    
    # Extraer humedad (si está disponible)
    match = re.search(r"Humedad:\s*(\d+)%", respuesta)
    if match:
        datos['humedad'] = int(match.group(1))
    
    # Extraer nubosidad (si está disponible)
    match = re.search(r"Nubosidad:\s*(\d+)%", respuesta)
    if match:
        datos['nubosidad'] = int(match.group(1))
    
    return datos

def wmo_severity(code: int) -> int:
    """
    Retorna la severidad de un código WMO (mayor = más severo).
    Se usa para determinar cuál código usar en la fusión.
    """
    if code >= 95:  # Tormentas
        return 10
    elif code >= 71:  # Nieve
        return 9
    elif code >= 61:  # Lluvia
        return 8
    elif code >= 51:  # Llovizna
        return 7
    elif code >= 45:  # Niebla
        return 6
    elif code >= 3:  # Nublado
        return 5
    elif code >= 1:  # Parcialmente nublado
        return 3
    else:  # Despejado
        return 1

def fusionar_clima_conservador(
    open_meteo_resp: str,
    weatherapi_resp: str,
    ciudad: str = "la ciudad"
) -> str:
    """
    Fusiona datos de Open-Meteo y WeatherAPI con estrategia conservadora.
    
    Estrategia:
    - Si CUALQUIERA detecta lluvia → reportar lluvia
    - Temperatura: promedio de ambas
    - Viento: promedio de ambas
    - Código WMO: el más severo (más nublado/lluvioso)
    - Nubosidad: el valor más alto
    """
    om = parse_clima_response(open_meteo_resp)
    wa = parse_clima_response(weatherapi_resp)
    
    # Si no pudimos parsear alguna respuesta, devolver la que funcione
    if not om and not wa:
        return f"❌ Error: No se pudieron obtener datos climáticos para {ciudad}."
    if not om:
        return weatherapi_resp
    if not wa:
        return open_meteo_resp
    
    # TEMPERATURA: Promedio
    temp_final = None
    if 'temperatura' in om and 'temperatura' in wa:
        temp_final = round((om['temperatura'] + wa['temperatura']) / 2, 1)
    elif 'temperatura' in om:
        temp_final = om['temperatura']
    elif 'temperatura' in wa:
        temp_final = wa['temperatura']
    
    # PRECIPITACIÓN: Conservador - si cualquiera reporta lluvia, hay lluvia
    precip_final = 0.0
    if 'precipitacion' in om:
        precip_final = max(precip_final, om['precipitacion'])
    if 'precipitacion' in wa:
        precip_final = max(precip_final, wa['precipitacion'])
    
    # VIENTO: Promedio
    viento_final = None
    if 'viento' in om and 'viento' in wa:
        viento_final = round((om['viento'] + wa['viento']) / 2, 1)
    elif 'viento' in om:
        viento_final = om['viento']
    elif 'viento' in wa:
        viento_final = wa['viento']
    
    # CÓDIGO WMO: El más severo
    wmo_final = 0
    if 'wmo_code' in om:
        wmo_final = om['wmo_code']
    if 'wmo_code' in wa:
        if wmo_severity(wa['wmo_code']) > wmo_severity(wmo_final):
            wmo_final = wa['wmo_code']
    
    # NUBOSIDAD: El valor más alto (conservador)
    nubes_final = 0
    if 'nubosidad' in om:
        nubes_final = max(nubes_final, om['nubosidad'])
    if 'nubosidad' in wa:
        nubes_final = max(nubes_final, wa['nubosidad'])
    
    # Si no tenemos nubosidad pero tenemos WMO, inferir
    if nubes_final == 0 and wmo_final > 0:
        if wmo_final >= 3:
            nubes_final = 75
        elif wmo_final >= 1:
            nubes_final = 40
    
    # Construir respuesta fusionada
    resultado = f"Datos actuales para {ciudad} (fusión Open-Meteo + WeatherAPI):\n"
    resultado += f"- Temperatura: {temp_final}°C\n"
    resultado += f"- Precipitación: {precip_final} mm\n"
    resultado += f"- Velocidad del Viento: {viento_final} km/h\n"
    resultado += f"- Código del Clima (WMO): {wmo_final}\n"
    
    if nubes_final > 0:
        resultado += f"- Nubosidad: {nubes_final}%\n"
    
    resultado += "\nNota: Recuerda analizar si el viento es fuerte (>40 km/h) para adaptar tus consejos."
    
    return resultado

def obtener_fuentes_disponibles() -> Tuple[bool, bool]:
    """
    Verifica qué fuentes de datos están disponibles.
    Retorna (open_meteo_disponible, weatherapi_disponible)
    """
    import os
    
    open_meteo = True  # Open-Meteo no requiere API key
    weatherapi = bool(os.getenv("WEATHERAPI_KEY"))
    
    return open_meteo, weatherapi
