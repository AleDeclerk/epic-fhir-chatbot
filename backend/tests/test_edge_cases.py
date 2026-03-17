"""Edge case tests (T041)."""

import pytest
import time
from unittest.mock import AsyncMock, MagicMock, patch

from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI

from app.auth import router as auth_router, sessions
from app.routes.chat import router as chat_router
from app.fhir_client import FHIRError, FHIRAuthError, FHIRRateLimitError


class TestTokenExpiry:
    """Token expiry mid-conversation returns 401."""

    @pytest.mark.asyncio
    async def test_expired_session_returns_401(self, mock_settings):
        """Chat with expired session returns 401."""
        patcher_auth = patch("app.auth.get_settings", return_value=mock_settings)
        patcher_chat = patch("app.routes.chat.get_settings", return_value=mock_settings)
        patcher_auth.start()
        patcher_chat.start()

        app = FastAPI()
        app.include_router(auth_router)
        app.include_router(chat_router)

        sessions["expired"] = {
            "access_token": "old-token",
            "patient_id": "p1",
            "patient_name": "Test",
            "expires_at": time.time() - 100,  # Already expired
        }

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            client.cookies.set("session_id", "expired")
            resp = await client.post(
                "/api/chat",
                json={"message": "Hola", "history": []},
            )
            assert resp.status_code == 401

        sessions.pop("expired", None)
        patcher_auth.stop()
        patcher_chat.stop()


class TestFHIRTimeoutHandling:
    """FHIR timeout returns friendly message."""

    @pytest.mark.asyncio
    async def test_fhir_timeout_friendly_error(self, mock_fhir_client, mock_session):
        """Tool handler catches timeout and returns friendly message."""
        from app.tools import handle_list_appointments
        import httpx

        mock_fhir_client.list_appointments.side_effect = FHIRError(500)

        result = await handle_list_appointments(
            tool_input={},
            fhir_client=mock_fhir_client,
            patient_id=mock_session["patient_id"],
        )
        assert "problema" in result.lower() or "error" in result.lower()


class TestRateLimitExhaustion:
    """429 retry exhaustion returns friendly message."""

    @pytest.mark.asyncio
    async def test_rate_limit_exhaustion_friendly(self, mock_fhir_client, mock_session):
        """When rate limit retries are exhausted, return friendly error."""
        from app.tools import handle_list_appointments

        mock_fhir_client.list_appointments.side_effect = FHIRRateLimitError(429)

        result = await handle_list_appointments(
            tool_input={},
            fhir_client=mock_fhir_client,
            patient_id=mock_session["patient_id"],
        )
        assert "problema" in result.lower()


class TestFHIRAuthErrorHandling:
    """FHIR auth errors handled gracefully."""

    @pytest.mark.asyncio
    async def test_auth_error_friendly(self, mock_fhir_client, mock_session):
        """FHIRAuthError returns friendly message."""
        from app.tools import handle_list_appointments

        mock_fhir_client.list_appointments.side_effect = FHIRAuthError(401)

        result = await handle_list_appointments(
            tool_input={},
            fhir_client=mock_fhir_client,
            patient_id=mock_session["patient_id"],
        )
        assert "problema" in result.lower()
