"""POST /api/chat endpoint."""

import logging
import time

from fastapi import APIRouter, Cookie, HTTPException

from app.agent import process_message
from app.auth import sessions
from app.config import Settings
from app.models import ChatRequest, ChatResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["chat"])


def get_settings() -> Settings:
    """Get settings instance. Separated for test patching."""
    return Settings()


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    session_id: str | None = Cookie(default=None),
) -> ChatResponse:
    """Process a chat message through the Claude agent."""
    # Check authentication
    if not session_id or session_id not in sessions:
        raise HTTPException(status_code=401, detail="No estás autenticado. Por favor iniciá sesión.")

    session = sessions[session_id]

    # Check token expiry
    if session["expires_at"] <= time.time():
        del sessions[session_id]
        raise HTTPException(status_code=401, detail="Tu sesión expiró. Por favor iniciá sesión de nuevo.")

    try:
        settings = get_settings()
        history = [msg.model_dump() for msg in request.history]

        response_text = await process_message(
            message=request.message,
            history=history,
            patient_id=session["patient_id"],
            access_token=session["access_token"],
            settings=settings,
        )

        return ChatResponse(message=response_text)

    except Exception as e:
        logger.error("Error processing chat: %s", e)
        raise HTTPException(
            status_code=500,
            detail="Hubo un problema procesando tu mensaje. Por favor intentá de nuevo.",
        )
