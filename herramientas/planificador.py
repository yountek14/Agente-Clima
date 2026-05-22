import re
from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class PlanStep:
    action: str
    description: str
    dependencies: List[str] = field(default_factory=list)
    priority: int = 1
    status: str = "pending"

@dataclass
class Plan:
    goal: str
    steps: List[PlanStep]

    def to_str(self) -> str:
        lines = []
        lines.append(f"  Objetivo: {self.goal}")
        lines.append(f"  Pasos del plan ({len(self.steps)}):")
        for i, step in enumerate(self.steps, 1):
            dep_text = f" [deps: {', '.join(step.dependencies)}]" if step.dependencies else ""
            lines.append(f"    {i}. [{step.status}] {step.description}{dep_text}")
        return "\n".join(lines)

    def ejecutar_siguiente(self) -> Optional[PlanStep]:
        for step in self.steps:
            if step.status == "pending":
                deps_ok = all(
                    s.status == "completed"
                    for s in self.steps
                    if s.description in step.dependencies
                )
                if deps_ok:
                    return step
        return None

    def marcar_completado(self, descripcion: str):
        for step in self.steps:
            if step.description == descripcion:
                step.status = "completed"
                break


class Planificador:
    REGLAS_PLAN = [
        {
            "patrones": [r"clima", r"meteorol[oó]gico", r"temperatura", r"lluvia", r"viento"],
            "accion": "consultar_clima",
            "descripcion": "Extraer datos meteorológicos actuales vía API Open-Meteo",
            "prioridad": 1
        },
        {
            "patrones": [r"historial", r"anterior", r"tendencia", r"comparar", r"pasado"],
            "accion": "consultar_historial",
            "descripcion": "Recuperar reportes previos desde memoria persistente",
            "prioridad": 2
        },
        {
            "patrones": [r"analiz", r"recomendacion", r"consejo", r"conclusi[oó]n", r"reporte", r"informe"],
            "accion": "analizar_datos",
            "descripcion": "Sintetizar datos actuales e históricos con IA generativa",
            "prioridad": 2
        },
        {
            "patrones": [r"guardar", r"almacenar", r"persistir", r"registrar"],
            "accion": "guardar_reporte",
            "descripcion": "Persistir el reporte en el sistema de memoria JSON",
            "prioridad": 3
        },
        {
            "patrones": [r"enviar", r"correo", r"email", r"mail"],
            "accion": "enviar_reporte_email",
            "descripcion": "Enviar reporte formateado al destinatario vía SMTP",
            "prioridad": 3
        }
    ]

    def __init__(self):
        self.pasos_fijos = [
            {
                "accion": "consultar_clima",
                "descripcion": "Extraer datos meteorológicos actuales vía API Open-Meteo",
                "prioridad": 1
            },
            {
                "accion": "consultar_historial",
                "descripcion": "Recuperar reportes previos desde memoria persistente",
                "prioridad": 1
            },
            {
                "accion": "consultar_recomendaciones",
                "descripcion": "Obtener lugares recomendados según clima, temporada y horario",
                "prioridad": 2
            },
            {
                "accion": "analizar_datos",
                "descripcion": "Sintetizar datos actuales e históricos con IA generativa",
                "prioridad": 2
            },
            {
                "accion": "guardar_reporte",
                "descripcion": "Persistir el reporte en el sistema de memoria JSON",
                "prioridad": 2
            },
            {
                "accion": "enviar_reporte_email",
                "descripcion": "Enviar reporte formateado al destinatario vía SMTP",
                "prioridad": 3
            }
        ]

    def crear_plan(self, solicitud: str) -> Plan:
        texto = solicitud.lower()

        pasos_activados = []
        for paso in self.pasos_fijos:
            pasos_activados.append(paso)

        plan_steps = []
        for p in pasos_activados:
            if p["accion"] in ("consultar_clima", "consultar_historial"):
                deps = []
            elif p["accion"] == "consultar_recomendaciones":
                deps = [s["descripcion"] for s in pasos_activados if s["accion"] in ("consultar_clima", "consultar_historial")]
            elif p["accion"] == "analizar_datos":
                deps = [s["descripcion"] for s in pasos_activados if s["accion"] in ("consultar_clima", "consultar_historial", "consultar_recomendaciones")]
            elif p["accion"] == "guardar_reporte":
                deps = [s["descripcion"] for s in pasos_activados if s["accion"] == "analizar_datos"]
            elif p["accion"] == "enviar_reporte_email":
                deps = [s["descripcion"] for s in pasos_activados if s["accion"] == "guardar_reporte"]
            else:
                deps = []

            plan_steps.append(PlanStep(
                action=p["accion"],
                description=p["descripcion"],
                dependencies=deps,
                priority=p["prioridad"],
                status="pending"
            ))

        return Plan(goal=solicitud, steps=plan_steps)
