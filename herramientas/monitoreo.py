import json
import uuid
import time
import os
import logging as std_logging
from datetime import datetime, timezone
from dataclasses import dataclass, field, asdict
from typing import Optional, List
from pathlib import Path


LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)


class LoggerEstructurado:
    def __init__(self, nombre: str = "agente-clima", nivel_minimo: str = "DEBUG",
                 archivo: bool = True):
        self.nombre = nombre
        self.niveles = {"DEBUG": 10, "INFO": 20, "WARNING": 30, "ERROR": 40, "CRITICAL": 50}
        self.nivel_minimo = self.niveles.get(nivel_minimo, 10)
        self.registros: list[dict] = []

        if archivo:
            log_path = LOG_DIR / f"{nombre}.log"
            manejador = std_logging.FileHandler(str(log_path), encoding="utf-8")
            manejador.setFormatter(std_logging.Formatter(
                "%(asctime)s | %(levelname)-8s | %(message)s"
            ))
            self._file_logger = std_logging.getLogger(f"file_{nombre}")
            self._file_logger.setLevel(std_logging.DEBUG)
            self._file_logger.addHandler(manejador)
        else:
            self._file_logger = None

    def _registrar(self, nivel: str, evento: str, trace_id: str = None, **metadata):
        if self.niveles.get(nivel, 0) < self.nivel_minimo:
            return
        registro = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "nivel": nivel,
            "logger": self.nombre,
            "evento": evento,
            "trace_id": trace_id or "sin-trace",
            **metadata
        }
        self.registros.append(registro)
        linea = json.dumps(registro, ensure_ascii=False, default=str)
        print(linea)
        if self._file_logger:
            getattr(self._file_logger, nivel.lower())(linea)

    def debug(self, evento: str, trace_id: str = None, **kwargs):
        self._registrar("DEBUG", evento, trace_id, **kwargs)
    def info(self, evento: str, trace_id: str = None, **kwargs):
        self._registrar("INFO", evento, trace_id, **kwargs)
    def warning(self, evento: str, trace_id: str = None, **kwargs):
        self._registrar("WARNING", evento, trace_id, **kwargs)
    def error(self, evento: str, trace_id: str = None, **kwargs):
        self._registrar("ERROR", evento, trace_id, **kwargs)
    def critical(self, evento: str, trace_id: str = None, **kwargs):
        self._registrar("CRITICAL", evento, trace_id, **kwargs)

    def obtener_por_nivel(self, nivel: str) -> list[dict]:
        return [r for r in self.registros if r["nivel"] == nivel]

    def obtener_por_trace(self, trace_id: str) -> list[dict]:
        return [r for r in self.registros if r["trace_id"] == trace_id]


logger_global = LoggerEstructurado("agente-clima")


@dataclass
class RegistroMetrica:
    timestamp: str
    operacion: str
    duracion_ms: float
    tokens_prompt: int = 0
    tokens_completion: int = 0
    tokens_total: int = 0
    costo_usd: float = 0.0
    exitoso: bool = True
    tipo_error: Optional[str] = None
    trace_id: str = ""


class RecolectorMetricas:
    PRECIOS = {
        "gpt-4o": {"prompt": 2.50, "completion": 10.00},
        "gpt-4o-mini": {"prompt": 0.15, "completion": 0.60},
        "gpt-4": {"prompt": 2.50, "completion": 10.00},
    }

    def __init__(self):
        self.metricas: list[RegistroMetrica] = []

    def estimar_costo(self, modelo: str, tokens_prompt: int, tokens_completion: int) -> float:
        precios = self.PRECIOS.get(modelo, self.PRECIOS["gpt-4o-mini"])
        return round(
            (tokens_prompt / 1_000_000) * precios["prompt"] +
            (tokens_completion / 1_000_000) * precios["completion"], 8
        )

    def registrar(self, operacion: str, duracion_ms: float,
                  tokens_prompt: int = 0, tokens_completion: int = 0,
                  exitoso: bool = True, tipo_error: str = None,
                  trace_id: str = "", modelo: str = "gpt-4o"):
        tokens_total = tokens_prompt + tokens_completion
        costo = self.estimar_costo(modelo, tokens_prompt, tokens_completion) if exitoso else 0.0
        self.metricas.append(RegistroMetrica(
            timestamp=datetime.now(timezone.utc).isoformat(),
            operacion=operacion,
            duracion_ms=round(duracion_ms, 2),
            tokens_prompt=tokens_prompt,
            tokens_completion=tokens_completion,
            tokens_total=tokens_total,
            costo_usd=costo,
            exitoso=exitoso,
            tipo_error=tipo_error,
            trace_id=trace_id,
        ))

    def resumen(self) -> dict:
        if not self.metricas:
            return {"total_operaciones": 0}
        exitosas = [m for m in self.metricas if m.exitoso]
        fallidas = [m for m in self.metricas if not m.exitoso]
        tiempos = [m.duracion_ms for m in exitosas]
        total_tokens = sum(m.tokens_total for m in exitosas)
        return {
            "total_operaciones": len(self.metricas),
            "exitosas": len(exitosas),
            "fallidas": len(fallidas),
            "tasa_error_pct": round(len(fallidas) / len(self.metricas) * 100, 2) if self.metricas else 0,
            "tiempo_promedio_ms": round(sum(tiempos) / len(tiempos), 2) if tiempos else 0,
            "tiempo_maximo_ms": round(max(tiempos), 2) if tiempos else 0,
            "tiempo_minimo_ms": round(min(tiempos), 2) if tiempos else 0,
            "tokens_totales": total_tokens,
            "costo_total_usd": round(sum(m.costo_usd for m in exitosas), 6),
        }

    def a_diccionarios(self) -> list[dict]:
        return [asdict(m) for m in self.metricas]


recolector_global = RecolectorMetricas()


@dataclass
class Span:
    span_id: str
    nombre: str
    trace_id: str
    parent_span_id: Optional[str] = None
    inicio: Optional[float] = None
    fin: Optional[float] = None
    duracion_ms: float = 0.0
    estado: str = "EN_PROGRESO"
    atributos: dict = field(default_factory=dict)
    error: Optional[str] = None


@dataclass
class Traza:
    trace_id: str
    nombre: str
    spans: list = field(default_factory=list)
    timestamp_inicio: Optional[str] = None
    timestamp_fin: Optional[str] = None
    duracion_total_ms: float = 0.0
    estado: str = "EN_PROGRESO"
    metadata: dict = field(default_factory=dict)


class SistemaTrazas:
    def __init__(self):
        self.trazas: list[Traza] = []
        self._traza_activa: Optional[Traza] = None
        self._spans_activos: dict[str, Span] = {}

    def iniciar_traza(self, nombre: str, **metadata) -> Traza:
        traza = Traza(
            trace_id=str(uuid.uuid4())[:8],
            nombre=nombre,
            timestamp_inicio=datetime.now(timezone.utc).isoformat(),
            metadata=metadata
        )
        self.trazas.append(traza)
        self._traza_activa = traza
        return traza

    def iniciar_span(self, nombre: str, parent_span_id: str = None, **atributos) -> Span:
        if not self._traza_activa:
            raise RuntimeError("No hay traza activa")
        span = Span(
            span_id=str(uuid.uuid4())[:8],
            nombre=nombre,
            trace_id=self._traza_activa.trace_id,
            parent_span_id=parent_span_id,
            atributos=atributos
        )
        span.inicio = time.perf_counter()
        self._traza_activa.spans.append(span)
        self._spans_activos[span.span_id] = span
        return span

    def finalizar_span(self, span: Span, estado: str = "EXITOSO", error: str = None, **atributos_extra):
        span.fin = time.perf_counter()
        span.duracion_ms = round((span.fin - span.inicio) * 1000, 2)
        span.estado = estado
        if error:
            span.error = error
        span.atributos.update(atributos_extra)
        self._spans_activos.pop(span.span_id, None)

    def finalizar_traza(self, estado: str = "EXITOSO"):
        if self._traza_activa:
            self._traza_activa.timestamp_fin = datetime.now(timezone.utc).isoformat()
            total = sum(s.duracion_ms for s in self._traza_activa.spans if s.parent_span_id is None)
            self._traza_activa.duracion_total_ms = round(total, 2)
            self._traza_activa.estado = estado
            self._traza_activa = None

    def obtener_traza(self, trace_id: str) -> Optional[Traza]:
        for t in self.trazas:
            if t.trace_id == trace_id:
                return t
        return None

    def obtener_traza_activa(self) -> Optional[Traza]:
        return self._traza_activa


sistema_trazas_global = SistemaTrazas()


class AnalizadorTrazas:
    @staticmethod
    def resumir(trazas: list[Traza]) -> dict:
        total = len(trazas)
        errores = sum(1 for t in trazas if t.estado == "ERROR")
        duraciones = [t.duracion_total_ms for t in trazas if t.duracion_total_ms > 0]
        tiempos_por_etapa: dict[str, list] = {}
        for t in trazas:
            for s in t.spans:
                tiempos_por_etapa.setdefault(s.nombre, []).append(s.duracion_ms)
        return {
            "total_trazas": total,
            "trazas_con_error": errores,
            "tasa_exito_pct": round(((total - errores) / total) * 100, 1) if total else 0,
            "duracion_promedio_ms": round(sum(duraciones) / len(duraciones), 2) if duraciones else 0,
            "duracion_maxima_ms": round(max(duraciones), 2) if duraciones else 0,
            "promedio_por_etapa_ms": {
                etapa: round(sum(vals) / len(vals), 2)
                for etapa, vals in tiempos_por_etapa.items()
            },
        }

    @staticmethod
    def detectar_anomalias(trazas: list[Traza], umbral_desviaciones: float = 2.0) -> list[dict]:
        from statistics import mean, stdev
        spans_totales = []
        for t in trazas:
            for s in t.spans:
                spans_totales.append({"trace_id": t.trace_id, "etapa": s.nombre, "duracion_ms": s.duracion_ms})
        if not spans_totales:
            return []
        agrupado = {}
        for sp in spans_totales:
            agrupado.setdefault(sp["etapa"], []).append(sp["duracion_ms"])
        stats = {etapa: {"media": mean(vals), "std": stdev(vals) if len(vals) > 1 else 0}
                 for etapa, vals in agrupado.items()}
        anomalias = []
        for sp in spans_totales:
            s = stats[sp["etapa"]]
            z = (sp["duracion_ms"] - s["media"]) / (s["std"] if s["std"] > 0 else 1)
            if abs(z) > umbral_desviaciones:
                anomalias.append({**sp, "z_score": round(z, 2)})
        return sorted(anomalias, key=lambda x: x["z_score"], reverse=True)

    @staticmethod
    def mostrar_cascada(traza: Traza) -> str:
        lineas = [f"\n{'='*70}", f"TRAZA: {traza.nombre} [{traza.trace_id}]",
                  f"Estado: {traza.estado} | Duracion total: {traza.duracion_total_ms}ms",
                  f"{'='*70}"]
        if not traza.spans:
            lineas.append("  (sin spans)")
            return "\n".join(lineas)
        inicio_min = min(s.inicio for s in traza.spans if s.inicio is not None)
        duracion_max = max((s.fin or s.inicio) - inicio_min for s in traza.spans if s.inicio is not None) * 1000
        ancho = 40
        lineas.append(f"\n{'Span':<25} {'Dur(ms)':>8}  {'Cascada temporal':^{ancho}}")
        lineas.append(f"{'─'*25} {'─'*8}  {'─'*ancho}")
        for span in traza.spans:
            if span.inicio is None:
                continue
            offset_ms = (span.inicio - inicio_min) * 1000
            pos = int((offset_ms / duracion_max) * ancho) if duracion_max > 0 else 0
            ancho_bar = max(1, int((span.duracion_ms / duracion_max) * ancho)) if duracion_max > 0 else 1
            nivel = 0
            pid = span.parent_span_id
            while pid:
                nivel += 1
                ps = next((s for s in traza.spans if s.span_id == pid), None)
                pid = ps.parent_span_id if ps else None
            nombre_display = f"{'  ' * nivel}{span.nombre}"[:24]
            caracter = "#" if span.estado == "EXITOSO" else "X"
            barra = (" " * pos + caracter * ancho_bar)[:ancho].ljust(ancho)
            icono = "OK" if span.estado == "EXITOSO" else "ERR"
            lineas.append(f"{nombre_display:<25} {span.duracion_ms:>7.1f}  |{barra}| {icono}")
        return "\n".join(lineas)
