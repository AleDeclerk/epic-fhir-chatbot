"""Tests for OAuth 2.0 SMART on FHIR auth module (TDD Red → Green)."""

import pytest
import time
from unittest.mock import AsyncMock, patch, MagicMock
from urllib.parse import urlparse, parse_qs

from httpx import AsyncClient, ASGITransport


@pytest.fixture
def auth_client(mock_settings):
    """Create a FastAPI app with auth routes and return client factory."""
    # Patch get_settings for the lifetime of the fixture
    patcher = patch("app.auth.get_settings", return_value=mock_settings)
    patcher.start()

    from app.auth import router
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(router)

    yield app, mock_settings

    patcher.stop()


class TestLoginRedirect:
    @pytest.mark.asyncio
    async def test_login_redirects_to_epic(self, auth_client):
        """GET /auth/login returns 307 redirect to Epic authorize."""
        app, _ = auth_client
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/auth/login", follow_redirects=False)
            assert resp.status_code == 307
            location = resp.headers["location"]
            assert "fhir.epic.com" in location
            assert "oauth2/authorize" in location

    @pytest.mark.asyncio
    async def test_login_includes_required_params(self, auth_client):
        """Redirect URL includes client_id, redirect_uri, scope, state, aud, PKCE."""
        app, _ = auth_client
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/auth/login", follow_redirects=False)
            location = resp.headers["location"]
            parsed = urlparse(location)
            params = parse_qs(parsed.query)
            assert "client_id" in params
            assert "redirect_uri" in params
            assert "scope" in params
            assert "state" in params
            assert "aud" in params
            assert "response_type" in params
            assert params["response_type"][0] == "code"
            # PKCE parameters
            assert "code_challenge" in params
            assert params["code_challenge_method"][0] == "S256"

    @pytest.mark.asyncio
    async def test_login_includes_aud_param(self, auth_client):
        """The aud parameter MUST be the FHIR base URL (Epic requirement)."""
        app, _ = auth_client
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/auth/login", follow_redirects=False)
            location = resp.headers["location"]
            parsed = urlparse(location)
            params = parse_qs(parsed.query)
            assert params["aud"][0] == "https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4"


class TestCallback:
    @pytest.mark.asyncio
    async def test_callback_invalid_state_returns_400(self, auth_client):
        """Callback with unknown state returns 400."""
        app, _ = auth_client
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/auth/callback?code=abc&state=invalid")
            assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_callback_exchanges_code_for_token(self, auth_client):
        """Callback exchanges auth code and sets session."""
        app, settings = auth_client
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # First get a valid state via login
            login_resp = await client.get("/auth/login", follow_redirects=False)
            location = login_resp.headers["location"]
            parsed = urlparse(location)
            params = parse_qs(parsed.query)
            state = params["state"][0]

            # Mock the token exchange
            mock_token_response = MagicMock()
            mock_token_response.status_code = 200
            mock_token_response.json.return_value = {
                "access_token": "epic-token-xyz",
                "token_type": "Bearer",
                "expires_in": 3600,
                "scope": "patient/Patient.read",
                "patient": "Tbt3KuCY0B5PSrJvCu2j-PlK.aiHsu2xUjUM8bWpetXoB",
            }

            # Mock both the token exchange and patient name fetch
            mock_patient_resp = MagicMock()
            mock_patient_resp.status_code = 200
            mock_patient_resp.json.return_value = {
                "resourceType": "Patient",
                "name": [{"given": ["Jason"], "family": "Argonaut"}],
            }

            with patch("app.auth.httpx.AsyncClient") as MockClient:
                mock_http = AsyncMock()
                mock_http.post.return_value = mock_token_response
                mock_http.get.return_value = mock_patient_resp
                mock_http.__aenter__ = AsyncMock(return_value=mock_http)
                mock_http.__aexit__ = AsyncMock(return_value=False)
                MockClient.return_value = mock_http

                resp = await client.get(
                    f"/auth/callback?code=authcode123&state={state}",
                    follow_redirects=False,
                )
                assert resp.status_code == 307
                assert settings.FRONTEND_URL in resp.headers["location"]

                # Verify code_verifier was sent in token exchange
                post_call = mock_http.post.call_args
                assert "code_verifier" in post_call.kwargs.get("data", {})


class TestStatus:
    @pytest.mark.asyncio
    async def test_status_unauthenticated(self, auth_client):
        """GET /auth/status returns authenticated=false without session."""
        app, _ = auth_client
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/auth/status")
            assert resp.status_code == 200
            data = resp.json()
            assert data["authenticated"] is False

    @pytest.mark.asyncio
    async def test_status_authenticated(self, auth_client):
        """GET /auth/status returns authenticated=true with valid session."""
        from app.auth import sessions

        app, _ = auth_client
        sessions["test-session"] = {
            "access_token": "token123",
            "patient_id": "patient-001",
            "patient_name": "Test Patient",
            "expires_at": time.time() + 3600,
        }

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/auth/status",
                cookies={"session_id": "test-session"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["authenticated"] is True
            assert data["patient_name"] == "Test Patient"

        del sessions["test-session"]


class TestLogout:
    @pytest.mark.asyncio
    async def test_logout_clears_session(self, auth_client):
        """POST /auth/logout clears the session."""
        from app.auth import sessions

        app, _ = auth_client
        sessions["logout-test"] = {
            "access_token": "token",
            "patient_id": "p1",
            "patient_name": "Test",
            "expires_at": time.time() + 3600,
        }

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/auth/logout",
                cookies={"session_id": "logout-test"},
            )
            assert resp.status_code == 200
            assert "logout-test" not in sessions
