from fastapi import FastAPI

app = FastAPI(title="coop-manager")


@app.get("/healthz")
def healthz() -> dict[str, str]:
    """Lebenszeichen für Docker und Monitoring."""
    return {"status": "ok"}
