# Tasks: FHIR Appointment Chatbot

**Input**: Design documents from `/specs/001-fhir-appointment-chatbot/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/api.md, quickstart.md

**Tests**: REQUIRED — Constitution Principle III mandates strict TDD (Red-Green-Refactor).

**Organization**: Tasks grouped by user story. Build order follows constitution: config -> auth -> fhir_client -> tools -> agent -> routes -> main -> frontend.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story (US1, US2, US3, US4)

## Path Conventions

- **Backend**: `backend/app/`, `backend/tests/`
- **Frontend**: `frontend/`

---

## Phase 1: Setup (Project Initialization)

**Purpose**: Create directory structure and install dependencies

- [ ] T001 Create project directory structure per plan.md: backend/app/, backend/app/routes/, backend/tests/, frontend/
- [ ] T002 [P] Initialize Python project with requirements.txt in backend/ (fastapi, uvicorn, httpx, pydantic, pydantic-settings, python-dotenv, anthropic, pytest, pytest-asyncio, pytest-httpx)
- [ ] T003 [P] Create .gitignore (include .env, __pycache__, .venv, *.pyc) and .env.example with all required variables per quickstart.md

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story

**CRITICAL**: No user story work can begin until this phase is complete

- [ ] T004 Create shared test fixtures in backend/tests/conftest.py (async test client, mock settings, mock httpx transport, mock session with patient_id and access_token)
- [ ] T005 Write failing tests for Settings class in backend/tests/test_config.py (TDD Red: test env var loading for EPIC_FHIR_BASE_URL, EPIC_CLIENT_ID, ANTHROPIC_API_KEY, all fields from quickstart.md)
- [ ] T006 Implement Settings class using Pydantic Settings in backend/app/config.py (TDD Green: load all env vars, provide defaults where appropriate)
- [ ] T007 [P] Write failing tests for Pydantic models in backend/tests/test_models.py (TDD Red: test ChatMessage, ChatRequest with max 20 history, ChatResponse, SlotInfo, AppointmentInfo, TokenData per data-model.md)
- [ ] T008 [P] Implement all Pydantic models in backend/app/models.py (TDD Green: ChatMessage, ChatRequest, ChatResponse, SlotInfo, AppointmentInfo, TokenData with validation)
- [ ] T009 Write failing tests for OAuth auth module in backend/tests/test_auth.py (TDD Red: test login redirect URL generation with PKCE, callback token exchange, status endpoint, logout, token refresh, expired token handling)
- [ ] T010 Implement OAuth 2.0 SMART on FHIR in backend/app/auth.py (TDD Green: login redirect with PKCE+state, callback exchanges code for tokens, extracts patient FHIR ID, session management, token refresh, /auth/status, /auth/logout)
- [ ] T011 Write failing tests for FHIR client base in backend/tests/test_fhir_client.py (TDD Red: test httpx client init, Authorization header injection, error handling for 4xx/5xx, 429 retry once, structured logging without tokens, timeout at 30s)
- [ ] T012 Implement FHIR client base class in backend/app/fhir_client.py (TDD Green: async httpx client, auth header from session token, error handling, 1 retry on 429, logging via logging module excluding tokens, 30s timeout)
- [ ] T013 Implement FastAPI app shell in backend/app/main.py (app factory, CORS for FRONTEND_URL, rate limiting middleware, include auth routes from auth.py, lifespan handler)

**Checkpoint**: Foundation ready — config, models, auth, FHIR client base, and app shell all tested and working. User story implementation can now begin.

---

## Phase 3: User Story 1 — View My Appointments (Priority: P1) MVP

**Goal**: Patient asks "What appointments do I have?" and sees upcoming appointments (next 90 days)

**Independent Test**: Log in as fhirjason, ask "¿Qué turnos tengo?", verify formatted appointment list returned

### Tests for User Story 1

> **TDD: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T014 [US1] Add failing tests for list_appointments() to backend/tests/test_fhir_client.py (TDD Red: mock GET /Appointment?patient={id}&date=ge{today}&date=le{today+90d}&status=booked, test with results, empty results, FHIR error, parse participant to extract practitioner name)
- [ ] T015 [P] [US1] Write failing tests for list_appointments tool handler in backend/tests/test_tools.py (TDD Red: test tool receives patient_id from session, calls fhir_client.list_appointments, returns formatted AppointmentInfo list, test error wrapping)
- [ ] T016 [P] [US1] Write failing tests for agent orchestrator in backend/tests/test_agent.py (TDD Red: test system prompt in Spanish with XML tags, test agentic loop with list_appointments tool_use -> tool_result -> end_turn, test tool_use/tool_result message structure, mock anthropic client)
- [ ] T017 [P] [US1] Write failing tests for POST /api/chat in backend/tests/test_chat.py (TDD Red: test 200 with valid session + message, test 401 without session, test 422 with invalid body, test history capped at 20 messages)

### Implementation for User Story 1

- [ ] T018 [US1] Implement list_appointments() in backend/app/fhir_client.py (TDD Green: GET /Appointment with patient, date range 90 days, status=booked, parse FHIR Bundle into AppointmentInfo list, extract practitioner name from participant)
- [ ] T019 [US1] Implement list_appointments tool handler in backend/app/tools.py (TDD Green: define tool JSON schema per contracts/api.md, handler calls fhir_client.list_appointments with session patient_id, formats result as string)
- [ ] T020 [US1] Implement Claude agent orchestrator in backend/app/agent.py (TDD Green: system prompt in Spanish with XML sections per research.md R7, tool definitions array with list_appointments, agentic loop: send messages -> check stop_reason -> execute tools -> return, 60s timeout for Claude API)
- [ ] T021 [US1] Implement POST /api/chat endpoint in backend/app/routes/chat.py (TDD Green: validate ChatRequest, check session auth, cap history at 20, call agent.process_message, return ChatResponse, handle errors with friendly messages per FR-011)
- [ ] T022 [US1] Wire chat route into main.py and create frontend/index.html (React 18 SPA via CDN: chat UI with message input, message list, login/logout buttons, calls /auth/login for OAuth, calls POST /api/chat with history, caps history at 20 messages per FR-016, Tailwind CSS styling)

**Checkpoint**: US1 fully functional. Patient can authenticate, ask about appointments, and see formatted results. End-to-end pipeline proven.

---

## Phase 4: User Story 2 — Search Available Slots (Priority: P2)

**Goal**: Patient asks "Are there openings with Dr. Smith next Tuesday?" and sees available slots (max 5, with "show more")

**Independent Test**: Ask "Mostrame disponibilidad de oftalmología para la semana que viene", verify slots returned with date/time/practitioner

### Tests for User Story 2

> **TDD: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T023 [US2] Add failing tests for search_practitioners() and search_slots() to backend/tests/test_fhir_client.py (TDD Red: mock GET /Practitioner?name={name}, mock GET /PractitionerRole?specialty={code}, mock GET /Schedule?actor=Practitioner/{id}, mock GET /Slot?schedule={id}&status=free&start=ge{date}, test fallback if Slot.Search returns 404 per research.md R1, test empty results)
- [ ] T024 [P] [US2] Add failing tests for search_available_slots tool in backend/tests/test_tools.py (TDD Red: test with practitioner_name, test with specialty, test date_from required, test results capped at 5 per FR-004, test "show more" offset parameter, test no results message)

### Implementation for User Story 2

- [ ] T025 [US2] Implement search_practitioners() and search_slots() in backend/app/fhir_client.py (TDD Green: Practitioner.Search by name, PractitionerRole search by specialty, Schedule.Search by actor, Slot.Search by schedule+status+date, fallback strategy if Slot.Search unavailable, return SlotInfo list)
- [ ] T026 [US2] Implement search_available_slots tool handler in backend/app/tools.py (TDD Green: JSON schema per contracts/api.md, calls fhir_client methods, caps at 5 results, includes offset for pagination, formats as readable string)
- [ ] T027 [US2] Add search_available_slots tool to agent tools array in backend/app/agent.py
- [ ] T028 [US2] Add integration tests for slot search conversational flow in backend/tests/test_agent.py (test agent asks for date when missing, test agent returns formatted slots, test "show more" follow-up)

**Checkpoint**: US1 + US2 functional. Patient can list appointments AND search for available slots independently.

---

## Phase 5: User Story 3 — Book an Appointment (Priority: P3)

**Goal**: Patient selects a slot and confirms booking. Chatbot creates the appointment.

**Independent Test**: Search for slots, select one, confirm booking, verify appointment appears in list

### Tests for User Story 3

> **TDD: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T029 [US3] Add failing tests for create_appointment() to backend/tests/test_fhir_client.py (TDD Red: mock POST /Appointment with status=booked, test with slot_id + patient_id + practitioner references, test successful creation returns AppointmentInfo, test failure when slot already taken returns error, test FHIR validation error)
- [ ] T030 [P] [US3] Add failing tests for book_appointment tool in backend/tests/test_tools.py (TDD Red: test requires slot_id, test injects patient_id from session, test returns confirmation with reference ID, test error handling for failed booking)

### Implementation for User Story 3

- [ ] T031 [US3] Implement create_appointment() in backend/app/fhir_client.py (TDD Green: POST /Appointment with status=booked, participant refs for Patient + Practitioner, slot reference, start/end times, return AppointmentInfo or error)
- [ ] T032 [US3] Implement book_appointment tool handler in backend/app/tools.py (TDD Green: JSON schema per contracts/api.md, calls fhir_client.create_appointment, formats confirmation with reference ID)
- [ ] T033 [US3] Add book_appointment tool to agent tools array in backend/app/agent.py
- [ ] T034 [US3] Add integration tests for booking flow in backend/tests/test_agent.py (test agent shows summary and asks confirmation before calling book_appointment, test agent handles declined confirmation, test agent handles booking failure gracefully)

**Checkpoint**: US1 + US2 + US3 functional. Full search-and-book flow works end-to-end.

---

## Phase 6: User Story 4 — Cancel an Appointment (Priority: P4)

**Goal**: Patient requests cancellation, confirms, and appointment status changes to cancelled

**Independent Test**: List appointments, request cancellation of one, confirm, verify status changed

### Tests for User Story 4

> **TDD: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T035 [US4] Add failing tests for cancel_appointment() to backend/tests/test_fhir_client.py (TDD Red: mock GET /Appointment/{id} then PUT /Appointment/{id} with status=cancelled, test successful cancellation, test appointment not found, test already cancelled)
- [ ] T036 [P] [US4] Add failing tests for cancel_appointment tool in backend/tests/test_tools.py (TDD Red: test requires appointment_id, test returns cancellation confirmation, test error handling)

### Implementation for User Story 4

- [ ] T037 [US4] Implement cancel_appointment() in backend/app/fhir_client.py (TDD Green: GET current appointment, PUT with status=cancelled, return updated AppointmentInfo or error)
- [ ] T038 [US4] Implement cancel_appointment tool handler in backend/app/tools.py (TDD Green: JSON schema per contracts/api.md, calls fhir_client.cancel_appointment, formats confirmation)
- [ ] T039 [US4] Add cancel_appointment tool to agent tools array in backend/app/agent.py
- [ ] T040 [US4] Add integration tests for cancellation flow in backend/tests/test_agent.py (test agent asks confirmation before cancelling, test agent disambiguates when multiple appointments match, test agent handles cancellation failure)

**Checkpoint**: All four user stories independently functional and testable.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Edge cases, error handling, documentation, and final validation

- [ ] T041 [P] Add edge case tests in backend/tests/test_edge_cases.py (token expiry mid-conversation returns 401, FHIR timeout returns friendly message, 429 retry exhaustion returns friendly message, past-date slot search rejected, ambiguous intent triggers clarification, concurrent slot booking failure handled)
- [ ] T042 [P] Implement edge case handlers across modules: token expiry check in chat route, friendly error wrapper in agent.py for all exceptions per FR-011/SC-006
- [ ] T043 [P] Create README.md with project overview, architecture diagram (text), setup instructions, and sandbox test credentials reference
- [ ] T044 Run quickstart.md verification checklist: backend starts, auth redirects, chat responds, frontend works, all tests pass

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories
- **US1 (Phase 3)**: Depends on Foundational — proves end-to-end pipeline
- **US2 (Phase 4)**: Depends on Foundational — can start after Foundational (independent of US1)
- **US3 (Phase 5)**: Depends on Foundational + US2 (needs search_slots for booking flow)
- **US4 (Phase 6)**: Depends on Foundational + US1 (needs list_appointments for disambiguation)
- **Polish (Phase 7)**: Depends on all user stories complete

### Within Each User Story

1. Tests MUST be written and FAIL before implementation (TDD Red)
2. FHIR client methods before tool handlers
3. Tool handlers before agent integration
4. Agent integration before route wiring
5. Each story complete before moving to next priority

### Parallel Opportunities

- **Phase 1**: T002 and T003 run in parallel
- **Phase 2**: T007/T008 (models) parallel with T005/T006 (config) after T004
- **Phase 3**: T015, T016, T017 (tests) run in parallel after T014
- **Phase 4**: T024 (tool tests) parallel with T023 (FHIR tests)
- **Phase 5**: T030 (tool tests) parallel with T029 (FHIR tests)
- **Phase 6**: T036 (tool tests) parallel with T035 (FHIR tests)
- **Phase 7**: T041, T042, T043 all run in parallel

---

## Parallel Example: User Story 1

```bash
# Launch all US1 tests in parallel (TDD Red):
Task: "T014 - FHIR client list_appointments tests"
Task: "T015 - Tool handler tests"
Task: "T016 - Agent orchestrator tests"
Task: "T017 - Chat endpoint tests"

# Then implement sequentially (TDD Green):
Task: "T018 - fhir_client.list_appointments()"
Task: "T019 - tools.list_appointments handler"
Task: "T020 - agent.py orchestrator"
Task: "T021 - routes/chat.py endpoint"
Task: "T022 - frontend/index.html + wire into main.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL — blocks all stories)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: Test end-to-end with fhirjason/epicepic1
5. Deploy/demo if ready

### Incremental Delivery

1. Setup + Foundational -> Foundation ready
2. Add US1 -> Test independently -> **MVP! (list appointments)**
3. Add US2 -> Test independently -> **Search capability added**
4. Add US3 -> Test independently -> **Full booking flow**
5. Add US4 -> Test independently -> **Cancellation added**
6. Polish -> Edge cases, docs -> **Production-ready MVP**

### Recommended Execution (Solo Developer)

Execute sequentially in priority order:
1. Phase 1 + Phase 2 (foundation)
2. Phase 3 (US1 — MVP, proves pipeline)
3. Phase 4 (US2 — search)
4. Phase 5 (US3 — book, depends on search)
5. Phase 6 (US4 — cancel)
6. Phase 7 (polish)

---

## Notes

- [P] tasks = different files, no dependencies on incomplete tasks
- [Story] label maps task to specific user story
- TDD is NON-NEGOTIABLE per constitution Principle III
- Verify tests fail (Red) before implementing (Green)
- Commit after each task or logical group (test + implementation pair)
- All FHIR client tests MUST mock Epic responses (never call sandbox in unit tests)
- Agent tests MUST mock Anthropic API (never call Claude in unit tests)
- Frontend is a single index.html with React 18 + Tailwind CSS via CDN
