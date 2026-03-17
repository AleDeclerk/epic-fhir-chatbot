"""Pydantic models for request/response validation and internal data."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """A single message in the conversation history."""

    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    """Incoming chat request from the frontend."""

    message: str
    history: list[ChatMessage] = Field(default_factory=list, max_length=20)


class ChatResponse(BaseModel):
    """Chat response returned to the frontend."""

    message: str


class SlotInfo(BaseModel):
    """Internal representation of a FHIR Slot."""

    slot_id: str
    start: datetime
    end: datetime
    practitioner_name: str
    practitioner_id: str
    location: str | None = None


class AppointmentInfo(BaseModel):
    """Internal representation of a FHIR Appointment."""

    appointment_id: str
    status: str
    start: datetime
    end: datetime
    practitioner_name: str
    location: str | None = None


class TokenData(BaseModel):
    """OAuth token data stored in session."""

    access_token: str
    refresh_token: str | None = None
    expires_at: datetime
    patient_id: str
    scope: str
