"""Tests for tool handlers (TDD Red → Green)."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime


class TestListAppointmentsTool:
    """T015: Tests for list_appointments tool handler."""

    @pytest.mark.asyncio
    async def test_list_appointments_uses_session_patient_id(self, mock_fhir_client, mock_session):
        """Tool injects patient_id from session, not from tool input."""
        from app.tools import handle_list_appointments

        mock_fhir_client.list_appointments.return_value = []

        result = await handle_list_appointments(
            tool_input={},
            fhir_client=mock_fhir_client,
            patient_id=mock_session["patient_id"],
        )
        mock_fhir_client.list_appointments.assert_called_once()
        call_args = mock_fhir_client.list_appointments.call_args
        assert call_args.kwargs["patient_id"] == mock_session["patient_id"]

    @pytest.mark.asyncio
    async def test_list_appointments_returns_formatted_list(self, mock_fhir_client, mock_session):
        """Returns formatted string with appointment details."""
        from app.tools import handle_list_appointments

        mock_fhir_client.list_appointments.return_value = [
            {
                "resourceType": "Appointment",
                "id": "appt-001",
                "status": "booked",
                "start": "2026-03-25T14:00:00-05:00",
                "end": "2026-03-25T14:30:00-05:00",
                "participant": [
                    {
                        "actor": {"reference": "Patient/p1", "display": "Jason"},
                        "status": "accepted",
                    },
                    {
                        "actor": {"reference": "Practitioner/pr1", "display": "Dr. Smith"},
                        "status": "accepted",
                    },
                ],
            }
        ]

        result = await handle_list_appointments(
            tool_input={},
            fhir_client=mock_fhir_client,
            patient_id=mock_session["patient_id"],
        )
        assert "Dr. Smith" in result
        assert "2026-03-25" in result

    @pytest.mark.asyncio
    async def test_list_appointments_empty_returns_message(self, mock_fhir_client, mock_session):
        """Returns friendly message when no appointments found."""
        from app.tools import handle_list_appointments

        mock_fhir_client.list_appointments.return_value = []

        result = await handle_list_appointments(
            tool_input={},
            fhir_client=mock_fhir_client,
            patient_id=mock_session["patient_id"],
        )
        assert "no" in result.lower() or "not found" in result.lower()

    @pytest.mark.asyncio
    async def test_list_appointments_error_returns_friendly_message(self, mock_fhir_client, mock_session):
        """Wraps FHIR errors in a friendly message."""
        from app.tools import handle_list_appointments
        from app.fhir_client import FHIRError

        mock_fhir_client.list_appointments.side_effect = FHIRError(500)

        result = await handle_list_appointments(
            tool_input={},
            fhir_client=mock_fhir_client,
            patient_id=mock_session["patient_id"],
        )
        assert "error" in result.lower() or "problem" in result.lower()


class TestSearchAvailableSlotsTool:
    """T024: Tests for search_available_slots tool handler."""

    @pytest.mark.asyncio
    async def test_search_with_practitioner_name(self, mock_fhir_client, mock_session):
        """Searches by practitioner name."""
        from app.tools import handle_search_available_slots

        mock_fhir_client.search_practitioner.return_value = [
            {"id": "prac-1", "name": [{"family": "Smith"}]}
        ]
        mock_fhir_client.search_schedules.return_value = [
            {"id": "sched-1"}
        ]
        mock_fhir_client.search_slots.return_value = [
            {"id": "slot-1", "start": "2026-03-20T09:00:00", "end": "2026-03-20T09:30:00", "status": "free"}
        ]

        result = await handle_search_available_slots(
            tool_input={"practitioner_name": "Smith", "date_from": "2026-03-20"},
            fhir_client=mock_fhir_client,
            patient_id=mock_session["patient_id"],
        )
        assert "slot-1" in result or "2026-03-20" in result

    @pytest.mark.asyncio
    async def test_search_requires_date_from(self, mock_fhir_client, mock_session):
        """date_from is required in the tool input."""
        from app.tools import handle_search_available_slots

        with pytest.raises(KeyError):
            await handle_search_available_slots(
                tool_input={"practitioner_name": "Smith"},
                fhir_client=mock_fhir_client,
                patient_id=mock_session["patient_id"],
            )

    @pytest.mark.asyncio
    async def test_search_caps_at_5_results(self, mock_fhir_client, mock_session):
        """Results capped at 5 per FR-004."""
        from app.tools import handle_search_available_slots

        mock_fhir_client.search_practitioner.return_value = [
            {"id": "prac-1", "name": [{"family": "Smith"}]}
        ]
        mock_fhir_client.search_schedules.return_value = [{"id": "sched-1"}]
        mock_fhir_client.search_slots.return_value = [
            {"id": f"slot-{i}", "start": f"2026-03-{20+i}T09:00:00", "end": f"2026-03-{20+i}T09:30:00", "status": "free"}
            for i in range(8)
        ]

        result = await handle_search_available_slots(
            tool_input={"practitioner_name": "Smith", "date_from": "2026-03-20"},
            fhir_client=mock_fhir_client,
            patient_id=mock_session["patient_id"],
        )
        # Should mention "showing 5" and "more available"
        assert "5" in result
        assert "more" in result.lower()

    @pytest.mark.asyncio
    async def test_search_no_results_message(self, mock_fhir_client, mock_session):
        """Returns friendly message when no slots found."""
        from app.tools import handle_search_available_slots

        mock_fhir_client.search_practitioner.return_value = [
            {"id": "prac-1", "name": [{"family": "Smith"}]}
        ]
        mock_fhir_client.search_schedules.return_value = [{"id": "sched-1"}]
        mock_fhir_client.search_slots.return_value = []

        result = await handle_search_available_slots(
            tool_input={"practitioner_name": "Smith", "date_from": "2026-03-20"},
            fhir_client=mock_fhir_client,
            patient_id=mock_session["patient_id"],
        )
        assert "no available" in result.lower() or "not found" in result.lower()


class TestBookAppointmentTool:
    """T030: Tests for book_appointment tool handler."""

    @pytest.mark.asyncio
    async def test_book_requires_slot_id(self, mock_fhir_client, mock_session):
        """slot_id is required."""
        from app.tools import handle_book_appointment

        with pytest.raises(KeyError):
            await handle_book_appointment(
                tool_input={},
                fhir_client=mock_fhir_client,
                patient_id=mock_session["patient_id"],
            )

    @pytest.mark.asyncio
    async def test_book_injects_patient_id(self, mock_fhir_client, mock_session):
        """Uses patient_id from session."""
        from app.tools import handle_book_appointment

        mock_fhir_client.book_appointment.return_value = {
            "id": "appt-new", "status": "booked", "start": "2026-03-20T09:00:00"
        }

        result = await handle_book_appointment(
            tool_input={"slot_id": "slot-1"},
            fhir_client=mock_fhir_client,
            patient_id=mock_session["patient_id"],
        )
        call_args = mock_fhir_client.book_appointment.call_args
        assert call_args.kwargs["patient_id"] == mock_session["patient_id"]
        assert "appt-new" in result

    @pytest.mark.asyncio
    async def test_book_error_returns_friendly_message(self, mock_fhir_client, mock_session):
        """Booking failure returns friendly message."""
        from app.tools import handle_book_appointment
        from app.fhir_client import FHIRError

        mock_fhir_client.book_appointment.side_effect = FHIRError(422)

        result = await handle_book_appointment(
            tool_input={"slot_id": "slot-taken"},
            fhir_client=mock_fhir_client,
            patient_id=mock_session["patient_id"],
        )
        assert "could not" in result.lower() or "error" in result.lower()


class TestCancelAppointmentTool:
    """T036: Tests for cancel_appointment tool handler."""

    @pytest.mark.asyncio
    async def test_cancel_requires_appointment_id(self, mock_fhir_client, mock_session):
        """appointment_id is required."""
        from app.tools import handle_cancel_appointment

        with pytest.raises(KeyError):
            await handle_cancel_appointment(
                tool_input={},
                fhir_client=mock_fhir_client,
                patient_id=mock_session["patient_id"],
            )

    @pytest.mark.asyncio
    async def test_cancel_returns_confirmation(self, mock_fhir_client, mock_session):
        """Returns confirmation message."""
        from app.tools import handle_cancel_appointment

        mock_fhir_client.cancel_appointment.return_value = {
            "id": "appt-001", "status": "cancelled"
        }

        result = await handle_cancel_appointment(
            tool_input={"appointment_id": "appt-001"},
            fhir_client=mock_fhir_client,
            patient_id=mock_session["patient_id"],
        )
        assert "cancelled" in result.lower()

    @pytest.mark.asyncio
    async def test_cancel_error_returns_friendly_message(self, mock_fhir_client, mock_session):
        """Cancellation failure returns friendly message."""
        from app.tools import handle_cancel_appointment
        from app.fhir_client import FHIRError

        mock_fhir_client.cancel_appointment.side_effect = FHIRError(500)

        result = await handle_cancel_appointment(
            tool_input={"appointment_id": "appt-bad"},
            fhir_client=mock_fhir_client,
            patient_id=mock_session["patient_id"],
        )
        assert "could not" in result.lower() or "problem" in result.lower()
