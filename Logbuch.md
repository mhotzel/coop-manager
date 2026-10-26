# Logbuch

Chronik der Entwicklung: was gemacht wurde, mit welchen Werkzeugen und warum. Die fachlichen
und technischen Entscheidungen selbst stehen in `Plan.md`.

## 2026-10-25 – Konzeptphase

**Was:** `Konzeption.md`, die Bildschirmentwürfe und Beispiellisten aus dem Altsystem sowie die
Satzung (v11 vom 30.06.2015) durchgesprochen. Ergebnis ist `Plan.md`.

**Wichtigste Ergebnisse:**

- Statusmodell der Mitgliedschaft: Antragsteller → Zulassung durch den Vorstand und Geldeingang
  → Mitglied → Kündigung/Ausschluss/Tod → Ausscheiden zum 31.12.
- Ausscheiden und Auszahlung sind getrennt; die Auszahlungsfähigkeit (Mindestkapital, Satzung
  6.6) stellt der Mitarbeiter fest, Teilauszahlungen sind möglich.
- Das Konto weist Anteile und Saldo getrennt aus; daraus ergeben sich die Buchungsarten
  (Eintritt, Rückzahlung, Umbuchung, Ausscheiden, Kürzung, Auszahlung, Verjährung, Storno).
- Rollen Admin, Buchhaltung, Buchhaltung lesend.
- Backend FastAPI, Frontend Vue 3 mit TypeScript, Event Sourcing wie in `purchase-prices`.
- Altdaten (Access) werden vollständig mit Historie über eigene Migrationsevents übernommen.

**Außerdem:** `CLAUDE` in `CLAUDE.md` umbenannt (nur mit Endung `.md` liest Claude Code die Datei
automatisch), `AGENTS` durch `AGENTS.md` mit den Arbeitsregeln ersetzt, dieses Logbuch angelegt. `README.md`
um eine Kurzfassung und Verweise auf die Dokumentationsdateien ergänzt.

## 2026-10-26 – Schritt 1a: Backend-Grundgerüst mit uv

**Was:** Python-Paket `coop_manager` unter `backend/` angelegt, mit einer Mini-App und einem
ersten Test.

**Befehle:**

```bash
uv init --package --name coop-manager --python 3.14 --author-from git backend
cd backend
uv add fastapi uvicorn              # Laufzeit-Abhängigkeiten
uv add --dev pytest ruff httpx2     # nur für die Entwicklung
uv run pytest                       # Tests ausführen
uv run ruff check                   # Code prüfen (Linter)
uv run ruff format                  # Code formatieren
uv run uvicorn coop_manager.app:app --reload   # Entwicklungsserver, http://localhost:8000/healthz
```

**Warum so:**

- `uv` verwaltet Python-Version, virtuelles Environment (`.venv`, nicht im Git) und
  Abhängigkeiten in einem Werkzeug. `uv run` führt einen Befehl im Environment aus, ohne dass es
  vorher aktiviert werden muss.
- `--package` erzeugt das *src-Layout* (`src/coop_manager/`): Das Paket wird installiert, und die
  Tests laufen gegen das installierte Paket, nicht gegen lose Dateien. Wie in `purchase-prices`.
- `pyproject.toml` enthält die Projektdaten, Abhängigkeiten (Mindestversionen) und die
  Einstellungen für pytest und ruff. `uv.lock` hält die exakten Versionen fest und gehört ins
  Git, damit Entwicklung und Container dieselben Pakete nutzen.
- `fastapi` ist das Web-Framework, `uvicorn` der Server, der es ausführt. `pydantic` (Prüfung
  von Daten anhand von Typangaben) und `starlette` (Unterbau von FastAPI) kommen automatisch mit.
- `httpx2` braucht der `TestClient` von FastAPI; Starlette meldet das ältere `httpx` als veraltet.
- ruff mit Zeilenlänge 120 und zusätzlich den Regeln `I` (Import-Sortierung), `UP` (moderne
  Python-Syntax) und `B` (typische Fehlerquellen).
- `app.py` enthält vorerst nur `GET /healthz`, das später auch Docker zur Zustandsprüfung nutzt.
  Die von uv erzeugte `backend/README.md` wurde entfernt, es gibt nur die README im Hauptordner.
