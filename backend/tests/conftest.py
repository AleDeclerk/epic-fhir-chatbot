"""Shared test fixtures for the FHIR Appointment Chatbot."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from httpx import ASGITransport, AsyncClient


@pytest.fixture
def mock_settings():
    """Mock Settings with test values."""
    from app.config import Settings

    return Settings(
        EPIC_FHIR_BASE_URL="https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4",
        EPIC_CLIENT_ID="test-client-id",
        EPIC_CLIENT_SECRET="test-client-secret",
        EPIC_REDIRECT_URI="http://localhost:8000/auth/callback",
        EPIC_AUTHORIZE_URL="https://fhir.epic.com/interconnect-fhir-oauth/oauth2/authorize",
        EPIC_TOKEN_URL="https://fhir.epic.com/interconnect-fhir-oauth/oauth2/token",
        ANTHROPIC_API_KEY="test-anthropic-key",
        CLAUDE_MODEL="claude-sonnet-4-20250514",
        APP_SECRET_KEY="test-secret-key",
        FRONTEND_URL="http://localhost:5173",
    )


@pytest.fixture
def mock_session():
    """Mock authenticated session data."""
    return {
        "patient_id": "Tbt3KuCY0B5PSrJvCu2j-PlK.aiHsu2xUjUM8bWpetXoB",
        "access_token": "fake-access-token-12345",
        "patient_name": "Jason Argonaut",
        "expires_at": 9999999999.0,
    }


@pytest.fixture
def mock_fhir_client():
    """Mock EpicFHIRClient with all methods as AsyncMock."""
    client = AsyncMock()
    client.list_appointments = AsyncMock(return_value=[])
    client.search_practitioner = AsyncMock(return_value=[])
    client.search_schedules = AsyncMock(return_value=[])
    client.search_slots = AsyncMock(return_value=[])
    client.book_appointment = AsyncMock(return_value={})
    client.cancel_appointment = AsyncMock(return_value={})
    client.close = AsyncMock()
    return client


@pytest.fixture
def sample_appointment_bundle():
    """Sample FHIR Appointment Bundle response."""
    return {
        "resourceType": "Bundle",
        "type": "searchset",
        "total": 1,
        "entry": [
            {
                "fullUrl": "https://fhir.epic.com/.../Appointment/abc123",
                "resource": {
                    "resourceType": "Appointment",
                    "id": "abc123",
                    "status": "booked",
                    "start": "2026-03-25T14:00:00-05:00",
                    "end": "2026-03-25T14:30:00-05:00",
                    "participant": [
                        {
                            "actor": {
                                "reference": "Patient/Tbt3KuCY0B5PSrJvCu2j-PlK.aiHsu2xUjUM8bWpetXoB",
                                "display": "Jason Argonaut",
                            },
                            "status": "accepted",
                        },
                        {
                            "actor": {
                                "reference": "Practitioner/eM5CWtq15N0WJeuCet5bJlQ3",
                                "display": "Family Medicine Physician",
                            },
                            "status": "accepted",
                        },
                    ],
                },
            }
        ],
    }


@pytest.fixture
def sample_practitioner_bundle():
    """Sample FHIR Practitioner Bundle response."""
    return {
        "resourceType": "Bundle",
        "type": "searchset",
        "total": 1,
        "entry": [
            {
                "fullUrl": "https://fhir.epic.com/.../Practitioner/eM5CWtq15N0WJeuCet5bJlQ3",
                "resource": {
                    "resourceType": "Practitioner",
                    "id": "eM5CWtq15N0WJeuCet5bJlQ3",
                    "name": [
                        {
                            "use": "official",
                            "family": "Physician",
                            "given": ["Family Medicine"],
                            "prefix": ["Dr."],
                        }
                    ],
                },
            }
        ],
    }


@pytest.fixture
def sample_schedule_bundle():
    """Sample FHIR Schedule Bundle response."""
    return {
        "resourceType": "Bundle",
        "type": "searchset",
        "total": 1,
        "entry": [
            {
                "fullUrl": "https://fhir.epic.com/.../Schedule/eIDmKq.4HlMO6fwMQ5B2eEw3",
                "resource": {
                    "resourceType": "Schedule",
                    "id": "eIDmKq.4HlMO6fwMQ5B2eEw3",
                    "actor": [
                        {
                            "reference": "Practitioner/eM5CWtq15N0WJeuCet5bJlQ3",
                            "display": "Family Medicine Physician",
                        }
                    ],
                },
            }
        ],
    }


@pytest.fixture
def sample_slot_bundle():
    """Sample FHIR Slot Bundle response."""
    return {
        "resourceType": "Bundle",
        "type": "searchset",
        "total": 1,
        "entry": [
            {
                "fullUrl": "https://fhir.epic.com/.../Slot/slot-001",
                "resource": {
                    "resourceType": "Slot",
                    "id": "slot-001",
                    "schedule": {
                        "reference": "Schedule/eIDmKq.4HlMO6fwMQ5B2eEw3",
                    },
                    "status": "free",
                    "start": "2026-03-20T09:00:00-05:00",
                    "end": "2026-03-20T09:30:00-05:00",
                },
            }
        ],
    }


@pytest.fixture
def empty_bundle():
    """Empty FHIR Bundle response."""
    return {
        "resourceType": "Bundle",
        "type": "searchset",
        "total": 0,
    }
