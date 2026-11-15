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

## 2026-10-30 – Schritt 2a: Konfiguration

**Was:** `config.py` mit `Settings` und `load_settings()`, `create_app()` nimmt jetzt `Settings`
statt `data_dir`, die App hält sie in `app.state.settings`. Dazu `tests/test_config.py` und
`.env.example`.

**Befehle:**

```bash
cd backend
uv run ruff format
uv run ruff check
uv run pytest
uv run --env-file ../.env uvicorn coop_manager.app:app   # Start mit Werten aus .env
```

**Warum so:**

- Alle `CM_*`-Variablen werden an einer Stelle gelesen, der übrige Code kennt nur `Settings`.
- `Settings` ist eine `dataclass`: eine Klasse, deren `__init__` Python aus den Feldern erzeugt.
  `frozen=True` macht sie unveränderlich, wie die Events.
- Der Standardwert steht nur in `load_settings()`. Tests bauen sich `Settings(tmp_path)` und müssen
  keine Umgebungsvariablen setzen.
- Kein `pydantic-settings`: eine Abhängigkeit mehr für wenige gut lesbare Zeilen.
- Weitere Variablen kommen mit dem Schritt, der sie braucht, sonst stünden wirkungslose Einstellungen
  im Code.
- `monkeypatch` ist eine pytest-Hilfe: Sie ändert die Umgebung für einen Test und stellt sie danach
  wieder her.

**Gelernt:** `uvicorn --env-file` scheitert mit `No module named 'dotenv'`, weil es `python-dotenv`
braucht. `uv run --env-file` kann das selbst, ein zusätzliches Paket ist nicht nötig.

## 2026-10-30 – Schritt 2b: Logging als JSON-Zeilen

**Was:** `logs.py` aus `purchase-prices` übernommen (`JsonFormatter`, `init_logging`), Einstellung
`CM_LOG_LEVEL`, Logzeile „app started“ beim Start, `tests/test_logs.py`. In `Plan.md` steht unter
„Offene Punkte“, dass Suchbegriffe nicht über die URL ins Access-Log gelangen dürfen.

**Befehle:**

```bash
cd backend
uv run ruff format
uv run ruff check
uv run pytest
uv run uvicorn coop_manager.app:app   # echter Start: jede Zeile ist JSON
```

**Warum so:**

- Logs gehen nach stdout, Docker sammelt sie ein (`docker logs`). Die App verwaltet keine Dateien.
  JSON-Zeilen lassen sich maschinell filtern.
- `logging` trennt Aufruf und Ausgabe: Der Code ruft `log.info(...)` auf, der Handler bestimmt das
  Ziel, der Formatter die Form. Ein Modul braucht nur `log = logging.getLogger(__name__)`.
- Logger bilden über ihre Namen einen Baum: `coop_manager.app` gibt seine Zeilen an `coop_manager`
  weiter, dort hängt der Handler. Werte aus `extra=` landen als `LogRecord`-Attribute im Record, der
  Formatter macht daraus eigene JSON-Felder.
- Abweichungen vom Vorbild: uvicorn bekommt denselben Handler, damit `docker logs` nur ein Format
  zeigt (im Vorbild schreibt gunicorn Text). Das Level kommt aus `CM_LOG_LEVEL`, weil FastAPI kein
  `app.debug` wie Flask hat. `handlers = [handler]` ersetzt die Handler, mehrfache `create_app()`
  in Tests erzeugen so keine doppelten Zeilen.
- `create_app()` läuft erst, nachdem uvicorn sein eigenes Logging eingerichtet hat. Darum bleiben
  unsere Handler bestehen.

**Gelernt:** Ein Logger ohne eigenes Level erbt es von oben, am Ende vom Root-Logger mit `WARNING`.
Das Level `INFO` für `uvicorn` setzt erst der echte Start. In einem Test ohne Server wird
`info` dort also verworfen.

## 2026-11-13 – Docstrings ergänzt

**Was:** Alle Klassen auf Docstrings geprüft. Ergänzt bei `UnknownEventError`, `EventStore`, den
Test-Projektionen `NoteList`, `PartyList` und `EventCounter` sowie bei den Methoden von
`Projections` (`create_schema`, `catch_up`, `_project`, `_checkpoint`), `EventStore` und `Projector`.

**Befehle:**

```bash
# Klassen ohne Docstring finden: ast liest den Code, ohne ihn auszuführen
git ls-files '*.py' | xargs python3 -c '
import ast, sys
for f in sys.argv[1:]:
    for n in ast.walk(ast.parse(open(f).read())):
        if isinstance(n, ast.ClassDef) and not ast.get_docstring(n):
            print(f"{f}:{n.lineno}", n.name)
'
cd backend
uv run ruff format
uv run ruff check
uv run pytest
```

**Warum so:**

- Ein Docstring ist der erste String im Rumpf einer Klasse oder Funktion. Python speichert ihn in
  `__doc__`, `help()` und Editoren zeigen ihn an. Ein Kommentar mit `#` landet dagegen nicht dort.
- Bei einer Klasse, die nur aus einem Docstring besteht, wie `UnknownEventError`, ist `pass` nicht
  mehr nötig: Der String ist schon ein gültiger Rumpf.

## 2026-11-13 – Auslöser (`actor`) im Plan festgehalten

**Was:** In `Plan.md` unter „Architektur“ festgehalten, dass jedes Event seinen Auslöser speichert.
Den Docstring von `EventStore.append` präzisiert: `actor` ersetzt den Wert nur, wenn er angegeben ist.

**Warum so:**

- Ein Event sagt was, wem und wann. `actor` ergänzt das Wer. Weil Events nie geändert werden,
  ergibt das eine lückenlose Spur aller Änderungen.
- Das Aggregate erzeugt Events ohne `actor`. Den angemeldeten Benutzer kennt erst der Endpunkt, der
  speichert. Die Fachlogik bleibt so frei von Anmeldedetails.
- `Event` ist `frozen`. `dataclasses.replace` erzeugt deshalb eine Kopie mit dem neuen `actor`,
  statt das Event zu ändern.

## 2026-11-14 – Docstrings für die übrigen Methoden

**Was:** Docstrings für die Methoden von `Aggregate`, `Database` und `JsonFormatter.format`
ergänzt, dazu in den Tests für `Note.write`, `Party.register`, `Party.rename` und
`EventCounter.reset`. Außerdem `# type: ignore` in `on()` (`events.py`): Der Typprüfer kennt kein
Attribut `_handles_events` an einer Funktion, Python erlaubt es aber.

**Befehle:**

```bash
# Methoden ohne Docstring finden (wie oben, nur für Funktionen in Klassen)
git ls-files '*.py' | xargs python3 -c '
import ast, sys
for f in sys.argv[1:]:
    for c in ast.walk(ast.parse(open(f).read())):
        if isinstance(c, ast.ClassDef):
            for n in c.body:
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and not ast.get_docstring(n):
                    print(f"{f}:{n.lineno}", c.name + "." + n.name)
'
cd backend
uv run ruff format
uv run ruff check
uv run pytest
```

**Warum so:**

- Ein `__init__`, das nur Parameter in Attribute schreibt (`EventStore`, `Projections`), bekommt
  keinen Docstring: Was es tut, sieht man auf einen Blick.
- Die mit `@on(...)` markierten Handler bleiben ebenfalls ohne Docstring, denn der Decorator sagt
  schon, auf welches Event sie reagieren.
- `ruff format` hat vor dem `#` des Kommentars zwei Leerzeichen gesetzt, wie es PEP 8 für
  Kommentare am Zeilenende vorsieht.

**Nachtrag – Typfehler in der Fixture `store`:** VS Code zeigte in `tests/test_eventsource.py`
zwei Fehler an. Sie kamen nicht von ruff, sondern von Pylance, dem Typprüfer in VS Code, der auf
pyright aufbaut. Nachgeprüft und behoben:

```bash
cd backend
uv run --with pyright pyright src tests   # pyright einmalig mitladen, ohne es zu installieren
```

- Die Fixture `store` enthält `yield`. Damit ist sie eine Generatorfunktion: Ihr Aufruf liefert
  keinen `EventStore`, sondern einen Generator, der einen `EventStore` liefert. pytest holt den Wert
  bis zum `yield`, führt den Test aus und lässt danach den Rest zum Aufräumen laufen.
- Die Annahme `-> EventStore` war deshalb falsch. Richtig ist `-> Iterator[EventStore]`
  (aus `collections.abc`), wie bei `get_db` in `db.py`.
- `ruff check` prüft Stil und typische Fehlermuster, aber keine Typen. Dafür braucht es einen
  Typprüfer wie pyright oder mypy.

## 2026-11-14 – pyright als Typprüfer aufgenommen

**Was:** `pyright` als Entwicklungsabhängigkeit hinzugefügt und in `pyproject.toml` eingestellt.
In `Plan.md` unter „Werkzeuge“ eingetragen.

**Befehle:**

```bash
cd backend
uv add --dev pyright      # trägt pyright in die Gruppe dev ein und aktualisiert uv.lock
uv run pyright            # prüft src und tests
```

In `pyproject.toml`:

```toml
[tool.pyright]
include = ["src", "tests"]
```

**Warum so:**

- Ein Linter wie `ruff` sucht nach Stilfragen und typischen Fehlermustern, prüft aber nicht, ob die
  Typannahmen zusammenpassen. Das macht ein Typprüfer wie `pyright`. Er hat zum Beispiel die falsche
  Annahme `-> EventStore` an der Fixture `store` gefunden (siehe Eintrag davor).
- Pylance in VS Code baut auf pyright auf. Mit dem Modus `standard`, der Voreinstellung, meldet die
  Kommandozeile dasselbe wie der Editor. `strict` würde z. B. jede Fixture ohne Typannahme bemängeln.
- Als Abhängigkeit in `uv.lock` hat jeder, der das Projekt mit `uv sync` einrichtet, dieselbe Version.
- Das Python-Paket `pyright` ist nur eine Hülle: Beim ersten Aufruf lädt es das eigentliche
  Programm (Node.js) herunter, dafür kommt `nodeenv` mit.

Nach jedem Schritt laufen jetzt: `ruff format`, `ruff check`, `pyright`, `pytest`.

## 2026-11-14 – uv_build-Version an uv 0.13 angepasst

**Was:** In `backend/pyproject.toml` die Grenzen des Build-Backends angehoben:
`uv_build>=0.12.24,<0.13.0` → `uv_build>=0.13.5,<0.14.0`. Damit ist die Warnung
„`build_system.requires` … does not contain the current uv version“ weg.

**Befehle:**

```bash
cd backend
uv sync --reinstall-package coop-manager   # Projekt neu bauen, um die Warnung zu prüfen
```

**Warum so:**

- `uv_build` ist das Build-Backend: Es macht aus `src/coop_manager` ein installierbares Paket. Das
  passiert bei jedem `uv sync`, weil das Projekt selbst mitinstalliert wird.
- Das Backend steckt in uv selbst. Liegt die eigene Version in den Grenzen, baut uv direkt damit.
  Sonst lädt es ein passendes älteres `uv_build` herunter und warnt. Das geht, ist aber ein Umweg.
- Die Obergrenze `<0.14.0` bleibt, weil eine neue Hauptversion anders bauen könnte. `uv init` trägt
  sie aus demselben Grund ein.
- `uv.lock` ändert sich nicht: Das Build-Backend gehört nicht zu den Abhängigkeiten des Projekts.

## 2026-11-15 – Python 3.14 über uv installiert

**Was:** Die virtuelle Umgebung in `backend/.venv` zeigte auf `/usr/bin/python3.14`. Das gab es
nach dem Upgrade auf Fedora 45 nicht mehr, dort ist nur noch `python3.15` installiert. `uv run`
brach deshalb ab mit „No interpreter found for Python 3.14“.

**Befehle:**

```bash
cd backend
uv python install 3.14    # lädt ein eigenes Python 3.14 nach ~/.local/share/uv/python
uv sync                   # baut .venv mit diesem Python neu auf
```

**Warum so:**

- `.python-version` legt das Projekt auf 3.14 fest. Ein von uv verwaltetes Python hängt nicht davon
  ab, welche Version die Distribution gerade mitbringt. Ein Systemupgrade bricht die Umgebung so
  nicht mehr.
- Die Alternative wäre gewesen, `.python-version` auf 3.15 zu stellen. Damit würde aber das
  Betriebssystem bestimmen, mit welcher Version das Projekt läuft, und nicht das Projekt selbst.
- Am Repository ändert sich nichts außer diesem Eintrag: `.venv` ist nicht eingecheckt, und
  `uv.lock` bleibt gleich.

## 2026-11-15 – Security-Header (Schritt 2c)

**Was:** Neues Modul `backend/src/coop_manager/security.py`. Es setzt bei jeder Antwort feste
Security-Header und bei HTTPS zusätzlich HSTS. Dazu kommt die neue Einstellung
`CM_TRUSTED_PROXIES` in `config.py` und `.env.example`. Tests stehen in `tests/test_security.py`
und `tests/test_config.py`.

**Befehle:**

```bash
cd backend
uv run ruff format && uv run ruff check && uv run pyright && uv run pytest
```

**Warum so:**

- **Die Header** stammen aus `purchase-prices`:
  - `X-Content-Type-Options: nosniff`: Der Browser rät keinen Dateityp.
  - `X-Frame-Options: DENY` und `frame-ancestors 'none'`: Die Seite darf nicht in einem fremden
    Rahmen erscheinen. Das schützt vor Clickjacking.
  - `Referrer-Policy: same-origin`: Die URL geht nicht an fremde Seiten.
  - `Permissions-Policy`: Kamera, Mikrofon usw. sind aus.
  - `Content-Security-Policy` (CSP): Skripte, Styles und Bilder dürfen nur vom eigenen Server
    kommen. Eingeschleuster Code von außen läuft damit nicht.
- **Middleware:** Eine Funktion, die um jede Anfrage herum läuft. `app.middleware("http")`
  registriert sie. Sie ruft mit `await call_next(request)` den eigentlichen Endpunkt auf und ergänzt
  danach die Header der Antwort. `setdefault` überschreibt dabei nichts, was ein Endpunkt bewusst
  selbst gesetzt hat.
- **HSTS** (`Strict-Transport-Security`) weist den Browser an, die Seite ein Jahr lang nur noch per
  HTTPS aufzurufen. Der Header wird nur gesendet, wenn die Anfrage per HTTPS kam.
- **Reverse Proxy:** Auf der Synology nimmt der DSM-Proxy HTTPS an und reicht die Anfrage per HTTP
  an die App weiter. Dass es eigentlich HTTPS war, sagt er im Header `X-Forwarded-Proto: https`.
  Diesen Header könnte aber jeder Client mitschicken. Darum gilt er nur, wenn die Anfrage von einer
  Adresse aus `CM_TRUSTED_PROXIES` kommt.
- **Keine eigene Klasse dafür:** In `purchase-prices` gibt es `TrustedProxyFix`, weil Flask so etwas
  nicht mitbringt. uvicorn hat `ProxyHeadersMiddleware` mit genau dieser Prüfung schon eingebaut.
  Wir hängen sie nur ein, wenn die Liste nicht leer ist.
- **Reihenfolge:** Bei Starlette liegt die zuletzt hinzugefügte Middleware außen und läuft zuerst.
  Deshalb wird die Proxy-Middleware nach der Header-Middleware hinzugefügt: Sie muss das Schema auf
  `https` umstellen, bevor die Header-Middleware nachsieht.
- **Tests:** `TestClient(app, client=("10.0.0.2", 50000))` gibt eine erfundene Absenderadresse vor.
  So lässt sich prüfen, dass `X-Forwarded-Proto` von einer fremden Adresse ignoriert wird.
- **CSP bleibt streng:** Die Swagger-Oberfläche unter `/docs` lädt ihre Skripte von einem fremden
  Server und funktioniert deshalb nicht mehr. Eine Lücke in der CSP nur für die Doku lohnt sich
  nicht. `/docs` und `/redoc` werden im Betrieb abgeschaltet (Schritt 8), `/openapi.json`
  funktioniert weiter.
- **Für später (Schritt 8):** Beim Start über die Kommandozeile hängt uvicorn selbst schon eine
  `ProxyHeadersMiddleware` ein, die standardmäßig nur `127.0.0.1` vertraut. Im Container prüfen,
  dass sie sich nicht mit unserer in die Quere kommt, z. B. mit `--no-proxy-headers`.

## 2026-11-15 – VS Code findet die virtuelle Umgebung von selbst

**Was:** Neue Datei `.vscode/settings.json` mit
`"python.defaultInterpreterPath": "${workspaceFolder}/backend/.venv/bin/python"`.

**Warum so:**

- Nachdem `uv sync` die Umgebung `backend/.venv` neu aufgebaut hatte, meldete VS Code in
  `tests/test_eventsource.py`, dass `import pytest` und `import coop_manager…` nicht aufgelöst werden
  können. VS Code hatte sich noch den alten Interpreter gemerkt. Dieser Fehler kam nur von Pylance:
  `pyright` auf der Kommandozeile nutzt `uv run` und damit immer die richtige Umgebung.
- Die Umgebung liegt in `backend/` und nicht direkt im geöffneten Ordner. Deshalb findet VS Code
  sie nicht immer von selbst. Die Einstellung sagt es ihm ausdrücklich.
- `${workspaceFolder}` ist der in VS Code geöffnete Projektordner. So passt der Pfad auf jedem
  Rechner, auf dem das Repository liegt.
- Die Datei wird eingecheckt, weil sie nur den Projektaufbau beschreibt und keine persönlichen
  Vorlieben enthält.

## 2026-11-15 – Generator statt Iterator bei `@contextmanager`

**Was:** VS Code hat `@asynccontextmanager` in `app.py` als veraltet durchgestrichen. Korrigiert:

- `app.py`: `lifespan(...) -> AsyncIterator[None]` → `-> AsyncGenerator[None]`
- `eventsource/store.py`: `transaction(...) -> Iterator[sqlite3.Connection]` →
  `-> Generator[sqlite3.Connection]`
- `pyproject.toml`: unter `[tool.pyright]` neu `reportDeprecated = "warning"`

**Befehle:**

```bash
cd backend
uv run ruff format && uv run ruff check && uv run pyright && uv run pytest
```

**Warum so:**

- Veraltet ist nicht der Decorator, sondern die Typannahme `Iterator` darunter. Pylance bringt die
  Typbeschreibungen der Standardbibliothek mit (typeshed). Dort ist die Variante mit
  `AsyncIterator` bzw. `Iterator` als `@deprecated` markiert.
- Eine Funktion mit `yield` ist ein Generator. Ein Iterator kann nur den nächsten Wert liefern. Ein
  Generator lässt sich außerdem schließen (`close()`), und man kann einen Fehler an der Stelle des
  `yield` in ihn hineinwerfen (`throw()`). Genau das nutzt `@contextmanager`: Tritt im `with`-Block
  ein Fehler auf, kommt er an der Stelle des `yield` in der Funktion an, und sie kann aufräumen,
  z. B. ein Rollback machen. `Generator` beschreibt das also genauer.
- Seit Python 3.13 haben die beiden hinteren Typparameter von `Generator[Yield, Send, Return]`
  Standardwerte. Deshalb reicht `Generator[X]`.
- `get_db` in `db.py`, `read_all` im Event Store und die Fixture `store` behalten `Iterator`. Sie
  stehen nicht unter `@contextmanager`, dort gibt es diese Regel nicht.
- Im Modus `standard` meldet `pyright` Veraltetes nicht. Mit `reportDeprecated = "warning"` fällt es
  jetzt auch auf der Kommandozeile auf, nicht nur in VS Code bei geöffneter Datei. Zur Probe die
  alte Schreibweise kurz zurückgesetzt: Die Warnung erschien.

## 2026-11-15 – Layout und Theme im Frontend (Schritt 2d)

**Was:** Das Seitengerüst und das Farbschema aus `purchase-prices` stehen jetzt in der Vue-App.

- `frontend/src/assets/css/colorscheme-dorfladen.css` und `style.css` sind unverändert aus
  `purchase-prices` kopiert, `frontend/src/assets/img/dlslogo.png` ebenso.
- `main.ts` importiert erst das Farbschema, dann `style.css`.
- `App.vue` übernimmt das Gerüst aus `base.html.j2`: Kopfzeile mit Logo und „Mitgliederverwaltung“,
  Aktionsleiste (noch leer, dort kommen in Schritt 3 Benutzername und Abmelden hin), Menü,
  Inhaltsbereich mit einer Willkommenskarte und Fußzeile mit dem Backend-Status.
- In `index.html` lautet der Titel jetzt „Mitgliederverwaltung“.

**Befehle:**

```bash
cd frontend
npm run build                       # Typprüfung (vue-tsc) und Build
npx vite preview --port 4179        # gebaute App lokal ausliefern, zum Anschauen
firefox --headless --window-size 1200,700 --screenshot desktop.png http://localhost:4179/
```

**Warum so:**

- **Ohne Komponentenbibliothek, aber mit fertigem CSS:** Die Entscheidung steht in `Plan.md`. Beide
  Anwendungen des Dorfladens sehen so gleich aus.
- **CSS-Variablen:** `colorscheme-dorfladen.css` setzt unter `:root` nur Variablen wie
  `--primary-color`. `style.css` verwendet sie mit `var(--primary-color)`. Wer die Farben ändern
  will, ändert also nur die erste Datei. Deshalb muss sie zuerst geladen werden.
- **CSS per `import` in `main.ts`:** Vite erkennt das und bündelt das CSS beim Bauen in eine eigene
  Datei unter `dist/assets/`. Sie kommt vom eigenen Server und passt damit zur strengen CSP aus
  Schritt 2c.
- **Logo per `import logoUrl from './assets/img/dlslogo.png'`:** Vite liefert dafür die URL der
  gebauten Datei. Die enthält einen Hash im Namen, z. B. `dlslogo-DR66A_zF.png`. Ändert sich das
  Bild, ändert sich der Name, und kein Browser zeigt mehr die alte Fassung aus dem Cache.
  `:src="logoUrl"` bindet den Wert an das Attribut. Der Doppelpunkt ist die Kurzform von `v-bind`.
- **`v-for`:** Die Menüeinträge stehen als TypeScript-Liste `menuEntries` im Code, die Vorlage
  erzeugt daraus mit `v-for` die Links. `:key` gibt jedem Eintrag eine feste Kennung, damit Vue
  beim Neuzeichnen weiß, welcher Eintrag welcher ist. Die Einträge haben noch kein Ziel: Der Vue
  Router kommt mit der ersten echten Seite (Login, Schritt 3).
- **Menü auf dem Handy:** `<details>` ist ein HTML-Element, das sich per Klick auf `<summary>`
  auf- und zuklappt. Breit soll es immer offen sein und als Seitenleiste dienen, auf dem Handy
  geschlossen als „☰ Menü“. `purchase-prices` schaltet das mit `layout.js` über einen direkten
  Zugriff auf das DOM. In Vue gibt es dafür den reaktiven Wert `menuOpen`, gebunden mit
  `:open="menuOpen"`. `window.matchMedia(...)` beobachtet die Fensterbreite, bei einer Änderung
  setzt `syncMenu` den Wert neu. `onUnmounted` meldet den Beobachter wieder ab.
- **Geprüft** mit Screenshots aus Firefox ohne Fenster (`--headless`) in Desktop- und
  Handybreite.

## 2026-11-15 – Aggregat `User` (Schritt 3a)

**Was:**

- `Plan.md`: Schritt 3 ist in die Unterschritte 3a bis 3f aufgeteilt. Neu eingetragen sind die
  Entscheidungen zu Argon2 über `pwdlib`, zur Session über die `SessionMiddleware` und dazu, dass der
  Admin Kennwörter neu setzen darf.
- Neue Abhängigkeit `pwdlib[argon2]`.
- `coop_manager/core/errors.py`: `DomainError` für verletzte fachliche Regeln.
- `coop_manager/users/domain.py`: Aggregat `User` mit den Prüfungen für Benutzername, Name,
  Kennwort und Rolle.
- `tests/test_users_domain.py`.

**Befehle:**

```bash
cd backend
uv add "pwdlib[argon2]"     # [argon2] ist ein „Extra“: lädt zusätzlich argon2-cffi mit
uv run ruff format && uv run ruff check && uv run pyright && uv run pytest
```

**Events:**

| Event | Daten |
|---|---|
| `user.registered` | `username`, `full_name`, `password_hash`, `role` |
| `user.name-changed` | `full_name` |
| `user.password-changed` | `password_hash` |
| `user.role-changed` | `role` |
| `user.deactivated`, `user.reactivated`, `user.terminated` | keine |

**Warum so:**

- **Vorbild ist `purchase-prices`**, mit einem Unterschied: Bei uns hat ein Benutzer genau eine
  Rolle. Statt `role-added` und `role-removed` gibt es deshalb `role-changed`. Die Rolle wird schon
  beim Anlegen übergeben, weil ein Benutzer ohne Rolle sinnlos wäre.
- **Die Namen der Felder in den Events** folgen dem Code: `full_name` statt `fullname` wie in
  `purchase-prices`.
- **Kennwort-Hash:** Gespeichert wird nur der Hash, nie das Kennwort selbst. Argon2 ist absichtlich
  langsam und braucht viel Speicher (64 MB). Wer die Datenbank stiehlt, kann so nicht Milliarden
  Kennwörter pro Sekunde durchprobieren. Jeder Hash enthält ein zufälliges Salz, darum ergibt
  dasselbe Kennwort jedes Mal einen anderen Hash. Der Hash beginnt mit
  `$argon2id$v=19$m=65536,t=3,p=4$`. Darin stehen Verfahren und Einstellungen, damit `verify` später
  weiß, wie es prüfen muss.
- **`hash_password` und `verify_password` sind eigene Funktionen**, nicht nur Methoden. Der Login in
  3b prüft das Kennwort gegen den Hash aus der Projektion, ohne das Aggregat zu laden.
- **Normalisieren vor dem Prüfen:** `normalize_username` schreibt klein und entfernt Leerzeichen am
  Rand, damit „Erika“ und „erika“ derselbe Benutzer sind. `normalize_full_name` bringt Umlaute in
  eine einheitliche Unicode-Form (NFC). Ein „ä“ kann sonst als ein Zeichen oder als „a“ plus
  Trema gespeichert sein, und Vergleiche gehen schief.
- **Ob ein Benutzername schon vergeben ist,** kann das Aggregat nicht wissen. Es kennt nur sich
  selbst. Das prüft in 3b der Service anhand der Projektion.
- **`terminate` (löschen) geht nur bei deaktivierten Benutzern:** zwei Schritte als Schutz vor
  versehentlichem Löschen. Die Events bleiben im Event Store, damit der `actor` alter Events
  zuzuordnen bleibt.
- **Tests:** `reloaded(user)` baut den Benutzer mit `User.from_events(...)` aus seinen Events neu
  auf. So prüft jeder Test auch, dass die Handler mit `@on` den Zustand richtig wiederherstellen,
  nicht nur, dass die Methode das Objekt geändert hat. Mit `pytest.mark.parametrize` läuft derselbe
  Test mit mehreren ungültigen Eingaben.

## 2026-11-15 – Projektion, Services und `create-admin` (Schritt 3b)

**Was:**

- `users/projections.py`: Der Projektor `UserList` hält die Tabelle `users` aktuell. Dazu die
  Abfragen `get_user`, `find_by_username` und `list_users`, die `UserView`-Objekte liefern.
- `users/login_attempts.py`: Die Login-Sperre (`LoginAttempts`), übernommen aus `purchase-prices`.
- `users/services.py`: `register_user`, die Änderungen (`change_full_name`, `change_password`,
  `change_role`, `deactivate`, `reactivate`, `terminate`) und `authenticate`.
- `core/errors.py`: Neu ist `NotFoundError`.
- `db.prepare()` hat einen neuen Parameter `schemas` für Tabellen, die nicht aus Events entstehen.
- `app.py`: In `PROJECTORS` und `SCHEMAS` tragen sich die Module ein.
- `config.py` und `.env.example`: Neu sind `CM_LOGIN_MAX_ATTEMPTS` (3) und
  `CM_LOGIN_LOCKOUT_SECONDS` (900).
- `cli.py`: Der Befehl `create-admin`. In `pyproject.toml` zeigt `coop-manager` jetzt auf
  `coop_manager.cli:main` statt auf das „Hello“ aus `uv init`.
- Tests: `tests/test_users_services.py` und `tests/test_cli.py`.

**Befehle:**

```bash
cd backend
uv sync                                      # Einstiegspunkt coop-manager neu installieren
uv run coop-manager --help
uv run --env-file ../.env coop-manager create-admin --username admin --full-name "Erika Muster"
uv run ruff format && uv run ruff check && uv run pyright && uv run pytest
```

**Warum so:**

- **Eine Rolle als Spalte:** `purchase-prices` braucht für mehrere Rollen eine zweite Tabelle
  `user_roles`. Bei uns gibt es genau eine Rolle, also reicht eine Spalte `role` in `users`.
- **Gelöschte Benutzer verschwinden aus der Projektion,** im Event Store bleiben sie erhalten. So ist
  der Benutzername wieder frei, und die Liste zeigt nur, wer noch existiert.
- **Die Datenbank als Parameter:** In Flask holt `purchase-prices` die Datenbank aus einem globalen
  Objekt (`db.get_read_db()`). Unsere Services bekommen `db: Database` übergeben. In der API liefert
  sie `Depends(get_db)`, in der CLI und in den Tests legt man sie selbst an. Man sieht so jeder
  Funktion an, womit sie arbeitet.
- **`_change(...)`** fasst zusammen, was jede Änderung braucht: Benutzer laden, prüfen, ob es ihn
  gibt, Methode aufrufen, speichern, loggen. Die einzelnen Services übergeben nur die Methode, z. B.
  `User.deactivate` oder `lambda user: user.change_role(role)`. Ein `lambda` ist eine kleine
  namenlose Funktion.
- **Regeln, die das Aggregat nicht prüfen kann, prüft der Service:** Ist der Benutzername noch frei?
  Will sich jemand selbst deaktivieren, löschen oder die Admin-Rolle entziehen? Dafür muss man
  andere Benutzer bzw. den `actor` kennen. Damit bleibt immer mindestens ein aktiver Admin übrig.
- **`authenticate` verrät nichts:**
  - Ein unbekannter oder deaktivierter Benutzer bekommt dieselbe Antwort (`None`) wie ein falsches
    Kennwort.
  - Für ihn wird trotzdem ein Hash geprüft (`_dummy_hash`), damit die Antwort gleich lange dauert.
    Sonst könnte man an der Antwortzeit messen, ob ein Name existiert.
  - Die Fehlversuche zählen auch für unbekannte Namen, damit die Sperre selbst nichts verrät.
  - `@cache` berechnet den Dummy-Hash nur einmal.
- **Login-Versuche nicht als Events:** Fehlversuche sind kein fachliches Ereignis. Sie liegen deshalb
  in einer eigenen Tabelle in `projections.sqlite`, die `prepare()` über `SCHEMAS` anlegt. Beim
  Neuaufbau der Projektionen bleibt sie unberührt.
- **CLI mit `argparse`:** Das kommt aus der Standardbibliothek und braucht kein zusätzliches Paket.
  `add_subparsers` macht aus `create-admin` einen Unterbefehl, später kommen z. B. `backup` oder
  `rebuild` dazu. `getpass.getpass` liest das Kennwort, ohne es auf dem Bildschirm anzuzeigen. Es
  wird nicht als Argument übergeben, sonst stünde es in der Shell-History. `sys.exit("Text")` gibt
  die Meldung aus und beendet mit Fehlercode 1.
- **Tests:**
  - Eine Fixture `db` legt für jeden Test frische Datenbanken in `tmp_path` an.
  - Die Sperrzeit wird nicht abgewartet: Der Test setzt `last_attempt` einfach in die Vergangenheit.
  - In den CLI-Tests ersetzt `monkeypatch` die Funktion `getpass` durch vorbereitete Antworten und
    setzt `sys.argv`, als hätte man den Befehl getippt.
  - `capsys` fängt die Ausgabe ab.

## 2026-11-15 – Login über die API (Schritt 3c)

**Was:**

- Neue Abhängigkeit `itsdangerous`. Die `SessionMiddleware` von Starlette braucht sie zum Signieren.
- `app.py`:
  - `init_session` richtet die `SessionMiddleware` ein.
  - `init_error_handlers` macht aus `DomainError` eine Antwort 400 und aus `NotFoundError` eine
    Antwort 404, jeweils mit `{"detail": ...}`.
  - Der Router aus `users/api.py` wird eingebunden.
- `config.py` und `.env.example`: Neu sind `CM_SECRET_KEY`, `CM_SESSION_TIMEOUT` (1800) und
  `CM_SESSION_COOKIE_SECURE` (true).
- `users/access.py`: Die Dependencies `current_user` und `require_role(...)` und die Liste
  `PUBLIC_PATHS`.
- `users/schemas.py`: Die Pydantic-Modelle `LoginRequest`, `UserOut` und `Me`.
- `users/api.py`: `POST /api/login`, `POST /api/logout` und `GET /api/me`.
- Tests: `tests/test_users_api.py`, `tests/test_access.py` und zwei Tests in `test_config.py`.

**Befehle:**

```bash
cd backend
uv add itsdangerous
uv run ruff format && uv run ruff check && uv run pyright && uv run pytest
```

**Warum so:**

- **Session im Cookie:** Die `SessionMiddleware` legt die Session-Daten (`user_id`, `csrf_token`)
  ins Cookie selbst, mit einer Signatur aus `CM_SECRET_KEY`. Lesen könnte man sie (Base64), fälschen
  aber nicht, und darin steht nichts Geheimes. Der Server muss sich dafür nichts merken.
- **Das Cookie:**
  - `HttpOnly`: JavaScript kommt nicht an das Cookie heran, ein eingeschleustes Skript kann es also
    nicht stehlen.
  - `Secure`: Das Cookie geht nur über HTTPS. Browser behandeln `http://localhost` als sicher, darum
    klappt das auch in der Entwicklung.
  - `SameSite=Lax`: Bei Anfragen, die von fremden Seiten ausgelöst werden, schickt der Browser das
    Cookie nur bei normalen Seitenaufrufen mit, nicht bei POST.
  - `Max-Age=1800`: Starlette setzt das Cookie bei jeder Antwort neu. Darum läuft die Session erst
    nach 30 Minuten **ohne** Anfrage ab.
- **Fehlender Schlüssel:** Die App erzeugt mit `secrets.token_hex(32)` einen zufälligen Schlüssel.
  Das ist sicher, nach einem Neustart sind aber alle abgemeldet. Darum steht eine Warnung im Log.
- **CSRF:** Eine fremde Seite kann den Browser dazu bringen, eine Anfrage an unsere App zu
  schicken, und der Browser hängt das Cookie an. Deshalb verlangt `current_user` bei POST, PUT,
  PATCH und DELETE zusätzlich den Header `X-CSRF-Token` mit dem Token aus der Session. Die fremde
  Seite kennt das Token nicht. `secrets.compare_digest` vergleicht in immer gleicher Zeit, so lässt
  sich das Token nicht über die Antwortzeit erraten.
- **`current_user` liest bei jeder Anfrage aus der Projektion:** Wird jemand deaktiviert, ist er
  bei der nächsten Anfrage draußen, nicht erst, wenn seine Session abläuft.
- **`require_role(ADMIN)`** ist eine Funktion, die eine Dependency *erzeugt*. Die innere Funktion
  `check` merkt sich die übergebenen Rollen (eine „Closure“) und hängt selbst an `current_user`.
  Verwendet wird sie so:
  `user: Annotated[UserView, Depends(require_role(ADMIN))]`.
- **`users/access.py` statt `core/access.py`:** Die Prüfung braucht die Benutzer-Projektion. `core`
  soll aber von keinem Fachmodul abhängen.
- **Der Kennwort-Hash verlässt das Backend nie:** Die API liefert `UserOut`, nicht `UserView`.
  FastAPI prüft und filtert die Antwort anhand der Typangabe `-> Me`. `max_length` in
  `LoginRequest` verhindert, dass jemand riesige Texte durch das absichtlich langsame Argon2
  schickt.
- **Sperre als 429** („Too Many Requests“) statt 401. Das Frontend kann so eine passende Meldung
  zeigen. Bei unbekanntem Namen und bei falschem Kennwort lautet die Meldung gleich.
- **„Standard ist verweigert“ per Test:**
  - In FastAPI muss jeder Endpunkt seine Prüfung selbst angeben. Vergisst man sie, ist er offen.
    Darum geht `test_access.py` alle Routen durch und verlangt `current_user`, auch indirekt über
    `require_role`, außer für die Pfade in `PUBLIC_PATHS`.
  - Stolperstein: Seit FastAPI 0.16x stehen eingebundene Router in `app.routes` nur als ein Eintrag
    (`_IncludedRouter`). Der erste Entwurf des Tests sah `/api/login` usw. gar nicht und wäre immer
    grün gewesen. Aufgefallen ist das, weil ein zweiter Test prüft, dass die erwarteten Pfade
    gefunden werden. Die Lösung ist `fastapi.routing.iter_route_contexts`.
  - Zur Probe kam kurz eine Route ohne Prüfung dazu, und der Test schlug an.

**Nachtrag – Zeilenlänge prüfen:** In `pyproject.toml` ist unter `[tool.ruff.lint]` jetzt auch die
Regel `E501` eingeschaltet. `line-length = 120` legte bisher nur fest, wie `ruff format` Code
umbricht. Kommentare und Docstrings bricht der Formatierer aber nicht um, und ohne `E501` meldete
`ruff check` zu lange Zeilen nicht. Die einzige solche Zeile, ein Docstring in
`eventsource/aggregate.py`, ist jetzt umgebrochen.

## 2026-11-15 – Login im Frontend (Schritt 3d)

**Was:**

- Neue Abhängigkeit `vue-router` (Version 5).
- Neu in `frontend/src/`:
  - `api.ts`: Alle Aufrufe ans Backend laufen über `api<T>()`.
  - `auth.ts`: Hält fest, wer angemeldet ist (`currentUser`), dazu `loadMe`, `login`, `logout`.
  - `router.ts`: Die Routen `/` und `/login` und ein Navigation Guard.
  - `views/LoginView.vue` und `views/HomeView.vue`.
- `main.ts` fragt `/api/me` ab, bevor die App eingehängt wird.
- `App.vue`:
  - Im Inhaltsbereich steht `<RouterView />`.
  - In der Aktionsleiste stehen der Name und „Abmelden“.
  - Das Menü erscheint erst nach der Anmeldung.

**Befehle:**

```bash
cd frontend
npm install vue-router
npm run build                     # Typprüfung und Build

# Ablauf gegen ein Test-Backend mit eigenem Datenordner (Port 8001):
cd ../backend
CM_DATA_DIR=/tmp/…/data CM_SESSION_COOKIE_SECURE=false uv run uvicorn coop_manager.app:app --port 8001
curl -c cookies -H 'Content-Type: application/json' -d '{"username":"…","password":"…"}' \
    http://localhost:8001/api/login
curl -b cookies http://localhost:8001/api/me
```

**Warum so:**

- **`api.ts` als einzige Stelle für `fetch`:**
  - JSON, der Header `X-CSRF-Token` bei schreibenden Anfragen und das Auslesen von `detail` stehen
    nur hier.
  - Ein Fehler wird als `ApiError` mit `status` und deutscher Meldung geworfen. Die Komponente zeigt
    `e.message` an.
  - Bei 422 (Pydantic-Validierung) ist `detail` eine Liste, deshalb gibt es dafür einen eigenen Text.
- **`api<T>(...)`:** `T` ist ein *Typparameter* (Generics). Der Aufrufer sagt mit `api<Me>(...)`,
  welche Form die Antwort hat, und TypeScript prüft danach jeden Zugriff darauf. Zur Laufzeit prüft
  das niemand. Darum steht neben den Interfaces `User` und `Me` der Hinweis, dass sie zu den
  Pydantic-Schemas im Backend passen müssen.
- **Zustand ohne Pinia:** `currentUser` ist ein `ref` auf Modulebene in `auth.ts`. Jede Komponente,
  die ihn importiert, sieht denselben Wert, und Vue zeichnet bei einer Änderung alles neu. Für einen
  einzigen gemeinsamen Wert reicht das.
- **Kein Ringimport:** `auth.ts` braucht `api.ts`. Umgekehrt muss `api.ts` bei 401 die Anmeldung
  zurücksetzen. Damit sich die beiden nicht gegenseitig importieren, nimmt `api.ts` über
  `onUnauthorized(...)` eine Funktion entgegen, und `main.ts` übergibt sie. Dort steht dann sichtbar,
  was bei abgelaufener Session passiert: abmelden und zur Anmeldung, mit `next` als Rückweg.
- **Navigation Guard:** `router.beforeEach` läuft vor jedem Seitenwechsel. Seiten ohne
  `meta: { public: true }` verlangen eine Anmeldung, sonst geht es zu `/login?next=/ziel`. Das
  ersetzt nicht die Prüfung im Backend, es spart nur den Umweg über eine Fehlermeldung.
- **`safeNext`:** Nach dem Login geht es nur zu Pfaden dieser Seite (wie `safe_next_url` in
  `purchase-prices`). Sonst könnte ein präparierter Link `…/login?next=//boese.example` nach der
  Anmeldung auf eine fremde Seite führen (Open Redirect).
- **`await loadMe()` vor `mount`:** `main.ts` ist ein ES-Modul, darin ist `await` auf oberster
  Ebene erlaubt. So weiß der Router beim ersten Aufruf schon, ob noch eine Session besteht, und
  ein Neuladen der Seite führt nicht kurz über die Anmeldeseite.
- **`v-model`** verbindet Eingabefeld und `ref` in beide Richtungen. `@submit.prevent` ruft
  `submit()` auf und verhindert, dass der Browser das Formular selbst abschickt und die Seite neu
  lädt. `:disabled="busy"` verhindert doppeltes Absenden.
- **`autocomplete="username"` und `"current-password"`:** Damit erkennen Passwortmanager das
  Formular.
- **Test:** Ein eigener Server auf Port 8001 mit eigenem Datenordner, weil auf 5173 schon ein Vite
  lief. `CM_SESSION_COOKIE_SECURE=false`, weil `curl` das Cookie sonst über HTTP nicht
  zurückschickt. Geprüft wurde: `/me` ohne Login gibt 401, ein falsches Kennwort gibt 401, der Login
  klappt auch mit „Chefin“ in anderer Schreibweise, `/me` mit Cookie gibt 200, Logout ohne CSRF gibt
  403, mit CSRF 204, danach gibt `/me` wieder 401.

## 2026-11-15 – Benutzerverwaltung im Backend (Schritt 3e, Teil 1)

**Was:**

- `Plan.md`: Neue Regel „API nach Befehlen und Abfragen“ und die Regel, dass Menü und Seiten von
  der Rolle abhängen.
- `users/api.py`: Die Endpunkte der Benutzerverwaltung, alle nur für den Admin:

  ```
  GET  /api/users                     Abfrage: Liste
  GET  /api/users/roles               Abfrage: Rollen mit deutschen Namen
  GET  /api/users/{user_id}           Abfrage: ein Benutzer
  POST /api/users/register            Befehl {username, full_name, password, role}
  POST /api/users/change-full-name    Befehl {user_id, full_name}
  POST /api/users/change-role         Befehl {user_id, role}
  POST /api/users/change-password     Befehl {user_id, password}
  POST /api/users/deactivate          Befehl {user_id}
  POST /api/users/reactivate          Befehl {user_id}
  POST /api/users/terminate           Befehl {user_id}, Antwort 204
  ```

- `users/schemas.py`: Je Befehl ein Pydantic-Modell. `UserOut` hat jetzt das Feld `active`.
- `tests/conftest.py`: Die gemeinsamen Fixtures `app`, `client`, `db`, `register` und `login`.
- `tests/test_users_admin_api.py`. `tests/test_users_api.py` nutzt jetzt die gemeinsamen Fixtures.

**Warum so:**

- **Befehle statt REST:** Matthias' Einwand. Bei REST wird „Rolle ändern“ zu „Ressource `role`
  ersetzen“ (`PUT`), und „löschen“ zu `DELETE`. Damit geht die fachliche Absicht verloren. In DDD
  und CQRS heißt ein Befehl nach dem, was fachlich passiert. Bei uns entspricht jeder Befehl genau
  einer Methode am Aggregat und einem Event (`change-role` → `User.change_role` →
  `user.role-changed`). Abfragen bleiben `GET`.
- **Namen wie im Domänenmodell:** `register` statt `create`, `terminate` statt `delete`. API,
  Code und Events sprechen dieselbe Sprache („Ubiquitous Language“).
- **Die ID steht im Body:** Ein Befehl ist so eine vollständige Nachricht. In der URL und damit
  im Access-Log stehen keine Daten.
- **kebab-case in Pfaden** (`change-role`): üblich bei URLs. Groß- und Kleinschreibung in Pfaden
  führt leicht zu Fehlern.
- **Ein Befehl liefert das Ergebnis:** Nach dem Speichern ist die Projektion schon aktuell, weil
  `db.save` sie synchron nachzieht. `_user_out` liest den Benutzer von dort und gibt ihn zurück.
  `terminate` antwortet mit 204, weil es den Benutzer danach nicht mehr gibt.
- **`Db` und `Admin` als Kurzformen:**
  `Admin = Annotated[UserView, Depends(require_role(ADMIN))]` steht einmal oben. Jeder Endpunkt
  schreibt dann nur `admin: Admin`. Der Parameter prüft die Rolle und liefert zugleich den
  `actor` für die Events.
- **Reihenfolge der Routen:** `/users/roles` muss vor `/users/{user_id}` stehen. FastAPI prüft die
  Routen der Reihe nach und hielte sonst „roles“ für eine Benutzer-ID.
- **Die Regeln stehen nur im Service:** Die API prüft nichts selbst, z. B. „nicht sich selbst
  deaktivieren“. Sie reicht den `DomainError` durch, und der Fehler-Handler macht daraus 400 mit
  der deutschen Meldung.
- **`conftest.py`:** pytest lädt diese Datei von selbst. Ihre Fixtures stehen allen Tests im
  Ordner zur Verfügung, ohne Import. `register` und `login` sind Fixtures, die eine Funktion
  liefern, wie in `purchase-prices`. `login` setzt nach erfolgreicher Anmeldung den CSRF-Header
  dauerhaft am Client. Die Tests schreiben dann nur noch `client.post(...)`.
- **Stolperstein `httpx2`:** Der `TestClient` von Starlette 1.x baut auf dem Paket `httpx2` auf,
  dem Nachfolger von `httpx`. Der Typ für Antworten heißt deshalb `httpx2.Response`.
