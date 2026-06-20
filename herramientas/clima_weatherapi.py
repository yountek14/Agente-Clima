import requests
from typing import Type, Optional
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool
import os

class ConsultarClimaWeatherAPIInput(BaseModel):
    latitud: float = Field(default=-41.4693, description="Latitud de la ciudad (por defecto Puerto Montt: -41.4693)")
    longitud: float = Field(default=-72.9424, description="Longitud de la ciudad (por defecto Puerto Montt: -72.9424)")
    ciudad: str = Field(default="Puerto Montt", description="Nombre de la ciudad para el reporte descriptivo")

class ConsultarClimaWeatherAPITool(BaseTool):
    name: str = "consultar_clima_weatherapi"
    description: str = "Obtiene condiciones meteorológicas actuales desde WeatherAPI.com (fuente secundaria)."
    args_schema: Type[BaseModel] = ConsultarClimaWeatherAPIInput

    def _run(self, latitud: float, longitud: float, ciudad: str = "Puerto Montt") -> str:
        api_key = os.getenv("WEATHERAPI_KEY")
        if not api_key:
            return "❌ Error: WEATHERAPI_KEY no configurada en variables de entorno."

        try:
            # WeatherAPI usa coordenadas en formato "lat,lon"
            url = "http://api.weatherapi.com/v1/current.json"
            params = {
                "key": api_key,
                "q": f"{latitud},{longitud}",
                "aqi": "no"
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            current = data.get("current", {})
            temp = current.get("temp_c")
            precip_mm = current.get("precip_mm", 0)
            humidity = current.get("humidity")
            wind_kph = current.get("wind_kph")
            cloud = current.get("cloud")
            
            # WeatherAPI tiene su propio sistema de condiciones
            condition = data.get("current", {}).get("condition", {})
            condition_text = condition.get("text", "Desconocido")
            condition_code = condition.get("code", 1000)
            
            # Mapear código WeatherAPI a WMO aproximado
            wmo_code = self._weatherapi_to_wmo(condition_code, cloud)
            
            resultado = (
                f"WeatherAPI para {ciudad}:\n"
                f"- Temperatura: {temp}°C\n"
                f"- Precipitación: {precip_mm} mm\n"
                f"- Humedad: {humidity}%\n"
                f"- Velocidad del Viento: {wind_kph} km/h\n"
                f"- Nubosidad: {cloud}%\n"
                f"- Condición: {condition_text}\n"
                f"- Código WMO aproximado: {wmo_code}\n"
            )
            return resultado

        except requests.exceptions.RequestException as e:
            return f"❌ Error de conexión con WeatherAPI: {str(e)}"
        except Exception as e:
            return f"❌ Error inesperado en WeatherAPI: {str(e)}"
    
    def _weatherapi_to_wmo(self, condition_code: int, cloud: int) -> int:
        """
        Mapea código de condición WeatherAPI a código WMO aproximado.
        WeatherAPI codes: https://www.weatherapi.com/docs/weather_conditions.json
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
