# Epic FHIR Chatbot

Chatbot conversacional para que pacientes puedan gestionar turnos
medicos usando lenguaje natural. Se conecta a la API FHIR R4 del
sandbox de Epic mediante un agente Claude con tool calling.

## Que hace

Un paciente abre el chat, escribe en espanol y puede:

- **Ver turnos** - "Que turnos tengo?"
- **Buscar disponibilidad** - "Hay turnos con oftalmologia para la semana que viene?"
- **Reservar** - "Reservame el de las 10:30"
- **Cancelar** - "Cancela mi turno del jueves"

El chatbot interpreta la intencion, ejecuta las operaciones contra
Epic FHIR R4 y responde de forma amigable.

## Arquitectura

```
Frontend (React)  -->  Backend (FastAPI)  -->  Claude Agent  -->  Tools  -->  FHIR Client  -->  Epic FHIR R4
                            |
                      OAuth 2.0 / SMART on FHIR
```

**4 capas desacopladas:**

| Capa | Archivo | Responsabilidad |
|------|---------|-----------------|
| Frontend | `frontend/index.html` | Chat UI (React 18 + Tailwind via CDN) |
| API | `backend/app/routes/chat.py` | POST /api/chat, validacion, sesion |
| Agente | `backend/app/agent.py` | Claude con tool calling, system prompt en espanol |
| FHIR Client | `backend/app/fhir_client.py` | Adapter HTTP contra Epic FHIR R4 |

## Stack

- **Backend**: Python 3.11+, FastAPI, uvicorn, httpx, Pydantic v2
- **IA**: Anthropic Claude API (claude-sonnet-4-20250514) con tool calling
- **Frontend**: React 18 + Tailwind CSS (single HTML, CDN)
- **Auth**: OAuth 2.0 / SMART on FHIR (standalone launch, confidential client)
- **FHIR**: Epic sandbox (`fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4/`)
- **Testing**: pytest, pytest-asyncio, pytest-httpx

## Estructura del proyecto

```
backend/
  app/
    __init__.py
    main.py              # FastAPI app, CORS, rate limiting
    config.py            # Pydantic Settings, variables de entorno
    auth.py              # OAuth 2.0 / SMART on FHIR
    fhir_client.py       # Adapter para Epic FHIR R4
    agent.py             # Orquestador del agente Claude
    tools.py             # Definiciones de tools + handlers
    models.py            # Modelos Pydantic (request/response)
    routes/
      __init__.py
      chat.py            # POST /api/chat
  tests/
    conftest.py          # Fixtures compartidos
    test_fhir_client.py  # Tests unitarios (FHIR mockeado)
    test_tools.py        # Tests de integracion (tool handlers)
    test_agent.py        # Tests del agente
    test_auth.py         # Tests OAuth
    test_chat.py         # Tests del endpoint
  requirements.txt
frontend/
  index.html             # React SPA (single file)
specs/                   # Especificaciones del proyecto
.env.example
```

## Prerequisitos

- Python 3.11+
- Cuenta de desarrollador en [fhir.epic.com](https://fhir.epic.com)
  con una app registrada (Non-Production Client ID)
- API key de [Anthropic](https://console.anthropic.com/)

## Setup

```bash
# 1. Clonar
git clone https://github.com/AleDeclerk/epic-fhir-chatbot.git
cd epic-fhir-chatbot
git checkout 001-fhir-appointment-chatbot

# 2. Backend
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. Variables de entorno
cp .env.example .env
# Editar .env con tus credenciales (ver seccion abajo)

# 4. Ejecutar backend
uvicorn app.main:app --reload --port 8000

# 5. Ejecutar frontend (en otra terminal)
cd frontend
python -m http.server 5173
```

## Variables de entorno

```bash
# Epic FHIR
EPIC_FHIR_BASE_URL=https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4
EPIC_CLIENT_ID=<tu-non-production-client-id>
EPIC_CLIENT_SECRET=<tu-client-secret>
EPIC_REDIRECT_URI=http://localhost:8000/auth/callback
EPIC_AUTHORIZE_URL=https://fhir.epic.com/interconnect-fhir-oauth/oauth2/authorize
EPIC_TOKEN_URL=https://fhir.epic.com/interconnect-fhir-oauth/oauth2/token

# Anthropic
ANTHROPIC_API_KEY=<tu-api-key>
CLAUDE_MODEL=claude-sonnet-4-20250514

# App
APP_SECRET_KEY=<secret-random-para-sesiones>
FRONTEND_URL=http://localhost:5173
```

## Uso

1. Abrir `http://localhost:5173`
2. Click en "Iniciar sesion" (redirige a Epic MyChart sandbox)
3. Login con: `fhirjason` / `epicepic1`
4. Escribir en el chat, por ejemplo: "Que turnos tengo?"

## Tools del agente

El agente Claude tiene 4 tools disponibles:

| Tool | Operacion FHIR | Descripcion |
|------|----------------|-------------|
| `list_appointments` | `GET /Appointment` | Lista turnos de los proximos 90 dias |
| `search_available_slots` | `GET /Practitioner` + `GET /Slot` | Busca disponibilidad (max 5 resultados) |
| `book_appointment` | `POST /Appointment` | Reserva un turno (requiere confirmacion) |
| `cancel_appointment` | `PUT /Appointment` | Cancela un turno (requiere confirmacion) |

## Tests

```bash
cd backend
pytest tests/ -v
```

Todos los tests mockean las respuestas de Epic y la API de Claude.
No se hacen llamadas reales en los tests unitarios.

## Principios del proyecto

Definidos en la [constitucion del proyecto](.specify/memory/constitution.md):

1. **Separacion por capas** - El agente nunca llama a FHIR directamente.
   Todo pasa por el adapter `fhir_client.py`.
2. **Seguridad primero** - Credenciales en `.env`, tokens nunca logueados,
   errores amigables siempre.
3. **TDD estricto** - Tests antes de implementacion. Red-Green-Refactor.

## Documentacion

La carpeta `specs/001-fhir-appointment-chatbot/` contiene:

| Archivo | Contenido |
|---------|-----------|
| `spec.md` | Especificacion con 4 user stories, 16 requerimientos, 7 edge cases |
| `plan.md` | Plan de implementacion con contexto tecnico y constitution check |
| `tasks.md` | 44 tareas organizadas por user story (7 fases) |
| `research.md` | Investigacion sobre Epic sandbox, OAuth, Claude tool calling |
| `data-model.md` | Modelo de datos: 5 recursos FHIR + 6 modelos Pydantic |
| `contracts/api.md` | Contratos de API: 5 endpoints REST + 4 tool schemas |
| `quickstart.md` | Guia rapida de setup y verificacion |

## Lo que NO incluye el MVP

- Base de datos persistente
- Notificaciones push o email
- Multi-idioma (solo espanol)
- Integracion con pagos
- Historial de conversaciones entre sesiones
- Reprogramacion de turnos (hay que cancelar y reservar de nuevo)

## Licencia

MIT
