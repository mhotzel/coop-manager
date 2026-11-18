#!/usr/bin/env bash
# Startet Backend (uvicorn) und Frontend (Vite) im Entwicklermodus. Strg+C beendet beide.
# Aufruf: ./dev.sh   – danach im Browser http://localhost:5173 öffnen.
set -eu
cd "$(dirname "$0")"  # egal, aus welchem Ordner das Skript aufgerufen wird

# Beim Ende des Skripts alle Prozesse seiner Prozessgruppe beenden, also beide Server samt
# ihrer Unterprozesse (uvicorn --reload und npm starten selbst weitere Prozesse).
trap 'kill 0' EXIT

(cd backend && uv run uvicorn coop_manager.app:app --reload) &
(cd frontend && npm run dev) &

# Wartet, bis einer der beiden endet (z. B. abgestürzt); dann stoppt der trap den anderen auch.
wait -n
