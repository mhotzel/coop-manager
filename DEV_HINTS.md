# Entwicklung: Starten und erste Schritte

Kurzanleitung für die lokale Entwicklung. Hintergründe stehen im [Logbuch](Logbuch.md).

## Einmalig einrichten

```bash
cp .env.example .env               # Konfiguration; .env wird nicht eingecheckt
cd backend && uv sync              # Python-Pakete nach backend/.venv
cd ../frontend && npm install      # Node-Pakete nach frontend/node_modules
```

In `.env` am besten `CM_SECRET_KEY` setzen, sonst endet jede Anmeldung mit einem Neustart des
Backends (mit `--reload` also bei jeder Codeänderung):

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

## Ersten Admin anlegen

Aus `backend/` heraus, damit die Daten im selben Ordner landen, den auch das Backend benutzt
(`CM_DATA_DIR=data`, also `backend/data/`):

```bash
cd backend
uv run coop-manager create-admin                                     # Benutzername „admin“
uv run coop-manager create-admin --username clara --full-name "Clara Chefin"
```

Das Kennwort wird verdeckt abgefragt. Danach legt der Admin im Frontend unter
„Benutzer“ weitere Benutzer an.

**Hinweis:** Der Admin darf nicht an die Mitglieder. Zum Testen der Mitglieder braucht es einen
Benutzer mit der Rolle „Buchhaltung“ (ändern) bzw. „Buchhaltung lesend“ (nur ansehen).

## Starten

Zwei Terminals, Backend und Frontend laufen nebeneinander:

```bash
# Terminal 1: Backend (uvicorn), http://localhost:8000
cd backend
uv run uvicorn coop_manager.app:app --reload

# Terminal 2: Frontend (Vite), http://localhost:5173
cd frontend
npm run dev
```

- Im Browser **http://localhost:5173** öffnen. Vite leitet `/api` und `/healthz` an das Backend
  weiter (siehe `frontend/vite.config.ts`).
- **http://localhost:8000/docs** zeigt die API-Beschreibung (Swagger). Die Endpunkte brauchen
  eine Anmeldung und bei POST das CSRF-Token im Header `X-CSRF-Token`. Zum Ausprobieren ist
  deshalb meist das Frontend oder ein Test einfacher.
- `--reload` startet das Backend bei jeder Codeänderung neu.

## API von Hand ausprobieren (curl)

Für Teile ohne Oberfläche, z. B. die Mitglieder-API vor Schritt 4d. `-c`/`-b` speichern und
schicken das Session-Cookie, `jq` holt das CSRF-Token aus der Login-Antwort:

```bash
API=http://localhost:8000/api
TOKEN=$(curl -s -c /tmp/cm-cookies -H 'Content-Type: application/json' \
  -d '{"username": "erika", "password": "…"}' $API/login | jq -r .csrf_token)

# Befehl: Antrag erfassen (erfundene Daten)
curl -s -b /tmp/cm-cookies -H "X-CSRF-Token: $TOKEN" -H 'Content-Type: application/json' \
  -d '{"person_type": "natural_person",
       "name": {"first_names": "Erika", "last_name": "Muster", "gender": "w"},
       "address": {"street": "Hauptstraße", "house_number": "1", "postal_code": "12345", "city": "Musterstadt"},
       "application_date": "2026-11-02", "shares_subscribed": 1}' \
  $API/members/apply | jq

# Abfrage: Suche
curl -s -b /tmp/cm-cookies -H "X-CSRF-Token: $TOKEN" -H 'Content-Type: application/json' \
  -d '{"query": "muster"}' $API/members/search | jq
```

`erika` muss dafür die Rolle „Buchhaltung“ haben (siehe oben).

## Von einem anderen Rechner (SSH-Tunnel)

Die Server lauschen nur auf `localhost`. Vom Arbeitsrechner aus:

```bash
ssh -L 5173:localhost:5173 -L 8000:localhost:8000 matthias@<rechner>
```

Danach lokal `http://localhost:5173` öffnen.

## Prüfen

```bash
cd backend
uv run pytest            # Tests
uv run ruff check        # Linter
uv run ruff format       # Formatierung
uv run pyright           # Typprüfung

cd ../frontend
npm run type-check       # TypeScript prüfen
```

## Neu anfangen

Alle Daten liegen in `backend/data/` (`eventstore.sqlite` und `projections.sqlite`). Zum
Zurücksetzen das Backend beenden, den Ordner löschen und den Admin neu anlegen. Die Projektionen
allein lassen sich auch löschen, sie werden beim Start aus dem Event Store neu aufgebaut.
