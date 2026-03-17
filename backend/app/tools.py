"""Tool definitions and handlers for the Claude agent."""

import logging
from datetime import date, timedelta

from app.fhir_client import EpicFHIRClient, FHIRError

logger = logging.getLogger(__name__)

# Tool JSON schemas for the Anthropic API
TOOL_SCHEMAS = [
    {
        "name": "list_appointments",
        "description": (
            "Lista los próximos turnos del paciente dentro de los próximos 90 días. "
            "Usa esta herramienta cuando el paciente pregunta por sus turnos, citas o "
            "próximas visitas. Devuelve fecha, hora, médico y estado de cada turno."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["booked", "cancelled", "all"],
                    "description": "Filtro de estado (default: booked)",
                },
            },
            "required": [],
        },
    },
    {
        "name": "search_available_slots",
        "description": (
            "Busca horarios disponibles para un turno médico. Usa esta herramienta "
            "cuando el paciente pide buscar disponibilidad con un médico o especialidad. "
            "Devuelve una lista de slots libres con fecha, hora y nombre del médico."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "practitioner_name": {
                    "type": "string",
                    "description": "Nombre del médico a buscar (opcional si se da especialidad)",
                },
                "specialty": {
                    "type": "string",
                    "description": "Especialidad médica (opcional si se da nombre)",
                },
                "date_from": {
                    "type": "string",
                    "description": "Fecha desde en formato ISO 8601 (YYYY-MM-DD)",
                },
                "date_to": {
                    "type": "string",
                    "description": "Fecha hasta en formato ISO 8601 (opcional, default: date_from + 7 días)",
                },
            },
            "required": ["date_from"],
        },
    },
    {
        "name": "book_appointment",
        "description": (
            "Reserva un turno en un slot disponible. Usa esta herramienta SOLO después "
            "de que el paciente haya confirmado explícitamente que quiere reservar. "
            "Devuelve los detalles del turno confirmado o un error si el slot ya no está disponible."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "slot_id": {
                    "type": "string",
                    "description": "ID del slot FHIR a reservar",
                },
                "reason": {
                    "type": "string",
                    "description": "Motivo de la consulta (opcional)",
                },
            },
            "required": ["slot_id"],
        },
    },
    {
        "name": "cancel_appointment",
        "description": (
            "Cancela un turno existente del paciente. Usa esta herramienta SOLO después "
            "de que el paciente haya confirmado explícitamente que quiere cancelar. "
            "Cambia el estado del turno a cancelado."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "appointment_id": {
                    "type": "string",
                    "description": "ID FHIR del appointment a cancelar",
                },
            },
            "required": ["appointment_id"],
        },
    },
]


def _extract_practitioner_name(appointment: dict) -> str:
    """Extract practitioner display name from appointment participants."""
    for p in appointment.get("participant", []):
        ref = p.get("actor", {}).get("reference", "")
        if "Practitioner" in ref:
            return p["actor"].get("display", "Médico")
    return "Médico"


def _format_appointment(appt: dict) -> str:
    """Format a single appointment for display."""
    practitioner = _extract_practitioner_name(appt)
    start = appt.get("start", "Fecha no disponible")
    status = appt.get("status", "desconocido")
    appt_id = appt.get("id", "")
    return f"- {start} | {practitioner} | Estado: {status} | ID: {appt_id}"


async def handle_list_appointments(
    tool_input: dict,
    fhir_client: EpicFHIRClient,
    patient_id: str,
) -> str:
    """Handle the list_appointments tool call."""
    try:
        today = date.today().isoformat()
        end_date = (date.today() + timedelta(days=90)).isoformat()
        status = tool_input.get("status", "booked")

        if status == "all":
            status = "booked,cancelled"

        appointments = await fhir_client.list_appointments(
            patient_id=patient_id,
            date_from=today,
            date_to=end_date,
            status=status,
        )

        if not appointments:
            return "No se encontraron turnos próximos en los próximos 90 días."

        lines = [f"Se encontraron {len(appointments)} turno(s):\n"]
        for appt in appointments:
            lines.append(_format_appointment(appt))
        return "\n".join(lines)

    except FHIRError as e:
        logger.error("FHIR error listing appointments: %s", e)
        return "Hubo un problema al consultar tus turnos. Por favor intentá de nuevo."


async def handle_search_available_slots(
    tool_input: dict,
    fhir_client: EpicFHIRClient,
    patient_id: str,
) -> str:
    """Handle the search_available_slots tool call."""
    try:
        practitioner_name = tool_input.get("practitioner_name")
        date_from = tool_input["date_from"]
        date_to = tool_input.get("date_to")
        if not date_to:
            from_date = date.fromisoformat(date_from)
            date_to = (from_date + timedelta(days=7)).isoformat()

        if not practitioner_name:
            return "Necesito el nombre del médico para buscar disponibilidad."

        # Search practitioner
        practitioners = await fhir_client.search_practitioner(practitioner_name)
        if not practitioners:
            return f"No se encontró ningún médico con el nombre '{practitioner_name}'."

        practitioner = practitioners[0]
        practitioner_id = practitioner["id"]
        practitioner_display = practitioner.get("name", [{}])[0].get("family", practitioner_name)

        # Search schedules
        schedules = await fhir_client.search_schedules(practitioner_id)
        if not schedules:
            return f"No se encontraron horarios para {practitioner_display}."

        # Search free slots
        all_slots = []
        for schedule in schedules:
            try:
                slots = await fhir_client.search_slots(
                    schedule_id=schedule["id"],
                    start_from=date_from,
                    start_to=date_to,
                    status="free",
                )
                for slot in slots:
                    slot["_practitioner_name"] = practitioner_display
                    slot["_practitioner_id"] = practitioner_id
                all_slots.extend(slots)
            except FHIRError:
                continue

        if not all_slots:
            return f"No hay turnos disponibles para {practitioner_display} en el período indicado."

        # Cap at 5 results
        all_slots.sort(key=lambda s: s.get("start", ""))
        display_slots = all_slots[:5]

        lines = [f"Se encontraron {len(all_slots)} turnos disponibles (mostrando {len(display_slots)}):\n"]
        for slot in display_slots:
            start = slot.get("start", "")
            end = slot.get("end", "")
            slot_id = slot.get("id", "")
            lines.append(f"- {start} a {end} | {practitioner_display} | Slot ID: {slot_id}")

        if len(all_slots) > 5:
            lines.append(f"\nHay {len(all_slots) - 5} turnos más disponibles. Pedime 'mostrar más' para verlos.")

        return "\n".join(lines)

    except FHIRError as e:
        logger.error("FHIR error searching slots: %s", e)
        return "Hubo un problema al buscar disponibilidad. Por favor intentá de nuevo."


async def handle_book_appointment(
    tool_input: dict,
    fhir_client: EpicFHIRClient,
    patient_id: str,
) -> str:
    """Handle the book_appointment tool call."""
    try:
        slot_id = tool_input["slot_id"]

        # We need the practitioner_id — read the slot to find the schedule
        # and then the practitioner. For now, use a simplified approach.
        result = await fhir_client.book_appointment(
            slot_id=slot_id,
            patient_id=patient_id,
            practitioner_id="",  # Will be extracted from slot context
        )

        appt_id = result.get("id", "desconocido")
        start = result.get("start", "")
        return f"Turno reservado exitosamente. ID: {appt_id}, Fecha: {start}"

    except FHIRError as e:
        logger.error("FHIR error booking appointment: %s", e)
        return "No se pudo reservar el turno. Es posible que el slot ya no esté disponible."


async def handle_cancel_appointment(
    tool_input: dict,
    fhir_client: EpicFHIRClient,
    patient_id: str,
) -> str:
    """Handle the cancel_appointment tool call."""
    try:
        appointment_id = tool_input["appointment_id"]
        result = await fhir_client.cancel_appointment(appointment_id)
        return f"Turno {appointment_id} cancelado exitosamente."

    except FHIRError as e:
        logger.error("FHIR error cancelling appointment: %s", e)
        return "No se pudo cancelar el turno. Por favor intentá de nuevo."


# Map tool names to handlers
TOOL_HANDLERS = {
    "list_appointments": handle_list_appointments,
    "search_available_slots": handle_search_available_slots,
    "book_appointment": handle_book_appointment,
    "cancel_appointment": handle_cancel_appointment,
}
