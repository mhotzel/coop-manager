import logging
import secrets
from collections.abc import AsyncGenerator, Sequence
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.sessions import SessionMiddleware

from .config import Settings, load_settings
from .core import DomainError, NotFoundError
from .db import prepare
from .eventsource import Projector
from .logs import init_logging
from .security import init_security
from .users import api as users_api
from .users import login_attempts
from .users.projections import UserList

log = logging.getLogger(__name__)

# Alle Projektoren und zusätzlichen Tabellen der Projektionsdatenbank; jedes Modul trägt sich hier ein.
PROJECTORS: list[Projector] = [UserList()]
SCHEMAS: list[str] = [login_attempts.SCHEMA]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Läuft einmal beim Start der App (vor dem `yield`) und einmal beim Beenden (danach)."""
    prepare(app.state.settings.data_dir, app.state.projectors, SCHEMAS)
    log.info("app started", extra={"data_dir": app.state.settings.data_dir})
    yield


def create_app(settings: Settings | None = None, projectors: Sequence[Projector] = PROJECTORS) -> FastAPI:
    """Baut die FastAPI-App: Einstellungen, Logging, Session, Security-Header, Fehler-Handler, Router."""
    app = FastAPI(title="coop-manager", lifespan=lifespan)
    app.state.settings = settings or load_settings()
    init_logging(app.state.settings.log_level)
    app.state.projectors = projectors
    init_session(app, app.state.settings)
    init_security(app, app.state.settings.trusted_proxies)
    init_error_handlers(app)

    app.include_router(users_api.router)

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        """Lebenszeichen für Docker und Monitoring."""
        return {"status": "ok"}

    return app


def init_session(app: FastAPI, settings: Settings) -> None:
    """Signiertes Session-Cookie.

    Es wird bei jeder Antwort erneuert und läuft nach `session_timeout` Sekunden ohne Anfrage ab.
    """
    secret_key = settings.secret_key
    if not secret_key:
        log.warning("CM_SECRET_KEY not set, using a random key; sessions end with every restart")
        secret_key = secrets.token_hex(32)
    app.add_middleware(
        SessionMiddleware,
        secret_key=secret_key,
        session_cookie="session",
        max_age=settings.session_timeout,
        same_site="lax",
        https_only=settings.session_cookie_secure,
    )


def init_error_handlers(app: FastAPI) -> None:
    """Fachliche Fehler als JSON im selben Format wie FastAPIs HTTPException: {"detail": "..."}."""

    @app.exception_handler(NotFoundError)
    async def not_found(request: Request, exc: NotFoundError) -> JSONResponse:
        return JSONResponse({"detail": str(exc)}, status_code=404)

    @app.exception_handler(DomainError)
    async def domain_error(request: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse({"detail": str(exc)}, status_code=400)


app = create_app()
