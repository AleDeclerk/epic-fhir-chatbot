"""Application configuration via Pydantic Settings."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Loads configuration from environment variables or .env file."""

    # Epic FHIR
    EPIC_FHIR_BASE_URL: str
    EPIC_CLIENT_ID: str
    EPIC_CLIENT_SECRET: str
    EPIC_REDIRECT_URI: str

    # Epic OAuth endpoints
    EPIC_AUTHORIZE_URL: str
    EPIC_TOKEN_URL: str

    # Anthropic
    ANTHROPIC_API_KEY: str
    CLAUDE_MODEL: str = "claude-sonnet-4-20250514"

    # App
    APP_SECRET_KEY: str
    FRONTEND_URL: str

    @property
    def OAUTH_SCOPES(self) -> str:
        """Return the OAuth scopes string for Epic SMART on FHIR."""
        return " ".join([
            "patient/Patient.read",
            "patient/Practitioner.read",
            "patient/Appointment.read",
            "patient/Appointment.write",
            "patient/Slot.read",
            "patient/Schedule.read",
            "launch/patient",
            "openid",
            "fhirUser",
        ])

    model_config = {"env_file": ".env", "extra": "ignore"}
