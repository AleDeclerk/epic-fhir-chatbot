# Quickstart: FHIR Appointment Chatbot

**Date**: 2026-03-16

## Prerequisites

- Python 3.11+
- Node.js (optional, only if serving frontend separately)
- An Epic developer account at [fhir.epic.com](https://fhir.epic.com)
- A registered application with Non-Production Client ID
- Anthropic API key

## 1. Clone and Setup

```bash
git clone <repo-url>
cd epic-fhir-chatbot
git checkout 001-fhir-appointment-chatbot
```

## 2. Backend Setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate    # macOS/Linux
pip install -r requirements.txt
```

## 3. Environment Variables

Copy `.env.example` to `.env` and fill in:

```bash
cp .env.example .env
```

Required variables:

```
# Epic FHIR
EPIC_FHIR_BASE_URL=https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4
EPIC_CLIENT_ID=<your-non-production-client-id>
EPIC_CLIENT_SECRET=<your-client-secret>
EPIC_REDIRECT_URI=http://localhost:8000/auth/callback

# Epic OAuth endpoints
EPIC_AUTHORIZE_URL=https://fhir.epic.com/interconnect-fhir-oauth/oauth2/authorize
EPIC_TOKEN_URL=https://fhir.epic.com/interconnect-fhir-oauth/oauth2/token

# Anthropic
ANTHROPIC_API_KEY=<your-anthropic-api-key>
CLAUDE_MODEL=claude-sonnet-4-20250514

# App
APP_SECRET_KEY=<random-secret-for-session-signing>
FRONTEND_URL=http://localhost:5173
```

## 4. Run Backend

```bash
uvicorn app.main:app --reload --port 8000
```

## 5. Run Frontend

Open `frontend/index.html` in a browser, or serve it:

```bash
cd frontend
python -m http.server 5173
```

## 6. Test the Flow

1. Open `http://localhost:5173` in your browser
2. Click "Login" — you'll be redirected to Epic MyChart sandbox
3. Log in with: `fhirjason` / `epicepic1`
4. After redirect, the chat interface becomes active
5. Try: "¿Qué turnos tengo?"

## 7. Run Tests

```bash
cd backend
pytest tests/ -v
```

## Verification Checklist

- [ ] Backend starts without errors on port 8000
- [ ] `GET /auth/login` redirects to Epic authorize
- [ ] OAuth callback sets session cookie
- [ ] `POST /api/chat` returns chatbot response
- [ ] `GET /auth/status` returns authenticated=true
- [ ] Frontend displays chat interface
- [ ] Patient can ask about appointments in Spanish
- [ ] All tests pass
- [ ] SC-004: End-to-end response time < 10 seconds (manual: time a chat request)
- [ ] SC-005: Intent accuracy ≥ 90% (manual: test 10 varied intents, ≥ 9 correct on first attempt)
