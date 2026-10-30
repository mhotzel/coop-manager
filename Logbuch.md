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

## 2026-10-26 – Schritt 1b: Frontend-Grundgerüst mit Vite, Vue 3 und TypeScript

**Was:** Vue-Projekt unter `frontend/` angelegt, Proxy zum Backend eingerichtet, eine
Probe-Komponente zeigt den Zustand von `/healthz` an.

**Befehle:**

```bash
npm create vue@latest -- --ts --bare frontend   # Startassistent: nur TypeScript, ohne Beispielcode
cd frontend
npm install          # Pakete nach node_modules/ (nicht im Git), Versionen in package-lock.json
npm run dev          # Entwicklungsserver, http://localhost:5173 (Backend parallel mit uvicorn starten)
npm run build        # Typprüfung (vue-tsc) und Build nach dist/ (nicht im Git)
```

**Warum so:**

- `create-vue` ist der offizielle Startassistent. Bewusst ohne Router, Pinia, ESLint und
  Testwerkzeuge; was davon gebraucht wird, kommt dazu, wenn es so weit ist (KISS).
- `package.json` entspricht `pyproject.toml`, `package-lock.json` entspricht `uv.lock` und gehört
  ins Git. `dependencies` landen im Browser (nur `vue`), `devDependencies` werden nur zum Bauen
  gebraucht (Vite, TypeScript, `vue-tsc`).
- Vite ist Entwicklungsserver und Build-Werkzeug zugleich: In der Entwicklung lädt es Änderungen
  sofort neu, für den Betrieb erzeugt es fertige Dateien in `dist/`, die später FastAPI ausliefert.
- Die drei `tsconfig*.json` steuern TypeScript: `tsconfig.app.json` für den Code im Browser,
  `tsconfig.node.json` für `vite.config.ts`, `tsconfig.json` verbindet beide. `env.d.ts` macht
  TypeScript mit Vite-Besonderheiten bekannt.
- Proxy in `vite.config.ts`: `/api` und `/healthz` gehen an uvicorn auf Port 8000. Der Browser
  spricht nur mit einer Adresse, daher kein CORS – wie später im Container, wo FastAPI beides
  ausliefert.
- `App.vue` ist eine *Single File Component*: `<script setup lang="ts">` (Logik in TypeScript),
  `<template>` (HTML mit `{{ }}` für Werte) und optional `<style>`. `ref()` macht einen Wert
  reaktiv, `onMounted` läuft, sobald die Komponente angezeigt wird. Das `interface Health`
  beschreibt die erwartete Form der Antwort.
- `index.html`: Sprache `de`, Titel `coop-manager`. Die erzeugte `frontend/README.md` wurde
  entfernt. `.vscode/extensions.json` empfiehlt in VS Code die Vue-Erweiterung.

## 2026-10-26 – Entwicklungsserver per SSH-Tunnel erreichen

**Was:** Keine Änderung am Projekt. Die Entwicklungsserver lauschen weiter nur auf 127.0.0.1,
der Zugriff vom Arbeitsrechner läuft über eine SSH-Portweiterleitung.

**Befehle (auf dem Arbeitsrechner):**

```bash
ssh -L 5173:localhost:5173 matthias@<rechner>                                # Vite
ssh -L 5173:localhost:5173 -L 8000:localhost:8000 matthias@<rechner>         # zusätzlich uvicorn, z. B. für /docs
```

Danach im lokalen Browser `http://localhost:5173` öffnen. Dauerhaft in `~/.ssh/config`:

```
Host coop
    HostName <rechner>
    LocalForward 5173 localhost:5173
    LocalForward 8000 localhost:8000
```

**Warum so:**

- Der Browser braucht nur Vite (Port 5173). Vite leitet `/api` und `/healthz` über den Proxy
  an uvicorn auf demselben Rechner weiter, daher muss uvicorn nicht von außen erreichbar sein.
- Der Tunnel ist verschlüsselt, die Server bleiben für das übrige Netz unsichtbar, und an der
  Firewall (firewalld) muss nichts freigegeben werden.
- Alternative wäre `host: true` in `vite.config.ts` (bzw. `npm run dev -- --host`) plus
  Freigabe des Ports in firewalld; dann wäre der Entwicklungsserver aber ohne Anmeldung für alle
  im Netz offen.

## 2026-10-30 – Schritt 1c: Events, Aggregate und Event Store

**Was:** Paket `coop_manager/eventsource/` aus `purchase-prices` übernommen, zunächst ohne
Projektionen, dazu `tests/test_eventsource.py`. Docstrings und Meldungen sind deutsch. Noch keine
Anbindung an FastAPI.

**Befehle:**

```bash
cd backend
uv run ruff format   # Code formatieren
uv run ruff check    # Code prüfen
uv run pytest        # Tests ausführen
```

**Warum so:**

- Event Sourcing speichert nicht den Zustand, sondern die Ereignisse. Der Zustand entsteht, indem
  ein Aggregat seine Events der Reihe nach abspielt (`from_events`).
- `events.py`: `Event` ist `frozen`, also unveränderlich. `uuid.uuid7()` erzeugt zeitlich
  sortierbare IDs, die Zeit ist UTC. Der Dekorator `@on("typ")` merkt sich an der Methode, für
  welche Eventtypen sie zuständig ist; `collect_handlers` sammelt das ein.
- `aggregate.py`: `_record()` erzeugt das Event und wendet es über denselben Handler an, der auch
  beim Laden läuft. So gibt es nur einen Weg, den Zustand zu ändern. `__init_subclass__` läuft
  automatisch, wenn eine Unterklasse definiert wird, und baut ihre Handler-Tabelle auf.
- `store.py`: `UNIQUE (subject, version)` ist die optimistische Sperre. Haben zwei Bearbeiter
  denselben Stand geladen, scheitert der zweite Speichervorgang mit `ConcurrencyError`.
- `transaction()` mit `BEGIN IMMEDIATE`: Die Events eines Vorgangs werden ganz oder gar nicht
  gespeichert. Die Verbindung läuft im Autocommit-Modus, Transaktionen sind also immer ausdrücklich.
- `position` nummeriert alle Events durch; daran orientieren sich die Projektionen in Schritt 1d.
- Der Ordner liegt nicht unter `core/` (Entscheidung in `Plan.md`).
- Gegenüber dem Vorbild kamen zwei Tests dazu: Ein Event kommt unverändert aus der Datenbank
  zurück, und ein Speichervorgang wird ganz oder gar nicht ausgeführt. Der Test für `read_all` ist
  ebenfalls neu, weil die Projektionen, die ihn im Vorbild mitprüfen, erst in Schritt 1d kommen.

## 2026-10-30 – Schritt 1d: Projektionen

**Was:** `eventsource/projection.py` aus `purchase-prices` übernommen (`Projector`, `Projections`),
fünf Tests ergänzt. Die Anbindung an FastAPI folgt als eigener Schritt 1e.

**Befehle:**

```bash
cd backend
uv run ruff format
uv run ruff check
uv run pytest
```

**Warum so:**

- Der Event Store taugt nicht zum Suchen. Darum gibt es Lesetabellen in `projections.sqlite`. Sie
  sind nur eine abgeleitete Kopie und lassen sich jederzeit aus den Events neu aufbauen.
- `Projector` ist wie ein Aggregat aufgebaut (`@on`, `__init_subclass__`), ignoriert aber Events
  ohne Handler, weil er sich nur für einen Teil der Events interessiert.
- Der Checkpoint merkt sich je Projektor die `position` des letzten verarbeiteten Events.
  Lesetabellen und Checkpoint ändern sich in einer Transaktion, passen also immer zusammen.
- `catch_up()` verarbeitet die neuen Events, `rebuild()` leert die Tabellen und spielt alles neu ab.
  Ein neuer Projektor hat keinen Checkpoint und beginnt deshalb von selbst bei null.
- Scheitert ein Projektor an einem Event, bleibt er dort stehen, bis der Fehler behoben ist, denn
  die Events werden streng der Reihe nach abgespielt. Die Events selbst gehen nicht verloren, aber
  die Lesetabellen veralten bis dahin. Projektoren dürfen also nicht an Eventdaten scheitern;
  fachliche Regeln wie die Eindeutigkeit prüft der Service, bevor das Event entsteht.
- Abweichung vom Vorbild: In `_project` steht eine eigene Variable `last_position`. Die Vorlage
  nutzte die Schleifenvariable nach der Schleife weiter, das meldet ruff bei uns als B007.

## 2026-10-30 – Schritt 1e: Anbindung an FastAPI

**Was:** `db.py` mit `Database`, `prepare()` und `get_db()`, `app.py` auf `create_app()` und Lifespan
umgestellt, `data/` in `.gitignore`, `tests/test_db.py`. Noch keine fachlichen Endpunkte.

**Befehle:**

```bash
cd backend
uv run ruff format
uv run ruff check
uv run pytest
uv run uvicorn coop_manager.app:app   # legt data/ mit beiden Datenbanken an
```

**Warum so:**

- `Depends(get_db)`: Der Endpunkt sagt nur, was er braucht, FastAPI ruft `get_db` auf. Der Teil vor
  dem `yield` läuft vor dem Endpunkt, der Teil danach hinterher, auch bei Fehlern. Das ersetzt
  `flask.g` aus dem Vorbild.
- Lifespan: Code, der einmal beim Start läuft. `prepare()` legt die Tabellen an und holt die
  Projektionen auf; eine gelöschte `projections.sqlite` entsteht so beim Start neu.
- `create_app()`: Tests bauen sich eine App mit temporärem Datenordner und eigenen Projektoren.
  `app = create_app()` am Dateiende hält `uvicorn coop_manager.app:app` lauffähig.
- `db.save()` speichert die Events und ruft danach `catch_up`, die Lesetabellen sind also sofort
  aktuell.
- `data/` ist ausgeschlossen, weil dort später echte Mitgliederdaten liegen.
- `CM_DATA_DIR` wird vorerst direkt gelesen, die Konfiguration folgt in Schritt 2.
- `check_same_thread=False`: Normale `def`-Endpunkte laufen im Thread-Pool, Dependency und Endpunkt
  können dabei in verschiedenen Threads landen. Sicher, weil jeder Request eine eigene Verbindung hat.

**Gelernt:** Der erste Test mit Requests nacheinander lief auch ohne das Flag durch, weil der Pool
dann denselben freien Thread wiederverwendet. Der Fehler (`sqlite3.ProgrammingError: SQLite objects
created in a thread can only be used in that same thread`) zeigt sich erst bei gleichzeitigen
Requests, deshalb gibt es `test_simultaneous_requests_work`. Eine solche Gegenprobe, bei der man die
Lösung kurz entfernt, zeigt, ob ein Test das Problem wirklich erkennt.

## 2026-10-30 – Unterschritte im Plan

**Was:** Die Unterschritte 1a–1e und die geplanten Unterschritte 2a–2d in `Plan.md` unter „Vorgehen“
eingetragen.

**Warum so:** Die Einteilung stand bisher nur im Logbuch und entstand erst beim Arbeiten. Im Plan
sieht man vorab, was als Nächstes kommt.
