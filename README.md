# AgenteClima - Agente Meteorologico Autonomo

Sistema agente inteligente para generacion automatizada de reportes meteorologicos con envio por correo electronico, chatbot conversacional, texto a voz y dashboard de monitoreo. Construido sobre **LangChain**, **Flask** y **GPT-4o (GitHub Models)**.

---

## Funcionalidades

| | |
|---|---|
| **Chatbot IA** | Conversacion contextualizada con datos climaticos en tiempo real |
| **Reportes automaticos** | Pipeline de 5 pasos: consulta clima, historial, analisis IA, guardado, envio por email |
| **Pronostico 7 dias** | Visualizacion por tarjetas con codigos WMO oficiales |
| **Texto a voz** | Edge TTS para leer respuestas en voz natural (espanol) |
| **Recomendaciones** | Lugares y actividades sugeridos segun clima, hora y temporada |
| **Sistema de usuarios** | Registro, login, perfil con avatar, historial personal |
| **Seguridad multicapa** | Deteccion de inyecciones (8 idiomas), filtro PII, filtro etico, rate limiting |
| **Dashboard metricas** | Monitoreo en tiempo real de trazas, tokens, costos y requests HTTP |
| **Stand Summit** | Pagina de exhibicion interactiva en `/stand` |

---

## Arquitectura

```
Usuario (Web/API) --> Flask (app.py) --> Agente LangChain (agente.py)
                                              |
                    ┌─────────────────────────┼─────────────────────────┐
                    │            │            │            │            │
               Planificar   Clima en     Historial   Analisis IA    Email
               (5 pasos)    vivo         usuario     (GPT-4o)       (SMTP)
                            │                         │
                    Open-Meteo API              GitHub Models
                    + WeatherAPI (fusion)       (Azure inference)
```

### Pipeline de generacion de reportes

1. **Consulta climatica**: `consultar_clima` obtiene datos en vivo desde Open-Meteo (con fusion opcional WeatherAPI)
2. **Recuperacion contextual**: `consultar_historial_usuario` lee reportes previos del usuario
3. **Analisis con IA**: GPT-4o sintetiza datos actuales + historicos + recomendaciones de lugares
4. **Persistencia**: `guardar_reporte_usuario` almacena el reporte en el historial del usuario
5. **Entrega**: `enviar_reporte_email` envia el HTML formateado por SMTP

---

## Justificacion de Componentes

| Componente | Framework / Libreria | Justificacion |
|---|---|---|
| **LLM** | `langchain-openai` + GitHub Models (gpt-4o) | Acceso gratuito a modelos via token GitHub; function calling nativo |
| **Framework agente** | `langchain-core` (BaseTool, ChatPromptTemplate, bind_tools) | Abstracciones maduras para tools con esquemas Pydantic |
| **Backend web** | Flask + Jinja2 | Servidor liviano, 15+ endpoints REST, plantillas HTML |
| **Memoria persistente** | JSON + sistema de archivos | Sin dependencias externas; reportes e historial entre sesiones |
| **Herramienta clima** | Open-Meteo API (gratuita, sin API key) + WeatherAPI (fusion opcional) | Datos en tiempo real con codigo WMO oficial + fuente redundante |
| **Herramienta email** | `smtplib` (stdlib) + Gmail SMTP | Envio directo sin servicios de terceros |
| **Texto a voz** | `edge-tts` | TTS gratuito con voz natural en espanol (Microsoft Edge) |
| **Seguridad** | `sentence-transformers`, `bcrypt`, regex multilenguaje | Deteccion semantica de inyecciones, hashing de passwords, filtros en 8 idiomas |
| **Planificacion** | `herramientas/planificador.py` (dataclasses) | Descomposicion dinamica de tareas con dependencias y prioridades |
| **Monitoreo** | `herramientas/monitoreo.py` + `/metricas` | Logging estructurado, trazas, token budget (50K/sesion) |

---

## Ejemplos de Toma de Decisiones

### 1. Seleccion visual adaptativa por codigo WMO
```python
# En agente.py - obtener_configuracion_visual()
if wmo_code in [0, 1]:       # Despejado -> icono sol
    return assets["despejado"]
elif wmo_code in [2, 3]:     # Nublado -> icono nube
    return assets["nublado"]
elif wmo_code >= 51:         # Lluvia -> icono lluvia
    return assets["lluvia"]
```

### 2. Alerta de seguridad por viento
El prompt del LLM incluye: "Si la velocidad del viento supera los 40 km/h, incluye una alerta de seguridad explicita."

### 3. Deteccion de inyecciones multi-idioma
```python
# Deteccion semantica con sentence-transformers (8 idiomas)
# + regex para patrones de prompt injection
# + 3 violaciones = auto-destruccion del agente
```

---

## Configuracion y Ejecucion

```bash
# 1. Clonar y entrar al proyecto
git clone <url-del-repo>
cd Agente-Clima

# 2. Crear y activar entorno virtual
python -m venv .venv
.venv\Scripts\activate     # Windows
# source .venv/bin/activate  # Linux/Mac

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Configurar variables de entorno
copy .env.example .env     # Windows
# cp .env.example .env       # Linux/Mac
# Luego editar .env con tus claves reales

# 5. Ejecutar
python run.py
```

El servidor arranca en `http://localhost:5000`.

Variables requeridas en `.env`:

```env
OPENAI_BASE_URL="https://models.inference.ai.azure.com"
GITHUB_TOKEN="github_pat_TU_TOKEN_AQUI"
OPENAI_API_KEY="github_pat_TU_TOKEN_AQUI"

LANGSMITH_TRACING="true"          # Opcional
LANGSMITH_API_KEY="lsv2_pt_TU_KEY_AQUI"
LANGSMITH_PROJECT="agente_meteorologico_ep2"

SMTP_SERVER="smtp.gmail.com"
SMTP_PORT=587
EMAIL_REMITENTE="tu_correo@gmail.com"
EMAIL_PASSWORD="tu_app_password"

WEATHERAPI_KEY="tu_api_key_aqui"  # Opcional (fallback a Open-Meteo)
```

Tambien se puede usar el script PowerShell:
```powershell
.\scripts\iniciar.ps1
```

---

## Estructura del Proyecto

```
Agente-Clima/
├── src/
│   ├── app.py                      # Servidor Flask (API + 20+ endpoints)
│   ├── agente.py                   # Orquestacion principal del agente
│   └── comunas.py                  # Catalogo de 15 comunas (Los Lagos)
├── herramientas/
│   ├── clima.py                    # Tool: consulta Open-Meteo API
│   ├── clima_weatherapi.py         # Tool: consulta WeatherAPI
│   ├── clima_fusion.py             # Fusion de datos de ambas fuentes
│   ├── historial.py                # Tool: historial compartido
│   ├── historial_usuario.py        # Tool: historial por usuario
│   ├── email_sender.py             # Tool: envio SMTP
│   ├── recomendaciones.py          # Tool: lugares y actividades segun clima
│   ├── planificador.py             # Planificacion y descomposicion de tareas
│   ├── seguridad.py                # Validacion, filtro etico, rate limiting
│   ├── auth.py                     # Autenticacion y manejo de sesiones
│   ├── detector_embedding.py       # Detector semantico de inyecciones
│   └── monitoreo.py                # Logging, metricas y trazas
├── static/
│   ├── style.css                   # Estilos Neo-Brutalistas Pastel
│   ├── chat.js                     # Chatbot interactivo + TTS
│   ├── pronostico.js               # Panel de pronostico 7 dias
│   ├── auth.js                     # Login, registro y perfil
│   └── app-main.js                 # Orquestacion del frontend
├── templates/
│   ├── index.html                  # Dashboard principal
│   ├── historial.html              # Historial de reportes del usuario
│   ├── perfil.html                 # Editor de perfil
│   ├── metricas.html               # Dashboard de monitoreo
│   ├── quienes_somos.html          # Informacion del proyecto
│   └── stand.html                  # Pagina de exhibicion Summit IA
├── datos/                          # Datos JSON persistentes (recomendaciones, historial)
├── memoria/                        # Datos de usuarios y sesiones
├── logs/                           # Logs de ejecucion
├── scripts/                        # Scripts de utilidad (iniciar.ps1)
├── docs/                           # Documentacion, guias y capturas
├── .env.example                    # Template de variables de entorno
├── requirements.txt                # Dependencias Python
├── run.py                          # Punto de entrada: python run.py
├── prueba_seguridad.py             # Suite de tests de seguridad (9 categorias)
└── BITACORA.md                     # Historial completo del proyecto
```

---

## Seguridad

El sistema implementa 7 capas de seguridad:

| Capa | Descripcion |
|---|---|
| Deteccion de inyecciones | Regex + embeddings semanticos en 8 idiomas (es, en, fr, de, pt, ru, zh, ja) |
| Filtro PII | Deteccion y redaccion de datos personales (RUT, email, telefono, IP) |
| Filtro etico | Bloqueo de contenido inapropiado, violento o peligroso |
| Rate limiting | Maximo 30 requests por 60 segundos por IP |
| Token budget | Limite de 50K tokens por sesion para control de costos |
| Passwords | Hashing con bcrypt para todos los usuarios |
| Auto-destruccion | Bloqueo del agente tras 3 violaciones de seguridad detectadas |

---

## Referencias

- LangChain. (2024). *Agents*. https://python.langchain.com/docs/modules/agents/
- OpenAI. (2024). *Function Calling Guide*. https://platform.openai.com/docs/guides/function-calling
- Open-Meteo. (2024). *Weather API*. https://open-meteo.com/en/docs
- WeatherAPI. (2024). *Weather API*. https://www.weatherapi.com/
- WMO. (2024). *Weather Codes*. https://www.nodc.noaa.gov/archive/arc0021/0002199/1.1/data/0-data/HTML/WMO-CODE/WMO4677.HTM
- Sentence-Transformers. (2024). *Documentation*. https://www.sbert.net/
- GitHub Models. (2024). *Marketplace*. https://github.com/marketplace/models
