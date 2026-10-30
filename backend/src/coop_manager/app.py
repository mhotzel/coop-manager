import os
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from .db import prepare
from .eventsource import Projector

PROJECTORS: list[Projector] = []


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Läuft einmal beim Start der App (vor dem `yield`) und einmal beim Beenden (danach)."""
    prepare(app.state.data_dir, app.state.projectors)
    yield


def create_app(data_dir: Path | None = None, projectors: Sequence[Projector] = PROJECTORS) -> FastAPI:
    app = FastAPI(title="coop-manager", lifespan=lifespan)
    app.state.data_dir = data_dir or Path(os.environ.get("CM_DATA_DIR", "data"))
    app.state.projectors = projectors

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        """Lebenszeichen für Docker und Monitoring."""
        return {"status": "ok"}

    return app


app = create_app()
