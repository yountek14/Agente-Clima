import json
import os
import difflib
from typing import Type, Optional
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool

MAX_REPORTES_POR_CIUDAD = 50

# 1. Definimos los esquemas de entrada usando Pydantic
class GuardarReporteInput(BaseModel):
    fecha: str = Field(description="Fecha del reporte en formato YYYY-MM-DD")
    ciudad: str = Field(description="Nombre de la ciudad del reporte")
    datos: str = Field(description="Texto o JSON string con los datos detallados del clima (temperatura, viento, lluvia)")

class ConsultarHistorialInput(BaseModel):
    ciudad: str = Field(description="Nombre de la ciudad para consultar el historial")
    consulta: Optional[str] = Field(default=None, description="Consulta opcional para filtrar registros por relevancia semántica (matching por palabras clave)")


# 2. Implementamos la herramienta para GUARDAR reportes
class GuardarReporteTool(BaseTool):
    name: str = "guardar_reporte"
    description: str = "Útil para guardar el reporte meteorológico del día en el historial persistente. Úsala siempre después de generar un reporte exitoso."
    args_schema: Type[BaseModel] = GuardarReporteInput
    
    # Ruta por defecto alineada a tu estructura de carpetas
    ruta_historial: str = "memoria/historial_reportes.json"

    def _run(self, fecha: str, ciudad: str, datos: str) -> str:
        try:
            # Asegurar que la carpeta exista
            os.makedirs(os.path.dirname(self.ruta_historial), exist_ok=True)
            
            # Leer historial existente o crear uno nuevo
            historial = {}
            if os.path.exists(self.ruta_historial):
                with open(self.ruta_historial, "r", encoding="utf-8") as f:
                    try:
                        historial = json.load(f)
                    except json.JSONDecodeError:
                        historial = {}

            # Inicializar nodo de la ciudad si no existe
            if ciudad not in historial:
                historial[ciudad] = []

            # Agregar el nuevo registro
            nuevo_registro = {"fecha": fecha, "datos": datos}
            historial[ciudad].append(nuevo_registro)

            if len(historial[ciudad]) > MAX_REPORTES_POR_CIUDAD:
                historial[ciudad] = historial[ciudad][-MAX_REPORTES_POR_CIUDAD:]

            # Guardar en disco
            with open(self.ruta_historial, "w", encoding="utf-8") as f:
                json.dump(historial, f, ensure_ascii=False, indent=4)

            return f"✅ Reporte de {ciudad} para el día {fecha} guardado exitosamente en el historial."
        
        except Exception as e:
            # Manejo de excepciones robusto según IL2.4
            return f"❌ Error al guardar el reporte: {str(e)}"


# 3. Implementamos la herramienta para CONSULTAR el historial
class ConsultarHistorialTool(BaseTool):
    name: str = "consultar_historial"
    description: str = "Útil para obtener reportes meteorológicos pasados de una ciudad. Úsala para comparar el clima actual con los días anteriores."
    args_schema: Type[BaseModel] = ConsultarHistorialInput
    
    ruta_historial: str = "memoria/historial_reportes.json"

    def _run(self, ciudad: str, consulta: Optional[str] = None) -> str:
        try:
            if not os.path.exists(self.ruta_historial):
                return f"El historial está vacío. No hay registros previos para {ciudad}."

            with open(self.ruta_historial, "r", encoding="utf-8") as f:
                historial = json.load(f)

            if ciudad not in historial or len(historial[ciudad]) == 0:
                return f"No se encontraron reportes anteriores para la ciudad: {ciudad}."

            reportes = historial[ciudad][-3:]

            if consulta:
                terminos = consulta.lower().split()
                reportes_filtrados = []
                for r in reportes:
                    texto_datos = str(r.get("datos", "")).lower()
                    coincidencias = sum(
                        1 for t in terminos
                        if difflib.SequenceMatcher(None, t, texto_datos).ratio() > 0.3
                        or t in texto_datos
                    )
                    if coincidencias > 0:
                        reportes_filtrados.append(r)
                if reportes_filtrados:
                    reportes = reportes_filtrados

            return json.dumps(reportes, ensure_ascii=False, indent=2)

        except Exception as e:
            return f"❌ Error al consultar el historial: {str(e)}"