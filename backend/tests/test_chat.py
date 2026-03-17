"""Tests for POST /api/chat endpoint (TDD Red → Green)."""

import pytest
import time
from unittest.mock import AsyncMock, patch, MagicMock

from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport

from app.auth import router as auth_router, sessions
from app.routes.chat import router as chat_router


@pytest.fixture
def chat_app(mock_settings):
    """Create app with chat route for testing."""
    patcher_auth = patch("app.auth.get_settings", return_value=mock_settings)
    patcher_chat = patch("app.routes.chat.get_settings", return_value=mock_settings)
    patcher_auth.start()
    patcher_chat.start()

    app = FastAPI()
    app.include_router(auth_router)
    app.include_router(chat_router)

    yield app

    patcher_auth.stop()
    patcher_chat.stop()


class TestChatEndpoint:
    """T017: Tests for POST /api/chat."""

    @pytest.mark.asyncio
    async def test_chat_401_without_session(self, chat_app):
        """Returns 401 when no session cookie."""
        transport = ASGITransport(app=chat_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/chat",
                json={"message": "Hola", "history": []},
            )
            assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_chat_422_invalid_body(self, chat_app):
        """Returns 422 with invalid request body."""
        sessions["chat-test"] = {
            "access_token": "token",
            "patient_id": "p1",
            "patient_name": "Test",
            "expires_at": time.time() + 3600,
        }

        transport = ASGITransport(app=chat_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            client.cookies.set("session_id", "chat-test")
            resp = await client.post("/api/chat", json={"bad": "data"})
            assert resp.status_code == 422

        del sessions["chat-test"]

    @pytest.mark.asyncio
    async def test_chat_200_with_valid_session(self, chat_app, mock_settings):
        """Returns 200 with valid session and message."""
        sessions["chat-ok"] = {
            "access_token": "token-abc",
            "patient_id": "patient-123",
            "patient_name": "Jason",
            "expires_at": time.time() + 3600,
        }

        with patch("app.routes.chat.process_message", new_callable=AsyncMock) as mock_process:
            mock_process.return_value = "¡Hola! ¿En qué puedo ayudarte?"

            transport = ASGITransport(app=chat_app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                client.cookies.set("session_id", "chat-ok")
                resp = await client.post(
                    "/api/chat",
                    json={"message": "Hola", "history": []},
                )
                assert resp.status_code == 200
                data = resp.json()
                assert "message" in data
                assert "ayudar" in data["message"]

        del sessions["chat-ok"]

    @pytest.mark.asyncio
    async def test_chat_history_max_20(self, chat_app):
        """Rejects history with more than 20 messages."""
        sessions["chat-max"] = {
            "access_token": "token",
            "patient_id": "p1",
            "patient_name": "Test",
            "expires_at": time.time() + 3600,
        }

        history = [{"role": "user", "content": f"msg {i}"} for i in range(21)]
        transport = ASGITransport(app=chat_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            client.cookies.set("session_id", "chat-max")
            resp = await client.post(
                "/api/chat",
                json={"message": "test", "history": history},
            )
            assert resp.status_code == 422

        del sessions["chat-max"]
