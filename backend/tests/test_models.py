"""Tests for Pydantic models (TDD Red → Green)."""

import pytest
from datetime import datetime


class TestChatMessage:
    def test_valid_user_message(self):
        from app.models import ChatMessage

        msg = ChatMessage(role="user", content="Hola")
        assert msg.role == "user"
        assert msg.content == "Hola"

    def test_valid_assistant_message(self):
        from app.models import ChatMessage

        msg = ChatMessage(role="assistant", content="Buenos días")
        assert msg.role == "assistant"

    def test_invalid_role_rejected(self):
        from app.models import ChatMessage
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ChatMessage(role="system", content="test")


class TestChatRequest:
    def test_valid_request(self):
        from app.models import ChatRequest, ChatMessage

        req = ChatRequest(
            message="¿Qué turnos tengo?",
            history=[ChatMessage(role="user", content="Hola")],
        )
        assert req.message == "¿Qué turnos tengo?"
        assert len(req.history) == 1

    def test_history_max_20(self):
        from app.models import ChatRequest, ChatMessage
        from pydantic import ValidationError

        history = [ChatMessage(role="user", content=f"msg {i}") for i in range(21)]
        with pytest.raises(ValidationError):
            ChatRequest(message="test", history=history)

    def test_empty_history_allowed(self):
        from app.models import ChatRequest

        req = ChatRequest(message="test", history=[])
        assert req.history == []


class TestChatResponse:
    def test_valid_response(self):
        from app.models import ChatResponse

        resp = ChatResponse(message="Tus turnos son...")
        assert resp.message == "Tus turnos son..."


class TestSlotInfo:
    def test_valid_slot(self):
        from app.models import SlotInfo

        slot = SlotInfo(
            slot_id="slot-001",
            start=datetime(2026, 3, 20, 9, 0),
            end=datetime(2026, 3, 20, 9, 30),
            practitioner_name="Dr. Smith",
            practitioner_id="prac-001",
        )
        assert slot.slot_id == "slot-001"
        assert slot.location is None

    def test_slot_with_location(self):
        from app.models import SlotInfo

        slot = SlotInfo(
            slot_id="slot-001",
            start=datetime(2026, 3, 20, 9, 0),
            end=datetime(2026, 3, 20, 9, 30),
            practitioner_name="Dr. Smith",
            practitioner_id="prac-001",
            location="Room 201",
        )
        assert slot.location == "Room 201"


class TestAppointmentInfo:
    def test_valid_appointment(self):
        from app.models import AppointmentInfo

        appt = AppointmentInfo(
            appointment_id="appt-001",
            status="booked",
            start=datetime(2026, 3, 25, 14, 0),
            end=datetime(2026, 3, 25, 14, 30),
            practitioner_name="Dr. Jones",
        )
        assert appt.appointment_id == "appt-001"
        assert appt.status == "booked"
        assert appt.location is None


class TestTokenData:
    def test_valid_token(self):
        from app.models import TokenData

        token = TokenData(
            access_token="abc123",
            expires_at=datetime(2026, 3, 16, 12, 0),
            patient_id="patient-001",
            scope="patient/Patient.read",
        )
        assert token.access_token == "abc123"
        assert token.refresh_token is None

    def test_token_with_refresh(self):
        from app.models import TokenData

        token = TokenData(
            access_token="abc123",
            refresh_token="refresh-xyz",
            expires_at=datetime(2026, 3, 16, 12, 0),
            patient_id="patient-001",
            scope="patient/Patient.read",
        )
        assert token.refresh_token == "refresh-xyz"
