# Implementation Plan: FHIR Appointment Chatbot

**Branch**: `001-fhir-appointment-chatbot` | **Date**: 2026-03-16 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/001-fhir-appointment-chatbot/spec.md`

## Summary

Build a conversational chatbot where patients manage medical
appointments (list, search, book, cancel) using natural language.
The backend (FastAPI + Python) orchestrates a Claude agent with tool
calling that delegates FHIR R4 operations to a decoupled adapter
communicating with Epic's sandbox. Authentication uses OAuth 2.0
SMART on FHIR standalone launch (confidential client). The frontend
is a single-page React chat UI.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: FastAPI, uvicorn, httpx, Pydantic v2,
python-dotenv, anthropic SDK
**Storage**: N/A (in-memory sessions, no database)
**Testing**: pytest, pytest-asyncio, pytest-httpx (for mocking)
**Target Platform**: Web (macOS/Linux dev server + modern browser)
**Project Type**: Web service (backend API) + SPA (frontend)
**Performance Goals**: <10s end-to-end response (SC-004),
<30s FHIR timeout, <60s Claude API timeout
**Constraints**: Stateless backend, 20-message context window,
5 slots per response, 90-day appointment horizon, Epic sandbox only
**Scale/Scope**: MVP, single patient per session, ~8 source files
backend + 1 frontend file

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### I. Layered Separation & Decoupling

| Rule | Status | Evidence |
|------|--------|----------|
| Agent MUST NOT call FHIR directly | PASS | `agent.py` calls tools; tools call `fhir_client.py` |
| Tools defined with JSON schema | PASS | 4 tools with `input_schema` in contracts/api.md |
| `fhir_client.py` independent of agent | PASS | No agent imports; pure FHIR adapter |
| Stateless backend | PASS | Session cookie for auth; chat history sent per request |
| Frontend MUST NOT access FHIR | PASS | Frontend calls `/api/chat` only; backend proxies FHIR |

### II. Security-First & Graceful Failure

| Rule | Status | Evidence |
|------|--------|----------|
| No hardcoded credentials | PASS | `.env` + Pydantic Settings via `config.py` |
| OAuth tokens never logged | PASS | FR-012 enforced in FHIR client logging |
| User input sanitized | PASS | Pydantic validation on ChatRequest |
| Rate limiting on endpoints | PASS | FastAPI middleware planned |
| Friendly error messages only | PASS | FR-011 + edge cases in spec |
| `.env` in `.gitignore` | PASS | Setup task includes this |

### III. Test-Driven Development (Non-Negotiable)

| Rule | Status | Evidence |
|------|--------|----------|
| Tests before implementation | PASS | TDD enforced per constitution |
| Red-Green-Refactor cycle | PASS | Task ordering: test → implement |
| Unit tests mock FHIR | PASS | pytest-httpx for `fhir_client.py` tests |
| Integration tests for tools | PASS | `test_tools.py` verifies tool invocation |
| Module tested before integration | PASS | Bottom-up build order enforces this |
| pytest as test runner | PASS | In requirements.txt |

**Gate result**: ALL PASS. Proceed to implementation.

## Project Structure

### Documentation (this feature)

```text
specs/001-fhir-appointment-chatbot/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── api.md
└── tasks.md              # Created by /speckit.tasks
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app, CORS, lifespan, rate limit
│   ├── config.py            # Pydantic Settings, env vars
│   ├── auth.py              # OAuth 2.0 / SMART on FHIR
│   ├── fhir_client.py       # Epic FHIR R4 adapter
│   ├── agent.py             # Claude agent orchestrator
│   ├── tools.py             # Tool definitions + handlers
│   ├── models.py            # Pydantic request/response models
│   └── routes/
│       ├── __init__.py
│       └── chat.py          # POST /api/chat endpoint
├── tests/
│   ├── __init__.py
│   ├── conftest.py          # Shared fixtures
│   ├── test_fhir_client.py  # Unit tests (mocked FHIR)
│   ├── test_tools.py        # Integration tests (tool handlers)
│   ├── test_agent.py        # Agent orchestration tests
│   ├── test_auth.py         # OAuth flow tests
│   └── test_chat.py         # API endpoint tests
├── requirements.txt
└── .env.example

frontend/
└── index.html               # React 18 SPA (CDN, single file)

.env.example
.gitignore
README.md
CLAUDE.md
```

**Structure Decision**: Web application layout (backend/ + frontend/)
matching the constitution's Build-From-Bottom-Up Sequence. Backend
uses FastAPI with module-per-responsibility. Frontend is a single
HTML file using React 18 + Tailwind CSS via CDN.

## Complexity Tracking

> No constitution violations detected. No complexity justifications needed.
