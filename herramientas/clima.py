import requests
from typing import Type
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool

class ConsultarClimaInput(BaseModel):
    latitud: float = Field(default=-41.4693, description="Latitud de la ciudad (por defecto Puerto Montt: -41.4693)")
    longitud: float = Field(default=-72.9424, description="Longitud de la ciudad (por defecto Puerto Montt: -72.9424)")
    ciudad: str = Field(default="Puerto Montt", description="Nombre de la ciudad para el reporte descriptivo")

class ConsultarClimaTool(BaseTool):
    name: str = "consultar_clima"
    description: str = "Útil para obtener las condiciones meteorológicas actuales de una ubicación geográfica (temperatura, velocidad del viento, lluvia y código del clima)."
    args_schema: Type[BaseModel] = ConsultarClimaInput

    def _run(self, latitud: float, longitud: float, ciudad: str = "Puerto Montt") -> str:
        # Endpoint de Open-Meteo (Gratuito, sin API Key)
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": latitud,
            "longitude": longitud,
            "current": ["temperature_2m", "rain", "wind_speed_10m", "weather_code"],
            "timezone": "auto"
        }
        
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status() # Lanza error si el status no es 200
            data = response.json()
            
            current = data.get("current", {})
            temp = current.get("temperature_2m")
            lluvia = current.get("rain")
            viento = current.get("wind_speed_10m")
            code = current.get("weather_code")
            
            # Formateamos un string estructurado que el LLM pueda interpretar fácilmente
            resultado = (
                f"Datos actuales para {ciudad}:\n"
                f"- Temperatura: {temp}°C\n"
                f"- Lluvia: {lluvia} mm\n"
                f"- Velocidad del Viento: {viento} km/h\n"
                f"- Código del Clima (WMO): {code}\n"
                f"Nota: Recuerda analizar si el viento es fuerte (>40 km/h) para adaptar tus consejos."
            )
            return resultado

        except requests.exceptions.RequestException as e:
            return f"❌ Error de conexión al consultar la API de clima: {str(e)}"
        except Exception as e:
            return f"❌ Error inesperado en la herramienta de clima: {str(e)}"