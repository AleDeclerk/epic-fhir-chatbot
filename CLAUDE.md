# epic-fire-scheduler Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-03-16

## Active Technologies

- Python 3.11+ + FastAPI, uvicorn, httpx, Pydantic v2, (001-fhir-appointment-chatbot)

## Project Structure

```text
src/
tests/
```

## Commands

cd src && pytest && ruff check .

## Code Style

Python 3.11+: Follow standard conventions

## Recent Changes

- 001-fhir-appointment-chatbot: Added Python 3.11+ + FastAPI, uvicorn,
  httpx, Pydantic v2,

<!-- MANUAL ADDITIONS START -->

## CLAUDE.md — Epic FHIR Chatbot

## Proyecto

Chatbot conversacional para gestión de turnos médicos via Epic FHIR R4 sandbox.
Stack: FastAPI + Claude API (tool calling) + React.

## Comandos

```bash
# Backend
cd backend && pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Tests
cd backend && pytest tests/ -v

# Frontend (servir estático)
cd frontend && python -m http.server 3000
```

## Estilo de código

### Python

- Type hints en todas las funciones
- Async/await para HTTP (httpx)
- Pydantic v2 para validación
- snake_case para funciones/variables, PascalCase para clases
- Docstrings en funciones públicas
- Logging con `logging`, nunca print()
- Max 88 chars por línea

### JavaScript

- Functional components con hooks
- camelCase para variables/funciones

## Arquitectura

- El agente Claude NUNCA llama a Epic directamente → siempre pasa por fhir_client.py
- Cada tool tiene su handler en tools.py que usa fhir_client.py
- El frontend envía el historial completo en cada request (stateless)
- Secrets en .env, cargados via config.py (Pydantic Settings)

## FHIR sandbox

- Base URL: <https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4/>
- OAuth authorize: <https://fhir.epic.com/interconnect-fhir-oauth/oauth2/authorize>
- OAuth token: <https://fhir.epic.com/interconnect-fhir-oauth/oauth2/token>
- Test login: fhirjason / epicepic1
- Recursos: Patient, Practitioner, Slot, Schedule, Appointment

## Skills

The `epic-fhir` skill is installed at `.claude/skills/epic-fhir/`. It provides verified reference material for Epic FHIR R4 integration:

- `SKILL.md` — OAuth 2.0 standalone launch flow, Python client pattern, security rules, sandbox gotchas
- `references/endpoints.md` — FHIR endpoint params and example responses (Patient, Practitioner, Schedule, Slot, Appointment)
- `references/scheduling-flows.md` — Complete async Python code for search availability, $book, cancel, list appointments
- `references/error-codes.md` — Epic error codes, HTTP status handling, retry with backoff

Tasks annotated with `[SKILL:epic-fhir]` in `specs/001-fhir-appointment-chatbot/tasks.md` MUST consult the corresponding skill reference files before implementation.

## Reglas

- NUNCA hardcodear credentials
- NUNCA loguear tokens OAuth
- Siempre pedir confirmación al usuario antes de book/cancel
- Responder errores FHIR con mensajes amigables, nunca raw errors
- Tests unitarios para fhir_client.py (mockear respuestas Epic)
<!-- MANUAL ADDITIONS END -->
