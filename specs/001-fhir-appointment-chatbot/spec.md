# Feature Specification: FHIR Appointment Chatbot

**Feature Branch**: `001-fhir-appointment-chatbot`
**Created**: 2026-03-16
**Status**: Implemented
**Input**: Chatbot conversacional para gestionar turnos medicos via Epic FHIR R4

## Clarifications

### Session 2026-03-16

- Q: How many conversation messages should be retained per request? → A: 20 messages maximum.
- Q: How many slot results should the chatbot display at once? → A: 5 slots, with "show more" prompt if additional results exist.
- Q: What time horizon defines "upcoming" when listing appointments? → A: 90 days from today.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - View My Appointments (Priority: P1)

As a patient, I want to see my upcoming medical appointments so I know
when and where I need to go.

The patient opens the chat and asks something like "What appointments do
I have?" or "When is my next visit?". The chatbot retrieves all future
booked appointments and displays them in a clear, readable list with
date, time, practitioner name, and status.

**Why this priority**: This is the simplest read-only operation and
proves the entire pipeline works end-to-end (frontend -> backend ->
agent -> FHIR client -> Epic). It delivers immediate value without
any mutation risk.

**Independent Test**: Can be fully tested by logging in as a sandbox
patient and asking "Show me my appointments". Delivers value as a
standalone appointment viewer even without other stories.

**Acceptance Scenarios**:

1. **Given** a patient is authenticated and has upcoming appointments,
   **When** they ask "What appointments do I have?",
   **Then** the chatbot lists each appointment with date, time,
   practitioner, and status in a human-readable format.

2. **Given** a patient is authenticated and has no upcoming appointments,
   **When** they ask about their appointments,
   **Then** the chatbot responds with a friendly message indicating no
   upcoming appointments were found.

3. **Given** a patient asks "When is my next appointment?",
   **When** the chatbot retrieves their appointments,
   **Then** it highlights the soonest upcoming appointment first.

---

### User Story 2 - Search Available Slots (Priority: P2)

As a patient, I want to search for available appointment slots by
practitioner name, specialty, or date range so I can find a convenient
time to see a doctor.

The patient writes something like "Are there openings with Dr. Smith
next Tuesday?" or "I need an ophthalmology appointment next week".
The chatbot extracts the practitioner, specialty, and date parameters
from the message, asks for any missing required info, and returns the
available time slots.

**Why this priority**: Searching is the prerequisite for booking. It
is still a read-only operation, but more complex than listing existing
appointments because it involves multi-step FHIR queries (Practitioner
-> Schedule -> Slot).

**Independent Test**: Can be tested by asking "Show me availability
for ophthalmology next week" and verifying the returned slots match
the sandbox data. Delivers value as a standalone availability checker.

**Acceptance Scenarios**:

1. **Given** a patient asks for slots with a specific practitioner on
   a specific date,
   **When** slots exist,
   **Then** the chatbot displays each slot with date, time, and
   practitioner name.

2. **Given** a patient asks for slots but does not specify a date,
   **When** the chatbot detects the missing information,
   **Then** it politely asks for a date or date range before searching.

3. **Given** a patient asks for slots but none are available,
   **When** the search returns empty,
   **Then** the chatbot informs the patient and suggests trying
   different dates or a different practitioner.

4. **Given** a patient asks for a specialty (e.g., "ophthalmology"),
   **When** practitioners matching that specialty exist,
   **Then** the chatbot searches across all matching practitioners
   and returns combined availability.

5. **Given** a search returns more than 5 available slots,
   **When** the chatbot displays the first 5,
   **Then** it offers "Would you like to see more options?" and
   shows the next 5 upon confirmation.

---

### User Story 3 - Book an Appointment (Priority: P3)

As a patient, I want to book one of the available slots so I can
confirm my medical appointment.

After seeing available slots (from US-02), the patient selects one
by saying "Book the 10:30 one" or "I want the first slot". The chatbot
shows a summary, asks for explicit confirmation, and then creates the
appointment.

**Why this priority**: This is the first write operation. It depends
on the search flow (US-02) to identify slots, and requires an explicit
confirmation step before mutating data.

**Independent Test**: Can be tested by first searching for slots,
selecting one, confirming the booking, and verifying the appointment
appears in the patient's appointment list. Delivers value as a
complete search-and-book flow.

**Acceptance Scenarios**:

1. **Given** the patient has just seen a list of available slots,
   **When** they select one (e.g., "the first one", "the 10:30"),
   **Then** the chatbot displays a booking summary (date, time,
   practitioner, location) and asks "Shall I confirm this booking?"

2. **Given** the patient confirms the booking,
   **When** the reservation succeeds,
   **Then** the chatbot displays the confirmed appointment details
   with a reference ID.

3. **Given** the patient confirms the booking,
   **When** the reservation fails (slot taken, server error),
   **Then** the chatbot displays a friendly error and suggests
   searching for other available slots.

4. **Given** the chatbot asks for confirmation,
   **When** the patient declines (e.g., "no", "cancel"),
   **Then** the chatbot does not book and asks what they'd like
   to do instead.

---

### User Story 4 - Cancel an Appointment (Priority: P4)

As a patient, I want to cancel an existing appointment so I can free
the slot if I cannot attend.

The patient says something like "Cancel my appointment on Thursday"
or "Cancel the appointment with Dr. Garcia". The chatbot identifies
which appointment to cancel, asks for confirmation, and then updates
the appointment status.

**Why this priority**: This is the second write operation. It is
lower priority because cancellation is less frequent than booking,
and requires careful disambiguation when the patient has multiple
appointments.

**Independent Test**: Can be tested by first verifying the patient
has a booked appointment, requesting cancellation, confirming, and
verifying the appointment status changes. Delivers value as a
self-service cancellation tool.

**Acceptance Scenarios**:

1. **Given** a patient has one upcoming appointment matching their
   description,
   **When** they request cancellation,
   **Then** the chatbot shows the appointment details and asks
   "Are you sure you want to cancel this appointment?"

2. **Given** a patient confirms the cancellation,
   **When** the cancellation succeeds,
   **Then** the chatbot confirms the appointment has been cancelled.

3. **Given** a patient has multiple appointments and their description
   is ambiguous (e.g., "cancel my appointment"),
   **When** the chatbot cannot determine which one,
   **Then** it lists the matching appointments and asks the patient
   to specify which one.

4. **Given** a patient confirms the cancellation,
   **When** the cancellation fails,
   **Then** the chatbot displays a friendly error message.

---

### Edge Cases

- **Authentication expired**: If the OAuth token expires mid-conversation,
  the system MUST inform the patient that their session has expired and
  prompt them to log in again.
- **Epic API unreachable**: If the FHIR server is down or times out,
  the chatbot MUST respond with a friendly message (e.g., "I'm having
  trouble connecting to the appointments system. Please try again in a
  few minutes.") and MUST NOT display technical error details.
- **Ambiguous natural language**: If the chatbot cannot determine the
  patient's intent, it MUST ask a clarifying question rather than
  guessing incorrectly (e.g., "I'm not sure I understood. Are you
  looking to book an appointment or check your existing ones?").
- **Concurrent modifications**: If a slot is booked between search and
  confirmation, the booking attempt will fail. The chatbot MUST handle
  this gracefully and suggest re-searching.
- **Rate limiting from Epic**: If Epic returns a 429, the system MUST
  retry once automatically. If it still fails, inform the patient of
  a temporary delay.
- **Empty practitioner search**: If no practitioner matches the name or
  specialty provided, the chatbot MUST inform the patient and suggest
  correcting the name or trying a different specialty.
- **Past-date slot search**: If the patient asks for slots on a past
  date, the chatbot MUST gently redirect them to search future dates.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST authenticate patients via OAuth 2.0
  SMART on FHIR standalone launch using Epic's sandbox authorization
  endpoints.
- **FR-002**: The system MUST interpret natural language messages and
  determine patient intent (search slots, book, cancel, list
  appointments) using an AI agent with tool calling.
- **FR-003**: The system MUST search for available appointment slots
  by practitioner name, medical specialty, and/or date range.
- **FR-004**: The system MUST display available slots with date, time,
  and practitioner name in a human-readable format. Results MUST be
  capped at 5 slots per response. If more results exist, the chatbot
  MUST offer to show the next batch.
- **FR-005**: The system MUST require explicit patient confirmation
  before executing any write operation (book or cancel).
- **FR-006**: The system MUST create appointments against the FHIR
  Appointment resource when a patient confirms a booking.
- **FR-007**: The system MUST cancel appointments by updating the
  FHIR Appointment status to "cancelled" when confirmed by the patient.
- **FR-008**: The system MUST list upcoming appointments within the
  next 90 days for the authenticated patient with date, time,
  practitioner, and status.
- **FR-009**: The system MUST ask clarifying questions when the patient's
  message lacks required information (e.g., missing date for a search).
- **FR-010**: The system MUST respond in Spanish for the MVP. Future
  versions may support detecting and matching the patient's language.
- **FR-011**: The system MUST never display raw error messages, stack
  traces, or technical details to the patient.
- **FR-012**: The system MUST log all FHIR API interactions without
  including OAuth tokens or patient credentials in the logs.
- **FR-013**: The system MUST handle token expiration gracefully by
  prompting the patient to re-authenticate.
- **FR-014**: The system MUST retry once on HTTP 429 responses from
  the FHIR server before informing the patient of a delay.
- **FR-015**: The frontend MUST provide a chat interface where the
  patient can type messages and receive formatted responses.
- **FR-016**: The frontend MUST send at most the 20 most recent
  messages per request. Older messages are dropped from the context
  sent to the backend.

### Key Entities

- **Patient**: The authenticated user. Identified by FHIR Patient ID
  obtained during OAuth flow. Key attributes: name, FHIR ID.
- **Practitioner**: A medical professional. Key attributes: name,
  specialty, FHIR ID.
- **Slot**: An available time window for an appointment. Key attributes:
  start time, end time, status (free/busy), associated schedule.
- **Schedule**: Links a practitioner to their available time slots.
  Key attributes: FHIR ID, associated practitioner, associated location.
- **Appointment**: A booked or cancelled patient visit. Key attributes:
  date/time, status (booked/cancelled), patient reference, practitioner
  reference, location, reference ID.

### Assumptions

- The Epic FHIR R4 sandbox at `fhir.epic.com` is available and supports
  the required FHIR resources (Patient, Practitioner, Slot, Schedule,
  Appointment).
- The sandbox provides test patient credentials (fhirjason / epicepic1)
  that grant the necessary OAuth scopes.
- The chatbot handles one patient per session (the authenticated user).
  There is no multi-user or multi-session persistence.
- The MVP operates exclusively in Spanish as the primary interface
  language.
- There is no persistent database; conversation history lives only in
  the current browser session and is sent with each request. Each
  request MUST include at most the 20 most recent messages to keep
  latency within the 10-second target (SC-004).
- The system does not support appointment rescheduling as a single
  operation in the MVP; the patient must cancel and rebook separately.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A patient can view their upcoming appointments within a
  single conversational exchange (one question, one answer).
- **SC-002**: A patient can find available slots, select one, and
  complete a booking in under 3 conversational turns after the initial
  search request.
- **SC-003**: A patient can cancel an appointment in under 3
  conversational turns (request, confirmation, result).
- **SC-004**: The chatbot responds to every patient message within 10
  seconds (including AI processing and FHIR calls combined).
- **SC-005**: The chatbot correctly interprets patient intent (search,
  book, cancel, list) at least 90% of the time on first attempt,
  without requiring clarification.
- **SC-006**: 100% of error scenarios (FHIR failures, expired tokens,
  unavailable slots) result in a friendly, non-technical patient-facing
  message.
- **SC-007**: All four user stories (list, search, book, cancel) are
  independently functional and testable against the Epic sandbox.
