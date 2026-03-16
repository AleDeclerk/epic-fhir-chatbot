# Data Model: FHIR Appointment Chatbot

**Date**: 2026-03-16
**Feature**: 001-fhir-appointment-chatbot

## Overview

This system does NOT have its own database. All entities are FHIR R4
resources retrieved from the Epic sandbox. The data model documents
the FHIR resources used, their key fields, relationships, and the
internal Pydantic models that represent them in the backend.

## FHIR Resources

### Patient

| Field       | FHIR Path                | Type     | Notes                         |
|-------------|--------------------------|----------|-------------------------------|
| id          | Patient.id               | string   | From OAuth token `patient`    |
| name        | Patient.name[0].text     | string   | Display name                  |
| identifier  | Patient.identifier       | array    | MRN and other IDs             |

**Obtained via**: OAuth token response (`patient` field) + `GET /Patient/{id}`

### Practitioner

| Field       | FHIR Path                     | Type     | Notes                    |
|-------------|-------------------------------|----------|--------------------------|
| id          | Practitioner.id               | string   | FHIR resource ID         |
| name        | Practitioner.name[0].text     | string   | Display name             |
| specialty   | PractitionerRole.specialty    | coding   | Via PractitionerRole     |

**Search**: `GET /Practitioner?name={name}` or
`GET /PractitionerRole?specialty={code}`

### Schedule

| Field          | FHIR Path              | Type      | Notes                   |
|----------------|------------------------|-----------|-------------------------|
| id             | Schedule.id            | string    | FHIR resource ID        |
| actor          | Schedule.actor         | reference | Practitioner + Location |
| planningHorizon| Schedule.planningHorizon| period   | Bookable window         |

**Search**: `GET /Schedule?actor=Practitioner/{id}`

### Slot

| Field    | FHIR Path       | Type      | Notes                        |
|----------|-----------------|-----------|------------------------------|
| id       | Slot.id         | string    | FHIR resource ID             |
| schedule | Slot.schedule   | reference | Links to Schedule            |
| status   | Slot.status     | code      | free, busy, busy-tentative   |
| start    | Slot.start      | dateTime  | ISO 8601                     |
| end      | Slot.end        | dateTime  | ISO 8601                     |

**Search**: `GET /Slot?schedule=Schedule/{id}&status=free&start=ge{date}`

**Note**: Slot.Search may NOT be available in R4 on Epic sandbox.
See research.md R1 for fallback strategy.

### Appointment

| Field        | FHIR Path                    | Type      | Notes                  |
|--------------|------------------------------|-----------|------------------------|
| id           | Appointment.id               | string    | FHIR resource ID       |
| status       | Appointment.status           | code      | booked, cancelled      |
| start        | Appointment.start            | dateTime  | ISO 8601               |
| end          | Appointment.end              | dateTime  | ISO 8601               |
| participant  | Appointment.participant      | array     | Patient + Practitioner |
| slot         | Appointment.slot             | reference | Optional Slot ref      |
| description  | Appointment.description      | string    | Reason for visit       |

**Search**: `GET /Appointment?patient={id}&date=ge{today}&status=booked`
**Create**: `POST /Appointment` with status=booked
**Cancel**: `PUT /Appointment/{id}` with status=cancelled

## State Transitions

### Appointment Lifecycle

```
[none] --book--> booked --cancel--> cancelled
```

- `booked`: Active appointment. Created via `POST /Appointment`.
- `cancelled`: Cancelled by patient. Updated via `PUT /Appointment/{id}`
  with `status: "cancelled"`.

No rescheduling in MVP (cancel + rebook).

## Internal Pydantic Models

These are the backend's internal representations, NOT FHIR resources.
They decouple the application from raw FHIR JSON.

### ChatMessage

- `role`: "user" | "assistant"
- `content`: string

### ChatRequest

- `message`: string (patient's current message)
- `history`: list[ChatMessage] (max 20, most recent)

### ChatResponse

- `message`: string (chatbot's response)
- `tool_calls`: list[ToolCallInfo] (optional, for logging)

### SlotInfo

- `slot_id`: string (FHIR Slot ID)
- `start`: datetime
- `end`: datetime
- `practitioner_name`: string
- `practitioner_id`: string
- `location`: string (optional)

### AppointmentInfo

- `appointment_id`: string (FHIR Appointment ID)
- `status`: string
- `start`: datetime
- `end`: datetime
- `practitioner_name`: string
- `location`: string (optional)

### TokenData

- `access_token`: string
- `refresh_token`: string (optional)
- `expires_at`: datetime
- `patient_id`: string (FHIR Patient ID)
- `scope`: string

## Relationships

```
Patient ──< Appointment >── Practitioner
                │
                └── Slot ──> Schedule ──> Practitioner
                                │
                                └──> Location
```

- A Patient has many Appointments
- An Appointment references one Patient and one Practitioner
- An Appointment optionally references one Slot
- A Slot belongs to one Schedule
- A Schedule references one Practitioner and one Location
