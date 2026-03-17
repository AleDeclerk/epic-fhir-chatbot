"""Tests for Settings configuration class (TDD Red → Green)."""

import pytest
from unittest.mock import patch


class TestSettings:
    """Test Settings loads environment variables correctly."""

    def test_settings_loads_all_required_fields(self, mock_settings):
        """All required fields are populated."""
        assert mock_settings.EPIC_FHIR_BASE_URL == "https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4"
        assert mock_settings.EPIC_CLIENT_ID == "test-client-id"
        assert mock_settings.EPIC_CLIENT_SECRET == "test-client-secret"
        assert mock_settings.EPIC_REDIRECT_URI == "http://localhost:8000/auth/callback"
        assert mock_settings.EPIC_AUTHORIZE_URL == "https://fhir.epic.com/interconnect-fhir-oauth/oauth2/authorize"
        assert mock_settings.EPIC_TOKEN_URL == "https://fhir.epic.com/interconnect-fhir-oauth/oauth2/token"
        assert mock_settings.ANTHROPIC_API_KEY == "test-anthropic-key"
        assert mock_settings.CLAUDE_MODEL == "claude-sonnet-4-20250514"
        assert mock_settings.APP_SECRET_KEY == "test-secret-key"
        assert mock_settings.FRONTEND_URL == "http://localhost:5173"

    def test_settings_default_claude_model(self):
        """CLAUDE_MODEL has a sensible default."""
        from app.config import Settings

        settings = Settings(
            EPIC_FHIR_BASE_URL="https://example.com",
            EPIC_CLIENT_ID="id",
            EPIC_CLIENT_SECRET="secret",
            EPIC_REDIRECT_URI="http://localhost:8000/auth/callback",
            EPIC_AUTHORIZE_URL="https://example.com/authorize",
            EPIC_TOKEN_URL="https://example.com/token",
            ANTHROPIC_API_KEY="key",
            APP_SECRET_KEY="secret",
            FRONTEND_URL="http://localhost:5173",
        )
        assert settings.CLAUDE_MODEL == "claude-sonnet-4-20250514"

    def test_settings_oauth_scopes(self, mock_settings):
        """OAUTH_SCOPES returns the expected scope string."""
        scopes = mock_settings.OAUTH_SCOPES
        assert "patient/Patient.read" in scopes
        assert "patient/Appointment.read" in scopes
        assert "patient/Appointment.write" in scopes
        assert "launch/patient" in scopes
        assert "openid" in scopes
