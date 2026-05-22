import json
import os
from datetime import datetime
from typing import Type, Optional
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool

RUTA_LUGARES = "memoria/lugares_recomendados.json"


class ConsultarRecomendacionesInput(BaseModel):
    codigo_wmo: int = Field(default=0, description="Código del clima WMO actual (0-99)")
    temperatura: float = Field(default=10.0, description="Temperatura actual en °C")
    lluvia_mm: float = Field(default=0.0, description="Cantidad de lluvia actual en mm")
    mes: int = Field(default=1, description="Número del mes actual (1-12)")
    horario: str = Field(default="mañana", description="Horario actual: 'mañana', 'tarde' o 'noche'")


NOMBRES_MES = {
    1: "enero", 2: "febrero", 3: "marzo", 4: "abril",
    5: "mayo", 6: "junio", 7: "julio", 8: "agosto",
    9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre"
}


def obtener_horario() -> str:
    hora = datetime.now().hour
    if hora < 12:
        return "mañana"
    elif hora < 19:
        return "tarde"
    return "noche"


def obtener_mes_actual() -> int:
    return datetime.now().month


class ConsultarRecomendacionesTool(BaseTool):
    name: str = "consultar_recomendaciones"
    description: str = (
        "Útil para obtener recomendaciones de lugares y actividades en Puerto Montt "
        "basadas en el clima actual (WMO, temperatura, lluvia), la temporada y el horario. "
        "Debe usarse después de consultar el clima."
    )
    args_schema: Type[BaseModel] = ConsultarRecomendacionesInput

    def _run(self, codigo_wmo: int, temperatura: float, lluvia_mm: float,
             mes: int, horario: str) -> str:
        try:
            if not os.path.exists(RUTA_LUGARES):
                return "No hay base de lugares disponibles."

            with open(RUTA_LUGARES, "r", encoding="utf-8") as f:
                data = json.load(f)

            nombre_mes = NOMBRES_MES.get(mes, "desconocido")
            lugares_filtrados = []

            for lugar in data["lugares"]:
                rango = lugar["rango_wmo"]
                if not (rango[0] <= codigo_wmo <= rango[1]):
                    continue
                if temperatura < lugar["temp_minima"]:
                    continue
                if lluvia_mm > lugar["lluvia_maxima"]:
                    continue
                temporada = lugar["temporada"]
                if "todo_el_año" not in temporada and nombre_mes not in temporada:
                    continue
                if horario not in lugar["horarios"]:
                    continue
                lugares_filtrados.append(lugar)

            if not lugares_filtrados:
                return "No se encontraron lugares recomendados para las condiciones actuales."

            lineas = []
            for l in lugares_filtrados:
                icono = {"aire_libre": "🌳", "bajo_techo": "🏠", "mixto": "🌂"}.get(l["categoria"], "📍")
                lineas.append(f"{icono} **{l['nombre']}** — {l['descripcion']}")

            return (
                f"Recomendaciones para Puerto Montt en {nombre_mes} ({horario}):\n"
                + "\n".join(lineas)
            )

        except Exception as e:
            return f"Error al consultar recomendaciones: {str(e)}"
