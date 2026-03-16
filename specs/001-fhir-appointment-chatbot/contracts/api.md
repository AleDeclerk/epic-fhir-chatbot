# API Contracts: FHIR Appointment Chatbot

**Date**: 2026-03-16

## Backend REST API

Base URL: `http://localhost:8000`

### POST /api/chat

Primary chat endpoint. Receives a patient message with conversation
history and returns the chatbot's response.

**Request**:
```json
{
  "message": "¿Qué turnos tengo?",
  "history": [
    {"role": "user", "content": "Hola"},
    {"role": "assistant", "content": "¡Hola! ¿En qué puedo ayudarte?"}
  ]
}
```

| Field     | Type             | Required | Notes                    |
|-----------|------------------|----------|--------------------------|
| message   | string           | yes      | Current patient message  |
| history   | ChatMessage[]    | yes      | Max 20 most recent       |

**Response (200)**:
```json
{
  "message": "Tus próximos turnos son:\n1. Lunes 24/03 09:00 - Dr. Smith\n2. Miércoles 26/03 14:00 - Dr. Jones"
}
```

| Field   | Type   | Notes                           |
|---------|--------|---------------------------------|
| message | string | Chatbot response (formatted)    |

**Error responses**:

| Status | Body                    | When                          |
|--------|-------------------------|-------------------------------|
| 401    | `{"detail": "..."}` | Session expired / not authed  |
| 422    | `{"detail": "..."}` | Invalid request body          |
| 500    | `{"detail": "..."}` | Internal error (generic msg)  |
| 429    | `{"detail": "..."}` | Rate limit exceeded           |

### GET /auth/login

Initiates the SMART on FHIR OAuth flow. Redirects the browser to
Epic's authorization endpoint.

**Response**: 302 redirect to Epic authorize URL.

### GET /auth/callback

OAuth callback endpoint. Epic redirects here after patient
authenticates.

**Query params**:

| Param | Type   | Notes                              |
|-------|--------|------------------------------------|
| code  | string | Authorization code from Epic       |
| state | string | Must match the original state      |

**Response**: 302 redirect to frontend with session cookie set.

### GET /auth/status

Returns current authentication status.

**Response (200)**:
```json
{
  "authenticated": true,
  "patient_name": "Jason Argonaut",
  "expires_in": 3200
}
```

### POST /auth/logout

Clears the session.

**Response (200)**:
```json
{
  "message": "Session cleared"
}
```

## Claude Agent Tool Schemas

These are the tools passed to the Anthropic API via the `tools`
parameter. Each tool is executed by the backend, NOT by Claude.

### search_available_slots

```json
{
  "name": "search_available_slots",
  "description": "Busca horarios disponibles para un turno médico. Usa esta herramienta cuando el paciente pide buscar disponibilidad con un médico o especialidad. Devuelve una lista de slots libres con fecha, hora y nombre del médico.",
  "input_schema": {
    "type": "object",
    "properties": {
      "practitioner_name": {
        "type": "string",
        "description": "Nombre del médico a buscar (opcional si se da especialidad)"
      },
      "specialty": {
        "type": "string",
        "description": "Especialidad médica (opcional si se da nombre)"
      },
      "date_from": {
        "type": "string",
        "description": "Fecha desde en formato ISO 8601 (YYYY-MM-DD)"
      },
      "date_to": {
        "type": "string",
        "description": "Fecha hasta en formato ISO 8601 (opcional, default: date_from + 7 días)"
      }
    },
    "required": ["date_from"]
  }
}
```

### book_appointment

```json
{
  "name": "book_appointment",
  "description": "Reserva un turno en un slot disponible. Usa esta herramienta SOLO después de que el paciente haya confirmado explícitamente que quiere reservar. Devuelve los detalles del turno confirmado o un error si el slot ya no está disponible.",
  "input_schema": {
    "type": "object",
    "properties": {
      "slot_id": {
        "type": "string",
        "description": "ID del slot FHIR a reservar"
      },
      "reason": {
        "type": "string",
        "description": "Motivo de la consulta (opcional)"
      }
    },
    "required": ["slot_id"]
  }
}
```

### cancel_appointment

```json
{
  "name": "cancel_appointment",
  "description": "Cancela un turno existente del paciente. Usa esta herramienta SOLO después de que el paciente haya confirmado explícitamente que quiere cancelar. Cambia el estado del turno a cancelado.",
  "input_schema": {
    "type": "object",
    "properties": {
      "appointment_id": {
        "type": "string",
        "description": "ID FHIR del appointment a cancelar"
      }
    },
    "required": ["appointment_id"]
  }
}
```

### list_appointments

```json
{
  "name": "list_appointments",
  "description": "Lista los próximos turnos del paciente dentro de los próximos 90 días. Usa esta herramienta cuando el paciente pregunta por sus turnos, citas o próximas visitas. Devuelve fecha, hora, médico y estado de cada turno.",
  "input_schema": {
    "type": "object",
    "properties": {
      "status": {
        "type": "string",
        "enum": ["booked", "cancelled", "all"],
        "description": "Filtro de estado (default: booked)"
      }
    },
    "required": []
  }
}
```

**Note**: `patient_id` is NOT a tool parameter. The backend injects
it from the authenticated session. This prevents the agent from
querying other patients' data.
