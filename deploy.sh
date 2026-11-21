#!/bin/sh
# Überträgt den Code auf das Zielsystem und baut und (re)startet dort den Container.
# data/ und .env auf dem Ziel bleiben unberührt. Aufruf: ./deploy.sh
set -eu

# Über Tailscale, damit es auch von außerhalb des Ladennetzes klappt.
HOST=${CM_DEPLOY_HOST:-chef@ds218-dls-tail}
DIR=${CM_DEPLOY_DIR:-/volume1/IT-Systeme/Docker/coop-manager}
# Synology: Der Benutzer ist nicht in der Gruppe docker, und sudo sucht nicht in /usr/local/bin.
DOCKER=${CM_DEPLOY_DOCKER:-sudo /usr/local/bin/docker}

cd "$(dirname "$0")"
# tar statt rsync: Die Synology erlaubt rsync über SSH nur mit eingeschaltetem rsync-Dienst.
# backend/ und frontend/ werden als Ganzes ersetzt, gelöschte Dateien verschwinden so auch auf dem Ziel.
# Die Liste ist bewusst ausdrücklich: node_modules, dist, .venv, data und Beispieldaten bleiben hier.
tar -c --exclude __pycache__ \
    Dockerfile compose.yaml .dockerignore \
    backend/pyproject.toml backend/uv.lock backend/src \
    frontend/package.json frontend/package-lock.json frontend/index.html frontend/env.d.ts \
    frontend/tsconfig.json frontend/tsconfig.app.json frontend/tsconfig.node.json frontend/vite.config.ts \
    frontend/public frontend/src |
    ssh "$HOST" "cd '$DIR' && rm -rf backend frontend && tar -x --no-same-owner"
ssh "$HOST" "cd '$DIR' && $DOCKER compose up -d --build && $DOCKER compose ps"
