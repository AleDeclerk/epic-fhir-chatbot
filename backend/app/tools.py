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
            "Lists the patient's upcoming appointments within the next 90 days. "
            "Use this tool when the patient asks about their appointments, visits, or "
            "upcoming schedule. Returns the date, time, practitioner, and status of each appointment."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["booked", "cancelled", "all"],
                    "description": "Status filter (default: booked)",
                },
            },
            "required": [],
        },
    },
    {
        "name": "search_available_slots",
        "description": (
            "Searches for available time slots for a medical appointment. Use this tool "
            "when the patient asks to search for availability with a practitioner or specialty. "
            "Returns a list of free slots with date, time, and practitioner name."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "practitioner_name": {
                    "type": "string",
                    "description": "Practitioner name to search for (optional if specialty is given)",
                },
                "specialty": {
                    "type": "string",
                    "description": "Medical specialty (optional if name is given)",
                },
                "date_from": {
                    "type": "string",
                    "description": "Start date in ISO 8601 format (YYYY-MM-DD)",
                },
                "date_to": {
                    "type": "string",
                    "description": "End date in ISO 8601 format (optional, default: date_from + 7 days)",
                },
            },
            "required": ["date_from"],
        },
    },
    {
        "name": "book_appointment",
        "description": (
            "Books an appointment in an available slot. Use this tool ONLY after "
            "the patient has explicitly confirmed they want to book. "
            "Returns the confirmed appointment details or an error if the slot is no longer available."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "slot_id": {
                    "type": "string",
                    "description": "FHIR Slot ID to book",
                },
                "reason": {
                    "type": "string",
                    "description": "Reason for the visit (optional)",
                },
            },
            "required": ["slot_id"],
        },
    },
    {
        "name": "cancel_appointment",
        "description": (
            "Cancels an existing patient appointment. Use this tool ONLY after "
            "the patient has explicitly confirmed they want to cancel. "
            "Changes the appointment status to cancelled."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "appointment_id": {
                    "type": "string",
                    "description": "FHIR Appointment ID to cancel",
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
            return p["actor"].get("display", "Practitioner")
    return "Practitioner"


def _format_appointment(appt: dict) -> str:
    """Format a single appointment for display."""
    practitioner = _extract_practitioner_name(appt)
    start = appt.get("start", "Date not available")
    status = appt.get("status", "unknown")
    appt_id = appt.get("id", "")
    return f"- {start} | {practitioner} | Status: {status} | ID: {appt_id}"


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
            return "No upcoming appointments found in the next 90 days."

        lines = [f"Found {len(appointments)} appointment(s):\n"]
        for appt in appointments:
            lines.append(_format_appointment(appt))
        return "\n".join(lines)

    except FHIRError as e:
        logger.error("FHIR error listing appointments: %s", e)
        return "There was a problem retrieving your appointments. Please try again."


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
            return "I need the practitioner's name to search for availability."

        # Search practitioner
        practitioners = await fhir_client.search_practitioner(practitioner_name)
        if not practitioners:
            return f"No practitioner found with the name '{practitioner_name}'."

        practitioner = practitioners[0]
        practitioner_id = practitioner["id"]
        practitioner_display = practitioner.get("name", [{}])[0].get("family", practitioner_name)

        # Search schedules
        schedules = await fhir_client.search_schedules(practitioner_id)
        if not schedules:
            return f"No schedules found for {practitioner_display}."

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
            return f"No available appointments for {practitioner_display} in the specified period."

        # Cap at 5 results
        all_slots.sort(key=lambda s: s.get("start", ""))
        display_slots = all_slots[:5]

        lines = [f"Found {len(all_slots)} available slot(s) (showing {len(display_slots)}):\n"]
        for slot in display_slots:
            start = slot.get("start", "")
            end = slot.get("end", "")
            slot_id = slot.get("id", "")
            lines.append(f"- {start} to {end} | {practitioner_display} | Slot ID: {slot_id}")

        if len(all_slots) > 5:
            lines.append(f"\nThere are {len(all_slots) - 5} more available slots. Ask me to 'show more' to see them.")

        return "\n".join(lines)

    except FHIRError as e:
        logger.error("FHIR error searching slots: %s", e)
        return "There was a problem searching for availability. Please try again."


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

        appt_id = result.get("id", "unknown")
        start = result.get("start", "")
        return f"Appointment booked successfully. ID: {appt_id}, Date: {start}"

    except FHIRError as e:
        logger.error("FHIR error booking appointment: %s", e)
        return "The appointment could not be booked. The slot may no longer be available."


async def handle_cancel_appointment(
    tool_input: dict,
    fhir_client: EpicFHIRClient,
    patient_id: str,
) -> str:
    """Handle the cancel_appointment tool call."""
    try:
        appointment_id = tool_input["appointment_id"]
        result = await fhir_client.cancel_appointment(appointment_id)
        return f"Appointment {appointment_id} cancelled successfully."

    except FHIRError as e:
        logger.error("FHIR error cancelling appointment: %s", e)
        return "The appointment could not be cancelled. Please try again."


# Map tool names to handlers
TOOL_HANDLERS = {
    "list_appointments": handle_list_appointments,
    "search_available_slots": handle_search_available_slots,
    "book_appointment": handle_book_appointment,
    "cancel_appointment": handle_cancel_appointment,
}
