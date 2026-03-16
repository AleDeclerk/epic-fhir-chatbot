# Research: FHIR Appointment Chatbot

**Date**: 2026-03-16
**Feature**: 001-fhir-appointment-chatbot

## R1: Epic FHIR R4 Sandbox — Slot & Schedule Availability

**Decision**: Plan for R4 using `Appointment.Search` and
`Appointment.Create`. Slot and Schedule Search are NOT confirmed
available in R4 on the Epic sandbox (Read-only in STU3, R4 status
unclear). The FHIR client MUST verify empirically at startup.

**Rationale**: The open.epic.com interface listing shows Slot and
Schedule as Read-only (STU3). R4 Slot.Search by schedule+status is
not listed. Epic's preferred scheduling workflow uses `$find`/`$book`
(STU3 only). For R4, the standard approach is:
1. `Practitioner.Search` by name to find practitioner ID
2. `Slot.Search?schedule=Schedule/{id}&status=free` — attempt this
   first, fall back to alternative if unavailable
3. Alternative: query `Appointment?practitioner={id}&status=free`
   or use a time-range scan

**Alternatives considered**:
- STU3 `$find` + `$book` (rejected: spec requires R4)
- Hybrid STU3/R4 (rejected: added complexity, unclear sandbox support)

**Action**: The FHIR client adapter MUST handle the case where
Slot.Search returns 404 or OperationOutcome. Include a fallback
strategy and log the discovery.

## R2: Appointment Booking in R4

**Decision**: Use `POST /Appointment` (standard FHIR Create) with
`status: booked`, referencing Slot, Patient, and Practitioner.

**Rationale**: `Appointment.$book` exists only in STU3. For R4, Epic
supports `Appointment.Create`. The payload must include:
- `status`: `"booked"`
- `participant`: references to Patient and Practitioner
- `slot`: reference to the selected Slot (if available)
- `start` / `end`: appointment time window

**Alternatives considered**:
- `$book` operation (rejected: STU3 only)

## R3: OAuth Architecture — Confidential Client

**Decision**: Run OAuth flow in the Python backend (confidential
client). The frontend redirects to the backend's `/auth/login`
endpoint, which initiates the SMART standalone launch.

**Rationale**:
- Confidential clients receive refresh tokens from Epic
- Client secret stays server-side (never in browser)
- Access tokens never exposed to the frontend
- Aligns with constitution: frontend MUST NOT access FHIR directly
- The backend stores tokens in memory and proxies all FHIR calls

**Flow**:
1. Frontend redirects to `GET /auth/login`
2. Backend redirects to Epic authorize endpoint (with PKCE)
3. User authenticates via MyChart sandbox
4. Epic redirects to `GET /auth/callback` on the backend
5. Backend exchanges code for tokens, extracts `patient` FHIR ID
6. Backend sets a session cookie and redirects to frontend
7. All subsequent `/api/chat` requests carry the session cookie

**Token lifecycle**:
- Access token: ~3600s (check `expires_in`)
- Refresh token: available for confidential clients
- On expiry: attempt refresh; if that fails, return 401 to frontend

**Alternatives considered**:
- Public client in frontend (rejected: no refresh tokens,
  token exposed in browser, violates constitution)

## R4: OAuth Registration

**Decision**: Developer MUST register an app at fhir.epic.com to
obtain a Non-Production Client ID. There is no pre-registered ID.

**Rationale**: Registration is free and immediate. Steps:
1. Create account at fhir.epic.com
2. Build Apps → Create
3. Select audience: Patients, select required FHIR APIs
4. Register public key for confidential client auth
5. Copy Non-Production Client ID

**Scopes to request**:
```
launch/patient openid fhirUser
patient/Patient.read patient/Practitioner.read
patient/Appointment.read patient/Appointment.write
patient/Slot.read patient/Schedule.read
```

**Note**: `patient/Slot.read` and `patient/Schedule.read` may not
be granted in patient-standalone context. Verify empirically.

## R5: Claude Agent — Tool Calling Architecture

**Decision**: Use Anthropic Python SDK `messages.create()` with
`tools` parameter. Standard agentic loop checking
`stop_reason == "tool_use"`.

**Rationale**: The canonical flow:
1. Send messages + tools to API
2. If `stop_reason == "tool_use"`: extract tool calls, execute,
   send `tool_result` blocks back
3. Repeat until `stop_reason == "end_turn"`

**Key constraints**:
- ALL `tool_use`/`tool_result` pairs MUST be in history
- Each tool call consumes 2 messages (assistant + user)
- With 20-message cap: budget ~5-6 user turns + 2-3 tool calls
- Parallel tool calls: multiple `tool_use` in one assistant message,
  all `tool_result` blocks in one user message

**Tool definitions**: 4 tools with JSON schema, rich descriptions
(3-4 sentences each). Use `strict: true` for schema validation.

## R6: Model Selection

**Decision**: Use `claude-sonnet-4-20250514` as specified in the
project requirements.

**Rationale**: Sonnet provides the right cost/speed balance for a
conversational chatbot with straightforward tool calling patterns.
At $3/$15 per MTok, it is 5x cheaper than Opus. The appointment
booking workflow is well-structured and does not require deep
multi-step reasoning.

**Alternatives considered**:
- `claude-opus-4-20250514` (rejected: 5x cost, moderate latency,
  unnecessary for this use case)
- `claude-sonnet-4-6` (viable upgrade path, same price, better
  performance — can swap later)

## R7: System Prompt Design

**Decision**: Write system prompt in Spanish using XML-tagged
sections for: identity, behavioral rules, confirmation workflow,
error handling, and tool usage guidance.

**Rationale**: Anthropic docs recommend XML tags for structured
system prompts. Writing in Spanish reinforces the language
requirement (FR-010). Key sections:
- `<idioma>`: Always respond in Spanish
- `<reglas>`: Never show technical errors, always ask before mutations
- `<confirmacion>`: Explicit confirmation flow for book/cancel
- `<errores>`: Friendly fallback messages for all failure modes

## R8: Test Patient Data

**Decision**: Use `fhirjason` / `epicepic1` as primary test patient.

**Rationale**: Confirmed working MyChart sandbox credential.
- Patient: Jason Argonaut
- FHIR ID: `Tbt3KuCY0B5PSrJvCu2j-PlK.aiHsu2xUjUM8bWpetXoB`
- Other available: fhirjessica, fhirdaisy (same password)
- Verify that test patient has scheduling data in sandbox

**Risk**: Sandbox test data may not include appointment/scheduling
resources for all patients. Verify by querying
`Appointment?patient={FHIR_ID}` after authenticating.
