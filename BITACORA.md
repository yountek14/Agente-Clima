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
│   ├── auth.py                    # Sistema de autenticación
│   ├── clima.py
│   ├── clima_fusion.py            # Fusión de datos meteorológicos
│   ├── clima_weatherapi.py        # Wrapper WeatherAPI
│   ├── detector_embedding.py
│   ├── email_sender.py
│   ├── historial.py
│   ├── historial_usuario.py       # Historial por usuario
│   ├── monitoreo.py
│   ├── planificador.py
│   ├── recomendaciones.py
│   └── seguridad.py
├── static/
│   ├── app-main.js
│   ├── auth.js                    # Lógica de autenticación
│   ├── chat.js
│   ├── pronostico.js
│   ├── style.css
│   ├── Logo.png
│   ├── Sol_Sprite.png
│   └── avatars/
│       └── avatar_default.svg
├── templates/
│   ├── index.html
│   ├── metricas.html
│   ├── perfil.html                # Página de perfil
│   ├── historial.html             # Página de historial
│   └── quienes_somos.html         # Página informativa
├── datos/
│   └── lugares_recomendados.json
├── memoria/
│   ├── usuarios.json              # Usuarios registrados
│   └── historial_usuarios.json    # Historial por usuario
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
│   └── RA2-Extraccion/
│       └── ...
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

## [BIT-010] 2026-06-19 — Sistema de autenticación, historial por usuario y mejoras meteorológicas

**Commit**: `71c965b` (feat: implementación completa de sistema de autenticación, historial por usuario y mejoras meteorológicas)

### 1. Sistema de autenticación completo

#### Backend (`herramientas/auth.py` - 323 líneas)
- Clase `GestorUsuarios` con persistencia en `memoria/usuarios.json`
- Hash de contraseñas con bcrypt (12 rondas), fallback a PBKDF2 si bcrypt no disponible
- Tokens de sesión de 64 caracteres (secrets.token_hex)
- Sesiones con expiración de 7 días
- CRUD completo: registro, login, logout, perfil, cambio de contraseña, foto de perfil

#### Endpoints de autenticación (`src/app.py`)
| Endpoint | Método | Función |
|----------|--------|---------|
| `/api/auth/registro` | POST | Crear cuenta (nombre, email, password) |
| `/api/auth/login` | POST | Iniciar sesión, retorna token |
| `/api/auth/logout` | POST | Cerrar sesión, elimina cookie |
| `/api/auth/estado` | GET | Verificar sesión activa |
| `/api/auth/perfil` | GET | Obtener perfil del usuario |
| `/api/auth/perfil` | PUT | Actualizar nombre/email |
| `/api/auth/perfil/password` | PUT | Cambiar contraseña |
| `/api/auth/perfil/foto` | POST | Subir foto de perfil |

#### Middleware de sesión
- Cookie `session_token` HttpOnly, SameSite=Lax, max-age 7 días
- Cookie `visitante_id` para conteo de consultas gratuitas
- `request.usuario_actual` disponible en todos los endpoints
- `request.visitante_id` para identificar visitantes

#### Frontend de autenticación (`static/auth.js` - 243 líneas)
- Modal de login/registro con estética manga (bordes negros, border-radius 40px)
- Verificación de sesión al cargar página
- Menú lateral dinámico: "Iniciar sesión" vs avatar + nombre + "Cerrar sesión"
- Botón "Historial" solo visible para usuarios logueados
- Autocompletado de correo en sección de reportes (readonly para logueados)

#### Páginas nuevas
| Página | Ruta | Descripción |
|--------|------|-------------|
| Perfil | `/perfil` | Editar nombre, email, contraseña, foto |
| Historial | `/historial` | Ver últimos 10 reportes con preview |
| Quiénes somos | `/quienes-somos` | Info del proyecto, equipo, tecnologías |

### 2. Control de acceso y límites

#### Visitantes (sin cuenta)
- Máximo 4 consultas al chat (persistencia por IP + cookie)
- Pueden generar reportes ingresando correo manualmente
- No ven opción "Historial" en menú
- No se guarda historial de sus reportes

#### Usuarios logueados
- Chat ilimitado (sujeto a rate limit 30/min)
- Correo autocompletado en reportes (readonly)
- Historial guardado (últimos 10 reportes)
- Acceso a página de historial
- Chatbot conoce su nombre (personalización)

### 3. Historial de reportes por usuario

#### Nuevo módulo (`herramientas/historial_usuario.py`)
- `consultar_historial_usuario(user_id, limite=3)` → string con historial
- `guardar_reporte_usuario(...)` → guarda reporte completo con HTML
- `obtener_todos_reportes_usuario(user_id)` → lista de reportes
- `obtener_reporte_usuario(user_id, index)` → reporte específico
- Máximo 10 reportes por usuario (FIFO)
- Persistencia en `memoria/historial_usuarios.json`

#### Pipeline de reporte modificado (`src/agente.py`)
- Nuevo parámetro `user_id` en `generar_reporte()`
- Paso 2: consulta historial del usuario (si existe)
- Paso 5: guarda reporte en historial del usuario (si está logueado)
- Prompt adaptativo según si hay historial o no
- Estructura HTML reorganizada:
  1. Header
  2. Condiciones en Tiempo Real
  3. Recomendaciones del Agente (arriba)
  4. Historial Comparativo (abajo, solo si existe)
  5. Footer

#### Endpoint de historial (`src/app.py`)
| Endpoint | Método | Función |
|----------|--------|---------|
| `/historial` | GET | Página HTML de historial |
| `/api/historial` | GET | Lista de reportes (sin HTML) |
| `/api/historial/<index>` | GET | Reporte específico (con HTML) |

### 4. Integración con WeatherAPI (doble fuente de datos)

#### Nuevo módulo (`herramientas/clima_weatherapi.py` - 94 líneas)
- Consulta WeatherAPI.com con latitud/longitud
- Mapeo de códigos WeatherAPI a WMO
- Datos: temperatura, precipitación, humedad, viento, nubosidad

#### Módulo de fusión (`herramientas/clima_fusion.py` - 131 líneas)
- **Estrategia conservadora**:
  - Precipitación: `max(Open-Meteo, WeatherAPI)` → si cualquiera detecta lluvia, se reporta
  - Temperatura: promedio de ambas APIs
  - Viento: promedio de ambas APIs
  - Código WMO: el más severo (función `wmo_severity()`)
  - Nubosidad: el valor más alto

#### Implementación en endpoints
- `/api/pronostico`: fusiona datos actuales de ambas APIs
- `/api/chat`: usa datos fusionados para contexto del chatbot
- `herramientas/clima.py`: usa fusión automáticamente si `WEATHERAPI_KEY` existe
- Fallback automático: si WeatherAPI falla, usa solo Open-Meteo

#### Configuración
```env
WEATHERAPI_KEY="tu_api_key_aqui"
```
- Plan gratuito: 1M llamadas/mes, sin tarjeta de crédito
- Registro: https://www.weatherapi.com/

### 5. Mejoras en precisión meteorológica

#### Datos de precipitación (`herramientas/clima.py`, `src/app.py`)
- Antes: solo `rain` (lluvia líquida)
- Ahora: `precipitation` (total), `rain`, `showers`, `snowfall`
- Tipo de precipitación detectado automáticamente:
  - Nieve → "Nevando (X cm)"
  - Chubascos → "Chubascos (X mm)"
  - Lluvia → "Lluvia (X mm)"
  - Otro → "Precipitación (X mm)"

#### Códigos WMO expandidos (`static/pronostico.js`)
- Antes: 8 códigos configurados (0, 1, 2, 3, 51, 53, 61, 80)
- Ahora: todos los códigos 0-99
  - Niebla (45, 48)
  - Lloviznas (51-57)
  - Lluvias (61-67)
  - Nieve (71-77)
  - Chubascos (80-86)
  - Tormentas (95-99)

#### Pronóstico semanal mejorado
- Nuevos datos: `precipitation_sum`, `precipitation_probability_max`
- Indicador visual 💧 en cada tarjeta con mm de precipitación
- Colores de fondo según intensidad de precipitación

### 6. Corrección de zona horaria

#### Problema
- `datetime.now()` usaba UTC → fecha incorrecta para Chile
- Ejemplo: mostraba "20 de junio" cuando en Chile era "19 de junio"

#### Solución
- Uso de `zoneinfo.ZoneInfo("America/Santiago")` en:
  - `src/app.py`: prompt del chatbot (fecha y hora actual)
  - `src/agente.py`: prompt de recomendaciones
  - `herramientas/recomendaciones.py`: `obtener_horario()`, `obtener_mes_actual()`
- Dependencia agregada: `tzdata>=2024.1`

### 7. Mejoras en chatbot

#### Contexto temporal
- System prompt ahora incluye: "Fecha y hora actual: viernes 19 de junio de 2026 a las 21:44 (hora de Chile)"
- Instrucción explícita: "Cuando te pregunten por 'mañana' o días específicos, usa los datos del pronóstico de 7 días"

#### Personalización
- Si usuario logueado: "El usuario se llama {nombre}. Úsalo para personalizar tus respuestas"
- Chatbot puede dirigirse al usuario por su nombre

#### Recomendaciones más concisas
- Antes: "párrafo analítico" con múltiples puntos → texto muy largo
- Ahora: "máximo 3-4 líneas" con:
  - 1 consejo rápido de vestimenta
  - 1-2 lugares recomendados máximo
  - Alerta de viento solo si aplica

#### LLM separado para texto
- Problema: `self.chain` tenía herramientas vinculadas → a veces devolvía respuestas vacías
- Solución: `self.llm_texto` sin herramientas para generación de texto
- Cadena separada: `prompt_texto | self.llm_texto`

### 8. Reorganización de estructura

#### Archivos movidos a `src/`
- `agente.py` → `src/agente.py`
- `app.py` → `src/app.py`
- `comunas.py` → `src/comunas.py`

#### Nuevos módulos en `herramientas/`
- `auth.py` - Sistema de autenticación
- `clima_weatherapi.py` - Wrapper para WeatherAPI
- `clima_fusion.py` - Lógica de fusión de datos
- `historial_usuario.py` - Historial por usuario

#### Nuevas páginas en `templates/`
- `perfil.html` - Página de perfil editable
- `historial.html` - Página de historial con modal
- `quienes_somos.html` - Información del proyecto

#### Nuevos archivos en `static/`
- `auth.js` - Lógica de autenticación frontend
- `avatars/avatar_default.svg` - Avatar por defecto

#### Datos movidos
- `memoria/lugares_recomendados.json` → `datos/lugares_recomendados.json`
- `memoria/usuarios.json` - Nuevo (usuarios registrados)
- `memoria/historial_usuarios.json` - Nuevo (historial por usuario)

### 9. Seguridad y validaciones

#### Rate limiting
- Chat: 30 requests/minuto por sesión
- Reportes: 30 requests/minuto por IP
- Visitantes: máximo 4 consultas gratuitas total

#### Validación de entrada
- Inyección de prompt (14 patrones regex + detector semántico)
- PII (email, teléfono, RUT, tarjeta)
- Longitud máxima: 2000 caracteres
- Código malicioso (XSS, eval, exec, subprocess)

#### Filtro ético
- Violencia, contenido ilegal, manipulación
- Multilingüe: español, inglés, francés, portugués, alemán, italiano

#### Sanitización de salida
- Detección y redacción de PII en respuestas del LLM

### 10. Mejoras en UI/UX

#### Modal de login/registro
- Estética manga: fondo `#E7E3D8`, borde negro 4px, border-radius 40px
- Animación de entrada (fadeIn + slideUp)
- Cierre con ESC o clic fuera del modal
- Switch entre login y registro sin cerrar modal

#### Previsualización de reporte
- Antes: iframe de 260px sin control de overflow → contenido se salía
- Ahora: iframe de 300px con `overflow: hidden` → contenido contenido

#### Avatar por defecto
- SVG inline (silueta de usuario)
- Borde negro 2px, tamaño 32x32px en menú, 120x120px en perfil

#### Menú lateral dinámico
- Visitante: "👤 Iniciar sesión"
- Logueado: avatar + nombre + "Cerrar sesión"
- Botón "Historial" solo visible para logueados

### 11. Dependencias agregadas
```
bcrypt>=4.0.0      # Hash de contraseñas
tzdata>=2024.1     # Zonas horarias IANA
```

### 12. Endpoints nuevos/resumidos
| Endpoint | Método | Función |
|----------|--------|---------|
| `/api/auth/registro` | POST | Crear cuenta |
| `/api/auth/login` | POST | Iniciar sesión |
| `/api/auth/logout` | POST | Cerrar sesión |
| `/api/auth/estado` | GET | Verificar sesión |
| `/api/auth/perfil` | GET/PUT | Perfil usuario |
| `/api/auth/perfil/password` | PUT | Cambiar contraseña |
| `/api/auth/perfil/foto` | POST | Subir foto |
| `/historial` | GET | Página historial |
| `/api/historial` | GET | Lista reportes |
| `/api/historial/<index>` | GET | Reporte específico |
| `/perfil` | GET | Página perfil |
| `/quienes-somos` | GET | Página info |

### 13. Archivos modificados (resumen)
- **45 archivos cambiados**, 4263 inserciones, 2433 eliminaciones
- 11 archivos nuevos creados
- 12 archivos eliminados (consolidados en bitácora)
- 8 archivos movidos/reorganizados

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
bcrypt>=4.0.0
tzdata>=2024.1
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
