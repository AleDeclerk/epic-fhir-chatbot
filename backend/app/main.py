"""FastAPI application entry point."""

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.auth import router as auth_router
from app.config import Settings
from app.routes.chat import router as chat_router

logger = logging.getLogger(__name__)

# Simple in-memory rate limiter
_rate_limit: dict[str, list[float]] = {}
RATE_LIMIT_MAX = 30  # requests per window
RATE_LIMIT_WINDOW = 60  # seconds


def get_settings() -> Settings:
    """Get settings instance."""
    return Settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )
    logger.info("Starting FHIR Appointment Chatbot API")
    yield
    logger.info("Shutting down")


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""
    if settings is None:
        settings = get_settings()

    app = FastAPI(
        title="FHIR Appointment Chatbot",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.FRONTEND_URL],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Rate limiting middleware
    @app.middleware("http")
    async def rate_limit_middleware(request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()

        if client_ip not in _rate_limit:
            _rate_limit[client_ip] = []

        # Clean old entries
        _rate_limit[client_ip] = [
            t for t in _rate_limit[client_ip] if now - t < RATE_LIMIT_WINDOW
        ]

        if len(_rate_limit[client_ip]) >= RATE_LIMIT_MAX:
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please wait."},
            )

        _rate_limit[client_ip].append(now)
        return await call_next(request)

    # Routes
    app.include_router(auth_router)
    app.include_router(chat_router)

    return app


def get_app() -> FastAPI:
    """Lazy app factory for uvicorn."""
    return create_app()


app = get_app()
