"""
Herramientas de historial por usuario para el agente meteorológico.
Permite guardar y consultar reportes históricos por usuario registrado.
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Optional
from langchain_core.tools import Tool

# Ruta al archivo de historial por usuario
HISTORIAL_USUARIOS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "memoria",
    "historial_usuarios.json"
)

# Máximo de reportes por usuario
MAX_REPORTES_POR_USUARIO = 10


def cargar_historial_usuarios() -> Dict:
    """Carga el historial de todos los usuarios desde el archivo JSON."""
    if not os.path.exists(HISTORIAL_USUARIOS_PATH):
        return {}
    
    try:
        with open(HISTORIAL_USUARIOS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def guardar_historial_usuarios(data: Dict) -> None:
    """Guarda el historial de usuarios en el archivo JSON."""
    os.makedirs(os.path.dirname(HISTORIAL_USUARIOS_PATH), exist_ok=True)
    with open(HISTORIAL_USUARIOS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def consultar_historial_usuario(user_id: str, limite: int = 3) -> str:
    """
    Consulta el historial de reportes de un usuario específico.
    
    Args:
        user_id: ID del usuario
        limite: Número máximo de reportes a retornar (default: 3)
    
    Returns:
        String con el historial formateado o mensaje si no hay historial
    """
    historial = cargar_historial_usuarios()
    
    if user_id not in historial or not historial[user_id]:
        return "No hay historial de reportes previos para este usuario."
    
    reportes = historial[user_id][-limite:]
    
    lineas = ["Historial de reportes previos:"]
    for r in reportes:
        fecha = r.get("fecha", "fecha desconocida")
        comuna = r.get("comuna_nombre", "ubicación desconocida")
        datos = r.get("datos_clima", "sin datos")
        lineas.append(f"- {fecha} en {comuna}: {datos}")
    
    return "\n".join(lineas)


def guardar_reporte_usuario(
    user_id: str,
    fecha: str,
    comuna_id: str,
    comuna_nombre: str,
    datos_clima: str,
    html_reporte: str,
    correo_destino: str
) -> str:
    """
    Guarda un nuevo reporte en el historial del usuario.
    
    Args:
        user_id: ID del usuario
        fecha: Fecha del reporte
        comuna_id: ID de la comuna
        comuna_nombre: Nombre de la comuna
        datos_clima: Resumen de datos climáticos
        html_reporte: HTML completo del reporte
        correo_destino: Correo al que se envió
    
    Returns:
        Mensaje de confirmación
    """
    historial = cargar_historial_usuarios()
    
    # Inicializar lista del usuario si no existe
    if user_id not in historial:
        historial[user_id] = []
    
    # Crear nuevo reporte
    nuevo_reporte = {
        "fecha": fecha,
        "comuna_id": comuna_id,
        "comuna_nombre": comuna_nombre,
        "datos_clima": datos_clima,
        "html_reporte": html_reporte,
        "correo_destino": correo_destino,
        "timestamp": datetime.now().isoformat()
    }
    
    historial[user_id].append(nuevo_reporte)
    
    # Mantener solo los últimos MAX_REPORTES_POR_USUARIO
    if len(historial[user_id]) > MAX_REPORTES_POR_USUARIO:
        historial[user_id] = historial[user_id][-MAX_REPORTES_POR_USUARIO:]
    
    guardar_historial_usuarios(historial)
    
    return f"Reporte guardado exitosamente en el historial de {comuna_nombre}."


def obtener_todos_reportes_usuario(user_id: str) -> List[Dict]:
    """
    Obtiene todos los reportes de un usuario.
    
    Args:
        user_id: ID del usuario
    
    Returns:
        Lista de reportes del usuario
    """
    historial = cargar_historial_usuarios()
    return historial.get(user_id, [])


def obtener_reporte_usuario(user_id: str, index: int) -> Optional[Dict]:
    """
    Obtiene un reporte específico de un usuario por índice.
    
    Args:
        user_id: ID del usuario
        index: Índice del reporte (0 = más reciente)
    
    Returns:
        Reporte o None si no existe
    """
    reportes = obtener_todos_reportes_usuario(user_id)
    if 0 <= index < len(reportes):
        return reportes[-(index + 1)]
    return None


# Definición de herramientas para LangChain
consultar_historial_usuario_tool = Tool(
    name="consultar_historial_usuario",
    description="Consulta el historial de reportes meteorológicos previos de un usuario registrado. Útil para comparar con condiciones actuales.",
    func=lambda user_id, limite=3: consultar_historial_usuario(user_id, limite)
)

guardar_reporte_usuario_tool = Tool(
    name="guardar_reporte_usuario",
    description="Guarda un reporte meteorológico en el historial del usuario registrado.",
    func=guardar_reporte_usuario
)
