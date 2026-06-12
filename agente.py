import os
import re
import time
from datetime import datetime
from dotenv import load_dotenv

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from herramientas.clima import ConsultarClimaTool
from herramientas.historial import GuardarReporteTool, ConsultarHistorialTool
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
            temperature=0.2
        ).bind_tools([
            ConsultarClimaTool(),
            GuardarReporteTool(),
            ConsultarHistorialTool(),
            EnviarEmailTool()
        ])

        self.tools_map = {
            "consultar_clima": ConsultarClimaTool(),
            "guardar_reporte": GuardarReporteTool(),
            "consultar_historial": ConsultarHistorialTool(),
            "consultar_recomendaciones": ConsultarRecomendacionesTool(),
            "enviar_reporte_email": EnviarEmailTool()
        }

        self.system_instruction = (
            "Eres un asistente meteorológico profesional y automatizado. Tu tarea es recopilar datos del clima y enviar un reporte detallado por correo.\n\n"
            "Flujo de trabajo sugerido:\n"
            "1. Utiliza la herramienta 'consultar_clima' para obtener las condiciones de la ciudad solicitada.\n"
            "2. Utiliza la herramienta 'consultar_historial' para revisar reportes anteriores.\n"
            "3. Redacta una conclusión útil para el usuario basada en los datos obtenidos.\n"
            "4. Guarda los datos usando la herramienta 'guardar_reporte' con la fecha actual.\n"
            "5. Envía el mensaje final usando la herramienta 'enviar_reporte_email'.\n\n"
            "Por favor, procede con la ejecución de las herramientas correspondientes de forma ordenada."
        )

        self.prompt = ChatPromptTemplate.from_messages([
            ("system", self.system_instruction),
            ("human", "{input}")
        ])

        self.chain = self.prompt | self.llm

        self.assets_clima = {
            "despejado": {
                "url_img": "https://cdn-icons-png.flaticon.com/512/869/869869.png",
                "color_borde": "#ffb300",
                "bg_header": "#fff8e1"
            },
            "nublado": {
                "url_img": "https://cdn-icons-png.flaticon.com/512/1163/1163624.png",
                "color_borde": "#78909c",
                "bg_header": "#f0f4f8"
            },
            "lluvia": {
                "url_img": "https://cdn-icons-png.flaticon.com/512/1163/1163657.png",
                "color_borde": "#1e88e5",
                "bg_header": "#e3f2fd"
            }
        }

    def obtener_configuracion_visual(self, clima_texto):
        try:
            match = re.search(r"Código del Clima \(WMO\):\s*(\d+)", clima_texto)
            if match:
                wmo_code = int(match.group(1))
                if wmo_code in [0, 1]:
                    return self.assets_clima["despejado"]
                elif wmo_code in [2, 3]:
                    return self.assets_clima["nublado"]
                elif wmo_code >= 51:
                    return self.assets_clima["lluvia"]
        except Exception:
            pass

        texto_min = clima_texto.lower()
        if "lluvia" in texto_min or "llovizna" in texto_min:
            return self.assets_clima["lluvia"]
        elif "nublado" in texto_min or "nubes" in texto_min:
            return self.assets_clima["nublado"]
        return self.assets_clima["despejado"]

    def generar_reporte(self, email: str, comuna_id: str, nombre_comuna: str, latitud: float, longitud: float) -> dict:
        traza = sistema_trazas.iniciar_traza(
            "generar_reporte",
            comuna=nombre_comuna,
            email=email,
        )
        trace_id = traza.trace_id
        span_raiz = sistema_trazas.iniciar_span("reporte_completo")

        logger.info("reporte_iniciado", trace_id=trace_id, comuna=nombre_comuna, email=email)

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

        # Paso 2: Historial
        span_historial = sistema_trazas.iniciar_span("consultar_historial", parent_span_id=span_raiz.span_id)
        logger.info("paso2_historial_iniciado", trace_id=trace_id)
        inicio = time.perf_counter()
        try:
            historial_res = self.tools_map["consultar_historial"].invoke({"ciudad": nombre_comuna})
            duracion = (time.perf_counter() - inicio) * 1000
            sistema_trazas.finalizar_span(span_historial, duracion_ms=round(duracion, 2))
            recolector.registrar("consultar_historial", duracion, trace_id=trace_id)
            logger.info("paso2_historial_ok", trace_id=trace_id, duracion_ms=round(duracion, 2))
            plan.marcar_completado("Recuperar reportes previos desde memoria persistente")
        except Exception as e:
            duracion = (time.perf_counter() - inicio) * 1000
            sistema_trazas.finalizar_span(span_historial, estado="ERROR", error=str(e))
            recolector.registrar("consultar_historial", duracion, exitoso=False, tipo_error=type(e).__name__, trace_id=trace_id)
            logger.error("paso2_historial_error", trace_id=trace_id, error=str(e))
            raise

        horario = obtener_horario()
        mes = obtener_mes_actual()

        match_temp = re.search(r"Temperatura:\s*([\d.]+)", clima_res)
        match_wmo = re.search(r"Código del Clima \(WMO\):\s*(\d+)", clima_res)
        match_lluvia = re.search(r"Lluvia:\s*([\d.]+)", clima_res)
        temp_val = float(match_temp.group(1)) if match_temp else 10.0
        wmo_val = int(match_wmo.group(1)) if match_wmo else 0
        lluvia_val = float(match_lluvia.group(1)) if match_lluvia else 0.0

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
            logger.info("paso3_recomendaciones_ok", trace_id=trace_id, duracion_ms=round(duracion, 2))
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

        prompt_formatos = (
            f"Tienes dos tareas independientes y debes devolverlas separadas estrictamente por el marcador '[SEPARADOR]'.\n\n"
            f"Tarea 1:\n"
            f"Toma este registro histórico en crudo: {historial_res}.\n"
            f"Transfórmalo en un texto limpio, formal e ideal para leer en un correo. Muestra las fechas y desglosa sus métricas correspondientes de forma clara (usa saltos de línea con <br> y puntos con • si corresponde). No dejes rastro de formato JSON, llaves ni contraslas residuales.\n\n"
            f"[SEPARADOR]\n\n"
            f"Tarea 2:\n"
            f"Analiza las condiciones actuales de {nombre_comuna} ({nombre_mes}, {horario}): {clima_res} junto al historial.\n"
            f"Redacta un párrafo analítico y cercano con:\n"
            f"- Consejos prácticos de vestimenta para el clima actual ({temp_val}°C, horario {horario}).\n"
            f"- Recomendaciones de actividades y lugares para disfrutar {nombre_comuna}, elige entre estas opciones según el clima:\n"
            f"{recomendaciones_res}\n"
            f"- Contexto del horario ({horario}) para ajustar las sugerencias.\n"
            f"REGLA CRÍTICA: Si la velocidad del viento supera los 40 km/h, incluye una alerta de seguridad explícita. No uses formato Markdown."
        )

        inicio_ia = time.perf_counter()
        try:
            response_ia = self.chain.invoke({"input": prompt_formatos})
            contenido_completo = response_ia.content if hasattr(response_ia, 'content') else str(response_ia)
            duracion_ia = (time.perf_counter() - inicio_ia) * 1000

            sistema_trazas.finalizar_span(span_ia, duracion_ms=round(duracion_ia, 2))
            recolector.registrar("analisis_ia", duracion_ia,
                                 tokens_prompt=response_ia.usage.prompt_tokens if hasattr(response_ia, 'usage') and response_ia.usage else 0,
                                 tokens_completion=response_ia.usage.completion_tokens if hasattr(response_ia, 'usage') and response_ia.usage else 0,
                                 trace_id=trace_id, modelo="gpt-4o")
            logger.info("paso4_analisis_ia_ok", trace_id=trace_id, duracion_ms=round(duracion_ia, 2))

            try:
                historial_formateado, conclusion_ia = contenido_completo.split("[SEPARADOR]")
                historial_formateado = historial_formateado.strip()
                conclusion_ia = conclusion_ia.strip()
            except Exception:
                historial_formateado = "Historial climático procesado correctamente."
                conclusion_ia = contenido_completo

            historial_formateado = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', historial_formateado)
            conclusion_ia = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', conclusion_ia)

            plan.marcar_completado("Sintetizar datos actuales e históricos con IA generativa")
        except Exception as e:
            duracion_ia = (time.perf_counter() - inicio_ia) * 1000
            sistema_trazas.finalizar_span(span_ia, estado="ERROR", error=str(e))
            recolector.registrar("analisis_ia", duracion_ia, exitoso=False, tipo_error=type(e).__name__, trace_id=trace_id)
            logger.error("paso4_analisis_ia_error", trace_id=trace_id, error=str(e))
            raise

        html_template = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
        </head>
        <body style="margin: 0; padding: 0; font-family: 'Segoe UI', Arial, sans-serif; background-color: #f5f7fa; color: #333333;">
            <div style="max-width: 600px; margin: 20px auto; background-color: #ffffff; border: 1px solid #e1e8ed; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 10px rgba(0,0,0,0.05); border-top: 6px solid {diseno['color_borde']};">

                <div style="background-color: {diseno['bg_header']}; padding: 25px; text-align: center; border-bottom: 1px solid #e1e8ed;">
                    <img src="{diseno['url_img']}" width="70" height="70" alt="Icono Clima" style="display: block; margin: 0 auto 10px auto;">
                    <h2 style="margin: 0; color: #1a202c; font-size: 22px; font-weight: 700;">Reporte Meteorológico Adaptativo</h2>
                    <p style="margin: 5px 0 0 0; color: #4a5568; font-size: 14px;">📍 {nombre_comuna}, Región de Los Lagos</p>
                </div>

                <div style="padding: 25px;">
                    <h3 style="margin: 0 0 12px 0; color: {diseno['color_borde']}; font-size: 16px; text-transform: uppercase; letter-spacing: 0.5px;">📋 Condiciones en Tiempo Real</h3>
                    <div style="background-color: #fafbfc; border-left: 4px solid {diseno['color_borde']}; padding: 15px; margin-bottom: 25px; border-radius: 0 8px 8px 0;">
                        <p style="margin: 0; line-height: 1.6; font-size: 15px;">{clima_res.replace('- ', '• ').replace('\n', '<br>')}</p>
                    </div>

                    <h3 style="margin: 0 0 12px 0; color: #4a5568; font-size: 16px; text-transform: uppercase; letter-spacing: 0.5px;">📊 Tendencias y Comparativa Histórica</h3>
                    <div style="background-color: #fafbfc; border-left: 4px solid #718096; padding: 15px; margin-bottom: 25px; border-radius: 0 8px 8px 0;">
                        <p style="margin: 0; line-height: 1.6; font-size: 14px; color: #4a5568;">{historial_formateado}</p>
                    </div>

                    <h3 style="margin: 0 0 12px 0; color: #2b6cb0; font-size: 16px; text-transform: uppercase; letter-spacing: 0.5px;">🧠 Recomendaciones del Agente Inteligente</h3>
                    <div style="background-color: #ebf8ff; border: 1px solid #bee3f8; padding: 18px; border-radius: 8px; margin-bottom: 15px;">
                        <p style="margin: 0; line-height: 1.6; font-size: 14px; color: #2b6cb0; font-weight: 500;">{conclusion_ia}</p>
                    </div>
                </div>

                <div style="background-color: #f7fafc; padding: 15px; text-align: center; border-top: 1px solid #e1e8ed;">
                    <p style="margin: 0; font-size: 12px; color: #a0aec0;">Sistema desarrollado por Ingeniería Informática 2026</p>
                    <p style="margin: 2px 0 0 0; font-size: 11px; color: #cbd5e0;">Operado de manera autónoma por Arquitectura LangChain & OpenAI</p>
                </div>
            </div>
        </body>
        </html>
        """

        # Paso 5: Guardar y enviar
        span_final = sistema_trazas.iniciar_span("guardar_enviar_email", parent_span_id=span_raiz.span_id)
        logger.info("paso5_guardar_enviar_iniciado", trace_id=trace_id)
        inicio = time.perf_counter()
        try:
            fecha_hoy = datetime.now().strftime("%Y-%m-%d")
            self.tools_map["guardar_reporte"].invoke({
                "ciudad": nombre_comuna,
                "fecha": fecha_hoy,
                "datos": clima_res
            })
            plan.marcar_completado("Persistir el reporte en el sistema de memoria JSON")

            self.tools_map["enviar_reporte_email"].invoke({
                "destinatario": email,
                "asunto": f"☁️ Reporte Meteorológico - {nombre_comuna}",
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
