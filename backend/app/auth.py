"""OAuth 2.0 SMART on FHIR authentication for Epic sandbox."""

import base64
import hashlib
import logging
import secrets
import time
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Cookie, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse

from app.config import Settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


async def _fetch_patient_name(
    fhir_base_url: str, access_token: str, patient_id: str
) -> str:
    """Fetch patient display name from FHIR. Returns empty on failure."""
    if not patient_id:
        return ""
    try:
        async with httpx.AsyncClient(timeout=10.0) as http:
            resp = await http.get(
                f"{fhir_base_url}/Patient/{patient_id}",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/fhir+json",
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                names = data.get("name", [])
                if names:
                    first = names[0]
                    if first.get("text"):
                        return first["text"]
                    given = " ".join(first.get("given", []))
                    family = first.get("family", "")
                    return f"{given} {family}".strip()
    except Exception:
        logger.debug("Could not fetch patient name, using empty")
    return ""

# In-memory session and state storage (MVP, single-server)
sessions: dict[str, dict] = {}
_oauth_states: dict[str, dict] = {}


def get_settings() -> Settings:
    """Get settings instance. Separated for test patching."""
    return Settings()


@router.get("/dev-login")
async def dev_login() -> RedirectResponse:
    """Create a dev session with Epic's test patient (fhirjason). DEV_MODE only."""
    settings = get_settings()
    if not settings.DEV_MODE:
        raise HTTPException(status_code=404, detail="Not found")

    session_id = secrets.token_urlsafe(32)
    sessions[session_id] = {
        "access_token": "dev-token-not-for-fhir-calls",
        "patient_id": "Tbt3KuCY0B5PSrJvCu2j-PlK.aiHsu2xUjUM8bWpetXoB",
        "patient_name": "Jason Argonaut (DEV)",
        "expires_at": time.time() + 86400,
        "scope": "dev-mode",
    }
    logger.info("DEV session created for test patient fhirjason")

    response = RedirectResponse(url=settings.FRONTEND_URL, status_code=307)
    response.set_cookie(
        key="session_id",
        value=session_id,
        httponly=True,
        samesite="lax",
        max_age=86400,
    )
    return response


@router.get("/login")
async def login() -> RedirectResponse:
    """Initiate OAuth standalone launch. Redirects to Epic authorize."""
    settings = get_settings()

    state = secrets.token_urlsafe(32)
    code_verifier = secrets.token_urlsafe(64)
    code_challenge = (
        base64.urlsafe_b64encode(
            hashlib.sha256(code_verifier.encode()).digest()
        )
        .rstrip(b"=")
        .decode()
    )
    _oauth_states[state] = {
        "created_at": time.time(),
        "code_verifier": code_verifier,
    }

    params = {
        "response_type": "code",
        "client_id": settings.EPIC_CLIENT_ID,
        "redirect_uri": settings.EPIC_REDIRECT_URI,
        "scope": settings.OAUTH_SCOPES,
        "state": state,
        "aud": settings.EPIC_FHIR_AUD_URL or settings.EPIC_FHIR_BASE_URL,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    authorize_url = f"{settings.EPIC_AUTHORIZE_URL}?{urlencode(params)}"
    return RedirectResponse(url=authorize_url, status_code=307)


@router.get("/callback")
async def callback(code: str, state: str) -> RedirectResponse:
    """Handle OAuth callback from Epic. Exchanges code for tokens."""
    settings = get_settings()

    # Validate state to prevent CSRF
    if state not in _oauth_states:
        raise HTTPException(status_code=400, detail="Invalid state parameter")
    state_data = _oauth_states.pop(state)
    code_verifier = state_data["code_verifier"]

    # Exchange authorization code for access token (with PKCE verifier)
    async with httpx.AsyncClient() as http:
        resp = await http.post(
            settings.EPIC_TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": settings.EPIC_REDIRECT_URI,
                "client_id": settings.EPIC_CLIENT_ID,
                "code_verifier": code_verifier,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

    if resp.status_code != 200:
        logger.error("Token exchange failed with status %d", resp.status_code)
        raise HTTPException(status_code=502, detail="Authentication failed")

    token_data = resp.json()
    access_token = token_data["access_token"]
    patient_id = token_data.get("patient", "")
    expires_in = token_data.get("expires_in", 3600)

    # Fetch patient name from FHIR
    patient_name = await _fetch_patient_name(
        settings.EPIC_FHIR_BASE_URL, access_token, patient_id
    )

    # Create session
    session_id = secrets.token_urlsafe(32)
    sessions[session_id] = {
        "access_token": access_token,
        "patient_id": patient_id,
        "patient_name": patient_name,
        "expires_at": time.time() + expires_in,
        "scope": token_data.get("scope", ""),
    }
    logger.info("Session created for patient FHIR ID (redacted)")

    # Redirect to frontend with session cookie
    response = RedirectResponse(url=settings.FRONTEND_URL, status_code=307)
    response.set_cookie(
        key="session_id",
        value=session_id,
        httponly=True,
        samesite="lax",
        max_age=expires_in,
    )
    return response


@router.get("/status")
async def status(session_id: str | None = Cookie(default=None)) -> dict:
    """Return current authentication status."""
    settings = get_settings()
    base = {"dev_mode": settings.DEV_MODE}

    if not session_id or session_id not in sessions:
        return {**base, "authenticated": False}

    session = sessions[session_id]
    remaining = session["expires_at"] - time.time()

    if remaining <= 0:
        del sessions[session_id]
        return {**base, "authenticated": False}

    return {
        **base,
        "authenticated": True,
        "patient_name": session.get("patient_name", ""),
        "expires_in": int(remaining),
    }


@router.post("/logout")
async def logout(session_id: str | None = Cookie(default=None)) -> dict:
    """Clear the session."""
    if session_id and session_id in sessions:
        del sessions[session_id]
        logger.info("Session cleared")

    response = JSONResponse(content={"message": "Session cleared"})
    response.delete_cookie("session_id")
    return response
