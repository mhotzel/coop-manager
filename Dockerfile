# Zwei Stufen: Die erste baut nur die Vue-App, ins fertige Image kommt davon allein der Ordner dist.

# --- Stufe 1: Frontend bauen ---
FROM node:24-slim AS frontend
WORKDIR /build

# Abhängigkeiten zuerst: Diese Schicht bleibt im Cache, solange sich die Lock-Datei nicht ändert.
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# --- Stufe 2: das eigentliche Image mit Python ---
FROM python:3.14-slim

COPY --from=ghcr.io/astral-sh/uv:0.13.7 /uv /usr/local/bin/uv

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_NO_DEV=1

# Abhängigkeiten zuerst, aus demselben Grund wie oben.
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --locked --no-install-project

# Lesbar für den Benutzer ohne Root-Rechte, egal welche Rechte die Dateien auf dem Host haben
# (eine Synology-Freigabe mit ACLs kommt als 0700 root an).
COPY --chmod=755 backend/src ./src
RUN uv sync --locked

# Nur die fertigen Dateien aus Stufe 1; Node und node_modules bleiben draußen.
COPY --from=frontend --chmod=755 /build/dist ./frontend

RUN groupadd --gid 1000 app && useradd --uid 1000 --gid app --no-create-home app && mkdir /data && chown app:app /data
USER app

ENV PATH=/app/.venv/bin:$PATH \
    CM_DATA_DIR=/data \
    CM_FRONTEND_DIR=/app/frontend \
    PYTHONUNBUFFERED=1

VOLUME /data
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz')"

# Ein Prozess: Beim Start holen die Projektionen auf, das darf nicht doppelt parallel laufen.
# --no-proxy-headers: X-Forwarded-* wertet allein die App aus (CM_TRUSTED_PROXIES).
CMD ["uvicorn", "coop_manager.app:app", "--host", "0.0.0.0", "--port", "8000", "--no-proxy-headers"]
