# Research: FHIR Appointment Chatbot

**Date**: 2026-03-16
**Feature**: 001-fhir-appointment-chatbot

## R1: Epic FHIR STU3 Sandbox — Scheduling API Availability

**Decision**: Use STU3 for all scheduling operations. Slot, Schedule,
$find, and $book are only available in STU3 on Epic's sandbox. R4
only supports Appointment.Read and Appointment.Search.

**Rationale**: Testing against the actual fhir.epic.com app registration
form confirmed that:
- STU3 offers: Appointment.Read, Appointment.$find, Appointment.$book,
  Slot.Read, Schedule.Read
- R4 offers: Appointment.Read, Appointment.Search, Practitioner.Search,
  Patient.Search — but NO $find, $book, Slot, or Schedule
- The Argonaut Scheduling IG that defines $find/$book was built on STU3
  and Epic never ported it to R4

**Alternatives considered**:
- R4 with read-only chatbot (rejected: no booking capability)
- Hybrid R4/STU3 (rejected: unnecessary complexity, same OAuth endpoints)
- Backend-services credential for booking (rejected: overkill for MVP)

**Action**: All FHIR operations use the STU3 base URL:
`https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/STU3/`

## R2: Appointment Booking via $find + $book (STU3)

**Decision**: Use `POST /Appointment/$find` to discover availability
and `POST /Appointment/$book` to create bookings. Both follow the
Argonaut Scheduling IG and are natively supported in STU3.

**Rationale**: $find is Epic's preferred discovery mechanism. It
consolidates the Practitioner→Schedule→Slot chain into a single call
that returns proposed Appointment resources. The server manages
concurrency, preventing double-booking races.

**Booking flow**:
1. `POST /Appointment/$find` with start, end, provider params
2. User selects from proposed appointments
3. `POST /Appointment/$book` with Parameters wrapper containing
   the selected appointment

**Fallback**: If $find is unavailable for the registered app, fall
back to the manual chain: Practitioner.Search → Schedule.Search →
Slot.Search → $book with slot reference.

**Alternatives considered**:
- Standard POST /Appointment (rejected: no atomic slot verification)
- R4 $book (rejected: does not exist in Epic's R4 implementation)

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

**Scopes to request (SMART v1 format for STU3)**:
```
launch/patient openid fhirUser
patient/Patient.read patient/Practitioner.read
patient/Appointment.read patient/Appointment.write
patient/Slot.read patient/Schedule.read
```

**App registration API selections at fhir.epic.com**:
- Appointment.Read (Appointments) (STU3)
- Appointment.Search (Appointments) (R4) — for listing
- Practitioner.Search (R4)
- Patient.Search (Demographics) (R4)

Note: $find and $book may not appear as selectable APIs in the form.
They are implicitly available when Appointment APIs are selected.

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
(3-4 sentences each).

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
