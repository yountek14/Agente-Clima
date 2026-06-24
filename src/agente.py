import os
import re
import time
from datetime import datetime
from typing import Optional
from dotenv import load_dotenv

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from herramientas.clima import ConsultarClimaTool
from herramientas.historial_usuario import consultar_historial_usuario, guardar_reporte_usuario
from herramientas.email_sender import EnviarEmailTool
from herramientas.planificador import Planificador
from herramientas.recomendaciones import ConsultarRecomendacionesTool, obtener_horario, obtener_mes_actual
from herramientas.monitoreo import (
    logger_global as logger,
    recolector_global as recolector,
    sistema_trazas_global as sistema_trazas,
)

load_dotenv()


class AgenteMeteorologicoSimple:
    def __init__(self):
        if not os.getenv("GITHUB_TOKEN"):
            raise ValueError("Falta GITHUB_TOKEN en las variables de entorno.")

        self.llm = ChatOpenAI(
            model="gpt-4o",
            openai_api_base=os.getenv("OPENAI_BASE_URL", "https://models.inference.ai.azure.com"),
            openai_api_key=os.getenv("GITHUB_TOKEN"),
            temperature=0.2,
            max_tokens=1024
        ).bind_tools([
            ConsultarClimaTool(),
            EnviarEmailTool()
        ])

        # LLM sin herramientas para generación de texto (análisis IA)
        self.llm_texto = ChatOpenAI(
            model="gpt-4o",
            openai_api_base=os.getenv("OPENAI_BASE_URL", "https://models.inference.ai.azure.com"),
            openai_api_key=os.getenv("GITHUB_TOKEN"),
            temperature=0.2,
            max_tokens=1024
        )

        self.tools_map = {
            "consultar_clima": ConsultarClimaTool(),
            "consultar_recomendaciones": ConsultarRecomendacionesTool(),
            "enviar_reporte_email": EnviarEmailTool()
        }

        self.system_instruction = (
            "Eres un asistente meteorológico profesional y automatizado. Tu tarea es recopilar datos del clima y enviar un reporte detallado por correo.\n\n"
            "Flujo de trabajo sugerido:\n"
            "1. Utiliza la herramienta 'consultar_clima' para obtener las condiciones de la ciudad solicitada.\n"
            "2. Redacta una conclusión útil para el usuario basada en los datos obtenidos.\n"
            "3. Envía el mensaje final usando la herramienta 'enviar_reporte_email'.\n\n"
            "Por favor, procede con la ejecución de las herramientas correspondientes de forma ordenada."
        )

        self.prompt = ChatPromptTemplate.from_messages([
            ("system", self.system_instruction),
            ("human", "{input}")
        ])

        self.chain = self.prompt | self.llm

        self.assets_clima = {
            "despejado": {
                "emoji": "☀️",
                "color_borde": "#ffb300",
                "bg_header": "#fff8e1",
                "label": "Despejado"
            },
            "parcialmente_nublado": {
                "emoji": "⛅",
                "color_borde": "#90a4ae",
                "bg_header": "#eceff1",
                "label": "Parcialmente nublado"
            },
            "nublado": {
                "emoji": "☁️",
                "color_borde": "#78909c",
                "bg_header": "#f0f4f8",
                "label": "Nublado"
            },
            "niebla": {
                "emoji": "🌫️",
                "color_borde": "#9e9e9e",
                "bg_header": "#f5f5f5",
                "label": "Niebla"
            },
            "llovizna": {
                "emoji": "🌦️",
                "color_borde": "#64b5f6",
                "bg_header": "#e3f2fd",
                "label": "Llovizna"
            },
            "lluvia": {
                "emoji": "🌧️",
                "color_borde": "#1e88e5",
                "bg_header": "#e3f2fd",
                "label": "Lluvia"
            },
            "nieve": {
                "emoji": "🌨️",
                "color_borde": "#b0bec5",
                "bg_header": "#eceff1",
                "label": "Nieve"
            },
            "tormenta": {
                "emoji": "⛈️",
                "color_borde": "#5c6bc0",
                "bg_header": "#e8eaf6",
                "label": "Tormenta"
            },
            "viento": {
                "emoji": "💨",
                "color_borde": "#78909c",
                "bg_header": "#eceff1",
                "label": "Ventoso"
            }
        }

    def obtener_configuracion_visual(self, clima_texto):
        """
        Determina configuracion visual del reporte segun el codigo WMO.
        Prioriza condiciones severas sobre las leves.
        """
        try:
            match = re.search(r"Código del Clima \(WMO\):\s*(\d+)", clima_texto)
            if match:
                wmo_code = int(match.group(1))
                
                if wmo_code >= 95:
                    return self.assets_clima["tormenta"]
                if wmo_code == 75 or wmo_code == 86:
                    return self.assets_clima["nieve"]
                if 71 <= wmo_code <= 77 or wmo_code in [85, 86]:
                    return self.assets_clima["nieve"]
                if wmo_code in [65, 67, 82]:
                    return self.assets_clima["lluvia"]
                if wmo_code in [63, 66, 81]:
                    return self.assets_clima["lluvia"]
                if wmo_code in [61, 80]:
                    return self.assets_clima["lluvia"]
                if 51 <= wmo_code <= 57:
                    return self.assets_clima["llovizna"]
                if 45 <= wmo_code <= 48:
                    return self.assets_clima["niebla"]
                if wmo_code == 3:
                    return self.assets_clima["nublado"]
                if wmo_code in [1, 2]:
                    return self.assets_clima["parcialmente_nublado"]
                return self.assets_clima["despejado"]
        except Exception:
            pass

        texto_min = clima_texto.lower()
        if "tormenta" in texto_min or "trueno" in texto_min:
            return self.assets_clima["tormenta"]
        if "nieve" in texto_min or "nevando" in texto_min or "granizo" in texto_min:
            return self.assets_clima["nieve"]
        if "lluvia" in texto_min or "llovizna" in texto_min or "chubasco" in texto_min:
            return self.assets_clima["lluvia"]
        if "niebla" in texto_min or "neblina" in texto_min:
            return self.assets_clima["niebla"]
        if "nublado" in texto_min or "nubes" in texto_min or "cubierto" in texto_min:
            return self.assets_clima["nublado"]
        
        match_viento = re.search(r"Viento:\s*([\d.]+)\s*km/h", clima_texto)
        if match_viento and float(match_viento.group(1)) > 40:
            return self.assets_clima["viento"]
        
        return self.assets_clima["despejado"]

    def _formatear_texto_html(self, texto: str) -> str:
        """
        Convierte texto plano generado por la IA en HTML estructurado:
        - Convierte lineas con bullets (- o •) en <ul><li>
        - Convierte saltos de linea en <br>
        - Detecta encabezados con # o lineas que empiezan con emojis
        - Agrupa items consecutivos en listas
        """
        lineas = texto.strip().split('\n')
        resultado = []
        en_lista = False
        
        for linea in lineas:
            stripped = linea.strip()
            if not stripped:
                if en_lista:
                    resultado.append('</ul>')
                    en_lista = False
                resultado.append('<br>')
                continue
            
            # Detectar items de lista (-, •, *)
            if re.match(r'^[-•*]\s+', stripped):
                if not en_lista:
                    resultado.append('<ul style="margin:8px 0; padding-left:20px;">')
                    en_lista = True
                contenido = re.sub(r'^[-•*]\s+', '', stripped)
                resultado.append(f'<li style="margin-bottom:6px;">{contenido}</li>')
                continue
            
            # Si habia lista activa y esta linea no es item, cerrarla
            if en_lista:
                resultado.append('</ul>')
                en_lista = False
            
            # Detectar encabezados (###, ##, #)
            if re.match(r'^#{1,3}\s+', stripped):
                nivel = len(re.match(r'^#+', stripped).group())
                contenido = re.sub(r'^#{1,3}\s+', '', stripped)
                size = {1: '18px', 2: '16px', 3: '14px'}.get(nivel, '14px')
                resultado.append(f'<h4 style="margin:12px 0 6px 0; font-size:{size};">{contenido}</h4>')
                continue
            
            # Detectar emoji al inicio como mini-encabezado
            if re.match(r'^[\U0001F300-\U0001F9FF]', stripped):
                resultado.append(f'<p style="margin:10px 0 4px 0; font-weight:600;">{stripped}</p>')
                continue
            
            # Linea normal
            bold_fixed = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', stripped)
            resultado.append(f'{bold_fixed}<br>')
        
        if en_lista:
            resultado.append('</ul>')
        
        return '\n'.join(resultado)

    def generar_reporte(
        self, 
        email: str, 
        comuna_id: str, 
        nombre_comuna: str, 
        latitud: float, 
        longitud: float,
        user_id: Optional[str] = None
    ) -> dict:
        traza = sistema_trazas.iniciar_traza(
            "generar_reporte",
            comuna=nombre_comuna,
            email=email,
            user_id=user_id or "visitante"
        )
        trace_id = traza.trace_id
        span_raiz = sistema_trazas.iniciar_span("reporte_completo")

        logger.info("reporte_iniciado", trace_id=trace_id, comuna=nombre_comuna, email=email, user_id=user_id)

        planificador = Planificador()
        plan = planificador.crear_plan(f"Reporte meteorológico para {nombre_comuna}")

        # Paso 1: Clima
        span_clima = sistema_trazas.iniciar_span("consultar_clima", parent_span_id=span_raiz.span_id)
        logger.info("paso1_clima_iniciado", trace_id=trace_id, comuna=nombre_comuna)
        inicio = time.perf_counter()
        try:
            clima_crudo = self.tools_map["consultar_clima"].invoke({
                "latitud": latitud,
                "longitud": longitud,
                "ciudad": nombre_comuna
            })
            clima_res = clima_crudo.split("Nota:")[0].strip()
            duracion = (time.perf_counter() - inicio) * 1000
            sistema_trazas.finalizar_span(span_clima, duracion_ms=round(duracion, 2))
            recolector.registrar("consultar_clima", duracion, trace_id=trace_id)
            logger.info("paso1_clima_ok", trace_id=trace_id, duracion_ms=round(duracion, 2))
            plan.marcar_completado("Extraer datos meteorológicos actuales vía API Open-Meteo")
        except Exception as e:
            duracion = (time.perf_counter() - inicio) * 1000
            sistema_trazas.finalizar_span(span_clima, estado="ERROR", error=str(e))
            recolector.registrar("consultar_clima", duracion, exitoso=False, tipo_error=type(e).__name__, trace_id=trace_id)
            logger.error("paso1_clima_error", trace_id=trace_id, error=str(e))
            raise

        # Paso 2: Historial (solo si es usuario registrado)
        historial_res = ""
        tiene_historial = False
        if user_id:
            span_historial = sistema_trazas.iniciar_span("consultar_historial_usuario", parent_span_id=span_raiz.span_id)
            logger.info("paso2_historial_usuario_iniciado", trace_id=trace_id, user_id=user_id)
            inicio = time.perf_counter()
            try:
                historial_res = consultar_historial_usuario(user_id)
                tiene_historial = "No hay historial" not in historial_res
                duracion = (time.perf_counter() - inicio) * 1000
                sistema_trazas.finalizar_span(span_historial, duracion_ms=round(duracion, 2))
                recolector.registrar("consultar_historial_usuario", duracion, trace_id=trace_id)
                logger.info("paso2_historial_usuario_ok", trace_id=trace_id, duracion_ms=round(duracion, 2), tiene_historial=tiene_historial)
                plan.marcar_completado("Recuperar reportes previos del usuario")
            except Exception as e:
                duracion = (time.perf_counter() - inicio) * 1000
                sistema_trazas.finalizar_span(span_historial, estado="ERROR", error=str(e))
                recolector.registrar("consultar_historial_usuario", duracion, exitoso=False, tipo_error=type(e).__name__, trace_id=trace_id)
                logger.error("paso2_historial_usuario_error", trace_id=trace_id, error=str(e))

        horario = obtener_horario()
        mes = obtener_mes_actual()

        match_temp = re.search(r"Temperatura:\s*([\d.]+)", clima_res)
        match_wmo = re.search(r"Código del Clima \(WMO\):\s*(\d+)", clima_res)
        match_lluvia = re.search(r"Precipitación total:\s*([\d.]+)", clima_res) or re.search(r"Lluvia:\s*([\d.]+)", clima_res)
        temp_val = float(match_temp.group(1)) if match_temp else 10.0
        wmo_val = int(match_wmo.group(1)) if match_wmo else 0
        lluvia_val = float(match_lluvia.group(1)) if match_lluvia else 0.0

        logger.info("paso3_valores_extraidos", trace_id=trace_id,
                   temp_val=temp_val, wmo_val=wmo_val, lluvia_val=lluvia_val,
                   horario=horario, mes=mes)

        # Paso 3: Recomendaciones
        span_rec = sistema_trazas.iniciar_span("consultar_recomendaciones", parent_span_id=span_raiz.span_id)
        logger.info("paso3_recomendaciones_iniciado", trace_id=trace_id, horario=horario)
        inicio = time.perf_counter()
        try:
            recomendaciones_res = self.tools_map["consultar_recomendaciones"].invoke({
                "codigo_wmo": wmo_val,
                "temperatura": temp_val,
                "lluvia_mm": lluvia_val,
                "mes": mes,
                "horario": horario,
                "comuna": nombre_comuna
            })
            duracion = (time.perf_counter() - inicio) * 1000
            sistema_trazas.finalizar_span(span_rec, duracion_ms=round(duracion, 2))
            recolector.registrar("consultar_recomendaciones", duracion, trace_id=trace_id)
            logger.info("paso3_recomendaciones_ok", trace_id=trace_id, duracion_ms=round(duracion, 2),
                       recomendaciones_preview=recomendaciones_res[:200] if recomendaciones_res else "VACÍO")
            plan.marcar_completado("Obtener lugares recomendados según clima, temporada y horario")
        except Exception as e:
            duracion = (time.perf_counter() - inicio) * 1000
            sistema_trazas.finalizar_span(span_rec, estado="ERROR", error=str(e))
            recolector.registrar("consultar_recomendaciones", duracion, exitoso=False, tipo_error=type(e).__name__, trace_id=trace_id)
            logger.error("paso3_recomendaciones_error", trace_id=trace_id, error=str(e))
            raise

        diseno = self.obtener_configuracion_visual(clima_res)

        # Paso 4: Análisis con IA
        span_ia = sistema_trazas.iniciar_span("analisis_ia", parent_span_id=span_raiz.span_id)
        logger.info("paso4_analisis_ia_iniciado", trace_id=trace_id)

        nombre_mes = {
            1: "enero", 2: "febrero", 3: "marzo", 4: "abril",
            5: "mayo", 6: "junio", 7: "julio", 8: "agosto",
            9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre"
        }.get(mes, "")

        # Fecha y hora actual para contexto temporal (zona horaria de Chile)
        from zoneinfo import ZoneInfo
        ahora_fecha = datetime.now(ZoneInfo("America/Santiago"))
        fecha_actual = ahora_fecha.strftime("%A %d de %B de %Y")
        hora_actual = ahora_fecha.strftime("%H:%M")
        contexto_temporal = f"Hoy es {fecha_actual}, son las {hora_actual} (hora de Chile)."

        # Prompt adaptativo según si hay historial o no
        if tiene_historial:
            prompt_formatos = (
                f"{contexto_temporal}\n\n"
                f"Tienes dos tareas independientes y debes devolverlas separadas estrictamente por el marcador '[SEPARADOR]'.\n\n"
                f"Tarea 1:\n"
                f"Para {nombre_comuna} con {temp_val}\u00b0C en {horario}, genera recomendaciones ESTRUCTURADAS (SIN emojis, solo texto):\n"
                f"Vestimenta: 1 consejo breve\n"
                f"Lugares recomendados (usa bullets -):\n"
                f"- Nombre del lugar: breve descripcion\n"
                f"- Nombre del lugar: breve descripcion\n"
                f"Consejo extra (opcional)\n"
                f"Si el viento supera 40 km/h, incluye: Alerta: viento fuerte\n"
                f"Basate en esta lista de lugares: {recomendaciones_res}\n\n"
                f"[SEPARADOR]\n\n"
                f"Tarea 2:\n"
                f"Toma este registro historico del usuario: {historial_res}.\n"
                f"Transformalo en un resumen ESTRUCTURADO (SIN emojis):\n"
                f"Fecha: metricas clave (usa bullets -)\n"
                f"- Temperatura: XX°C | Lluvia: XX mm | Viento: XX km/h\n"
                f"Mantenlo limpio, sin JSON ni llaves residuales.\n"
            )
        else:
            prompt_formatos = (
                f"{contexto_temporal}\n\n"
                f"Para {nombre_comuna} con {temp_val}\u00b0C en {horario}, genera recomendaciones ESTRUCTURADAS (SIN emojis, solo texto):\n"
                f"Vestimenta: 1 consejo breve\n"
                f"Lugares recomendados (usa bullets -):\n"
                f"- Nombre del lugar: breve descripcion\n"
                f"- Nombre del lugar: breve descripcion\n"
                f"Consejo extra (opcional)\n"
                f"Si el viento supera 40 km/h, incluye: Alerta: viento fuerte\n"
                f"Basate en esta lista de lugares: {recomendaciones_res}\n"
            )

        # Log del prompt enviado
        logger.info("paso4_prompt_enviado", trace_id=trace_id, 
                   prompt_length=len(prompt_formatos),
                   tiene_historial=tiene_historial,
                   recomendaciones_length=len(recomendaciones_res))

        inicio_ia = time.perf_counter()
        try:
            # Usar LLM sin herramientas para generación de texto
            from langchain_core.prompts import ChatPromptTemplate
            prompt_texto = ChatPromptTemplate.from_messages([
                ("system", "Eres un asistente meteorológico profesional. Genera recomendaciones útiles y concisas basadas en los datos proporcionados."),
                ("human", "{input}")
            ])
            chain_texto = prompt_texto | self.llm_texto
            response_ia = chain_texto.invoke({"input": prompt_formatos})
            contenido_completo = response_ia.content if hasattr(response_ia, 'content') else str(response_ia)
            duracion_ia = (time.perf_counter() - inicio_ia) * 1000

            sistema_trazas.finalizar_span(span_ia, duracion_ms=round(duracion_ia, 2))
            recolector.registrar("analisis_ia", duracion_ia,
                                 tokens_prompt=response_ia.usage.prompt_tokens if hasattr(response_ia, 'usage') and response_ia.usage else 0,
                                 tokens_completion=response_ia.usage.completion_tokens if hasattr(response_ia, 'usage') and response_ia.usage else 0,
                                 trace_id=trace_id, modelo="gpt-4o")
            logger.info("paso4_analisis_ia_ok", trace_id=trace_id, duracion_ms=round(duracion_ia, 2),
                       contenido_completo_preview=contenido_completo[:300] if contenido_completo else "VACÍO")

            if tiene_historial:
                try:
                    conclusion_ia, historial_formateado = contenido_completo.split("[SEPARADOR]")
                    conclusion_ia = conclusion_ia.strip()
                    historial_formateado = historial_formateado.strip()
                except Exception:
                    conclusion_ia = contenido_completo
                    historial_formateado = ""
            else:
                conclusion_ia = contenido_completo
                historial_formateado = ""

            # Limpiar etiquetas internas y emojis residuales
            conclusion_ia = re.sub(r'(?i)Tarea\s*\d+\s*:?\s*', '', conclusion_ia).strip()
            conclusion_ia = re.sub(r'[\U0001F300-\U0001F9FF\u2600-\u27BF\u2B50\u2702-\u27B0\u24C2-\U0001F251]', '', conclusion_ia).strip()
            if historial_formateado:
                historial_formateado = re.sub(r'(?i)Tarea\s*\d+\s*:?\s*', '', historial_formateado).strip()
                historial_formateado = re.sub(r'[\U0001F300-\U0001F9FF\u2600-\u27BF\u2B50\u2702-\u27B0\u24C2-\U0001F251]', '', historial_formateado).strip()

            # Formatear texto plano a HTML estructurado con listas y saltos
            conclusion_ia = self._formatear_texto_html(conclusion_ia)
            if historial_formateado:
                historial_formateado = self._formatear_texto_html(historial_formateado)

            # Log para debugging
            logger.info("paso4_conclusion_ia_generada", trace_id=trace_id, 
                       conclusion_length=len(conclusion_ia), 
                       conclusion_preview=conclusion_ia[:200] if conclusion_ia else "VACÍO")

            conclusion_ia = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', conclusion_ia)
            if historial_formateado:
                historial_formateado = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', historial_formateado)

            plan.marcar_completado("Sintetizar datos actuales e históricos con IA generativa")
        except Exception as e:
            duracion_ia = (time.perf_counter() - inicio_ia) * 1000
            sistema_trazas.finalizar_span(span_ia, estado="ERROR", error=str(e))
            recolector.registrar("analisis_ia", duracion_ia, exitoso=False, tipo_error=type(e).__name__, trace_id=trace_id)
            logger.error("paso4_analisis_ia_error", trace_id=trace_id, error=str(e))
            raise

        # Construir HTML del reporte con estructura reorganizada
        # Orden: Condiciones -> Recomendaciones -> Historial (si existe) -> Footer
        seccion_recomendaciones = f"""
                    <h3 style="margin: 0 0 12px 0; color: #2b6cb0; font-size: 16px; text-transform: uppercase; letter-spacing: 0.5px;">🧠 Recomendaciones del Agente Inteligente</h3>
                    <div style="background-color: #ebf8ff; border: 1px solid #bee3f8; padding: 18px; border-radius: 8px; margin-bottom: 25px; line-height: 1.7; font-size: 14px; color: #2b6cb0;">
                        {conclusion_ia}
                    </div>
        """

        seccion_historial = ""
        if tiene_historial and historial_formateado:
            seccion_historial = f"""
                    <h3 style="margin: 0 0 12px 0; color: #4a5568; font-size: 16px; text-transform: uppercase; letter-spacing: 0.5px;">📊 Tu Historial Comparativo</h3>
                    <div style="background-color: #fafbfc; border-left: 4px solid #718096; padding: 15px; margin-bottom: 15px; border-radius: 0 8px 8px 0; line-height: 1.7; font-size: 14px; color: #4a5568;">
                        {historial_formateado}
                    </div>
            """

        # Limpiar clima_res: eliminar lineas tecnicas (WMO, Nota) para el usuario final
        lineas_limpias = []
        for linea in clima_res.split('\n'):
            if 'WMO' in linea or linea.strip().startswith('Nota:'):
                continue
            lineas_limpias.append(linea)
        clima_res_limpio = '\n'.join(lineas_limpias).replace('- ', '• ').replace('\n', '<br>')

        html_template = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
        </head>
        <body style="margin: 0; padding: 0; font-family: 'Segoe UI', Arial, sans-serif; background-color: #f5f7fa; color: #333333;">
            <div style="max-width: 600px; margin: 20px auto; background-color: #ffffff; border: 1px solid #e1e8ed; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 10px rgba(0,0,0,0.05); border-top: 6px solid {diseno['color_borde']};">

                <div style="background-color: {diseno['bg_header']}; padding: 25px; text-align: center; border-bottom: 1px solid #e1e8ed;">
                    <div style="font-size: 52px; line-height: 1; margin-bottom: 6px;">{diseno['emoji']}</div>
                    <h2 style="margin: 0; color: #1a202c; font-size: 22px; font-weight: 700;">Reporte Meteorol&oacute;gico</h2>
                    <p style="margin: 5px 0 0 0; color: #4a5568; font-size: 14px;">📍 {nombre_comuna}, Regi&oacute;n de Los Lagos &mdash; {diseno['label']}</p>
                </div>

                <div style="padding: 25px;">
                    <h3 style="margin: 0 0 12px 0; color: {diseno['color_borde']}; font-size: 16px; text-transform: uppercase; letter-spacing: 0.5px;">📋 Condiciones en Tiempo Real</h3>
                    <div style="background-color: #fafbfc; border-left: 4px solid {diseno['color_borde']}; padding: 15px; margin-bottom: 25px; border-radius: 0 8px 8px 0;">
                        <p style="margin: 0; line-height: 1.6; font-size: 15px;">{clima_res_limpio}</p>
                    </div>

                    {seccion_recomendaciones}

                    {seccion_historial}
                </div>

                <div style="background-color: #f7fafc; padding: 15px; text-align: center; border-top: 1px solid #e1e8ed;">
                    <p style="margin: 0; font-size: 12px; color: #a0aec0;">Sistema desarrollado por Ingeniería Informática 2026</p>
                    <p style="margin: 2px 0 0 0; font-size: 11px; color: #cbd5e0;">Operado de manera autónoma por Arquitectura LangChain & OpenAI</p>
                </div>
            </div>
        </body>
        </html>
        """

        # Paso 5: Guardar (si es usuario) y enviar
        span_final = sistema_trazas.iniciar_span("guardar_enviar_email", parent_span_id=span_raiz.span_id)
        logger.info("paso5_guardar_enviar_iniciado", trace_id=trace_id)
        inicio = time.perf_counter()
        try:
            fecha_hoy = datetime.now().strftime("%Y-%m-%d")
            
            # Guardar en historial del usuario si está registrado
            if user_id:
                guardar_reporte_usuario(
                    user_id=user_id,
                    fecha=fecha_hoy,
                    comuna_id=comuna_id,
                    comuna_nombre=nombre_comuna,
                    datos_clima=clima_res,
                    html_reporte=html_template,
                    correo_destino=email
                )
                plan.marcar_completado("Persistir el reporte en el historial del usuario")

            self.tools_map["enviar_reporte_email"].invoke({
                "destinatario": email,
                "asunto": f"{diseno['emoji']} Reporte Meteorol\u00f3gico - {nombre_comuna}",
                "cuerpo": html_template
            })
            plan.marcar_completado("Enviar reporte formateado al destinatario vía SMTP")
            duracion = (time.perf_counter() - inicio) * 1000
            sistema_trazas.finalizar_span(span_final, duracion_ms=round(duracion, 2))
            recolector.registrar("guardar_enviar_email", duracion, trace_id=trace_id)
            logger.info("paso5_guardar_enviar_ok", trace_id=trace_id, duracion_ms=round(duracion, 2))
        except Exception as e:
            duracion = (time.perf_counter() - inicio) * 1000
            sistema_trazas.finalizar_span(span_final, estado="ERROR", error=str(e))
            recolector.registrar("guardar_enviar_email", duracion, exitoso=False, tipo_error=type(e).__name__, trace_id=trace_id)
            logger.error("paso5_guardar_enviar_error", trace_id=trace_id, error=str(e))

        sistema_trazas.finalizar_span(span_raiz)
        sistema_trazas.finalizar_traza(estado="EXITOSO")
        logger.info("reporte_completado", trace_id=trace_id, comuna=nombre_comuna)

        pasos_ejecutados = [s.description for s in plan.steps if s.status == "completed"]

        return {
            "exito": True,
            "html_reporte": html_template,
            "pasos_ejecutados": pasos_ejecutados,
            "trace_id": trace_id,
        }
