# BITÁCORA — Agente-Clima

> Historia cronológica del proyecto. Cada entrada tiene fecha, código,
> resumen, y referencias a commits/archivos para trazabilidad completa.
> Diseñada para lectura tanto humana como por IA.

---

## [BIT-001] 2026-05-29 — Fundación del proyecto

**Commits**: `46fd028`, `1e6876a`

Arquitectura inicial del agente meteorológico autónomo:
- **Orquestador**: `AgenteMeteorologicoSimple` con LangChain + `gpt-4o` (GitHub Models)
- **4 herramientas**: `consultar_clima`, `guardar_reporte`, `consultar_historial`, `enviar_reporte_email`
- **Planificador de 6 pasos** con dependencias y ejecución secuenciada
- **15 comunas** de la Región de Los Lagos en `comunas.py`
- API gratuita Open-Meteo para datos climáticos
- Envío de reportes por SMTP (Gmail)
- Memoria persistente en `memoria/historial_reportes.json`
- Sistema de logging, métricas y trazas en `herramientas/monitoreo.py`

Stack inicial: `python-dotenv`, `langchain*`, `openai`, `pydantic`, `requests`, `flask`, `flask-cors`

---

## [BIT-002] 2026-06-05 — v1.5: Interfaz web + chatbot

**Commit**: `1e6876a` (Version 1.5)

Salto mayor: de consola a aplicación web completa.

### Arquitectura web
- Servidor Flask (`app.py`) con endpoints REST
- `GET /` → `templates/index.html` (Jinja2)
- `GET /api/comunas` → lista de comunas
- `GET /api/pronostico` → pronóstico 7 días con caché (10 min)
- `POST /api/chat` → chatbot con historial por sesión
- `POST /generar-reporte` → pipeline 6 pasos + envío email
- Flask-CORS para peticiones cross-origin

### Frontend Neo-Brutalista Pastel
- Layout 3 columnas: [menú negro 240px | chat/reporte 1fr | pronóstico 300px]
- Paleta: #E7E3D8 (fondo), #EBCF7C (sol), #D3D3D3 (nublado), #B8D6EB (lluvia)
- Chat con efecto máquina de escribir (18ms/carácter)
- Avatares circulares con borde negro: 👤 usuario, Logo.png agente
- Panel de pronóstico semanal con tarjetas, iconos y badges
- Botones de sugerencia rápida: outfit, lugar para salir
- Botones de herramienta: 📋 copiar, 🔊 leer en voz alta

### Archivos nuevos
- `templates/index.html`, `templates/metricas.html`
- `static/style.css`, `static/app-main.js`, `static/chat.js`, `static/pronostico.js`
- `static/Logo.png`, `static/Sol_Sprite.png`
- `herramientas/recomendaciones.py`, `memoria/lugares_recomendados.json`
- `iniciar.ps1` (script de arranque)

### Archivos eliminados
- `static/index.html` (reemplazado por `templates/index.html`)

### Bugs corregidos (v1.0 → v1.5)
1. CSS no cargaba con Go Live → ejecutar con Flask, no Live Server
2. Nombre incorrecto `styles.css` → `style.css`
3. Argumentos incorrectos en `generar_reporte()` → corregida firma completa
4. `generar_reporte()` retornaba formato incorrecto → `{exito, html_reporte, pasos_ejecutados}`
5. Overflow en flexbox del chat → `min-height: 0` + `flex-shrink: 0`

---

## [BIT-003] 2026-06-11 — Mejora del chat + métricas

**Commit**: `955483d` (mejora del chat)

- Dashboard de métricas en `/metricas` con tarjetas (requests, errores, tokens, costos)
- API de métricas: `GET /api/metricas`, `GET /api/metricas/detalle`
- Sprite animado del personaje (Sol_Sprite.png, grid 3x3)
- Mejoras en el sistema de chat y visualización

---

## [BIT-004] 2026-06-16 — Sesión de hardening de seguridad

**Commit**: `bd55fe6` (Commit para mejorar seguridad)

### 1. Easter egg: Autodestruct toggleable por chat
- Comandos: `!boom`, `/boom`, `boom!`, `explosión!`, `detonar`, `activar autodestruct`
- Cancelación: `!noboom`, `/noboom`, `cancelar autodestruct`, ESC, clic en overlay
- Flag `autodestructActivo` previene re-entrada
- Animación `pulse-hint` en el mensaje de cancelación

### 2. Defensas contra ataques de gasto de tokens (5 fixes)
| # | Fix | Ubicación |
|---|-----|-----------|
| 1 | `max_tokens=1024` en el LLM | `agente.py:34` |
| 2 | Ventana deslizante: máx 20 mensajes (10 intercambios) | `app.py:329-331` |
| 3 | Presupuesto de tokens: máx 50,000 por sesión | `app.py:333-341` |
| 4 | `maxlength="2000"` en input del chat | `index.html:39` |
| 5 | Truncado de historial: máx 50 reportes por ciudad | `historial.py:52-53` |

### 3. Fix: Overflow horizontal de mensajes largos
- `overflow-wrap: break-word`, `word-break: break-word` en `.mensaje`
- `overflow-x: hidden` en `.scroll-burbujas-chat` y `.panel-clima-derecho`
- `min-width: 0` en `.mensaje-fila`

### 4. Botón para cancelar respuesta del agente
- Reemplaza botones de enviar y micrófono con círculo rojo pulsante durante generación
- Flag `cancelarGeneracion` verificada al inicio de cada iteración de typewriter
- Flag `generandoRespuesta` previene re-entrada
- Limpieza unificada en `finally`

### 5. Pruebas de seguridad
Verificación de 5 capas: inyección de prompt (11 variantes), PII, inyección de código,
filtro ético, edge cases de falsos positivos.

### Estado final de seguridad
- [x] Rate limiting: 30 req/60s por sesión
- [x] Validación de entrada: inyección, PII, longitud (2000), código
- [x] Filtro ético: violencia, contenido ilegal, manipulación
- [x] Sanitización de salida: PII en respuestas del LLM
- [x] Auto-destrucción tras 3 violaciones (toggleable por chat)
- [x] `max_tokens=1024` en LLM
- [x] Ventana deslizante de historial (20 mensajes)
- [x] Presupuesto de tokens por sesión (50,000)
- [x] `maxlength` en frontend (2000 chars)

---

## [BIT-005] 2026-06-19 — Planificación: Geolocalización móvil

**Documento original**: `planificacion_ubicacion_movil.txt`

Funcionalidad planificada (sin implementar aún):

### Objetivo
Detectar ubicación del usuario vía GPS del dispositivo y auto-seleccionar
la comuna más cercana de Los Lagos, sin APIs externas de pago.

### Enfoque
- `navigator.geolocation.getCurrentPosition()` (API nativa del navegador)
- Cálculo de distancia Haversine en el backend (matemática pura)
- Comparación contra las 15 comunas en `COMUNAS_DE_LOS_LAGOS`
- Sin Google Maps API key, sin nuevas dependencias

### Arquitectura propuesta
```
[Celular] --GPS--> [navigator.geolocation] --lat/lon--> [POST /api/geolocalizar]
                                                              |
                                                  Haversine contra 15 comunas
                                                              |
                                                  Comuna más cercana (< 100km)
                                                              |
                                           { comuna_id, nombre, distancia_km }
                                                              |
                                  [app-main.js] --> seleccionarComuna(id, nombre)
```

### Cambios estimados (~60 líneas)
| Archivo | Cambio |
|---------|--------|
| `app.py` | +25 líneas: endpoint `POST /api/geolocalizar` + función haversine |
| `app-main.js` | +35 líneas: función `detectarUbicacion()` |
| `index.html` | +1 línea: botón 📍 |

### Casos edge
| Escenario | Comportamiento |
|-----------|---------------|
| Usuario fuera de la región (>100km) | API devuelve `null`, no se cambia ciudad |
| Usuario niega permiso de ubicación | Default Puerto Montt, botón 📍 activo |
| Navegador sin geolocation API | No se ejecuta, sin errores |
| Desktop sin chip GPS | Geolocation falla, no hace nada |
| GPS inexacto | Se elige la comuna más cercana igual |

---

## [BIT-006] 2026-06-19 — Detector semántico de contenido malicioso

**Commits**: `bef0a04` (cambios locales) + `d8e2329` (merge)

Aportado por compañero de equipo.

### Nuevo: `herramientas/detector_embedding.py` (208 líneas)
- Clasifica mensajes mediante embeddings semánticos con `SentenceTransformer` (`all-MiniLM-L6-v2`)
- Soporte multilingüe: español, inglés, francés, portugués, alemán, italiano, chino, japonés
- 5 categorías de riesgo: `seguro`, `prompt_injection`, `violencia`, `contenido_ilegal`, `manipulacion`
- **Umbrales**: bloqueo ≥ 0.82, zona gris ≥ 0.58, seguro < 0.58
- Clase `ResultadoEmbedding` con campos: `es_seguro`, `riesgo`, `similitud_max`, `categoria_match`, `ejemplo_match`, `mensaje`, `modelo_cargado`
- Instancia global `detector_embedding_global`
- Degradación elegante: si el modelo no carga, marca todo como seguro

### Modificado: `herramientas/seguridad.py`
- Integrado el detector de embeddings como capa adicional en `ValidadorEntrada.validar()`
- El resultado del embedding se incluye en el reporte de validación
- Ajustada la lógica de `es_seguro` y `riesgo_maximo` para compatibilizar ambos tipos de resultado

### Nuevas dependencias
- `sentence-transformers>=2.7.0`
- `numpy>=1.26.0`

---

## [BIT-007] 2026-06-19 — TTS (Text-to-Speech)

**Archivos**: `app.py` (endpoint TTS)

- Endpoint `POST /api/tts` usando `edge-tts` (gratis, sin API key)
- Convierte respuestas del agente a audio MP3
- Botón 🔊 en burbujas de chat
- Dependencia: `edge-tts>=7.0.0`

---

## [BIT-008] 2026-06-19 — Reordenamiento del proyecto

**Commit**: (este cambio)

### Objetivo
Limpiar la raíz del proyecto y organizar archivos por tipo.

### Cambios estructurales
| Antes | Después |
|-------|---------|
| `agente.py`, `app.py`, `comunas.py` en raíz | → `src/agente.py`, `src/app.py`, `src/comunas.py` |
| `memoria/*.json` | → `datos/*.json` |
| `iniciar.ps1` en raíz | → `scripts/iniciar.ps1` |
| `imagenes_referencia/`, `ERRORES/` | → `docs/imagenes/` |
| `RA2-Extraccion/` | → `docs/RA2-Extraccion/` |
| Reportes `.txt` sueltos | → Consolidados en esta `BITACORA.md` |

### Archivos eliminados
- `CODIGO_COMPLETO.txt` — redundante (git ya tiene el historial)
- `app_err.txt`, `app_out.txt` — logs temporales de Flask
- `reporte_sesion_2026-06-16.txt` — consolidado en [BIT-004]
- `REPORTE_v1.5.txt` — consolidado en [BIT-002]
- `planificacion_ubicacion_movil.txt` — consolidado en [BIT-005]
- `CHANGELOG.md` — consolidado aquí
- `memoria/` — carpeta vacía tras mover JSONs

### Estructura final
```
Agente-Clima/
├── README.md
├── BITACORA.md
├── requirements.txt
├── .env
├── .gitignore
├── src/
│   ├── agente.py
│   ├── app.py
│   └── comunas.py
├── herramientas/
│   ├── clima.py
│   ├── detector_embedding.py
│   ├── email_sender.py
│   ├── historial.py
│   ├── monitoreo.py
│   ├── planificador.py
│   ├── recomendaciones.py
│   └── seguridad.py
├── static/
│   ├── app-main.js
│   ├── chat.js
│   ├── pronostico.js
│   ├── style.css
│   ├── Logo.png
│   └── Sol_Sprite.png
├── templates/
│   ├── index.html
│   └── metricas.html
├── datos/
│   ├── historial_reportes.json
│   └── lugares_recomendados.json
├── logs/
│   └── agente-clima.log
├── scripts/
│   └── iniciar.ps1
├── docs/
│   ├── imagenes/
│   │   ├── referencia/
│   │   │   ├── al_iniciar.png
│   │   │   └── durante_conversacion.png
│   │   ├── actual/
│   │   │   ├── al_iniciar.png
│   │   │   └── durante_conversacion.png
│   │   └── errores/
│   │       └── no_aparecen_comunas.png
│   ├── RA2-Extraccion/
│   │   └── ...
│   └── planificacion.txt
└── .vscode/
    ├── settings.json
    └── tasks.json
```

---

## [BIT-009] 2026-06-19 — Refuerzo multilingüe de seguridad + suite de pruebas

**Commit**: `1747c28` (pull desde origin/main, aportado por compañero)

### Modificado: `herramientas/detector_embedding.py` (+46 líneas)
- Ampliados ejemplos semilla multilingües: añadidos alemán, italiano para inyección de prompt, violencia, contenido ilegal y manipulación
- Nuevos ejemplos de jailbreak: `developer mode override instructions`, `modo desarrollador ignora las reglas`, `jailbreak bypass`
- Nuevos ejemplos de manipulación: `deepfake to defame a politician`, `create fake news to cause panic` (multilenguaje)
- **Umbrales recalibrados**: `UMBRAL_BLOQUEO` 0.82 → **0.68**, `UMBRAL_SEGURO` 0.58 → **0.48** (mayor sensibilidad)

### Modificado: `herramientas/seguridad.py` (+44 líneas)
- Ampliadas `CATEGORIAS_RESTRINGIDAS` con keywords en inglés, francés, portugués, alemán e italiano para violencia, contenido ilegal y manipulación
- Optimización del `SanitizadorSalida`: caché de regex compilados (`_regex_cache` + `_compilar_patrones()`) para evitar recompilación en cada llamada

### Nuevo: `prueba_seguridad.py` (326 líneas)
Suite de pruebas completa con **9 categorías**:
| # | Categoría | Descripción |
|---|-----------|-------------|
| 1 | Inyección de prompt | Mensajes multilingües (8 idiomas) para bypass de instrucciones |
| 2 | Detección de PII | Email, teléfono, RUT chileno, tarjeta de crédito, mixto |
| 3 | Validación de longitud | Texto vacío, normal, y largo (2500 chars) |
| 4 | Código / inyección Python | XSS, eval, exec, subprocess, os.system, __import__ |
| 5 | Filtro ético | Violencia, ilegal, manipulación en español, inglés, francés, portugués |
| 6 | Mensajes seguros | Línea base en 8 idiomas (consultas de clima legítimas) |
| 7 | Limitador de tasa | 35+ peticiones en <60s deben ser bloqueadas |
| 8 | Sanitizador de salida | Verificación y redacción de PII en respuestas |
| 9 | Casos límite | Comandos camuflados, prompt injection mezclado, PII en preguntas, Unicode |

Resultado esperado: `passed/total` con conteo final de PASS/FAIL.

---

## Resumen de dependencias

```
python-dotenv>=1.0.0
langchain>=1.3.0
langchain-core>=1.4.0
langchain-openai>=1.2.0
langchain-community>=0.4.0
pydantic>=2.7.0
requests>=2.31.0
flask>=3.0.0
flask-cors>=5.0.0
edge-tts>=7.0.0
sentence-transformers>=2.7.0
numpy>=1.26.0
```

---

## Cómo ejecutar

```powershell
# Opción 1: Script de inicio
.\scripts\iniciar.ps1

# Opción 2: Manual
.\.venv\Scripts\python.exe src\app.py
```

URL local: `http://localhost:5000`
