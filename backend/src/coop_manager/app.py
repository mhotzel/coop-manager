import logging
from collections.abc import AsyncGenerator, Sequence
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .config import Settings, load_settings
from .db import prepare
from .eventsource import Projector
from .logs import init_logging
from .security import init_security

log = logging.getLogger(__name__)

PROJECTORS: list[Projector] = []


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Läuft einmal beim Start der App (vor dem `yield`) und einmal beim Beenden (danach)."""
    prepare(app.state.settings.data_dir, app.state.projectors)
    log.info("app started", extra={"data_dir": app.state.settings.data_dir})
    yield


def create_app(settings: Settings | None = None, projectors: Sequence[Projector] = PROJECTORS) -> FastAPI:
    app = FastAPI(title="coop-manager", lifespan=lifespan)
    app.state.settings = settings or load_settings()
    init_logging(app.state.settings.log_level)
    app.state.projectors = projectors
    init_security(app, app.state.settings.trusted_proxies)

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        """Lebenszeichen für Docker und Monitoring."""
        return {"status": "ok"}

    return app


app = create_app()
