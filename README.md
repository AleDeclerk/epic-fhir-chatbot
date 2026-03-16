# Epic FHIR Chatbot

A conversational chatbot that lets patients manage medical appointments
using natural language. It connects to Epic's FHIR R4 sandbox API
through a Claude agent with tool calling.

## What It Does

A patient opens the chat, types in Spanish, and can:

- **View appointments** — "Que turnos tengo?"
- **Search availability** — "Hay turnos con oftalmologia para la semana que viene?"
- **Book** — "Reservame el de las 10:30"
- **Cancel** — "Cancela mi turno del jueves"

The chatbot interprets the intent, executes operations against
Epic FHIR R4, and responds in a friendly, non-technical way.

## Architecture

```
Frontend (React)  -->  Backend (FastAPI)  -->  Claude Agent  -->  Tools  -->  FHIR Client  -->  Epic FHIR R4
                            |
                      OAuth 2.0 / SMART on FHIR
```

**4 decoupled layers:**

| Layer | File | Responsibility |
|-------|------|----------------|
| Frontend | `frontend/index.html` | Chat UI (React 18 + Tailwind via CDN) |
| API | `backend/app/routes/chat.py` | POST /api/chat, validation, session |
| Agent | `backend/app/agent.py` | Claude with tool calling, Spanish system prompt |
| FHIR Client | `backend/app/fhir_client.py` | HTTP adapter for Epic FHIR R4 |

## Tech Stack

- **Backend**: Python 3.11+, FastAPI, uvicorn, httpx, Pydantic v2
- **AI**: Anthropic Claude API (claude-sonnet-4-20250514) with tool calling
- **Frontend**: React 18 + Tailwind CSS (single HTML file, CDN)
- **Auth**: OAuth 2.0 / SMART on FHIR (standalone launch, confidential client)
- **FHIR**: Epic sandbox (`fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4/`)
- **Testing**: pytest, pytest-asyncio, pytest-httpx

## Project Structure

```
backend/
  app/
    __init__.py
    main.py              # FastAPI app, CORS, rate limiting
    config.py            # Pydantic Settings, environment variables
    auth.py              # OAuth 2.0 / SMART on FHIR
    fhir_client.py       # Epic FHIR R4 adapter
    agent.py             # Claude agent orchestrator
    tools.py             # Tool definitions + handlers
    models.py            # Pydantic request/response models
    routes/
      __init__.py
      chat.py            # POST /api/chat
  tests/
    conftest.py          # Shared fixtures
    test_fhir_client.py  # Unit tests (mocked FHIR)
    test_tools.py        # Integration tests (tool handlers)
    test_agent.py        # Agent tests
    test_auth.py         # OAuth tests
    test_chat.py         # Endpoint tests
  requirements.txt
frontend/
  index.html             # React SPA (single file)
specs/                   # Project specifications
.env.example
```

## Prerequisites

- Python 3.11+
- Developer account at [fhir.epic.com](https://fhir.epic.com)
  with a registered app (Non-Production Client ID)
- API key from [Anthropic](https://console.anthropic.com/)

## Setup

```bash
# 1. Clone
git clone https://github.com/AleDeclerk/epic-fhir-chatbot.git
cd epic-fhir-chatbot
git checkout 001-fhir-appointment-chatbot

# 2. Backend
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. Environment variables
cp .env.example .env
# Edit .env with your credentials (see section below)

# 4. Run backend
uvicorn app.main:app --reload --port 8000

# 5. Run frontend (in another terminal)
cd frontend
python -m http.server 5173
```

## Environment Variables

```bash
# Epic FHIR
EPIC_FHIR_BASE_URL=https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4
EPIC_CLIENT_ID=<your-non-production-client-id>
EPIC_CLIENT_SECRET=<your-client-secret>
EPIC_REDIRECT_URI=http://localhost:8000/auth/callback
EPIC_AUTHORIZE_URL=https://fhir.epic.com/interconnect-fhir-oauth/oauth2/authorize
EPIC_TOKEN_URL=https://fhir.epic.com/interconnect-fhir-oauth/oauth2/token

# Anthropic
ANTHROPIC_API_KEY=<your-api-key>
CLAUDE_MODEL=claude-sonnet-4-20250514

# App
APP_SECRET_KEY=<random-secret-for-session-signing>
FRONTEND_URL=http://localhost:5173
```

## Usage

1. Open `http://localhost:5173`
2. Click "Log in" (redirects to Epic MyChart sandbox)
3. Log in with: `fhirjason` / `epicepic1`
4. Type in the chat, for example: "Que turnos tengo?"

## Agent Tools

The Claude agent has 4 tools available:

| Tool | FHIR Operation | Description |
|------|----------------|-------------|
| `list_appointments` | `GET /Appointment` | Lists appointments for the next 90 days |
| `search_available_slots` | `GET /Practitioner` + `GET /Slot` | Searches availability (max 5 results per page) |
| `book_appointment` | `POST /Appointment` | Books an appointment (requires explicit confirmation) |
| `cancel_appointment` | `PUT /Appointment` | Cancels an appointment (requires explicit confirmation) |

## Tests

```bash
cd backend
pytest tests/ -v
```

All tests mock Epic and Claude API responses.
No real external calls are made during unit tests.

## Project Principles

Defined in the [project constitution](.specify/memory/constitution.md):

1. **Layered Separation** — The agent never calls FHIR directly.
   Everything goes through the `fhir_client.py` adapter.
2. **Security First** — Credentials in `.env`, tokens never logged,
   friendly error messages always.
3. **Strict TDD** — Tests before implementation. Red-Green-Refactor.

## Documentation

The `specs/001-fhir-appointment-chatbot/` folder contains:

| File | Contents |
|------|----------|
| `spec.md` | Specification with 4 user stories, 16 requirements, 7 edge cases |
| `plan.md` | Implementation plan with technical context and constitution check |
| `tasks.md` | 44 tasks organized by user story (7 phases) |
| `research.md` | Research on Epic sandbox, OAuth, Claude tool calling |
| `data-model.md` | Data model: 5 FHIR resources + 6 Pydantic models |
| `contracts/api.md` | API contracts: 5 REST endpoints + 4 tool schemas |
| `quickstart.md` | Quick setup and verification guide |

## Out of Scope (MVP)

- Persistent database
- Push or email notifications
- Multi-language support (Spanish only for MVP)
- Payment integration
- Cross-session conversation history
- Appointment rescheduling (must cancel and rebook separately)

## License

MIT
