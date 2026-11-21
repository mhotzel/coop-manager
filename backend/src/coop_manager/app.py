import logging
import secrets
from collections.abc import AsyncGenerator, Sequence
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import Response
from starlette.types import Scope

from .accounts import api as accounts_api
from .config import Settings, load_settings
from .core import DomainError, NotFoundError
from .db import prepare
from .eventsource import Projector
from .handbook import api as handbook_api
from .logs import init_logging
from .members import api as members_api
from .members.projections import MemberList
from .reports import api as reports_api
from .security import init_security
from .users import api as users_api
from .users import login_attempts
from .users.projections import UserList

log = logging.getLogger(__name__)

# Alle Projektoren und zusätzlichen Tabellen der Projektionsdatenbank; jedes Modul trägt sich hier ein.
PROJECTORS: list[Projector] = [UserList(), MemberList()]
SCHEMAS: list[str] = [login_attempts.SCHEMA]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Läuft einmal beim Start der App (vor dem `yield`) und einmal beim Beenden (danach)."""
    prepare(app.state.settings.data_dir, app.state.projectors, SCHEMAS)
    log.info("app started", extra={"data_dir": app.state.settings.data_dir})
    yield


def create_app(settings: Settings | None = None, projectors: Sequence[Projector] = PROJECTORS) -> FastAPI:
    """Baut die FastAPI-App: Einstellungen, Logging, Session, Security-Header, Fehler-Handler, Router."""
    settings = settings or load_settings()
    # Ohne Doku stehen alle drei auf None und sind damit abgeschaltet.
    docs = settings.api_docs
    app = FastAPI(
        title="coop-manager",
        lifespan=lifespan,
        docs_url="/docs" if docs else None,
        redoc_url="/redoc" if docs else None,
        openapi_url="/openapi.json" if docs else None,
    )
    app.state.settings = settings
    init_logging(app.state.settings.log_level)
    app.state.projectors = projectors
    init_session(app, app.state.settings)
    init_security(app, app.state.settings.trusted_proxies)
    init_error_handlers(app)

    app.include_router(users_api.router)
    app.include_router(members_api.router)
    app.include_router(accounts_api.router)
    app.include_router(reports_api.router)
    app.include_router(handbook_api.router)

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        """Lebenszeichen für Docker und Monitoring."""
        return {"status": "ok"}

    # Zuletzt einhängen: Routen werden der Reihe nach geprüft, /api und /healthz haben so Vorrang.
    if settings.frontend_dir is not None:
        app.mount("/", SpaStaticFiles(directory=settings.frontend_dir), name="frontend")

    return app


class SpaStaticFiles(StaticFiles):
    """Liefert die gebaute Vue-App aus (SPA = Single Page Application).

    Gibt es die angefragte Datei nicht, kommt `index.html`: Adressen wie `/members/5` kennt nur der
    Vue Router im Browser, der Server muss beim Neuladen trotzdem die App liefern. Ausnahme `/api/…`:
    Eine unbekannte API-Adresse bleibt ein 404 als JSON. Vor Pfaden wie `/../.env` schützt
    `StaticFiles` selbst.
    """

    async def get_response(self, path: str, scope: Scope) -> Response:
        """Die Datei zu `path`, sonst `index.html`; unter `api/` bleibt es beim 404."""
        try:
            return await super().get_response(path, scope)
        except HTTPException as exc:
            if exc.status_code != 404 or path == "api" or path.startswith("api/"):
                raise
            return await super().get_response("index.html", scope)


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
