# Ingeniería de Soluciones con Inteligencia Artificial

Este repositorio contiene todos los materiales, ejemplos y prácticas del curso **Ingeniería de Soluciones con Inteligencia Artificial**. El curso está organizado en tres grandes módulos (RA), cada uno con submódulos (IL) y ejemplos prácticos en Python y Jupyter.

---

## Descripción General

El curso cubre desde los fundamentos de la IA generativa y el prompt engineering, hasta el desarrollo de agentes inteligentes y las mejores prácticas para llevar soluciones a producción, incluyendo observabilidad, seguridad y ética.

- **Nivel:** Intermedio
- **Modalidad:** Práctica y conceptual
- **Requisitos:** Python básico, interés en IA

### Herramienta de entorno: [uv](https://docs.astral.sh/uv/) (Astral)

En este curso el flujo **recomendado y el que mejor evita dolores de cabeza** es **[uv](https://docs.astral.sh/uv/)**: instala dependencias muy rápido, usa el **`uv.lock`** para que todos tengan **las mismas versiones** (Windows, macOS o Linux), y gestiona la versión de Python del proyecto sin pelearte con el Python del sistema. No es obligatorio, pero es la opción más moderna y alineada con cómo se trabaja hoy en proyectos Python serios.

---

## Inicio Rápido (Setup para Estudiantes)

### 1. Hacer Fork y Clonar

```bash
# 1. Hacer fork desde GitHub (botón "Fork" en la esquina superior derecha)
# 2. Clonar tu fork
git clone https://github.com/TU-USUARIO/Ingenier-a-de-Soluciones-con-Inteligencia-Artificial.git
cd Ingenier-a-de-Soluciones-con-Inteligencia-Artificial
```

### 2. Entorno virtual e instalar dependencias

Las dependencias están declaradas en `pyproject.toml`. Con **uv**, el archivo **`uv.lock`** fija versiones exactas para que el curso sea **reproducible** en cualquier máquina. El proyecto pide **Python 3.11 o superior** (`requires-python` en `pyproject.toml`).

#### Opción recomendada: [uv](https://docs.astral.sh/uv/) (Astral)

**1. Instalar uv** (la guía oficial y más opciones: [Installing uv](https://docs.astral.sh/uv/getting-started/installation/)).

**macOS / Linux:**

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows (PowerShell como administrador o usuario normal):**

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Tras instalar, cierra y abre la terminal (o reinicia el IDE) para que `uv` quede en el `PATH`.

**2. Sincronizar el proyecto** (crea `.venv` e instala todo según el lockfile):

```bash
uv sync
```

**3. Activar el entorno** (opcional si vas a usar solo `uv run …`):

```bash
# macOS / Linux
source .venv/bin/activate

# Windows (cmd)
.venv\Scripts\activate.bat

# Windows (PowerShell)
.venv\Scripts\Activate.ps1
```

Si PowerShell bloquea scripts, ejecuta una vez: `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser` (solo en tu usuario).

**4. Comprobar que todo importa bien:**

```bash
uv run python scripts/verify_env.py
```

**Comandos útiles con uv (sin activar el venv):** muchas veces puedes evitar `activate` y usar:

```bash
uv run jupyter lab
uv run pytest
uv run python ruta/al/script.py
```

**Añadir una dependencia** (mantiene el lock actualizado): `uv add nombre-paquete` y vuelve a commitear `pyproject.toml` y `uv.lock`.

**Python no instalado en tu máquina:** uv puede instalar una versión compatible para el proyecto, por ejemplo:

```bash
uv python install 3.11
uv sync
```

(Consulta [Python versions](https://docs.astral.sh/uv/concepts/python-versions/) en la documentación de uv.)

#### Opción alternativa: venv y pip

Si no puedes usar uv, puedes reproducir un entorno parecido con pip (versiones **no** fijadas por `uv.lock`):

```bash
python3 -m venv .venv
source .venv/bin/activate   # macOS / Linux
# Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configurar Variables de Entorno

```bash
# Copiar el archivo de ejemplo (macOS / Linux)
cp .env.example .env
```

En **Windows** (cmd): `copy .env.example .env` — en PowerShell: `Copy-Item .env.example .env`

Edita el archivo `.env` con tus credenciales:

```env
OPENAI_BASE_URL="https://models.inference.ai.azure.com"
GITHUB_BASE_URL="https://models.inference.ai.azure.com"
OPENAI_EMBEDDINGS_URL="https://models.github.ai/inference"
GITHUB_TOKEN="tu_github_token_aqui"
LANGSMITH_TRACING="true"
LANGSMITH_API_KEY="tu_langsmith_api_key_aqui"
LANGSMITH_PROJECT="ingenieria_soluciones_con_ia"
```

**Cómo obtener tus tokens:**
- **GITHUB_TOKEN**: Ve a [GitHub Settings > Developer settings > Personal access tokens](https://github.com/settings/tokens) y crea un token con permisos de lectura. Asegúrate de tener acceso a [GitHub Models](https://github.com/marketplace/models).
- **LANGSMITH_API_KEY**: Crea una cuenta en [LangSmith](https://smith.langchain.com/) y genera una API key desde Settings.

> **IMPORTANTE:** Nunca subas tu archivo `.env` al repositorio. Ya está incluido en `.gitignore`.

### 4. Ejecutar Jupyter

Con el entorno activado:

```bash
jupyter lab
```

O sin activar el entorno (usa el `.venv` del proyecto):

```bash
uv run jupyter lab
```

Opcional: registrar el kernel de este entorno en Jupyter para elegirlo en la interfaz:

```bash
uv run python -m ipykernel install --user --name ingenieria-soluciones-ia --display-name "Python (ingenieria-soluciones-ia)"
```

### 5. Opcional: Docker (Jupyter Lab con uv en Linux)

Sirve si prefieres **no instalar Python ni uv en tu máquina** o quieres un entorno idéntico al de otros compañeros. Sigue usando **`uv.lock`** dentro del contenedor.

**Requisitos:** [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Windows y macOS; en Windows activa el backend **WSL2**) o **Docker Engine + Docker Compose** en Linux.

#### Variables de entorno (cross‑platform)

El contenedor carga variables desde el archivo **`.env`** (en la raíz del repo) vía `env_file` en `docker-compose.yml`. Esto funciona igual en **Windows/macOS/Linux**.

- **Crea `.env` desde el ejemplo** (si solo vas a abrir Jupyter, puede tener valores vacíos):
   ```bash
   cp .env.example .env
   ```

- **No subas `.env` al repo**: contiene credenciales.
- **Evita imprimir secretos en consola**: comandos como `docker compose config` / `docker-compose config` pueden mostrar variables de `.env` en texto plano.

#### Levantar el contenedor

En la raíz del repositorio:

**Opción A (recomendada, Docker Compose v2):**

```bash
docker compose up --build
```

**Opción B (fallback, Docker Compose v1):**

```bash
docker-compose up --build
```

Abre **Jupyter Lab** en el navegador: `http://127.0.0.1:8888/lab` (sin token; el contenedor está configurado solo para desarrollo local).

**Detalle importante:** el `docker-compose.yml` guarda el virtualenv del contenedor en un **volumen nombrado** (`ingenieria-ia-venv`), no dentro de tu carpeta del proyecto. Así se evita mezclar un `.venv` compilado en Linux con herramientas nativas de Windows o macOS.

Comandos útiles:

```bash
docker compose down   # detiene el servicio (v2)
docker-compose down   # detiene el servicio (v1)

# Comprobar imports (contenedor ya en marcha con up):
docker compose exec jupyter uv run python scripts/verify_env.py
docker-compose exec jupyter uv run python scripts/verify_env.py
```

#### Troubleshooting rápido

- **Puerto 8888 ocupado**: cambia el mapeo en `docker-compose.yml` de `"8888:8888"` a `"8889:8888"` (u otro puerto libre).
- **Windows: errores con volúmenes / permisos**: usa Docker Desktop con **WSL2** y asegúrate de que la carpeta del repo esté compartida/visible para Docker.
- **Warning sobre buildx con `docker-compose`**: si tu instalación usa Compose v1, puede aparecer un aviso de buildx. Lo más robusto es usar **Compose v2** (`docker compose …`) cuando esté disponible.

---

## Estructura del Proyecto

```
RA1/  # Fundamentos de IA Generativa y Prompt Engineering
  IL1.1/  # Introducción a LLMs y conexión con APIs
  IL1.2/  # Técnicas de prompting (zero-shot, few-shot, chain-of-thought)
  IL1.3/  # Infraestructura RAG (Retrieval-Augmented Generation)
  IL1.4/  # Evaluación y optimización de LLMs

RA2/  # Desarrollo de Agentes Inteligentes con LLM
  IL2.1/  # Arquitectura y frameworks (LangChain, CrewAI)
  IL2.2/  # Memoria y herramientas externas (MCP)
  IL2.3/  # Planificación y orquestación de agentes
  IL2.4/  # Documentación técnica y diseño de arquitectura

RA3/  # Observabilidad, Seguridad y Ética en Agentes IA
  IL3.1/  # Herramientas de observabilidad y métricas
  IL3.2/  # Trazabilidad y procesamiento de logs
  IL3.3/  # Protocolos de seguridad y ética
  IL3.4/  # Escalabilidad y sostenibilidad
```

Cada subcarpeta IL contiene:
- **Notebooks (`.ipynb`)**: Prácticas guiadas paso a paso
- **Scripts Python (`.py`)**: Ejemplos ejecutables
- **Guías (`.md`)**: Teoría, patrones y mejores prácticas
- **README.md**: Objetivo y contexto de cada módulo

---

## Tecnologías y Librerías Principales

| Librería | Uso |
|----------|-----|
| `openai` | Cliente para APIs de modelos de lenguaje |
| `langchain` | Framework para construir aplicaciones con LLMs |
| `langchain-openai` | Integración LangChain con OpenAI |
| `langgraph` | Grafos de estado para agentes |
| `crewai` / `crewai_tools` | Orquestación multi-agente y herramientas CrewAI |
| `faiss-cpu` | Base de datos vectorial para RAG |
| `langsmith` | Observabilidad y evaluación de LLMs |
| `streamlit` | Interfaces web para demos |
| `pandas` / `numpy` | Procesamiento y análisis de datos |
| `matplotlib` / `plotly` | Visualización de datos |

---

## Navegación Recomendada

1. **Empieza por RA1** si eres nuevo en IA generativa y prompting
2. **RA2** para aprender a construir agentes inteligentes
3. **RA3** para llevar tus agentes a producción

Cada IL tiene ejemplos autocontenidos y README propio con explicaciones detalladas.

---

## Videotutoriales del Curso

Para un aprendizaje más visual, sigue la lista de reproducción completa:

[**Ver playlist en YouTube**](https://www.youtube.com/playlist?list=PL2gz3vdpKdfVHQqH39oPu4mxLrmAUd2eX)

---

## Evaluaciones y Entregables

| Tipo | Descripción | Peso |
|------|-------------|------|
| Quizzes | Evaluaciones formativas teóricas (1 por RA) | Variable |
| Proyectos Parciales | Proyectos prácticos con presentación (1 por RA) | Variable |
| Proyecto Final | Evaluación transversal integrando los 3 RA | 40% |

Los proyectos se desarrollan en parejas con presentación individual.

---

## Solución de Problemas Comunes

### Error de importación de módulos o versiones distintas entre compañeros

Con **uv** (recomendado): vuelve a alinear el entorno con el lock del repo:

```bash
uv sync
uv run python scripts/verify_env.py
```

Si usas **pip**: activa `.venv` e instala de nuevo: `pip install -r requirements.txt`.

### `uv` no se reconoce como comando

Reinstala uv con los comandos de instalación de la sección 2, reinicia la terminal y comprueba `uv --version`. En Windows, instala también las [actualizaciones de Visual C++ Redistributable](https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist) si el instalador falla.

### Error de API key
```bash
# Verifica que tu .env tenga las credenciales correctas
cat .env  # macOS / Linux; en Windows: type .env
```

### Problemas con Jupyter kernel

Con **uv**:

```bash
uv run python -m ipykernel install --user --name ingenieria-soluciones-ia --display-name "Python (ingenieria-soluciones-ia)"
```

En Jupyter, elige el kernel **Python (ingenieria-soluciones-ia)**. Sin uv (venv clásico): `python -m ipykernel install --user --name=curso-ia --display-name="Curso IA"`.

### Docker Compose: «couldn't find env file» o error al levantar

Crea el archivo antes de `docker compose up`:

```bash
cp .env.example .env
```

En **Windows** también vale `copy .env.example .env`. Si el puerto **8888** está ocupado, edita `docker-compose.yml` y cambia `"8888:8888"` por otro puerto libre, por ejemplo `"8889:8888"`.

### Matplotlib avisa que no puede escribir caché (sandbox / permisos)

En entornos restringidos puedes fijar un directorio temporal:

```bash
export MPLCONFIGDIR=/tmp/matplotlib
uv run python scripts/verify_env.py
```

En Docker esto ya va configurado en la imagen (`MPLCONFIGDIR=/tmp/matplotlib`).

---

## Recursos Adicionales

- [LangChain Docs](https://python.langchain.com/)
- [CrewAI Docs](https://docs.crewai.com/)
- [OpenAI API](https://platform.openai.com/docs/)
- [LangSmith Docs](https://docs.smith.langchain.com/)
- [GitHub Models](https://github.com/marketplace/models)
- [Clean Architecture](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html)

---

## Contribuciones

Para dudas, sugerencias o mejoras, abre un issue o pull request.

Repositorio original del curso: [davila7/Ingenier-a-de-Soluciones-con-Inteligencia-Artificial](https://github.com/davila7/Ingenier-a-de-Soluciones-con-Inteligencia-Artificial)
