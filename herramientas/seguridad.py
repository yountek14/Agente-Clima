import re
import time
from dataclasses import dataclass, field
from typing import Optional, Dict, List

from herramientas.detector_embedding import detector_embedding_global as detector_embedding


@dataclass
class ResultadoValidacion:
    es_valido: bool
    mensaje: str
    riesgo: str = "bajo"
    detalles: dict = field(default_factory=dict)


CATEGORIAS_RESTRINGIDAS = {
    "violencia": [
        "hackear", "atacar", "explotar vulnerabilidad", "destruir",
        "arma", "bomba", "daño físico", "violencia",
        "hack", "attack", "exploit", "destroy", "weapon",
        "bomb", "physical harm", "violence", "hacker",
        "pirater", "attaquer", "exploiter", "détruire",
        "arme", "bombe", "dommage physique",
        "hackear", "atacar", "explorar vulnerabilidade", "destruir",
        "bomba", "dano físico", "violência",
        "hacken", "angreifen", "zerstören", "waffe",
        "bombe", "körperlicher schaden", "gewalt",
        "hackerare", "attaccare", "distruggere", "arma",
        "bomba", "danno fisico", "violenza",
    ],
    "contenido_ilegal": [
        "robar datos", "suplantar identidad", "falsificar",
        "evadir impuestos", "lavado de dinero", "tráfico",
        "steal data", "impersonate", "forge", "forgery",
        "evade tax", "money laundering", "trafficking",
        "falsify", "identity theft", "tax evasion",
        "voler des données", "usurper", "falsifier",
        "fraude fiscale", "blanchir", "trafic",
        "falsificar documentos", "sonegar impostos",
        "roubar dados", "suplantar",
        "stehlen daten", "fälschen", "geldwäsche",
        "rubare dati", "falsificare", "riciclaggio",
    ],
    "manipulacion": [
        "manipular personas", "engaño masivo", "desinformación",
        "propaganda", "deepfake dañino",
        "manipulate people", "mass deception", "disinformation",
        "propaganda", "harmful deepfake", "fake news",
        "manipuler", "désinformation", "tromperie massive",
        "propagande", "deepfake nuisible",
        "manipular pessoas", "desinformação", "engano em massa",
        "propaganda", "notícias falsas",
        "manipulieren", "desinformation", "massenbetrug",
        "manipolare", "disinformazione", "inganno di massa",
        "deepfake dannoso",
    ],
}


class ValidadorEntrada:
    PATRONES_INYECCION = [
        r"(?i)ignora\s+(todas\s+)?las\s+instrucciones\s+(anteriores|previas)",
        r"(?i)ignore\s+(all\s+)?(previous|prior|above)\s+instructions",
        r"(?i)system\s*prompt",
        r"(?i)prompt\s+del\s+sistema",
        r"(?i)olvida\s+(todo|tus\s+instrucciones)",
        r"(?i)forget\s+(your|all)\s+instructions",
        r"(?i)act\s+as\s+(if\s+you\s+are|a)\s+",
        r"(?i)actúa\s+como\s+si\s+(fueras|eres)",
        r"(?i)eres\s+ahora\s+un",
        r"(?i)you\s+are\s+now\s+a",
        r"(?i)jailbreak",
        r"(?i)DAN\s+mode",
        r"(?i)developer\s+mode",
        r"(?i)modo\s+(desarrollador|admin)",
    ]

    PATRONES_PII = {
        "email": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
        "telefono": r"(?:\+?56)?\s*(?:9\s*\d{4}\s*\d{4}|[2-9]\d{7,8})",
        "rut_chileno": r"\b\d{1,2}\.?\d{3}\.?\d{3}-?[\dkK]\b",
        "tarjeta_credito": r"\b(?:\d{4}[-\s]?){3}\d{4}\b",
    }

    PATRONES_CODIGO = [
        r"<script[^>]*>",
        r"javascript:",
        r"eval\(",
        r"exec\(",
        r"__import__",
        r"subprocess",
        r"os\.system",
    ]

    def __init__(self, max_longitud: int = 2000):
        self.max_longitud = max_longitud
        self.historial: list[dict] = []

    def detectar_inyeccion(self, texto: str) -> ResultadoValidacion:
        encontrados = []
        for patron in self.PATRONES_INYECCION:
            if re.search(patron, texto):
                encontrados.append(patron)
        if encontrados:
            return ResultadoValidacion(False, "Intento de inyección de prompt detectado",
                                       riesgo="critico", detalles={"patrones": encontrados})
        return ResultadoValidacion(True, "Sin inyección detectada")

    def detectar_pii(self, texto: str) -> ResultadoValidacion:
        pii = {}
        for tipo, patron in self.PATRONES_PII.items():
            coincidencias = re.findall(patron, texto)
            if coincidencias:
                pii[tipo] = len(coincidencias)
        if pii:
            return ResultadoValidacion(False, f"PII detectado: {', '.join(pii.keys())}",
                                       riesgo="alto", detalles={"pii_tipos": pii})
        return ResultadoValidacion(True, "Sin PII detectado")

    def validar_longitud(self, texto: str) -> ResultadoValidacion:
        if len(texto) == 0:
            return ResultadoValidacion(False, "Texto vacío", riesgo="bajo")
        if len(texto) > self.max_longitud:
            return ResultadoValidacion(False, f"Texto excede máximo ({len(texto)}/{self.max_longitud})",
                                       riesgo="medio")
        return ResultadoValidacion(True, f"Longitud válida ({len(texto)})")

    def validar_contenido(self, texto: str) -> ResultadoValidacion:
        problemas = []
        ratio_especiales = sum(1 for c in texto if not c.isalnum() and not c.isspace()) / max(len(texto), 1)
        if ratio_especiales > 0.4:
            problemas.append("Alto ratio de caracteres especiales")
        for patron in self.PATRONES_CODIGO:
            if re.search(patron, texto, re.IGNORECASE):
                problemas.append(f"Código sospechoso: {patron}")
        if problemas:
            return ResultadoValidacion(False, "; ".join(problemas), riesgo="alto", detalles={"problemas": problemas})
        return ResultadoValidacion(True, "Contenido válido")

    def validar(self, texto: str) -> dict:
        resultados = {
            "inyeccion": self.detectar_inyeccion(texto),
            "pii": self.detectar_pii(texto),
            "longitud": self.validar_longitud(texto),
            "contenido": self.validar_contenido(texto),
        }

        emb_resultado = detector_embedding.evaluar(texto)
        resultados["embedding"] = emb_resultado

        es_seguro = all(
            r.es_valido if hasattr(r, "es_valido") else r.es_seguro
            for r in resultados.values()
        )
        niveles = ["bajo", "medio", "alto", "critico"]
        riesgo_maximo = max(
            [r for r in resultados.values() if hasattr(r, "riesgo")],
            key=lambda r: niveles.index(r.riesgo)
        ).riesgo
        reporte = {"es_seguro": es_seguro, "riesgo_maximo": riesgo_maximo, "validaciones": resultados}
        self.historial.append(reporte)
        return reporte


class FiltroEtico:
    def __init__(self):
        self.categorias = CATEGORIAS_RESTRINGIDAS

    def evaluar(self, texto: str) -> dict:
        texto_lower = texto.lower()
        categorias_detectadas = []
        terminos_detectados = []
        for categoria, terminos in self.categorias.items():
            for termino in terminos:
                if termino in texto_lower:
                    categorias_detectadas.append(categoria)
                    terminos_detectados.append(termino)
        categorias_unicas = list(set(categorias_detectadas))
        es_seguro = len(categorias_unicas) == 0
        return {
            "es_seguro": es_seguro,
            "categorias": categorias_unicas,
            "terminos": terminos_detectados,
            "mensaje": "Contenido aprobado" if es_seguro else f"Bloqueado: {categorias_unicas}",
        }


class LimitadorTasa:
    def __init__(self, max_peticiones: int = 30, ventana_segundos: float = 60.0):
        self.max_peticiones = max_peticiones
        self.ventana = ventana_segundos
        self.peticiones: Dict[str, list] = {}

    def permitir(self, clave: str) -> tuple[bool, int]:
        ahora = time.time()
        if clave not in self.peticiones:
            self.peticiones[clave] = []
        self.peticiones[clave] = [t for t in self.peticiones[clave] if ahora - t < self.ventana]
        if len(self.peticiones[clave]) >= self.max_peticiones:
            return False, 0
        self.peticiones[clave].append(ahora)
        restantes = self.max_peticiones - len(self.peticiones[clave])
        return True, restantes


class SanitizadorSalida:
    PATRONES_PII_SALIDA = {
        "email": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
        "rut_chileno": r"\b\d{1,2}\.?\d{3}\.?\d{3}-?[\dkK]\b",
        "tarjeta_credito": r"\b(?:\d{4}[-\s]?){3}\d{4}\b",
    }

    _regex_cache: dict[str, re.Pattern] = {}

    @classmethod
    def _compilar_patrones(cls):
        if not cls._regex_cache:
            for tipo, patron in cls.PATRONES_PII_SALIDA.items():
                cls._regex_cache[tipo] = re.compile(patron)

    def verificar_pii(self, texto: str) -> ResultadoValidacion:
        self._compilar_patrones()
        pii = {}
        for tipo, patron in self._regex_cache.items():
            coincidencias = patron.findall(texto)
            if coincidencias:
                pii[tipo] = len(coincidencias)
        if pii:
            return ResultadoValidacion(False, f"PII en salida: {pii}", riesgo="alto", detalles={"pii": pii})
        return ResultadoValidacion(True, "Salida limpia")

    def sanitizar_pii(self, texto: str) -> str:
        self._compilar_patrones()
        for tipo, patron in self._regex_cache.items():
            texto = patron.sub(f"[{tipo.upper()}_REDACTADO]", texto)
        return texto


validador_entrada_global = ValidadorEntrada(max_longitud=2000)
filtro_etico_global = FiltroEtico()
limitador_tasa_global = LimitadorTasa(max_peticiones=30, ventana_segundos=60)
sanitizador_salida_global = SanitizadorSalida()
