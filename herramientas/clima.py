import requests
from typing import Type
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool
import os

class ConsultarClimaInput(BaseModel):
    latitud: float = Field(default=-41.4693, description="Latitud de la ciudad (por defecto Puerto Montt: -41.4693)")
    longitud: float = Field(default=-72.9424, description="Longitud de la ciudad (por defecto Puerto Montt: -72.9424)")
    ciudad: str = Field(default="Puerto Montt", description="Nombre de la ciudad para el reporte descriptivo")

class ConsultarClimaTool(BaseTool):
    name: str = "consultar_clima"
    description: str = "Útil para obtener las condiciones meteorológicas actuales de una ubicación geográfica (temperatura, velocidad del viento, lluvia y código del clima). Usa fusión de múltiples fuentes para mayor precisión."
    args_schema: Type[BaseModel] = ConsultarClimaInput

    def _run(self, latitud: float, longitud: float, ciudad: str = "Puerto Montt") -> str:
        # Intentar fusión de fuentes si WeatherAPI está disponible
        if os.getenv("WEATHERAPI_KEY"):
            try:
                from herramientas.clima_weatherapi import ConsultarClimaWeatherAPITool
                from herramientas.clima_fusion import fusionar_clima_conservador
                
                # Obtener datos de Open-Meteo
                open_meteo_resp = self._consultar_open_meteo(latitud, longitud, ciudad)
                
                # Obtener datos de WeatherAPI
                weatherapi_tool = ConsultarClimaWeatherAPITool()
                weatherapi_resp = weatherapi_tool._run(latitud, longitud, ciudad)
                
                # Si ambas respuestas son válidas, fusionar
                if not open_meteo_resp.startswith("❌") and not weatherapi_resp.startswith("❌"):
                    return fusionar_clima_conservador(open_meteo_resp, weatherapi_resp, ciudad)
                elif not open_meteo_resp.startswith("❌"):
                    return open_meteo_resp
                elif not weatherapi_resp.startswith("❌"):
                    return weatherapi_resp
            except Exception:
                pass  # Si falla la fusión, continuar con Open-Meteo solo
        
        # Fallback: solo Open-Meteo
        return self._consultar_open_meteo(latitud, longitud, ciudad)
    
    def _consultar_open_meteo(self, latitud: float, longitud: float, ciudad: str) -> str:
        """Consulta solo Open-Meteo (fuente original)."""
        # Endpoint de Open-Meteo (Gratuito, sin API Key)
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": latitud,
            "longitude": longitud,
            "current": ["temperature_2m", "precipitation", "rain", "showers", "snowfall", "wind_speed_10m", "weather_code"],
            "timezone": "auto"
        }
        
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status() # Lanza error si el status no es 200
            data = response.json()
            
            current = data.get("current", {})
            temp = current.get("temperature_2m")
            precipitacion = current.get("precipitation")
            lluvia = current.get("rain")
            chubascos = current.get("showers")
            nieve = current.get("snowfall")
            viento = current.get("wind_speed_10m")
            code = current.get("weather_code")
            
            # Determinar tipo de precipitación activa
            precipitacion_total = precipitacion or 0
            tipo_precipitacion = "Sin precipitación"
            if precipitacion_total > 0:
                if nieve and nieve > 0:
                    tipo_precipitacion = f"Nevando ({nieve} cm)"
                elif chubascos and chubascos > 0:
                    tipo_precipitacion = f"Chubascos ({chubascos} mm)"
                elif lluvia and lluvia > 0:
                    tipo_precipitacion = f"Lluvia ({lluvia} mm)"
                else:
                    tipo_precipitacion = f"Precipitación ({precipitacion_total} mm)"
            
            # Formateamos un string estructurado que el LLM pueda interpretar fácilmente
            resultado = (
                f"Datos actuales para {ciudad}:\n"
                f"- Temperatura: {temp}°C\n"
                f"- Precipitación total: {precipitacion_total} mm\n"
                f"- Detalle: {tipo_precipitacion}\n"
                f"- Velocidad del Viento: {viento} km/h\n"
                f"- Código del Clima (WMO): {code}\n"
                f"Nota: Recuerda analizar si el viento es fuerte (>40 km/h) para adaptar tus consejos."
            )
            return resultado

        except requests.exceptions.RequestException as e:
            return f"❌ Error de conexión al consultar la API de clima: {str(e)}"
        except Exception as e:
            return f"❌ Error inesperado en la herramienta de clima: {str(e)}"