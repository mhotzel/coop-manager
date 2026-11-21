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

## 2026-11-15 – Benutzerverwaltung im Frontend (Schritt 3e, Teil 2)

**Was:**

- `frontend/src/users.ts`: Je Abfrage und Befehl der Benutzer-API eine Funktion, z. B.
  `changeRole(userId, role)`.
- `views/users/UserListView.vue` (`/users`): Tabelle mit Benutzername, Name, Rolle und Status.
- `views/users/UserNewView.vue` (`/users/new`): Formular zum Anlegen. Danach geht es zur
  Bearbeitungsseite.
- `views/users/UserEditView.vue` (`/users/:id`):
  - Name, Rolle und Kennwort ändern.
  - Deaktivieren, reaktivieren und löschen, mit Rückfrage. Bei sich selbst ist der Bereich
    ausgeblendet.
- `router.ts`: Die drei Routen mit `meta: { roles: [ADMIN] }`. Der Guard prüft die Rolle.
- `App.vue`: Das Menü zeigt nur die Einträge zur eigenen Rolle. „Benutzer“ ist ein `RouterLink`.
  Auf dem Handy klappt das Menü nach einem Seitenwechsel wieder zu.
- `auth.ts`: Die Rollen-Konstanten. `User` hat jetzt das Feld `active`.
- `api.ts`: `errorText(e)` für die Fehlerbox.

**Befehle:**

```bash
cd frontend
npx vue-tsc --build      # nur Typprüfung
npm run build
```

**Warum so:**

- **`users.ts` statt `fetch` in den Seiten:** Die Seiten rufen `changeRole(...)` auf und kennen
  weder Pfade noch JSON-Felder. Der Name passt zum Befehl im Backend (`/api/users/change-role`).
- **`computed`:** `visibleEntries` im Menü und `isSelf` auf der Bearbeitungsseite werden
  automatisch neu berechnet, wenn sich die Werte ändern, von denen sie abhängen, z. B. nach dem
  Login eines anderen Benutzers.
- **`Promise.all([...])`** schickt mehrere Anfragen gleichzeitig ab und wartet auf alle, hier die
  Benutzer und die Rollen.
- **`run(command, success)`** fasst zusammen, was jeder Befehl braucht: Meldungen leeren, Buttons
  sperren, Befehl ausführen, Ergebnis anzeigen oder Fehler zeigen. Die einzelnen Befehle sind
  Einzeiler wie `saveRole`.
- **Stolperstein:** Zuerst standen die Befehle direkt in der Vorlage, z. B.
  `@submit.prevent="run(() => users.changeRole(...))"`, mit `import * as users`. `vue-tsc`
  meldete: „Property 'value' does not exist“. Vue behandelt Namen aus dem Script in der Vorlage, als
  könnten sie ein `ref` sein, und das passt nicht zu einem Namespace-Import. Mit benannten
  Funktionen im Script ist die Vorlage auch leichter zu lesen.
- **`props: true` im Router** gibt `:id` aus dem Pfad als Prop an die Komponente.
  `defineProps<{ id: string }>()` legt den Typ fest. Die Komponente muss so nichts über den Router
  wissen.
- **`declare module 'vue-router' { interface RouteMeta … }`** macht TypeScript mit unseren eigenen
  `meta`-Feldern bekannt (`public`, `roles`). Ohne diese Angabe wäre `to.meta.roles` vom Typ
  `unknown`.
- **Feste Pfade gewinnen:** Anders als FastAPI ordnet der Vue Router Routen nach Spezifität.
  `/users/new` passt immer vor `/users/:id`, die Reihenfolge ist egal.
- **`@toggle` am Menü:** Klappt man es auf dem Handy per Klick auf, ändert der Browser das
  `open`-Attribut selbst. `@toggle` überträgt das auf `menuOpen`. Sonst wüsste Vue nichts davon,
  und das Zuklappen nach einem Seitenwechsel (`router.afterEach`) würde nicht greifen.
- **Selbst-Schutz zweifach:** Die Seite blendet „Deaktivieren“ und „Löschen“ bei sich selbst aus,
  wie `purchase-prices`. Verbindlich ist die Regel im Backend-Service.
- **`confirm()`** ist die einfache Rückfrage des Browsers. Ein eigener Dialog lohnt sich erst, wenn
  es mehr davon gibt.
- **Zentriert:** Die Masken zum Anlegen und Bearbeiten stehen mittig, mit `card-center` aus
  `style.css`: höchstens 600 px breit, links und rechts `margin: auto`. Auf der Bearbeitungsseite
  steckt die ganze Seite in `<div class="card-center">`, damit auch die Meldungen und
  „Zurück zur Liste“ mittig stehen. Die Liste bleibt breit, weil die Tabelle den Platz braucht.
- **Lokale `.env`:** Kopie von `.env.example` mit eigenem `CM_SECRET_KEY` aus
  `secrets.token_hex(32)`. Damit bleibt man beim Entwickeln angemeldet, auch wenn `--reload` den
  Server neu startet. Die Datei ist per `.gitignore` ausgeschlossen und nur für den Besitzer
  lesbar (`chmod 600`).

**Nachtrag – `.env` wird automatisch gelesen:**

- Neue Abhängigkeit `python-dotenv`.
- `load_settings()` sucht mit `find_dotenv(usecwd=True)` eine `.env` im aktuellen Ordner und
  darüber. Aus `backend/` heraus findet es so `../.env`. `--env-file` ist nicht mehr nötig.
- **Vorrang:** `_read_env_file(...) | dict(os.environ)`. Der Operator `|` verbindet zwei
  Dictionaries, bei gleichem Schlüssel gewinnt das rechte. Echte Umgebungsvariablen gehen also vor.
  Im Container setzt Docker die Werte, eine `.env` gibt es dort nicht.
- **`os.environ` bleibt unverändert:** Anders als `load_dotenv()` liest `dotenv_values()` die Datei
  nur. Sonst würden Werte aus der `.env` in Tests und Unterprozesse durchsickern.
- **Tests:** Die Fixture `no_env_file` in `conftest.py` mit `autouse=True` gilt für jeden Test. Sie
  ersetzt `find_env_file` durch eine Funktion, die nichts findet. So hängen die Tests nicht davon
  ab, ob und wie jemand eine lokale `.env` angelegt hat. Zwei neue Tests prüfen das Lesen der
  Datei, den Vorrang der Umgebung und die Suche nach oben.

## 2026-11-15 – Eigenes Kennwort ändern (Schritt 3f)

**Was:**

- Backend: Der Befehl `POST /api/me/change-password` mit `{current_password, new_password}`, für
  alle Angemeldeten. Dazu die Service-Funktion `change_own_password` und das Schema
  `ChangeOwnPassword`. Tests in `test_users_services.py` und `test_users_api.py`.
- Frontend: Die Seite `views/PasswordView.vue` unter `/password`, die Funktion
  `changeOwnPassword` in `auth.ts` und der Button „Kennwort ändern“ in der Aktionsleiste.
- `Plan.md`: Schritt 3 ist erledigt.

**Warum so:**

- **Das bisherige Kennwort ist Pflicht:** Sonst könnte jemand an einem kurz verlassenen,
  angemeldeten Rechner das Kennwort ändern und den Besitzer aussperren.
- **Die Prüfung steckt im Service, innerhalb von `_change`:** Die innere Funktion `change(user)`
  prüft erst `user.check_password(...)` und ruft dann `user.change_password(...)` auf. Ist das
  bisherige Kennwort falsch, entsteht kein Event. Der Test prüft das über die Länge des Streams.
- **Dasselbe Event wie beim Admin** (`user.password-changed`). Der Unterschied steht im `actor`:
  Hier ist es der Benutzer selbst, beim Neusetzen durch den Admin der Admin.
- **Fehlversuche zählen nicht für die Login-Sperre:** Man muss ohnehin angemeldet sein. Jeder
  Fehlversuch steht aber als Warnung im Log (`wrong current password`).
- **Der Pfad heißt `/api/me/…`, nicht `/api/users/…`:** Der Befehl betrifft immer den angemeldeten
  Benutzer. Die ID kommt aus der Session, nicht aus dem Body. So kann niemand darüber das Kennwort
  eines anderen ändern.
- **Frontend:** Ob die beiden neuen Kennwörter gleich sind, prüft schon die Seite, das ist nur
  Komfort. Die Regeln prüft das Backend. Danach werden alle drei Felder geleert, auch nach einem
  Fehler, damit kein Kennwort im Formular stehen bleibt.

## 2026-11-15 – Aggregat `Member` mit Adresszeilen und Briefanrede (Schritt 4a)

**Was:**

- `Plan.md`: Unterschritte 4a bis 4d und neuer Abschnitt „Mitglieder im Modell (Schritt 4)“ mit
  Abgrenzung zu Schritt 5, Nummernvergabe über `MemberNumbers`, Status zum Stichtag, Suche per
  POST, Änderungen nach fachlicher Absicht und unveränderlicher Art der Person. Der offene Punkt zur
  Suche im Access-Log ist damit erledigt.
- Neues Paket `backend/src/coop_manager/members/`:
  - `values.py`: Die Wertobjekte `PersonName`, `Address` und `Contact`, die Konstanten (Art der
    Person, Geschlecht) und die Prüfungen.
  - `addressing.py`: `address_lines`, `long_address_lines`, `salutation` und `list_name` als reine
    Funktionen.
  - `domain.py`: Das Aggregat `Member` mit `apply` (Antrag erfassen) und den Änderungsbefehlen.
- Tests: `tests/test_members_domain.py` und `tests/test_members_addressing.py`.

**Events:**

| Event | Daten |
|---|---|
| `member.applied` | `member_number`, `person_type`, `name`, `address`, `contact`, `address_lines`, `application_date`, `shares_subscribed` |
| `member.name-changed` | `name` (Firmenname, Titel, Vornamen, Nachname, Geschlecht) |
| `member.address-changed` | `address` (Straße, Hausnummer, PLZ, Ort, Land) |
| `member.contact-changed` | `contact` (Telefon, E-Mail) |
| `member.address-lines-changed` | `address_lines` (sechs Zeilen) |
| `member.salutation-changed` | `salutation` (abweichende Briefanrede, leer = erzeugen) |
| `member.mail-preference-changed` | `no_mail` |
| `member.notes-changed` | `notes` |

**Warum so:**

- **Wertobjekte (Value Objects):** `PersonName`, `Address` und `Contact` sind `@dataclass(frozen=True)`.
  Sie haben keine eigene Identität, zwei Anschriften mit denselben Feldern sind gleich (`==`).
  `frozen` macht sie unveränderlich. Eine Änderung ist deshalb immer ein neues Objekt, und der
  Vergleich `address != self.address` entscheidet, ob ein Event entsteht.
- **Gruppen im Event:** `name` und `address` stehen als verschachtelte Dictionaries im Event
  (`asdict(...)`). Beim Laden macht `PersonName(**event.data["name"])` wieder ein Objekt daraus.
  `**` übergibt die Einträge des Dictionaries als benannte Argumente.
- **Datum als Text:** Events werden als JSON gespeichert, und JSON kennt kein Datum. Darum
  `application_date.isoformat()` (z. B. `"2026-11-02"`) und beim Laden `date.fromisoformat(...)`.
- **Drei Dateien statt einer:** `domain.py` braucht beim Antrag die erzeugten Adresszeilen,
  `addressing.py` braucht die Wertobjekte. Stünden die Wertobjekte in `domain.py`, würden sich beide
  Dateien gegenseitig importieren. Mit `values.py` geht die Richtung nur in eine Richtung:
  `values` ← `addressing` ← `domain`.
- **Adresszeilen werden beim Antrag einmal erzeugt.** Danach ändern sie sich nur noch über
  `change_address_lines`, von Hand oder später per Button „Adresszeilen erzeugen“. Ein Umzug ändert
  sie nicht von selbst. So bleibt z. B. eine Anschrift an die Erben erhalten. Die Warnung, wenn
  Name oder Anschrift nicht zu den Zeilen passen, kommt in 4c/4d.
- **Briefanrede wird nie gespeichert,** nur die abweichende. `salutation(...)` erzeugt sie beim
  Report. Reihenfolge: verstorben → abweichende Anrede → juristische Person → Geschlecht.
- **Prüfungen:**
  - Pflichtfelder hängen von der Art der Person ab: natürliche Person mit Vornamen und Nachname
    und ohne Firmenname, juristische Person mit Firmenname und optionalem Ansprechpartner.
  - Eine deutsche Postleitzahl hat fünf Ziffern, eine ausländische ist frei.
  - Leeres Land bedeutet Deutschland.
  - Obergrenzen für die Länge schützen die Datenbank. Die 35 Zeichen der Anschriftzone sind nur
    eine Warnung (`long_address_lines`).
- **`clean(...)`** vereinheitlicht wie beim Benutzer Unicode (NFC) und Leerzeichen. Hinweise sind
  mehrzeilig, dort fällt nur Leerraum am Anfang und Ende weg.
- **Linter-Hinweis B008:** `contact: Contact = Contact()` als Standardwert wird nur einmal beim
  Definieren der Funktion ausgewertet und von allen Aufrufen geteilt. Bei veränderlichen Objekten
  ist das eine klassische Falle. Darum `contact: Contact | None = None` und in der Funktion
  `contact or Contact()`.

## 2026-11-15 – Docstrings nachgetragen, `ruff` prüft sie jetzt

**Was:**

- Fehlende Docstrings ergänzt: in `members/` (noch vor dem Commit von 4a) und in dem Code aus
  Schritt 3 (`users/`, `create_app`, `cli.main`). Es waren insgesamt 55 Stellen.
- `pyproject.toml`: Die `ruff`-Regeln `D101`, `D102` und `D103` sind eingeschaltet, mit einer
  Ausnahme für `tests/**`.

**Befehle:**

```bash
cd backend
uv run ruff check --select D101,D102,D103,D107 --output-format concise src   # einmalig: wo fehlt etwas?
uv run ruff check                                                           # jetzt immer mit dabei
```

**Warum so:**

- Matthias hatte die Docstrings vermisst. Gefunden hat sie `ruff` mit den pydocstyle-Regeln
  (`D…`):
  - `D101`: Klasse ohne Docstring.
  - `D102`: Methode ohne Docstring.
  - `D103`: Funktion ohne Docstring.
  - `D107` gilt für `__init__` und bleibt aus. Nach der bisherigen Regel braucht ein `__init__`,
    das nur Parameter übernimmt, keinen. `Member.__init__` und `User.__init__` legen den
    Anfangszustand fest und haben trotzdem einen bekommen.
- Private Namen (`_change`, die `@on`-Handler) zählen für `ruff` nicht als öffentlich und bleiben
  ohne Pflicht. Das passt zur bisherigen Regel.
- **`per-file-ignores`** nimmt die Tests aus: Dort sagt der Name der Testfunktion, was geprüft
  wird.
- **Nebeneffekt:** FastAPI übernimmt den Docstring eines Endpunkts als Beschreibung in die
  OpenAPI-Doku (`/openapi.json`).

## 2026-11-15 – Nummernvergabe, Zulassung, Projektion und Suche (Schritt 4b)

**Was:**

- `members/numbers.py`: Das Aggregat `MemberNumbers`, ein einziger Stream `member-numbers` mit dem
  Event `member-number.assigned`.
- `members/status.py`: `MembershipDates` und `status_on(dates, tag)`, also der Status zum Stichtag
  (Antragsteller oder abgelehnt).
- `members/domain.py`: `admit`, `reject` und `withdraw` mit den Events `member.admitted`,
  `member.rejected` und `member.withdrawn`, dazu `status(tag)`.
- `members/projections.py`: Der Projektor `MemberList` und `search_members(...)`.
- `members/services.py`: `apply_for_membership` mit Wiederholung bei Konflikt, die Befehle und
  `get_member`.
- `db.py`: `Database.save_all([...])` speichert mehrere Aggregate in einer Transaktion.
- `app.py`: `MemberList` ist in `PROJECTORS` eingetragen.
- Tests: `test_members_numbers.py`, `test_members_services.py` und Ergänzungen in
  `test_members_domain.py`.

**Warum so:**

- **Eindeutige Nummer per eigenem Stream:**
  - Die Versionsprüfung des Event Stores gilt nur innerhalb eines Streams (eindeutig ist
    `subject` + `version`). Zwei Anträge sind zwei verschiedene Streams und kämen sich nie in die
    Quere.
  - Darum laufen alle Vergaben über **einen** Stream. Wer zuerst speichert, bekommt Version n+1,
    der zweite scheitert mit `ConcurrencyError`.
  - Der Service fängt das ab, lädt das Register neu und nimmt die nächste freie Nummer, höchstens
    dreimal.
  - So setzt man im Event Sourcing eine Regel durch, die über mehrere Aggregate geht
    („Eindeutigkeit“), ohne den Event Store selbst zu verändern.
- **`save_all` statt zweimal `save`:** Register und Mitglied müssen zusammen gespeichert werden.
  Sonst gäbe es eine vergebene Nummer ohne Mitglied oder ein Mitglied ohne eingetragene Nummer.
  `transaction(...)` umschließt beide `save`-Aufrufe. Weil sich verschachtelte Transaktionen der
  äußeren anschließen, wird alles mit einem einzigen `COMMIT` gespeichert, oder gar nichts.
- **Test für gleichzeitige Anträge:** Echte Gleichzeitigkeit lässt sich schlecht testen. Der Test
  ersetzt deshalb `_load_numbers` per `monkeypatch`. Beim ersten Aufruf lädt er das Register und
  lässt dann über eine zweite Datenbankverbindung „jemand anderen“ Nummer 1 vergeben. Das
  geladene Register ist damit veraltet, das Speichern scheitert, der zweite Versuch bekommt
  Nummer 2.
- **Status wird berechnet:** `status_on(MembershipDates(...), tag)` steht in einer eigenen Datei, weil
  Aggregat **und** Projektion ihn brauchen. Die Projektion speichert nur die Daten (Antrag,
  Zulassung, Ablehnung) und berechnet den Status beim Lesen für „heute“. Reports können später
  denselben Status für jeden anderen Stichtag berechnen.
- **Ablehnung und Rücknahme** sind zwei Events, weil sie fachlich verschieden sind: Die eine
  beschließt der Vorstand, die andere erklärt die Person. Beide setzen in Aggregat und Projektion
  `rejection_date` und führen zum Status „abgelehnt“.
- **Suche:**
  - `search_text` enthält Firma, Titel, Vornamen, Nachname, Straße, PLZ und Ort, mit `casefold()`
    klein geschrieben. `casefold` kann mehr als `lower`, z. B. „ß“ → „ss“.
  - SQLites `LIKE` kennt Groß/klein nur bei ASCII, „Ü“ und „ü“ wären verschieden.
  - Jedes Wort wird eine eigene Bedingung (`AND`).
  - `%` und `_` sind in `LIKE` Platzhalter. `_escape_like` maskiert sie, damit eine Suche nach
    „%“ nicht alles findet.
- **Stolperstein Suche nach Ziffern:** Der erste Test erwartete, dass „2“ nur Mitglied 2 findet.
  Gefunden wurden aber alle, weil in der Postleitzahl „12345“ eine 2 steckt. Jetzt trifft ein
  Wort nur aus Ziffern die Mitgliedsnummer genau oder den Anfang der PLZ, das steht so auch im
  Plan.
- **Werte im SQL immer als `?`:** Auch bei der zusammengesetzten Suche kommen nur die festen
  Bausteine per f-String ins SQL. Die Suchwörter selbst gehen als Parameter hinein, so ist keine
  SQL-Injection möglich.
- **Umbenannt: `Facts` → `MembershipDates`** (Matthias' Hinweis). Die Klasse ist nicht der Status,
  sondern enthält die Daten der Mitgliedschaft (Antrag, Zulassung, Ablehnung, in Schritt 5 auch
  Eintritt, Kündigung und Ausscheiden), aus denen `status_on` den Status für einen Tag berechnet.

## 2026-11-15 – Mitglieder-API mit Befehlen und Abfragen (Schritt 4c)

**Was:**

- `members/schemas.py`: Pydantic-Modelle. `SearchRequest`, `MemberDetail` mit
  `from_member(member, today)` und je ein Befehl pro fachlicher Aktion: `ApplyForMembership`,
  `Decision`, `Withdraw` und `ChangeName` bis `ChangeNotes`.
- `members/api.py`: Router unter `/api/members`.
  - Abfragen: `POST /search` und `GET /{member_id}`.
  - Befehle: `POST /apply`, `/admit`, `/reject`, `/withdraw`, `/change-name`, `/change-address`,
    `/change-contact`, `/change-address-lines`, `/change-salutation`, `/change-mail-preference`
    und `/change-notes`.
- `members/addressing.py`: `address_warnings(lines, generated)` mit den deutschen Warntexten.
- `app.py`: Der Router ist eingebunden.
- Tests: `test_members_api.py` und drei neue Tests in `test_members_addressing.py`.
- Geprüft mit `uv run pytest` (208 grün), `uv run ruff check` und `uv run ruff format`.

**Warum so:**

- **Rechte über zwei Kurzformen:** `Reader = require_role(ACCOUNTING, ACCOUNTING_READONLY)` und
  `Writer = require_role(ACCOUNTING)`. Am Parameter jedes Endpunkts sieht man so sofort, wer ihn
  benutzen darf. Der Admin steht in keiner der beiden Listen und bekommt 403. Der bestehende Test
  in `test_access.py` prüft die neuen Routen automatisch mit: Jede braucht einen angemeldeten
  Benutzer.
- **Dataclasses als Pydantic-Feldtypen:** `PersonName`, `Address` und `Contact` stehen direkt in
  den Schemas. Pydantic prüft dann Typen und Pflichtfelder (fehlt z. B. der Ort: 422), die
  fachlichen Regeln prüft weiter das Aggregat (400). So gibt es die Felder nur einmal. In der
  OpenAPI-Beschreibung erscheinen sie als eigene Schemas.
- **Die Detailansicht kommt aus dem Aggregat, nicht aus der Projektion.** Die Projektion
  `members` enthält nur, was Suche und Liste brauchen, keinen Kontakt und keine Hinweise. Ein
  einzelnes Mitglied aus seinen Events zu laden ist billig, und die Services liefern das
  Aggregat nach jedem Befehl ohnehin zurück.
- **Berechnete Angaben werden beim Lesen gebildet:** Status von heute, Briefanrede,
  `generated_address_lines` und `warnings`. Die Warnung „passt nicht“ vergleicht einfach die
  gespeicherten mit den neu erzeugten Zeilen. Speichert das Frontend die erzeugten Zeilen mit
  `change-address-lines`, verschwindet sie wieder.
- **`salutation_override` und `salutation`:** Das gespeicherte Feld (abweichende Anrede, oft
  leer) und die tatsächlich verwendete Anrede heißen in der Antwort verschieden. Sonst wüsste das
  Frontend nicht, was in das Eingabefeld gehört.
- **Stolperstein `date: date`:** Ein Feld, das so heißt wie sein Typ, überdeckt den Typ im
  Klassenkörper, das ist bei Pydantic eine bekannte Fehlerquelle. Die Felder heißen darum wie in
  den Events `decision_date` bzw. `withdrawal_date`. Für die Rücknahme gibt es deshalb ein eigenes
  Schema `Withdraw`.
- **Obergrenzen (`max_length`) in den Schemas** nur als Schutz vor riesigen Anfragen, wie bei den
  Benutzern. Die fachlichen Längen prüft das Aggregat.

## 2026-11-16 – Mitgliedersuche im Frontend (Schritt 4d-1)

Schritt 4d (Frontend für die Mitglieder) ist aufgeteilt in 4d-1 Suche, 4d-2 Detailseite mit
Zulassung/Ablehnung/Rücknahme, 4d-3 Antrag erfassen und 4d-4 Bearbeiten in Abschnitten auf der
Detailseite (ein Abschnitt = ein Befehl, keine eigene Bearbeitungsseite).

**Was:**

- `frontend/src/members.ts`: Interface `MemberRow` (Gegenstück zur Dataclass im Backend),
  `searchMembers()`, `statusLabel()` mit den deutschen Texten zu den Status und `lastQuery`.
- `frontend/src/views/members/MemberSearchView.vue`: Suchfeld und Ergebnistabelle (Nr., Name,
  Anschrift, Status). Beim Öffnen läuft gleich eine Suche, leer liefert sie die ersten 50.
- `router.ts`: Route `/members` für `accounting` und `accounting_readonly`.
- `App.vue`: Der Menüeintrag „Mitglieder“ führt jetzt zur Suche.
- Geprüft mit `npm run type-check` und von Hand im Browser.

**Warum so:**

- **`interface` statt Laufzeitprüfung:** TypeScript prüft die Form nur beim Übersetzen. Ob das
  Backend wirklich so antwortet, prüft niemand, darum der Kommentar „Muss zu … passen“.
  `string | null` entspricht `str | None`, `Record<string, string>` einem `dict[str, str]`.
- **Status-Texte im Frontend:** Für zwei selten geänderte Werte ist eine kleine Tabelle einfacher
  als ein eigener Endpunkt wie bei den Rollen. Kommen in Schritt 5 viele dazu, lässt sich das
  umstellen.
- **Suchbegriff im Modul, nicht in der Adresse:** `lastQuery` lebt in `members.ts` (wie
  `currentUser` in `auth.ts`) und bleibt so beim Zurückkommen von einer anderen Seite erhalten.
  Ein Zustand mit `ref` in der Komponente verschwindet dagegen, sobald man die Seite verlässt.
  `/members?q=…` wäre üblich, ginge aber beim Neuladen an den Server und stünde im Access-Log,
  genau das vermeidet `POST /search`.
- **`rows` ist `null`, solange nicht gesucht wurde:** So lässt sich „noch nichts geladen“ von
  „nichts gefunden“ (`[]`) unterscheiden, und die Meldung erscheint nicht kurz beim Laden.
- **Hinweis bei 50 Treffern:** Das Backend schneidet dort ab. Ohne Hinweis hielte man die Liste
  für vollständig.

## 2026-11-16 – Detailseite mit Zulassung, Ablehnung und Rücknahme (Schritt 4d-2)

**Was:**

- Backend: `Member.withdrawn` und das Feld `withdrawn` in `MemberDetail`. Ablehnung und Rücknahme
  setzen beide `rejection_date`, an der Detailansicht ließen sie sich bisher nicht unterscheiden.
  Neuer Test `test_rejection_is_not_a_withdrawal`, die Tests zur Rücknahme prüfen das Feld mit.
  Geprüft mit `uv run pytest` (209 grün), `ruff` und `pyright`.
- `members.ts`: Interfaces `PersonName`, `Address`, `Contact`, `MemberDetail`, dazu
  `getMember()`, die Befehle `admit()`, `reject()`, `withdraw()` und die Helfer
  `personTypeLabel()`, `genderLabel()`, `formatDate()` und `todayIso()`.
- `views/members/MemberDetailView.vue`: alle Daten in Abschnitten (Karten), die Knöpfe
  Zulassen, Ablehnen, Rücknahme mit einem kleinen Datumsformular.
- `router.ts`: Route `/members/:id` (`member-detail`). In der Suche führt der Name dorthin.
- `Plan.md`: Entscheidungen zu `withdrawn` und zur einen Detailseite eingetragen.
- Geprüft mit `npm run type-check` und von Hand im Browser.

**Warum so:**

- **Ein Feld `withdrawn` statt zweier Datumsfelder:** Es kann nur eines von beiden geben, danach
  ist der Antrag erledigt. Ein Datum und ein Schalter bilden das genau ab. Der Status rechnet
  weiter nur mit `rejection_date`.
- **Datum als Text, ohne `Date`:** `<input type="date">` liefert `"2026-11-16"`, genau das Format
  des Backends. `new Date("2026-11-02")` gilt dagegen als Mitternacht in UTC und kann je nach
  Zeitzone den Vortag ergeben, ebenso `toISOString()` kurz nach Mitternacht. `formatDate` zerlegt
  den Text darum nur, `todayIso` baut das Datum aus den lokalen Angaben.
- **Union-Typ `'admit' | 'reject' | 'withdraw'`:** Welche Entscheidung gerade erfasst wird, steht
  in einem `ref` mit diesem Typ. `Record<Action, …>` verlangt dann für jede Aktion genau einen
  Eintrag (Titel, Befehl). Fehlt einer, meldet TypeScript einen Fehler.
- **Regeln für die Knöpfe doppelt:** Das Frontend blendet nur aus, was im aktuellen Zustand keinen
  Sinn hat (und alles für „Buchhaltung lesend“). Verbindlich prüft das Aggregat. Lehnt es ab,
  steht seine Meldung in der Fehlerbox.
- **Jeder Befehl antwortet mit der Detailansicht:** Die Seite ersetzt einfach `member` durch die
  Antwort, ein erneutes Laden ist nicht nötig.
- **`<dl>` mit CSS-Grid** für Bezeichnung und Wert, auf dem Handy untereinander. Das Styling steht
  `scoped` in der Komponente, bis eine zweite Seite es braucht.

## 2026-11-16 – Antrag erfassen und Mitglieder bearbeiten (Schritte 4d-3 und 4d-4)

Matthias hat beide Schritte auf einmal freigegeben („alle restlichen Sachen direkt umsetzen“).
Damit ist Schritt 4 (Mitglieder) abgeschlossen.

**Was:**

- `members.ts`: `applyForMembership()` und die Befehle `changeName()`, `changeAddress()`,
  `changeContact()`, `changeAddressLines()`, `changeSalutation()`, `changeMailPreference()`,
  `changeNotes()`. `PERSON_TYPE_LABELS` und `GENDER_LABELS` sind exportiert, damit die Formulare
  daraus ihre Auswahl bauen.
- Drei Feld-Komponenten in `views/members/`: `NameFields.vue`, `AddressFields.vue`,
  `ContactFields.vue`. Antrag und Bearbeitung benutzen dieselben Felder.
- `MemberApplyView.vue` unter `/members/new` (nur `accounting`): Art der Person, Name,
  Anschrift, Kontakt, Antragsdatum (vorbelegt mit heute) und Anteile (vorbelegt mit 1). Nach dem
  Speichern geht es zur Detailseite. Auf der Suchseite gibt es dafür den Knopf „Neuer Antrag“.
- `MemberDetailView.vue`: Jeder Abschnitt hat „Bearbeiten“ und speichert mit seinem eigenen
  Befehl: Name, Anschrift, Kontakt, Adresszeilen, Briefanrede, Hinweise. „Keine Post“ ist ein
  Knopf „Setzen“/„Aufheben“. Die Warnungen stehen jetzt oben auf der Seite.
- `style.css`: Eingabefelder vom Typ `tel` und `email` sehen aus wie die übrigen.
- `Plan.md`: Schritt 4 als erledigt markiert.
- Geprüft mit `npm run type-check`, `npm run build-only` und von Hand im Browser.

**Warum so:**

- **`defineModel` für die Feld-Komponenten:** Die Elternseite schreibt `<NameFields v-model="name" />`
  wie bei einem einfachen `<input>`. Die Komponente ändert die Eigenschaften des übergebenen
  Objekts direkt. Das ist die einfachste Form; „sauberer“ wäre, bei jeder Eingabe ein neues
  Objekt zurückzumelden, das bringt hier aber nichts.
- **Entwürfe statt direkter Bindung:** Beim Bearbeiten kopiert `startEdit` die Daten
  (`{ ...x }`, `[...x]`) in eigene `draft…`-Refs. Ohne Kopie änderte das Formular die Anzeige
  sofort mit, und „Abbrechen“ müsste den alten Stand wiederherstellen.
- **Immer nur ein Abschnitt offen:** Solange ein Formular offen ist, verschwinden die anderen
  „Bearbeiten“-Knöpfe. So kann kein ungespeicherter Entwurf verloren gehen.
- **Eine Hilfsfunktion `run` für alle Befehle**, wie in `UserEditView.vue`: Fehler anzeigen,
  Erfolg melden, Formular schließen. Bei einem Fehler bleibt das Formular mit den Eingaben offen.
- **„Adresszeilen erzeugen“ fragt nur, wenn die Zeilen im Entwurf von den erzeugten abweichen**
  (`window.confirm`). Ob sie von Hand angepasst oder nur veraltet sind, lässt sich nicht
  unterscheiden; im Zweifel fragt die Seite lieber.
- **Länge der Adresszeilen schon beim Tippen:** Über 35 Zeichen steht neben der Zeile ein roter
  Hinweis. Die Warnung des Backends kommt zusätzlich nach dem Speichern.
- **Firmenname bei natürlicher Person leeren:** Wechselt man im Antrag von „juristisch“ auf
  „natürlich“, ist das Firmenfeld ausgeblendet, sein Inhalt aber noch da. Das Backend würde den
  Antrag dann ablehnen, darum schickt `submit` den Firmennamen in diesem Fall leer.
- **`router.replace` nach dem Antrag:** „Zurück“ im Browser führt so nicht wieder in das
  ausgefüllte Formular, mit dem man versehentlich einen zweiten Antrag anlegen könnte.
- **`noUncheckedIndexedAccess`:** In `tsconfig.app.json` eingeschaltet. `draftLines[index]` hat
  deshalb den Typ `string | undefined`. In der Vorlage nehmen wir für die Länge darum `line`
  aus dem `v-for`, das ist sicher ein `string`.

## 2026-11-16 – Kein Datum in der Zukunft bei Entscheidungen

**Anlass:** Beim Testen wurde ein Antrag abgelehnt, im Datumsfeld stand aber versehentlich der
17.11. statt des 16.11. Gespeichert war damit eine Ablehnung für morgen: Die Detailseite zeigte
„Abgelehnt am 17.11.2026“, der Status war heute noch „Antragsteller“, Knöpfe gab es keine mehr.
Die Berechnung war richtig, die Eingabe hätte aber nicht angenommen werden dürfen. Nachgesehen
mit `sqlite3` direkt in `backend/data/eventstore.sqlite` und `projections.sqlite`.

**Was:**

- `Member.admit`, `reject` und `withdraw` bekommen `today` und lehnen ein Datum nach heute ab:
  „Das Datum darf nicht in der Zukunft liegen.“ Ebenso die Services, die API übergibt
  `date.today()`.
- Tests: Zukunft für alle drei Entscheidungen abgelehnt, heute erlaubt, dazu ein API-Test. In
  `test_members_domain.py` steht ein festes `TODAY = date(2026, 11, 30)`. Geprüft mit
  `uv run pytest` (214 grün), `ruff` und `pyright`.
- Frontend: Das Datumsfeld bekommt `min` (Antragsdatum) und `max` (heute), der Browser bietet
  andere Tage gar nicht erst an.
- `Plan.md`: Entscheidung eingetragen.

**Warum so:**

- **`today` als Parameter statt `date.today()` im Aggregat:** Wie bei `status(today)`. Sonst
  hinge das Ergebnis eines Tests vom Tag ab, an dem er läuft. Ein Test mit dem 20.11. als
  Entscheidungsdatum würde dann bis zum 19.11. scheitern und danach bestehen.
- **Prüfung in beiden Schichten:** `max` im Browser ist Komfort und verhindert Versehen. Die Regel
  selbst steht im Aggregat, denn auch die API ohne Oberfläche muss sie einhalten.
- **Der Testdatensatz bleibt, wie er ist:** Events werden nicht geändert, und ab dem 17.11. ist
  er von selbst „abgelehnt“. Es sind nur Entwicklungsdaten.

## 2026-11-17 – Schritt 5a: Anteilspreis als Systemeinstellung

**Entscheidungen vorab:** Die Aufteilung von Schritt 5 in 5a bis 5h steht jetzt in `Plan.md`.
Für das Hauptbuch nehmen wir Variante A: ein Aggregat `Ledger` mit einem einzigen Stream. Die
Systemeinstellungen sollen später in der Oberfläche durch den Admin änderbar sein. Darum werden
sie schon jetzt per Event Sourcing gespeichert, gesetzt werden sie vorerst aber nur über die
Kommandozeile, wie beim Anlegen des Admins.

**Was:**

- `core/money.py`: `parse_euro("50,00")` → `5000` Cent und `format_euro(5000)` → `„50,00 €“`.
  Wird ab 5b auch für die Buchungen gebraucht.
- Neues Paket `system_settings/`:
  - `domain.py`: Aggregat `SystemSettings` im Stream `system-settings`. `change_share_price(cents)`
    prüft „größer als 0“ und erzeugt bei unverändertem Preis kein Event. Event:
    `settings.share-price-changed` mit `share_price` in Cent.
  - `services.py`: `get_system_settings(db)` und `change_share_price(db, cents, actor)`.
- `cli.py`: neue Unterbefehle `set-share-price <betrag>` und `show-settings`. Das Öffnen der
  Datenbank steckt jetzt in `open_db()`, das auch `create-admin` nutzt.
- Tests: `test_money.py`, `test_system_settings.py` und drei neue Fälle in `test_cli.py`. Geprüft
  mit `uv run pytest` (240 grün), `uv run ruff check .`, `uv run ruff format --check .` und
  `uv run pyright`.
- `Plan.md`: Aufteilung 5a–5h, Entscheidungen zu Systemeinstellungen und Hauptbuch, Glossar
  (`Ledger`, `SystemSettings`), die Admin-Seite unter „Mögliche Weiterentwicklungen“.
  `DEV_HINTS.md`: Abschnitt „Anteilspreis festlegen“.

**Warum so:**

- **`SystemSettings` statt `Settings`:** `config.Settings` gibt es schon, das ist die technische
  Konfiguration aus der `.env` (Datenverzeichnis, Schlüssel). Der Anteilspreis ist dagegen
  fachlich und gehört mit Verlauf in den Event Store.
- **Ein Stream für alle Einstellungen:** Es gibt nur ein Objekt „Systemeinstellungen“, also eine
  feste Subject-Kennung wie bei `MemberNumbers`. Weitere Einstellungen bekommen später einfach
  eigene Events im selben Stream.
- **Keine Projektion, keine API:** Der Stream ist winzig und wird bei Bedarf direkt geladen.
  Projektion und Endpunkte kommen erst mit der Admin-Seite, wenn sie gebraucht werden.
- **Euro als Text parsen, nicht über `float`:** `float("0.1") + float("0.2")` ergibt
  `0.30000000000000004`. Darum zerlegt ein regulärer Ausdruck die Eingabe in Euro und Cent, und
  es wird nur mit ganzen Zahlen gerechnet. Mehr als zwei Nachkommastellen werden abgelehnt.
- **Gleicher Preis, kein Event:** Sonst stünde im Verlauf eine „Änderung“, die nichts geändert
  hat.

## 2026-11-17 – Schritt 5b, Teil 1: Konten eröffnen

**Vorab:** Die Entwicklungsdaten in `backend/data/` gelöscht (`eventstore.sqlite`,
`projections.sqlite`), weil die alten Anträge noch kein Konto haben. Danach müssen Admin,
Anteilspreis und Genossenschaftskonto neu angelegt werden (siehe `DEV_HINTS.md`).

**Was:**

- Neues Paket `accounts/`:
  - `domain.py`: Aggregat `Ledger` im Stream `ledger`, Datenklasse `Account` (Nummer, Kontoart,
    Mitglieds-ID, Bezeichnung). Befehle `open_member_account(number, member_id)` und
    `open_cooperative_account(name)`, beide erzeugen das Event `account.opened`. Regeln: Nummer
    positiv und frei, 9999 nur für die Genossenschaft, ein Konto je Mitglied, das
    Genossenschaftskonto nur einmal und mit Bezeichnung. Abfragen `cooperative_account()`,
    `account_of(member_id)` und `member_account_numbers()`.
  - `services.py`: `get_ledger(db)` und `open_cooperative_account(db, name, actor)`.
- `members/numbers.py`: `next_number(account_numbers)` berücksichtigt jetzt auch die Nummern der
  Mitgliedskonten. `RESERVED` nutzt die Konstante `COOPERATIVE_ACCOUNT_NUMBER`.
- `members/services.py`: `apply_for_membership` eröffnet das Konto mit derselben Nummer und
  speichert Nummernregister, Mitglied und Hauptbuch mit `save_all` in einer Transaktion.
- `config.py`, `.env.example`: neue Einstellung `CM_COOPERATIVE_ACCOUNT_NAME`.
- `cli.py`: neuer Befehl `create-cooperative-account`. Ausprobiert in einem Wegwerf-Ordner mit
  `CM_DATA_DIR=<ordner> uv run coop-manager create-cooperative-account`: Der erste Aufruf legt
  das Konto an, der zweite bricht mit „Das Genossenschaftskonto gibt es bereits.“ ab.
- Tests: `test_ledger.py`, dazu neue Fälle in `test_members_numbers.py`,
  `test_members_services.py` und `test_cli.py`. Geprüft mit `uv run pytest` (254 grün),
  `uv run ruff check .`, `uv run ruff format --check .` und `uv run pyright`.
- `Plan.md`: 5b in zwei Teile aufgeteilt, Entscheidungen „Nummer 9999 fest im Code“ und „Konten
  im `Ledger`-Stream“. `DEV_HINTS.md`: Abschnitt „Genossenschaftskonto anlegen“.

**Warum so:**

- **Konten im selben Stream wie die Buchungen:** Eine Buchung muss prüfen können, ob ihre Konten
  existieren. Liegt alles in einem Aggregat, ist das eine einfache Abfrage, ohne einen zweiten
  Stream zu laden.
- **Ein Event für beide Kontoarten:** Ein Konto ist ein Konto, nur die Art unterscheidet sich.
  Weil die Art im Event steht, wird das Genossenschaftskonto an ihr erkannt, nicht an der Nummer.
- **`save_all` mit drei Aggregaten:** Entweder entstehen Nummer, Mitglied und Konto zusammen oder
  gar nichts. Die vorhandene Wiederholschleife bei `ConcurrencyError` gilt damit auch für das
  Hauptbuch: Bucht jemand gleichzeitig, wird der Antrag einfach noch einmal versucht.
- **Nummernregel an einer Stelle:** Statt einer zweiten Funktion bekommt `next_number` die
  Kontonummern als Parameter. So bleiben Mitglieds- und Kontonummer gleich, auch wenn bei der
  Migration einmal eine Kontonummer von Hand vergeben wurde.
- **9999 fest im Code statt einstellbar:** Wäre die Nummer einstellbar, müsste auch
  `MemberNumbers` sie aus der Konfiguration kennen. Das wäre aufwendiger, ohne dass es gebraucht
  wird, denn bei der Migration ist es ohnehin das Konto 9999.
- **Keine Projektion, keine API:** Die kommen mit der Kontoansicht in 5d.

## 2026-11-17 – Schritt 5b, Teil 2: Buchungen, Saldo und Anteile

Matthias hat diesen Teil zur selbstständigen Umsetzung freigegeben.

**Was:**

- `accounts/domain.py`:
  - Konstanten für die acht Buchungsarten aus dem Plan (`SUBSCRIPTION`, `REFUND`, `TRANSFER`,
    `EXIT`, `LOSS_DEDUCTION`, `PAYOUT`, `LIMITATION_WRITEOFF`, `REVERSAL`).
  - Datenklasse `Booking`: ID (UUIDv7), Art, Soll- und Habenkonto, Betrag in Cent, Anteile,
    Text, Buchungstag und Wertstellung.
  - `Ledger.post_booking(...)` mit den Grundregeln jeder Buchung, Event `booking.posted`.
  - Abfragen `balance(number)`, `shares(number)` und `bookings_of(number)`.
- `tests/test_ledger.py`: 19 neue Fälle, u. a. Vorzeichen, Ausscheiden (Anteile weg, Saldo
  bleibt), Auszahlung, jede Eingabeprüfung, kein Minus auf Mitgliedskonten, kein Event bei
  Fehler, Laden aus dem echten Event Store. Geprüft mit `uv run pytest` (273 grün),
  `uv run ruff check .`, `uv run ruff format --check .` und `uv run pyright`.
- `Plan.md`: Grundregeln, Vorzeichen und Berechnung von Saldo und Anteilen eingetragen.

**Warum so:**

- **Nur die Grundregeln im Hauptbuch:** Was für *jede* Buchung gilt, prüft `post_booking`. Was nur
  für eine Art gilt (Eintritt: Betrag = Anteile × Preis, Umbuchung: nicht auf das
  Genossenschaftskonto), gehört zu den Vorgängen in 5c bis 5h. So bleibt `post_booking` kurz,
  und jede Regel steht dort, wo man sie sucht.
- **Haben positiv, Soll negativ:** So steht es in `Konzeption.md`. Der Saldo eines Mitgliedskontos
  ist dann, was die Genossenschaft dem Mitglied schuldet, und das Genossenschaftskonto wird mit
  jedem Eintritt negativ, wie im Altsystem.
- **Anteile buchen wie Beträge:** Dieselbe Regel für beide macht das Ausscheiden einfach: Anteile
  gehen auf das Genossenschaftskonto, der Betrag 0 lässt den Saldo als Anspruch stehen.
- **Saldo berechnen statt speichern:** Ein gespeicherter Saldo könnte von den Buchungen abweichen.
  Für die Zahl der Buchungen im Dorfladen ist das Aufsummieren schnell genug. Für Listen und
  Kontoansicht kommt später eine Projektion.
- **Wertstellung nicht nach dem Buchungstag:** Wie bei Zulassung und Ablehnung wird erfasst, was
  geschehen ist. Ein Zahlungseingang von letzter Woche ist erlaubt, einer von morgen nicht.
- **`booking_date` als Parameter:** Der Service übergibt später `date.today()`, die Tests ein
  festes Datum, damit sie nicht vom Tag abhängen.
- **Eigene ID je Buchung:** Das Storno (5e) braucht eine Referenz auf die Originalbuchung. Die
  Event-ID wäre auch eindeutig, aber eine eigene ID im Event bleibt bei einer Migration stabil
  und ist im Code leichter zu finden.
- **Noch kein Service:** Es gibt noch keinen Vorgang, der bucht. Der erste Service kommt mit dem
  Eintritt in 5c, ebenso die Wiederholung bei `ConcurrencyError`.


## 2026-11-17 – Schritt 5c, Teil 1: Eintritt, Rückzahlung, Status „Mitglied“

Schritt für Schritt umgesetzt, mit Erklärung und Freigabe je Unterschritt.

**Was:**

- Entscheidungen in `Plan.md`:
  - Variante A: Der Service hält den Geldeingang am Mitglied fest (`member.paid-in`).
  - 5c ist in zwei Teile aufgeteilt (Domäne/Services, dann API).
  - Neuer Schritt 5i für weitere Anteile.
  - Rückzahlung zum aktuellen Anteilspreis.
  - Die API bucht nur über fachliche Vorgänge.
  - Offener Punkt: Schemaänderungen an Projektionen.
- Unterschritt 1, Mitglied:
  - `members/status.py`: Status `MEMBER` („Mitglied“), `MembershipDates.payment_date` und
    `entry_date()`, das spätere Datum von Zulassung und Geldeingang.
  - `members/domain.py`:
    - `Member.record_payment(payment_date, today)` erzeugt das Event `member.paid-in`, nur
      einmal und nicht nach Ablehnung oder Rücknahme.
    - Neue Abfrage `entry_date()`.
    - `withdraw` lehnt ab, wenn die Person schon Mitglied ist.
- Unterschritt 2, neue Datei `accounts/bookings.py`:
  - `subscribe(...)` (Eintritt) und `refund(...)` (Rückzahlung) liefern ein
    `BookingResult(booking, warning)`.
  - Gemeinsamer Ablauf in `_book`: laden, prüfen, buchen, abgleichen, dann Hauptbuch und Mitglied
    zusammen speichern (`save_all`). Bei `ConcurrencyError` wird bis zu dreimal wiederholt.
  - Abgleich in `_reconcile`: Stimmen eingezahlte und gezeichnete Anteile genau überein, wird
    `record_payment` mit der Wertstellung aufgerufen. Sonst kommt eine Warnung zurück:
    zu wenig, zu viel, oder Antrag abgelehnt.
- Unterschritt 3, Projektion:
  - `members/projections.py`: Spalte `payment_date` und Handler für `member.paid-in`. Liste und
    Suche zeigen damit den Status „Mitglied“.
  - `frontend/src/members.ts`: Label „Mitglied“.
  - `DEV_HINTS.md`: was nach einer Schemaänderung zu tun ist.
- Tests:
  - `tests/test_members_domain.py`: 8 neue Fälle.
  - Neue Datei `tests/test_bookings.py` mit 17 Fällen, darunter Teilzahlung, Überzahlung mit
    Rückzahlung des Überschusses, Zahlung nach Ablehnung, gleichzeitige Buchung und der Weg bis
    in die Liste.
- Geprüft mit `uv run pytest` (299 grün), `uv run ruff check .`, `uv run ruff format --check .`,
  `uv run pyright` und im Frontend `npm run type-check`.
- Dev-Daten: `backend/data/projections.sqlite` gelöscht, damit die neue Spalte entsteht. Beim
  Start wurde die Projektion aus dem Event Store neu aufgebaut.

**Warum so:**

- **Der Status bleibt aus den Fakten berechnet:** Das Mitglied speichert nur das Datum des
  Geldeingangs, wie zuvor Zulassung und Ablehnung. „Mitglied“ ist, wer beides hat. Ab dem
  späteren der beiden Daten gilt die Person als Mitglied. Darum funktioniert die Reihenfolge
  Zulassung, dann Zahlung genauso wie Zahlung, dann Zulassung.
- **Die API bucht nur über Vorgänge:** Jeder Vorgang prüft seine eigenen Regeln, `post_booking`
  nur die Grundregeln. Wer bucht, kann so die Fachlichkeit nicht umgehen. Es gibt also keinen
  Endpunkt, mit dem man frei buchen kann.
- **Eigene Datei `bookings.py`:** `members/services.py` importiert `accounts/services.py`, weil mit
  dem Antrag das Konto eröffnet wird. Die Buchungsvorgänge brauchen umgekehrt das Mitglied. In
  einer dritten Datei gibt es keinen Importzyklus.
- **Wiederholen mit frischem Stand:** Bucht jemand gleichzeitig, scheitert das Speichern an der
  Versionsprüfung des Hauptbuchs. Der neue Versuch rechnet mit dem aktuellen Kontostand, sonst
  könnte der Abgleich den Geldeingang verpassen. Der Test simuliert genau das.
- **Warnung statt Fehler bei falschem Betrag:** Das Geld ist auf dem Bankkonto angekommen und muss
  gebucht werden. Die Mitgliedschaft kommt erst zustande, wenn der Vorgang geklärt ist (siehe
  Plan).
- **Strengere Rückzahlungsregel:** Zurückgezahlt wird nur bei abgelehntem oder zurückgenommenem
  Antrag oder bei ungeklärter Zahlung. Das schließt auch den Fall aus, dass jemand passend gezahlt
  hat, das Geld zurückbekommt und nach der Zulassung „Mitglied“ mit 0 Anteilen wäre.
- **Rücknahme nur, solange die Person nicht Mitglied ist:** Für Mitglieder gibt es später die
  Kündigung (5f).
- **Schemaänderung vorerst durch Löschen der Projektion:** `CREATE TABLE IF NOT EXISTS` ändert
  bestehende Tabellen nicht. Solange es nur Dev-Daten gibt, reicht Löschen und Neuaufbau. Vor dem
  Produktivbetrieb braucht es eine Lösung (offener Punkt im Plan).

## 2026-11-17 – Schritt 5c, Teil 2: API für Eintritt, Rückzahlung und Kontostand

**Was:**

- Neue Datei `accounts/schemas.py`:
  - `AccountView`: Nummer, Art, Inhaber, Saldo, Anteile, aktueller Anteilspreis und alle
    Buchungen. Die Dataclass `Booking` dient direkt als Feldtyp.
  - `BookingResponse`: das Konto nach der Buchung und ggf. eine Warnung.
  - `ShareBooking`: der Befehl mit Kontonummer, Anteilen, Wertstellung und optionalem Text.
- Neue Datei `accounts/api.py`:
  - `GET /api/accounts/{number}` dürfen beide Buchhaltungsrollen aufrufen.
  - `POST /api/accounts/subscribe` und `POST /api/accounts/refund` darf nur die Buchhaltung
    aufrufen.
  - In `app.py` eingehängt.
- `accounts/bookings.py`: `subscribe` und `refund` nehmen jetzt die Kontonummer statt der
  Mitglieds-ID. Den Inhaber finden sie im Hauptbuch.
  - Eine unbekannte Nummer ergibt `NotFoundError` (404).
  - Das Genossenschaftskonto als Ziel ergibt einen `DomainError` (400).
  - Ein leerer Text wird zu „Eintritt“ bzw. „Rückzahlung“.
- `members/schemas.py` und `frontend/src/members.ts`: Die Detailansicht hat jetzt
  `payment_date` und `entry_date`.
- `Plan.md`: Kontonummer in der API eingetragen.
- Tests:
  - Neue Datei `tests/test_accounts_api.py` mit 14 Fällen, unter anderem Eintritt bis zum Status
    „Mitglied“, Warnung, ein mitgeschickter Betrag wird ignoriert, Rückzahlung, 400, 404,
    Genossenschaftskonto, Rechte, ohne Anmeldung.
  - `tests/test_bookings.py` auf Kontonummern umgestellt, dazu drei neue Fälle.
- Geprüft mit `uv run pytest` (314 grün), `uv run ruff check .`, `uv run ruff format --check .`,
  `uv run pyright` und `npm run type-check`.

**Warum so:**

- **Kontonummer statt Mitglieds-ID:** Matthias fand `/api/accounts/{nummer}` natürlicher. Damit
  ist auch das Genossenschaftskonto abrufbar. Die Befehle tragen dieselbe Nummer, damit die API
  das Konto überall gleich anspricht.
- **Kein Betrag im Befehl:** Der Service rechnet Anteile × aktuellen Preis. Wer die API aufruft,
  kann keinen abweichenden Betrag buchen. Pydantic ignoriert unbekannte Felder wie `amount`, ein
  Test zeigt das.
- **Antwort mit Kontoansicht und Warnung:** Das Frontend zeigt nach dem Buchen gleich den neuen
  Stand und die Warnung, ohne die Daten noch einmal zu laden, wie bei den Mitglieds-Befehlen.
- **Anteilspreis in der Kontoansicht:** Die Buchungsmaske (5d) kann den Betrag vorab anzeigen,
  ohne dass es dafür einen eigenen Endpunkt braucht.
- **Ohne Anmeldung 401, auch bei POST:** Die Anmeldung wird vor dem CSRF-Token geprüft. Ich hatte
  zuerst 403 erwartet, der Test hat das richtiggestellt.

## 2026-11-17 – Schritt 5d, Teil 1: Kontoansicht

**Was:**

- Neue Datei `frontend/src/accounts.ts`:
  - Typen `AccountView` und `Booking` passend zur API, dazu `getAccount()`.
  - Texte zu den acht Buchungsarten.
  - `formatEuro()` rechnet mit ganzen Cent wie `format_euro` im Backend.
  - `signedFor()` liefert Betrag und Anteile aus Sicht eines Kontos, `counterAccount()` das
    Gegenkonto.
- Neue Seite `frontend/src/views/accounts/AccountView.vue`, Route `/accounts/:number`, für beide
  Buchhaltungsrollen:
  - Oben stehen Inhaber mit Status, Saldo, Anteile, gezeichnete Anteile, Geldeingang, Eintritt
    und Anteilspreis.
  - Darunter folgt die Buchungstabelle, die älteste zuerst, mit dem Gegenkonto als Link.
- Menü: neuer Eintrag „Gen.-Kto“ mit dem Tooltip „Genossenschaftskonto“. Das ausgeschriebene Wort
  ragte über die Seitenleiste hinaus. Menüeinträge nehmen jetzt ein vollständiges Routenziel mit
  Parametern und optional einen `hint`.
- Mitglied-Detailseite: „Geldeingang am“, „Eintritt am“ und ein Knopf „Konto anzeigen“.
- Status-Tag „Mitglied“ in Grün, über `statusTagClass()` in Suche, Detail- und Kontoansicht.
- `Plan.md`: 5d in Teil 1 (Ansicht) und Teil 2 (Buchungsmaske) aufgeteilt.
- `DEV_HINTS.md`: Abschnitt „API in der Browser-Konsole ausprobieren“.
- Geprüft mit `npm run type-check` und `npm run build`. Matthias hat die Seiten im Browser
  angesehen und abgenommen.

**Warum so:**

- **`watch` statt `onMounted`:** Ein Klick auf das Gegenkonto bleibt auf derselben Seite, nur der
  Parameter ändert sich. Vue verwendet die Komponente weiter, `onMounted` liefe nicht noch
  einmal, und die Seite zeigte das alte Konto. `watch(..., { immediate: true })` lädt beim
  ersten Anzeigen und bei jedem neuen Parameter.
- **Vorzeichen aus Sicht des Kontos:** Dieselbe Buchung steht auf dem Mitgliedskonto mit +, auf
  dem Genossenschaftskonto mit −, wie `balance()` im Backend rechnet. So passt die Summe der
  Tabelle immer zum Saldo.
- **Euro selbst formatieren statt mit `Intl`:** Das Ergebnis sieht genauso aus wie im Backend
  und hängt nicht von den Spracheinstellungen des Browsers ab.
- **Browser-Konsole statt Swagger:** Swagger kann den CSRF-Header nicht mitschicken. In der
  Konsole hat man Cookie und Token der angemeldeten Sitzung.

## 2026-11-17 – Schritt 5d, Teil 2a: Buchungsbefehle im Frontend

**Was:**

- `frontend/src/accounts.ts` erweitert:
  - Typen `ShareBooking` (Befehl) und `BookingResponse` (Konto danach plus Warnung) passend zu
    `accounts/schemas.py`.
  - `subscribe()` und `refund()` rufen `POST /api/accounts/subscribe` bzw. `/refund` auf.
  - `parseEuro()` macht aus der Eingabe im Betragsfeld ganze Cent, in deutscher Schreibweise:
    Komma als Dezimaltrenner, Punkte als Tausendertrenner („1.500,50“, „150,5“, auch mit
    €-Zeichen). Ungültiges ergibt `null`.
  - `sharesForAmount()` rechnet einen Betrag in Anteile um. Geht der Betrag nicht glatt auf,
    ergibt das `null`.
- Geprüft mit `npm run type-check`. Die beiden Rechenfunktionen habe ich in ein Wegwerfskript
  kopiert und mit `node check.ts` an Beispielen ausprobiert. Node 24 versteht TypeScript direkt,
  weil es die Typangaben einfach weglässt.

**Warum so:**

- **Kein Betrag im Befehl:** Der Server rechnet Anteile × aktuellen Preis selbst. So kann das
  Frontend keinen Betrag schicken, der nicht zum Preis passt.
- **Komma für Cent, Punkte für Tausender (Matthias' Vorgabe):** Die Tausenderpunkte müssen
  richtig gruppiert sein, also immer genau drei Ziffern dahinter. „150.50“ wird deshalb abgelehnt
  und nicht stillschweigend als 15.050 € gelesen.
- **Mit ganzen Cent gerechnet:** Der Text wird in Euro- und Centteil zerlegt, nicht über
  `parseFloat`. So entsteht kein Rundungsfehler wie bei 0,1 + 0,2.

## 2026-11-17 – Schritt 5d, Teil 2b: Buchungsmaske für Eintritt und Rückzahlung

**Was:**

- Neue Komponente `frontend/src/views/accounts/BookingForm.vue`:
  - Felder Buchungsart (Eintritt/Rückzahlung), Anteile, Betrag, Wertstellung und Buchungstext.
  - Anteile und Betrag füllen sich gegenseitig: Anteile eingetippt → Betrag = Anteile × Preis;
    Betrag eingetippt → `parseEuro()` und `sharesForAmount()` ergeben die Anteile. Geht der Betrag
    nicht glatt im Anteilspreis auf, erscheint ein Hinweis, und „Buchen“ bleibt gesperrt.
  - Wertstellung vorbelegt mit heute, `max` = heute. Leerer Text → `null`, das Backend setzt dann
    „Eintritt“ bzw. „Rückzahlung“ ein.
  - Beim Buchen ruft sie `subscribe()` bzw. `refund()` auf, zeigt Erfolg, Warnung (gelb) oder
    Fehler (rot) an, leert die Felder und meldet das neue Konto mit `emit('booked', …)`.
- `AccountView.vue`: blendet die Maske ein, wenn `canBook` gilt (Rolle Buchhaltung,
  Mitgliedskonto, Anteilspreis gesetzt). `onBooked()` übernimmt das Konto aus der Antwort und lädt
  den Inhaber neu, damit Status, Geldeingang und Eintritt sofort stimmen.
- Geprüft mit `npm run type-check` und einem Probe-Build (`vite build` in ein Wegwerfverzeichnis).

**Warum so:**

- **Eigene Komponente:** `AccountView` bleibt die Anzeige; Storno, Umbuchung usw. kommen später
  in die Maske, ohne die Kontoseite aufzublähen.
- **Props hinein, Emits hinaus:** Die Maske bekommt Kontonummer und Anteilspreis von der
  Elternseite und ändert selbst nichts an deren Daten. Sie meldet nur „gebucht, hier das neue
  Konto“; die Elternseite entscheidet, was sie damit macht. So bleibt klar, wem welche Daten gehören.
- **`@input` statt `watch` für die Umrechnung:** Würden sich beide Felder gegenseitig beobachten,
  löste jede Änderung die andere wieder aus. Mit `@input` reagiert nur das Feld, in dem gerade
  getippt wird.
- **Nur Anteile an den Server:** Der Betrag ist reine Anzeige; der Server rechnet selbst
  (siehe Plan, „Die API bucht nur über fachliche Vorgänge“).
- **Knopf während der Anfrage gesperrt (`busy`) und `finally`:** verhindert Doppelbuchungen durch
  Doppelklick; `finally` gibt den Knopf auch nach einem Fehler wieder frei.
- **`share_price!` im Template:** Das Ausrufezeichen sagt TypeScript „ist hier nicht null“. Das
  stimmt, weil `canBook` es vorher prüft, TypeScript kann das über das `v-if` aber nicht erkennen.

## 2026-11-18 – Startskript `dev.sh` für die Entwicklung

**Was:**

- Neues Skript `dev.sh` im Projektordner (ausführbar mit `chmod +x dev.sh`). `./dev.sh` startet
  uvicorn (Backend, mit `--reload`) und Vite (Frontend) zusammen, Strg+C beendet beide.
- `DEV_HINTS.md`, Abschnitt „Starten“: `./dev.sh` ist jetzt der Normalfall, die zwei Terminals
  bleiben als Alternative beschrieben.
- Geprüft: Skript gestartet, `/healthz` direkt (Port 8000) und über den Vite-Proxy (Port 5173)
  abgefragt, mit SIGINT (wie Strg+C) beendet, danach mit `ss -ltn` und `ps` kontrolliert, dass die
  Ports frei sind und kein Prozess übrig bleibt.

**Warum so:**

- **`&`:** startet einen Befehl im Hintergrund, so laufen beide Server gleichzeitig.
- **`( cd backend && … )`:** Die Klammern bilden eine Subshell; das `cd` gilt nur darin.
- **`cd "$(dirname "$0")"`:** `$0` ist der Pfad des Skripts. So funktioniert der Aufruf aus jedem
  Ordner.
- **`trap 'kill 0' EXIT`:** Beim Ende des Skripts (auch durch Strg+C) geht ein Signal an die ganze
  Prozessgruppe. Damit enden auch die Unterprozesse, die `uv`, uvicorn (`--reload`) und `npm`
  selbst starten, und nichts bleibt im Hintergrund hängen.
- **`wait -n`:** wartet, bis *einer* der beiden Server endet. Stürzt etwa das Backend ab, läuft das
  Skript weiter zum Ende, der `trap` greift und beendet auch das Frontend. So läuft nie unbemerkt
  nur noch eine Hälfte.
- **Bewusst einfach:** Eine Variante mit `start`/`stop`/`status`, PID- und Logdateien hielte das
  Terminal frei, wäre aber dreimal so lang und fehleranfälliger (verwaiste PID-Dateien). KISS.
- **Stolperfalle beim Testen:** `pgrep -f dev.sh` bzw. `pkill -f …` finden auch den eigenen
  Prüfbefehl, weil das Suchwort in dessen Kommandozeile steht. `pkill` beendet dann sich selbst.

## 2026-11-18 – Mitgliedsseite und Buchungsmaske schmal und mittig

**Was:**

- `MemberDetailView.vue`: Der ganze Seiteninhalt steckt in einem Rahmen `<div class="card-center">`
  (max. 600 px breit, mittig), wie die Antragsmaske. Der Diff ist groß, aber nur wegen der neuen
  Einrückung; `git diff -w` (Leerraum ignorieren) zeigt die eigentlichen drei Zeilen.
- `BookingForm.vue`: Die Karte „Neue Buchung“ hat `class="card card-center"`.
- Die Kontoübersicht und die Buchungstabelle auf der Kontoseite bleiben breit.

**Warum so:**

- **Vorhandene Klasse statt neuem CSS:** `card-center` aus `style.css` setzt `max-width: 600px`,
  `width: 100%` (schrumpft auf dem Handy mit) und `margin-left/right: auto`. Mit `auto` auf beiden
  Seiten verteilt der Browser den freien Platz gleichmäßig, das zentriert den Block.
- **Ein Rahmen statt Klasse an jeder Karte:** So werden auch der Knopf „Zur Suche“ und die
  Meldungen über den Karten schmal und stehen bündig mit ihnen.
- **Tabelle breit:** Die Buchungstabelle braucht Platz für ihre Spalten, sonst wird sie gequetscht.
- **Kein Prettier:** Es ist im Projekt nicht eingerichtet; ein Lauf hätte die ganze Datei
  umformatiert. Fremde Formatierungsänderungen gehören nicht in einen fachlichen Commit.

## 2026-11-18 – Entscheidungen zum Storno (Schritt 5e) im Plan

**Was:** In `Plan.md` eingetragen:

- „Buchungen und Storno“: Wertstellung des Stornos = Wertstellung der Originalbuchung; die
  Statusauswirkung ist jetzt geregelt. Ein Storno nimmt den Geldeingang am Mitglied zurück
  (Gegen-Event, Arbeitsname `member.paid-in-revoked`) bzw. hält ihn neu fest (Storno einer
  Rückzahlung), immer mit Warnung.
- „Hauptbuch“: Verweis auf diese Regel.
- „Vorgehen“: 5e in drei Teile gegliedert (Domäne/Service, API `POST /api/accounts/reverse`,
  Frontend).

**Warum so:**

- **Widerspruch aufgelöst:** Der Plan sagte einmal „Status nicht still zurücksetzen, nur warnen“,
  an anderer Stelle „Gegen-Event am Mitglied“. Jetzt gilt beides zusammen: Der Status folgt den
  Buchungen, aber nie still. So zeigt die App keinen Status „Mitglied“ an, dessen Grundlage fehlt.
- **Wertstellung wie das Original:** Das Storno soll die Buchung so aufheben, als hätte es sie nie
  gegeben, auch in Reports zu einem früheren Stichtag.
- **`reverse` im Endpunkt:** Storno heißt laut Glossar `reversal`.

## 2026-11-18 – Schritt 5e, Teil 1: Storno in Domäne und Service

**Was:**

- `accounts/domain.py`:
  - `Booking` hat das Feld `reverses` (ID der stornierten Buchung, sonst `None`). Es steht auch
    im Event `booking.posted`. Beim Einlesen `data.get("reverses")`, damit ältere Events ohne das
    Feld weiter laden.
  - `Ledger.reverse(booking_id, text, booking_date)`: prüft „Buchung gibt es“, „ist kein Storno“,
    „noch nicht storniert“ und bucht dann über `post_booking` mit vertauschten Konten, gleichem
    Betrag, gleichen Anteilen und der Wertstellung des Originals.
  - `booking(id)` und `reversal_of(id)` zum Nachschlagen.
- `members/domain.py`: `Member.revoke_payment()` mit dem Event `member.paid-in-revoked`; setzt
  `payment_date` zurück, damit entfallen Eintrittsdatum und Status „Mitglied“. Die Projektion
  setzt `payment_date` auf `NULL`.
- `accounts/bookings.py`:
  - `reverse(db, booking_id, reason, today, actor)`: Grund ist Pflicht und kommt in den Text
    („Storno zu „Eintritt“: …“), dann derselbe Ablauf `_book` wie bei Eintritt und Rückzahlung.
  - Die Prüfung „mindestens ein Anteil“ ist aus `_book` in `_ensure_shares` gewandert, das
    Eintritt und Rückzahlung aufrufen; beim Storno gibt es keine eingegebene Anzahl.
  - `_reconcile` bekommt die ganze Buchung statt nur der Wertstellung. Neu: Ist ein Geldeingang
    erfasst, passen die Anteile aber nicht mehr, wird er mit Warnung zurückgenommen. Erfasst ein
    Storno den Geldeingang neu, gibt es ebenfalls eine Warnung.
- Tests in `test_ledger.py`, `test_members_domain.py` und `test_bookings.py`; geprüft mit
  `uv run pytest` (330 grün), `uv run ruff check` und `uv run pyright`.
- `Plan.md`: Referenz im Event statt „Projektion mit Referenz“ (die Buchungen haben keine eigene
  Projektion, die Kontoansicht liest das `Ledger`); Stornogrund steht im Buchungstext.

**Warum so:**

- **Storno über `post_booking`:** Alle Grundregeln gelten damit auch für das Storno, insbesondere
  „Mitgliedskonto nicht ins Minus“. Ein Eintritt, der schon zurückgezahlt ist, lässt sich so nicht
  stornieren, ohne dass `reverse` das eigens prüfen muss.
- **Grund im Text (Variante A):** kein zusätzliches Feld in Event, Klasse, API und Tabelle; in
  der Kontoansicht ist der Grund sofort lesbar.
- **Neues Feld mit Vorgabewert `None`:** So brauchen bestehende Aufrufe und alte Events keine
  Änderung. Event Sourcing verlangt, dass alte Events immer lesbar bleiben; daher `data.get`.
- **Ein Zweig, den es heute noch nicht gibt:** Dass ein Storno den Geldeingang *neu* erfasst, kann
  mit den heutigen Vorgängen nicht eintreten (wer die gezeichneten Anteile erreicht, hat sofort
  den Geldeingang, danach ist keine Rückzahlung mehr erlaubt). Der Zweig steht trotzdem drin, weil
  der Plan es so festlegt und spätere Vorgänge (5i, weitere Anteile) ihn brauchen können. Getestet
  wird er direkt über `_reconcile`. Mein erster Testfall dafür war falsch und schlug fehl, daran
  ist das aufgefallen.
- **`revoke_payment` ohne Datum:** Das Event hält nur die Tatsache fest; wann storniert wurde,
  steht in der Eventzeit und in der Stornobuchung.

## 2026-11-18 – Rollenkonstante im Menü englisch benannt

**Was:** In `frontend/src/App.vue` heißt die Konstante `FACHLICH` jetzt `ACCOUNTING_ROLES`, mit
einem deutschen Kommentar, wofür sie steht. Geprüft mit `npm run type-check`.

**Warum:** Bezeichner sind im Projekt englisch (AGENTS.md); `FACHLICH` war ein Ausreißer. Der
neue Name sagt, was drinsteht (die beiden Buchhaltungsrollen), und passt zu `ROLES` im Backend.

## 2026-11-18 – Schritt 5e, Teil 2: Storno in der API

**Was:**

- `accounts/schemas.py`: Befehl `ReverseBooking` mit `booking_id` und `reason` (höchstens 200
  Zeichen, wie der Text bei Eintritt und Rückzahlung).
- `accounts/api.py`: `POST /api/accounts/reverse`, nur für die Rolle Buchhaltung. Antwortet wie
  die anderen Befehle mit der Kontoansicht und ggf. der Warnung.
- `accounts/bookings.py`: Die Regel „welches Konto ist das Mitgliedskonto einer Buchung“ steht
  jetzt in `member_account_of(booking)`; der Service und die API nutzen sie beide.
- Tests in `test_accounts_api.py`: Storno mit Warnung und zurückgenommenem Geldeingang, doppeltes
  Storno und Storno eines Stornos (400), fehlender Grund (400), unbekannte Buchung (404), Rolle
  „Buchhaltung lesend“ (403). Geprüft mit `uv run pytest` (336 grün), `uv run ruff check` und
  `uv run pyright`.

**Warum so:**

- **Nur die Buchungs-ID im Body:** Das Konto ergibt sich aus der Buchung. Müsste das Frontend die
  Kontonummer mitschicken, könnte sie falsch sein, und der Service müsste das extra prüfen.
- **Konto für die Antwort aus der Gegenbuchung:** Der Service gibt die Stornobuchung zurück; deren
  Mitgliedskonto ist dasselbe wie beim Original. Eine Hilfsfunktion statt der Regel an zwei Stellen.
- **Kein Feld „storniert durch“ im Backend:** Original und Storno stehen immer auf demselben Konto,
  also in derselben Liste der Kontoansicht. Das Frontend findet das Storno zu einer Buchung, indem
  es nach `reverses == id` sucht. Ein eigenes Ansichtsmodell für Buchungen bräuchte es dafür nicht.

## 2026-11-18 – Schritt 5e, Teil 3: Storno im Frontend

**Was:**

- `frontend/src/accounts.ts`: `Booking` hat das Feld `reverses`; neu sind `ReverseBooking` und
  `reverse()` für `POST /api/accounts/reverse`.
- `frontend/src/views/accounts/AccountView.vue`:
  - `reversalOf` (`computed`): eine `Map` von der ID des Originals zu seinem Storno. Damit sieht
    jede Zeile, ob sie storniert ist; ein Storno erkennt man an `reverses`.
  - Original und Storno sind grau (CSS-Klasse `reversed`), beim Original steht „storniert am …“.
  - Knopf „Stornieren“ in einer eigenen Spalte, nur für die Buchhaltung und nur bei Buchungen,
    die weder Storno noch schon storniert sind; auf jedem Konto.
  - Der Grund wird mit `window.prompt` abgefragt; Abbrechen oder leerer Grund tut nichts.
  - Nach dem Storno: Warnung als gelbe Box über der Tabelle. Auf dem Mitgliedskonto wird die
    Antwort übernommen und der Inhaber neu geladen (`onBooked`), auf dem Genossenschaftskonto
    wird das angezeigte Konto neu geladen, weil der Server das Mitgliedskonto zurückgibt.
  - Checkbox „Stornierte ausblenden“; `visibleBookings` (`computed`) filtert die Paare heraus.
- `Plan.md`: Storno auf jedem Konto, Grund per Browser-Dialog, „storniert durch“ im Frontend.
- Geprüft mit `npm run type-check`.

**Warum so:**

- **`computed` statt Daten zu ändern:** Paare und Filter sind aus der Buchungsliste abgeleitet.
  Vue rechnet sie neu, sobald sich die Liste ändert; die Liste selbst bleibt wie vom Server.
- **`Map` statt Suche je Zeile:** Einmal durch die Liste laufen und danach nur nachschlagen ist
  einfacher zu lesen als in jeder Zeile alle Buchungen zu durchsuchen.
- **`window.prompt`:** wenig Code, wie `confirm` beim Löschen von Benutzern. Ein eigenes
  Eingabefeld kann später kommen.
- **Auch auf dem Genossenschaftskonto:** Matthias' Entscheidung; es gibt keinen fachlichen Grund,
  es dort zu verbieten. Das Backend findet das Mitgliedskonto selbst aus der Buchung.

## 2026-11-18 – Schritt 5f, Teil 1: Kündigung und Teilkündigung im Backend

**Was:**

- `Plan.md`: 5f nach Vorgang aufgeteilt (Teil 1–4); Entscheidungen „ausgeschieden ab dem 01.01.“,
  „Ausscheidensdatum überschreibbar, solange 31.12. nach dem Eingang“ und „Ausschluss aufheben“.
- `members/status.py`: neue Status `notice_given` („gekündigt“) und `exited` („ausgeschieden“),
  `MembershipDates` mit `notice_date` und `exit_date`, `default_exit_date()` für die Frist.
- `members/domain.py`:
  - Wertetyp `Notice` (ID, Art, Eingang, Ausscheiden, bei Teilkündigung die Anteile); der
    `Member` führt die Liste `notices`.
  - `give_notice` (Event `member.notice-given`), `give_partial_notice`
    (`member.partial-notice-given`), `withdraw_notice` (`member.notice-withdrawn`).
  - Gemeinsame Prüfungen in `_ensure_notice_possible`: Eingang nicht in der Zukunft, am Eingangstag
    Mitglied, noch keine Kündigung der Mitgliedschaft, Ausscheiden ist ein 31.12. nach dem Eingang.
- `members/services.py`: die drei Vorgänge; die Teilkündigung holt die gehaltenen Anteile aus dem
  Hauptbuch. Ohne Ausscheidensdatum gilt die Frist.
- `members/schemas.py` und `members/api.py`: `POST /api/members/give-notice`,
  `/give-partial-notice`, `/withdraw-notice`; die Detailansicht zeigt `notices`, `notice_date`
  und `exit_date`.
- `members/projections.py`: Spalten `notice_id`, `notice_date`, `exit_date`, damit die Suche den
  Status richtig berechnet.
- Tests in `test_members_domain.py` und neu `test_members_notice_api.py`; geprüft mit
  `uv run pytest` (362 grün), `uv run ruff check`, `uv run ruff format --check` und `uv run pyright`.

**Wichtig nach dem Update:** `backend/data/projections.sqlite` löschen. `CREATE TABLE IF NOT
EXISTS` ergänzt keine Spalten in einer bestehenden Tabelle (siehe „Offene Punkte“ im Plan). Fehlt
die Datei, baut `prepare` sie beim Start aus den Events neu auf; es gehen keine Daten verloren.
Angemeldete Sitzungen und Login-Versuche liegen auch in dieser Datei, man muss sich neu anmelden.

**Warum so:**

- **Zwei Vorgänge statt einer erkannten Vollkündigung:** Rechtlich sind es verschiedene
  Erklärungen (§ 65 und § 67b GenG). Außerdem steht so im Event selbst, was gemeint war; die
  Projektion braucht dafür keinen Kontostand.
- **Liste von Kündigungen mit eigener ID:** Teilkündigungen können mehrfach vorkommen, und 5g
  legt je Kündigung einen Auseinandersetzungsanspruch an.
- **Gehaltene Anteile als Parameter:** Das Mitglied kennt sein Konto nicht, das Hauptbuch schon.
  Der Service holt die Zahl und gibt sie mit; die Regel selbst bleibt im Aggregat.
- **Status zuerst „Antragsteller“ prüfen:** Ohne Eintritt gibt es weder Kündigung noch Ausscheiden.
  So bleibt der Status auch dann richtig, wenn ein Storno den Geldeingang zurücknimmt.
- **Für 5g gemerkt:** Ist das Ausscheiden einer Teilkündigung gebucht, sinken die Anteile auf dem
  Konto; diese Teilkündigung darf dann nicht noch einmal abgezogen werden.

## 2026-11-18 – Schritt 5f, Teil 2: Kündigung im Frontend

**Was:**

- `frontend/src/members.ts`: Interface `Notice`, `MemberDetail` mit `notices`, `notice_date`,
  `exit_date`; Statustexte „gekündigt“ (orange) und „ausgeschieden“ (blau); `defaultExitYear()`
  für den Vorschlag; `giveNotice`, `givePartialNotice`, `withdrawNotice`.
- Neue Komponente `frontend/src/views/members/NoticeCard.vue`, Karte „Kündigungen“:
  - Tabelle der laufenden Kündigungen mit Knopf „Zurücknehmen“ (Sicherheitsabfrage `confirm`).
  - Knöpfe „Mitgliedschaft kündigen“ und „Teilkündigung“, nur für die Buchhaltung und nur, wenn
    der Status heute „Mitglied“ ist.
  - Formular: Eingang (heute vorbelegt), Ausscheiden als Jahr zum 31.12. (Vorschlag rechnet per
    `watch` mit, wenn man den Eingang ändert), bei der Teilkündigung die Anteile.
  - Meldet die neue Detailansicht mit `@changed` an die Seite zurück.
- `MemberDetailView.vue`: Karte eingebunden (ab dem Eintritt oder wenn es Kündigungen gibt);
  Kopfkarte zeigt „Kündigung eingegangen“ und „Ausscheiden zum“. Der Knopf „Rücknahme“ (des
  Antrags) erscheint nicht mehr bei Mitgliedern, das Backend lehnt das ohnehin ab.
- Geprüft mit `npm run type-check`.

**Warum so:**

- **Eigene Komponente:** Die Detailseite hat schon fast 500 Zeilen; die Kündigung bringt eigene
  Felder und eigene Meldungen mit. Muster wie `BookingForm.vue`: Prop hinein, Event heraus.
- **Jahresfeld statt Datumsfeld:** Ausgeschieden wird immer zum 31.12. Mit nur dem Jahr lässt
  sich gar kein falsches Datum eingeben; das Backend prüft trotzdem.
- **`watch` statt `computed` für das Jahr:** Das Jahr ist ein Vorschlag, den man überschreiben
  darf. Ein `computed` wäre nur lesbar; `watch` setzt den Wert neu, wenn sich der Eingang ändert,
  und lässt ihn sonst in Ruhe.

### Nachtrag zu 5f-2: Hinweis „teilgekündigt“

**Was:** Matthias wünschte sich, teilgekündigte Mitglieder in der Suche zu erkennen.

- Backend: Die Projektion hat eine zweite Tabelle `partial_notices` (`notice_id`, `member_id`,
  `exit_date`). `member.partial-notice-given` fügt ein, `member.notice-withdrawn` löscht. Die Suche
  ermittelt `partial_notice` per `EXISTS`-Unterabfrage: Gibt es eine Teilkündigung mit
  `exit_date >= heute`? `MemberDetail` hat dasselbe Feld aus `Member.has_partial_notice(today)`.
- Frontend: `showPartialNotice()` in `members.ts`; Suche und Kopfkarte der Mitgliedsseite zeigen
  ein oranges Tag „teilgekündigt“ neben dem Status.
- Tests: Suche und Detail nach Teilkündigung und Zurücknehmen, keine Anzeige bei Kündigung der
  Mitgliedschaft, Ende nach dem 31.12.; 365 grün, ruff, pyright und type-check sauber.
- Wieder `backend/data/projections.sqlite` löschen (neue Tabelle).

**Warum so:**

- **Eigene Tabelle statt Zählspalte:** Beim Zurücknehmen kommt nur die `notice_id`. Mit der
  Tabelle reicht ein `DELETE … WHERE notice_id = ?`; eine Zählspalte wüsste nicht, ob die
  zurückgenommene Kündigung überhaupt eine Teilkündigung war.
- **Datum als Text vergleichen:** ISO-Daten („2026-11-02“) sortieren als Text genauso wie als
  Datum, deshalb funktioniert `p.exit_date >= ?` in SQLite ohne Umwandlung.
- **Nur bei Status „Mitglied“ anzeigen:** Bei „gekündigt“ wäre der Hinweis doppelt.

## 2026-11-18 – Schritt 5f, Teil 3: Tod erfassen

**Was:**

- `members/status.py`: Status `deceased` („verstorben“), `MembershipDates.date_of_death`,
  `effective_exit_date()`: nach einem Tod der 31.12. des Todesjahres, sonst aus der Kündigung.
  Reihenfolge in `status_on`: ausgeschieden, verstorben, gekündigt, Mitglied.
- `members/domain.py`: `record_death` (Event `member.died`) prüft „nicht in der Zukunft“, „noch
  nicht erfasst“ und „am Sterbetag Mitglied oder gekündigt“; `revoke_death`
  (`member.death-revoked`) für Fehlerfassungen; `Member.exit_date()` liefert das wirksame Ausscheiden.
- Briefanrede: `salutation(..., deceased=True)` gab es schon; die Detailansicht übergibt es jetzt.
- Service und API: `POST /api/members/record-death` und `/revoke-death`; `MemberDetail` mit
  `date_of_death`, `exit_date` ist jetzt das wirksame Ausscheiden.
- Projektion: Spalte `date_of_death`, damit die Suche „verstorben“ zeigt.
- Frontend:
  - `members.ts`: `recordDeath`, `revokeDeath`, Status „verstorben“.
  - `MemberDetailView.vue`: Aktion „Tod erfassen“ im vorhandenen Datumsformular, danach ein
    Hinweis mit Knopf „Adresszeilen bearbeiten“, der das Formular öffnet und hinscrollt. Knopf
    „Erfassung des Todes zurücknehmen“ mit Sicherheitsabfrage. Kopfkarte zeigt „Verstorben am“.
  - `NoticeCard.vue`: Kündigungen mit späterem Termin als „gegenstandslos (Tod)“ markiert.
- Tests: 15 neue in `test_members_domain.py` und `test_members_notice_api.py`; 380 grün, ruff,
  pyright und `npm run type-check` sauber.
- Wieder `backend/data/projections.sqlite` löschen (neue Spalte).

**Warum so:**

- **Wirksames Ausscheiden berechnet, nicht gespeichert:** Der Tod zieht das Ausscheiden vor, die
  Kündigung bleibt dabei unverändert. Nimmt man die Erfassung des Todes zurück, gilt automatisch
  wieder die Kündigung. Das ist der Vorteil, Status und Termine aus Fakten zu berechnen.
- **Tod nur bei Mitgliedern:** Ein Antragsteller hat keine Mitgliedschaft, die auf Erben übergehen
  könnte; dafür gibt es die Rücknahme.
- **Zurücknehmen statt Ändern:** Events sind unveränderlich. Eine Korrektur ist ein neues Event, so
  bleibt nachvollziehbar, dass zuerst falsch erfasst wurde.
- **`confirmAction` jetzt `async`:** Erst nach dem Speichern steht fest, ob es geklappt hat; nur dann
  erscheint der Hinweis zu den Erben. Dafür wartet die Funktion mit `await` auf `run()`.

## 2026-11-18 – Schritt 5f, Teil 4: Ausschluss erfassen und aufheben

**Was:** Matthias hat 5f-4 ohne vorherige Einzelerklärung freigegeben („gleich komplett
umsetzen, außer du hast Fragen“); der Plan legte das Wesentliche schon fest.

- `members/status.py`: Status `expelled` („ausgeschlossen“), `MembershipDates.expulsion_date`.
  `effective_exit_date()` nimmt jetzt den frühesten Termin aus Kündigung, Tod und Ausschluss.
  Reihenfolge in `status_on`: ausgeschieden, verstorben, ausgeschlossen, gekündigt, Mitglied.
- `members/domain.py`: `expel` (Event `member.expelled`) prüft „nicht in der Zukunft“, „noch nicht
  erfasst“ und „am Beschlusstag Mitglied oder gekündigt“; `lift_expulsion`
  (`member.expulsion-lifted`) mit Datum, nicht vor dem Ausschluss. `record_death` erlaubt jetzt
  auch Ausgeschlossene (bis zum 31.12. sind sie noch Mitglied).
- Service und API: `POST /api/members/expel` und `/lift-expulsion` (Body wie Zulassung:
  `member_id`, `decision_date`); `MemberDetail` mit `expulsion_date`.
- Projektion: Spalte `expulsion_date`.
- Frontend: Aktionen „Ausschließen“ und „Ausschluss aufheben“ im vorhandenen Datumsformular, je mit
  kurzem Hinweis; Kopfkarte zeigt „Ausgeschlossen am“; Status orange. `NoticeCard.vue` zeigt
  „gegenstandslos (Tod)“ bzw. „gegenstandslos (Ausschluss)“.
- Tests: 14 neue; die Datei `test_members_notice_api.py` heißt jetzt `test_members_exit_api.py`
  (`git mv`), weil sie Kündigung, Tod und Ausschluss abdeckt. 396 grün, ruff, pyright und
  `npm run type-check` sauber.
- Wieder `backend/data/projections.sqlite` löschen (neue Spalte).

**Warum so:**

- **Frühester Termin statt fester Reihenfolge:** Kündigung, Tod und Ausschluss können zusammen
  vorkommen. Die Mitgliedschaft endet mit dem ersten, das greift; `min()` drückt das direkt aus.
- **Aufheben „als nie geschehen“:** Ein erfolgreicher Widerspruch macht den Beschluss unwirksam.
  Weil der Status aus den Daten berechnet wird, gilt nach dem Aufheben automatisch wieder, was
  vorher galt, z. B. die Kündigung, auch rückwirkend über das Jahresende hinweg.
- **Gegenstandslos nur bei Tod oder Ausschluss:** Sonst würde eine Teilkündigung mit späterem Termin
  als die Kündigung der Mitgliedschaft fälschlich markiert; das fiel beim Schreiben auf.
- **`git mv` statt neu anlegen:** So sieht Git die Umbenennung, und die Geschichte der Datei bleibt
  mit `git log --follow` erhalten.

## 2026-11-18 – Schritt 5g, Teil 1: Ausscheiden zum Jahresende im Backend

**Was:**

- `Plan.md`: 5g in zwei Teile; Auseinandersetzungsanspruch je Konto aus dem Saldo; eine
  Ausscheidensbuchung je Konto und 31.12.; nur abgeschlossene Jahre; Warnung in Reports erst mit
  Schritt 6.
- `members/domain.py`: `ExitDue` und `Member.exit_due(day)`: Was scheidet zum 31.12. aus (voll
  und/oder Teilkündigungen) und warum. `partially_noticed_shares` zählt nur Teilkündigungen,
  deren Ausscheiden noch nicht gebucht ist (`booked_exit_dates` aus dem Hauptbuch).
- `accounts/domain.py`: `Ledger.exit_booking(number, day)` und `booked_exit_dates(number)`, beide
  ohne stornierte Buchungen.
- `members/services.py`: `all_members(db)` lädt alle Mitglieder über das Nummernregister; die
  Teilkündigung gibt die gebuchten Termine mit.
- Neu `accounts/exits.py`: `exits_due(db, year)` (Liste mit Grund, Anteilen, Saldo, „gebucht“) und
  `post_exits(db, year, today, actor)` (bucht alle offenen auf einmal, Betrag 0, Wertstellung
  31.12., mit Wiederholung bei gleichzeitiger Buchung wie `_book`).
- `accounts/api.py`: `GET /api/accounts/exits/{year}` (beide Buchhaltungsrollen) und
  `POST /api/accounts/post-exits` mit `{year}` (nur Buchhaltung).
- `accounts/bookings.py`: Beim Storno läuft der Abgleich des Geldeingangs nur noch bei Eintritt und
  Rückzahlung (`_book(..., reconcile=...)`).
- Tests: neu `test_exits.py`, dazu API-Tests in `test_members_exit_api.py`; 410 grün, ruff und
  pyright sauber. Die beiden Tests zu den Korrekturen habe ich gegen den Code ohne Korrektur
  laufen lassen: Sie schlagen dort fehl, prüfen also wirklich etwas.

**Warum so:**

- **„Gebucht“ aus dem Hauptbuch ablesen:** Die Buchung ist der Beweis. Ein zusätzliches Event am
  Mitglied müsste mit der Buchung übereinstimmen und beim Storno mitgepflegt werden; so kann es
  gar nicht auseinanderlaufen.
- **Anspruch aus dem Saldo:** Der Saldo ist ohnehin das, was die Genossenschaft schuldet. Ein
  eigener Anspruchs-Datensatz wäre eine zweite Wahrheit.
- **Abgleich nur beim Eintritt:** „Eingezahlte = gezeichnete Anteile“ gilt nur bis zum ersten
  Ausscheiden. Danach würde der Abgleich ein Storno als Teilzahlung missverstehen.
- **Alle Mitglieder laden statt Projektion:** Einfacher und immer konsistent mit den Aggregaten;
  bei der Größe des Dorfladens schnell genug.
- **Test gegen den Code ohne Korrektur (Mutationstest von Hand):** Ein Test, der auch ohne die
  Korrektur grün wäre, würde nichts absichern.

## 2026-11-18 – Schritt 5g, Teil 2: Seite „Jahresende“

**Was:**

- `frontend/src/accounts.ts`: Interface `ExitEntry`, `exitReasonsLabel()` („Kündigung“,
  „Teilkündigung“, „Tod“, „Ausschluss“), `getExits(year)` und `postExits(year)`.
- Neue Seite `frontend/src/views/accounts/YearEndView.vue`:
  - Jahresfeld, vorbelegt mit dem Vorjahr; `watch` mit `immediate` lädt beim Öffnen und bei jeder
    Änderung neu.
  - Tabelle mit Nummer (Link zum Mitglied), Name, Grund, Anteilen („alle (3)“ bei vollem
    Ausscheiden), Anspruch (Link zum Konto, z. B. für ein Storno) und Status „offen“/„gebucht“.
  - Knopf „Ausscheiden buchen (n)“ nur für die Buchhaltung, nur mit offenen Fällen und nur für
    abgeschlossene Jahre, mit `confirm()`. Für das laufende Jahr ein Hinweis „Vorschau“.
- `router.ts`: Route `/year-end`; `App.vue`: Menüpunkt „Jahresende“.
- Backend: Das Jahr ist in `GET /api/accounts/exits/{year}` (`Path(ge=…, le=…)`) und in
  `PostExits` (`Field(ge=…, le=…)`) auf 1900–2200 begrenzt, mit Test.
- Geprüft mit `npm run type-check`, `uv run pytest` (411 grün), ruff und pyright.

**Warum so:**

- **Jahresgrenze im Backend:** Beim Schreiben der Seite fiel auf, dass Jahr 0 in Python kein
  gültiges Datum ergibt (`date(0, 12, 31)`) und der Server mit 500 antworten würde. Mit der
  Grenze antwortet FastAPI selbst mit 422, bevor unser Code läuft.
- **Nichts laden bei ungültigem Jahr:** Während man „2025“ eintippt, stehen kurz „2“, „20“ und
  „202“ im Feld; dafür soll keine Anfrage an den Server gehen.
- **Anspruch verlinkt auf das Konto:** Dort steht der Storno-Knopf; eine eigene Storno-Funktion auf
  dieser Seite wäre doppelt.

## 2026-11-18 – Schritt 5h, Teil 1: Auszahlung, Verlustvortrag, Verjährung

**Was:**

- `Plan.md`: 5h in drei Teile; Regeln für Auszahlung, Kürzung und Ausbuchung (Wertstellung nach dem
  gebuchten Ausscheiden, Ausbuchung immer über den Rest).
- `accounts/domain.py`: `Ledger.claim(number, share_price)` (Saldo minus Anteile × Preis, nie
  unter 0) und `last_exit_date(number)`.
- `accounts/bookings.py`: `payout`, `deduct_loss`, `write_off` über den gemeinsamen Ablauf
  `_reduce_claim` (Anspruch vorhanden, Ausscheiden gebucht, Wertstellung danach, Betrag 1 Cent bis
  Anspruch; `write_off` nimmt den Rest), alle über `_book(..., reconcile=False)`.
- `accounts/schemas.py` und `api.py`: `ClaimBooking`, `WriteOff`; `POST /api/accounts/payout`,
  `/deduct-loss`, `/write-off`; `AccountView` mit `claim`.
- Frontend:
  - `accounts.ts`: `claim` in `AccountView`, `ClaimBooking`, `payout`, `deductLoss`, `writeOff`.
  - `AccountView.vue`: Zeile „Offener Anspruch“, sobald er größer als 0 ist.
  - `BookingForm.vue` neu geschrieben: zwei Gruppen von Buchungsarten. Mit Anspruch stehen
    Auszahlung, Kürzung Verlustvortrag und Ausbuchung Verjährung zur Wahl (Auszahlung vorgewählt);
    sie zeigen nur das Betragsfeld, die Ausbuchung gar keines (ganzer Rest, mit Sicherheitsabfrage).
    Fällt der Anspruch weg, springt die Auswahl per `watch` auf eine passende Art.
- Tests: neu `test_claims.py`, dazu API-Tests in `test_members_exit_api.py`; 427 grün, ruff,
  pyright und `npm run type-check` sauber.

**Warum so:**

- **Ein gemeinsamer Ablauf für drei Arten:** Sie unterscheiden sich nur in Buchungsart, Text und
  ob der Betrag frei oder der Rest ist. Die Regeln stehen so nur an einer Stelle.
- **Anspruch berechnen statt speichern:** wie in 5g entschieden; Auszahlungen mindern den Saldo,
  damit sinkt der Anspruch von selbst. Ein Storno stellt ihn ebenso von selbst wieder her.
- **`switch` über alle Arten in `send()`:** TypeScript prüft, dass jede Art des Typs `Kind` einen
  Zweig hat. Kommt später eine Art dazu und fehlt der Zweig, meldet `type-check` einen Fehler.
- **`Omit<ClaimBooking, 'amount'>`:** ein TypeScript-Hilfstyp, „ClaimBooking ohne das Feld amount“.
  So muss für die Ausbuchung kein eigenes Interface geschrieben werden.

## 2026-11-18 – Schritt 5h, Teil 2: Seite „Offene Ansprüche“

**Was:**

- Neu `accounts/claims.py`: `open_claims(db, today)` liefert alle Konten mit gebuchtem Ausscheiden
  und offenem Anspruch (`ClaimEntry` mit Nummern, Name, Status, Ausscheiden, Anspruch), das älteste
  Ausscheiden zuerst.
- `accounts/api.py`: `GET /api/accounts/claims` für beide Buchhaltungsrollen, **vor**
  `GET /{number}` definiert.
- Frontend: `ClaimEntry` und `getClaims()` in `accounts.ts`; neue Seite
  `views/accounts/OpenClaimsView.vue` (Tabelle mit Links zu Mitglied und Konto, Summe in `<tfoot>`);
  Route `/claims`; Menüpunkt „Ansprüche“ mit Tooltip „Offene Ansprüche“.
- `Plan.md`: Entscheidungen zur Liste.
- Tests in `test_claims.py` und `test_members_exit_api.py`; 434 grün, ruff, pyright und
  `npm run type-check` sauber.

**Warum so:**

- **Reihenfolge der Routen:** FastAPI prüft die Routen in der Reihenfolge, in der sie definiert
  sind. `/{number}` passt auf jeden einzelnen Pfadteil, also auch auf „claims“, und hätte mit 422
  geantwortet, weil „claims“ keine Zahl ist. Deshalb steht `/claims` davor (mit Kommentar).
  `/exits/{year}` hat zwei Pfadteile und kollidiert deshalb nicht.
- **`sorted` ist stabil:** Bei gleichem Ausscheidensdatum bleibt die Reihenfolge nach
  Mitgliedsnummer erhalten, weil `all_members` schon danach sortiert ist.
- **Summe mit `reduce`:** Array-Methode in JavaScript, die alle Einträge zu einem Wert
  zusammenfasst; hier beginnend bei 0 jeweils plus den Anspruch.

## 2026-11-18 – Schritt 5j, Teil 1: Ausscheiden mit Spende des Anteils (Backend)

**Was:**

- `members/status.py`: `MembershipDates.donation_date`. `effective_exit_date()` nimmt die Spende
  als weiteren Kandidaten, und zwar den Tag selbst, nicht den 31.12. Damit ergibt `status_on()`
  ab dem Folgetag „ausgeschieden“, ohne eigene Sonderregel.
- `members/domain.py`: `donate_shares(donation_date, today)` mit Event `member.shares-donated` und
  `revoke_donation()` mit `member.donation-revoked`. Prüfungen: nicht in der Zukunft, nur einmal,
  am Tag der Spende Mitglied oder gekündigt. Nach der Spende keine neue Kündigung;
  `has_partial_notice()` ist danach falsch; Grund `donated`, falls die Spende genau auf einen
  31.12. fällt.
- `accounts/domain.py`: neue Buchungsart `SHARE_DONATION` („Spende Anteil“).
- `accounts/bookings.py`: Vorgang `donate()` bucht den ganzen Saldo und alle Anteile vom
  Mitgliedskonto an das Genossenschaftskonto und hält die Spende am Mitglied fest (zusammen mit
  `save_all` gespeichert). `reverse()` nimmt bei einer Spendenbuchung die Spende am Mitglied zurück.
- `accounts/api.py`, `schemas.py`: `POST /api/accounts/donate` mit `{account_number, value_date, text}`.
- `members/projections.py`: Spalte `donation_date`, beide Events, Status in der Suche;
  „teilgekündigt“ entfällt nach der Spende. `MemberDetail.donation_date` in der API.
- Tests: neu `test_donation.py` (14 Tests), drei API-Tests in `test_members_exit_api.py`;
  451 grün, ruff und pyright sauber.
- `Plan.md`: Schritt 5j, Abschnitt „Ausscheiden mit Spende des Anteils“, Statusmodell,
  Buchungsarten, Glossar.

**Wichtig für die Entwicklungsdatenbank:** Die Projektion `members` hat eine neue Spalte. Wie unter
„Offene Punkte“ beschrieben, ändert `CREATE TABLE IF NOT EXISTS` eine bestehende Tabelle nicht.
Vor dem nächsten Start also `projections.sqlite` löschen; sie wird aus den Events neu aufgebaut.

**Warum so:**

- **Bewusste fachliche Entscheidung** von Matthias, obwohl rechtlich umstritten (siehe Plan).
- **Ausscheiden über `effective_exit_date`:** Das wirksame Ausscheiden ist schon der früheste
  Termin aus Kündigung, Tod und Ausschluss. Die Spende ist nur ein weiterer Termin, so werden
  laufende Kündigungen automatisch gegenstandslos, und Status, Jahresende und Suche stimmen ohne
  weitere Sonderfälle.
- **Event am Mitglied plus Buchung (Variante A wie beim Geldeingang):** Der Status bleibt aus den
  Events des Mitglieds berechenbar; beides wird gemeinsam gespeichert, also nie nur eines davon.
- **Ganzer Saldo statt Anteile × Preis:** Nach einer gebuchten Teilkündigung kann der Saldo größer
  sein als der Wert der Anteile (offener Anspruch). Gespendet wird alles, das Konto steht danach
  auf 0, und die Person taucht nicht in der Liste der offenen Ansprüche auf.
- **Kein Abgleich mit dem Geldeingang (`reconcile=False`):** Die Spende hat mit dem Eintritt nichts
  zu tun; ein Abgleich würde sonst den Geldeingang zurücknehmen, weil keine Anteile mehr da sind.

## 2026-11-19 – Schritt 5j, Teil 2: Spende des Anteils im Frontend

**Was:**

- `frontend/src/accounts.ts`: Funktion `donate()` für `POST /api/accounts/donate`, Interface
  `ShareDonation`, Text „Spende Anteil“ für die Buchungsart `share_donation` in der Buchungsliste.
- `views/accounts/BookingForm.vue`: neue Buchungsart „Spende Anteil“. Sie hat keine Eingabefelder
  für Anteile oder Betrag, nur Wertstellung und Text, und zeigt, was gespendet wird (alle Anteile,
  ganzer Saldo). Vor dem Buchen fragt `confirm()` nach. Angeboten wird sie nur, solange das Konto
  Anteile hat; dafür bekommt die Maske die neuen Props `shares` und `balance` von `AccountView.vue`.
- `members.ts`, `views/members/MemberDetailView.vue`: Feld `donation_date`, auf der Mitgliederseite
  die Zeile „Anteil gespendet am“.
- Geprüft mit `npm run type-check`.

**Warum so:**

- **In der Buchungsmaske statt als Knopf am Mitglied:** Die Spende ist zuerst eine Buchung. Storniert
  wird sie ebenfalls in der Kontoansicht, das Ausscheiden ergibt sich daraus. So bleibt der Vorgang an
  einer Stelle.
- **Status prüft das Backend:** Ob die Person spenden darf (Mitglied oder gekündigt, nicht
  verstorben, ausgeschlossen oder ausgeschieden), entscheidet `donate_shares()` im Backend. Das
  Frontend blendet die Art nur aus, wenn es nichts zu spenden gibt, und zeigt sonst die Fehlermeldung
  des Servers. So steht die Regel nur an einer Stelle.
- **Bedingung `v-else-if` erweitert:** Das Betragsfeld erscheint jetzt ausdrücklich nur bei
  Auszahlung und Verlustvortrag. Vorher hieß es „alles außer Ausbuchung“, das hätte die Spende
  fälschlich mit eingeschlossen.

## 2026-11-19 – Anforderung: Auswertung der Vorgänge eines Geschäftsjahres

**Was:** In `Plan.md` unter Schritt 6 und im neuen Abschnitt „Auswertung der Vorgänge eines
Geschäftsjahres“ festgehalten: Excel je Geschäftsjahr mit Eintritten, weiteren Anteilen,
Kündigungen, Todesfällen, Ausschlüssen, Spenden, Ausscheiden, Auszahlungen und Umbuchungen.
Kündigungen zählen mit ihrem Eingang, Buchungen mit der Wertstellung, keine Summen, Storniertes und
Zurückgenommenes bleibt weg. Eine gemeinsame Liste mit Spalte „Vorgang“ zum Filtern, Todesfälle mit
dem Sterbedatum, Ausschlüsse mit dem Beschluss des Vorstands.

**Warum:** Matthias will für jedes Geschäftsjahr einen Überblick über alle Vorgänge. Umgesetzt wird
es zusammen mit den anderen Reports in Schritt 6.

## 2026-11-19 – Schritt 5h, Teil 3a: Umbuchung zwischen Mitgliedskonten (Backend)

**Was:**

- `members/status.py`: `MembershipDates.transfer_date`; `effective_exit_date()` nimmt es als
  weiteren Termin, wie die Spende den Tag selbst.
- `members/domain.py`: `ensure_can_give_shares()` (Mitglied, gekündigt, verstorben, Verstorbene
  auch nach dem 31.12.), `ensure_can_receive_shares()` (Mitglied oder zugelassener Antragsteller
  ohne Einzahlung), `transfer_all_shares()` mit Event `member.all-shares-transferred` und
  `revoke_transfer()` mit `member.transfer-revoked`. Nach der Übertragung keine Kündigung mehr,
  `has_partial_notice()` ist danach falsch.
- `accounts/bookings.py`: Vorgang `transfer()`. Neu ist `_book_between()`: wie `_book`, aber mit
  zwei Mitgliedern, gespeichert werden Hauptbuch und beide Mitglieder zusammen. `reverse()` leitet
  das Storno einer Umbuchung an `_reverse_transfer()` weiter.
- `accounts/api.py`, `schemas.py`: `POST /api/accounts/transfer` mit
  `{account_number, target_account_number, shares, value_date, text}`; Antwort mit dem abgebenden Konto.
- `members/projections.py`, `members/schemas.py`: Spalte bzw. Feld `transfer_date`.
- Tests: neu `test_transfer.py` (15 Tests), zwei API-Tests in `test_members_exit_api.py`;
  468 grün, ruff und pyright sauber.
- `Plan.md`: neuer Abschnitt „Umbuchung“, Erben bestätigt, Schritt 5h-3 aufgeteilt in a und b.

**Wichtig für die Entwicklungsdatenbank:** Die Projektion `members` hat wieder eine neue Spalte,
also vor dem nächsten Start `backend/data/projections.sqlite` löschen.

**Warum so:**

- **Erbe über den normalen Eintritt:** Der Erbe stellt einen Antrag über die geerbten Anteile und
  wird zugelassen. Die Umbuchung ersetzt nur seine Einzahlung, deshalb läuft derselbe Abgleich
  (`_reconcile`) wie beim Eintritt. Es gibt keinen Sonderweg „Erbe“.
- **Ausscheiden, wenn nichts mehr da ist:** Wer alle Anteile abgibt, scheidet aus, wie bei der
  Spende über `effective_exit_date`. Beim Storno entscheidet der Kontostand: Sind wieder Anteile da,
  entfällt das Ausscheiden.
- **Abgleich beim Storno nur, wenn die Umbuchung den Empfänger zum Mitglied gemacht hat:** Erkannt
  daran, dass sein Geldeingang die Wertstellung der Umbuchung hat. Ein Mitglied, das nur Anteile
  dazubekommen hat, bleibt so sicher Mitglied.
- **Eigene Funktion `_book_between()` statt `_book` umzubauen:** `_book` bleibt für alle Buchungen
  mit nur einem Mitglied unverändert und leicht zu lesen.
- **Ausscheiden schon gebucht → erst stornieren:** So braucht die App keine zweite Art der
  Umbuchung für den Anspruch.

## 2026-11-19 – Schritt 5h, Teil 3b: Umbuchung in der Buchungsmaske

**Was:**

- `frontend/src/accounts.ts`: `transfer()` und Interface `ShareTransfer` für `POST /api/accounts/transfer`.
- `views/accounts/BookingForm.vue`: Buchungsart „Umbuchung“, angeboten, solange das Konto Anteile
  hat. Feld „Auf Konto“: Nach der Eingabe (Ereignis `@change`, also beim Verlassen des Feldes)
  lädt die Maske Zielkonto und Inhaber und zeigt „Name (Status)“ darunter; eigenes Konto,
  Genossenschaftskonto und unbekannte Nummern ergeben einen Hinweis. Anteile und Betrag wie beim
  Eintritt. Vor dem Buchen eine Rückfrage, bei allen Anteilen mit dem Satz „das Mitglied scheidet
  damit aus“.
- `members.ts`: Feld `transfer_date` und Hilfsfunktion `displayName()`; die Kontoansicht nutzt sie
  jetzt auch statt ihrer eigenen Berechnung.
- `MemberDetailView.vue`: Zeile „Alle Anteile übertragen am“.
- **Fehler aus 5j-2 behoben:** Der Hinweistext der Spende zeigte die Zahl der Anteile nicht. Im
  Template ist `shares` die gleichnamige computed-Variable der Eingabe, nicht die Prop; richtig ist
  `props.shares`.
- Geprüft mit `npm run type-check`.

**Warum so:**

- **Inhaber anzeigen statt nur Nummer:** Eine Umbuchung auf das falsche Konto wäre ärgerlich (Storno
  nötig). Name und Status zeigen sofort, ob das richtige Konto gemeint ist und ob es ein
  Antragsteller (Erbe) oder ein Mitglied ist.
- **Prüfungen doppelt, aber verbindlich nur im Backend:** Eigenes Konto und Genossenschaftskonto
  meldet die Maske schon vorher, damit man nicht erst beim Buchen davon erfährt. Ob abgeben und
  empfangen erlaubt ist, entscheidet das Backend.
- **Namensgleichheit Prop/computed:** In `<script setup>` gewinnt im Template die Variable aus dem
  Skript vor der Prop gleichen Namens. Deshalb `props.shares` ausdrücklich schreiben.

## 2026-11-19 – Schritt 5i, Teil 1: Weitere Anteile zeichnen und einzahlen (Backend)

**Was:**

- `members/domain.py`: `AdditionalSubscription` (ID, Anteile, Datum der Zulassung),
  `subscribe_additional_shares()` mit Event `member.additional-shares-subscribed`,
  `revoke_additional_shares()` mit `member.additional-shares-revoked`, dazu
  `additional_shares_subscribed()` und `total_shares_subscribed()`.
- `accounts/domain.py`: Buchungsart `ADDITIONAL_SHARES` („Weitere Anteile“) und
  `Ledger.paid_additional_shares()`: Anteile aus nicht stornierten Buchungen dieser Art.
- `accounts/bookings.py`: Vorgang `pay_additional_shares()`. Der Abgleich beim Eintritt
  (`_reconcile`) und die Prüfung „bereits eingezahlt“ in `subscribe()` zählen jetzt nur die Anteile
  ohne „Weitere Anteile“.
- `members/services.py`, `api.py`, `schemas.py`: `POST /api/members/subscribe-additional-shares`,
  `POST /api/members/revoke-additional-shares`; die Detailansicht hat `additional_subscriptions`
  und `additional_shares_open`. Dafür bekommt `_detail()` die Datenbank, denn die offenen Anteile
  stehen im Hauptbuch.
- `accounts/api.py`: `POST /api/accounts/pay-additional-shares` (gleicher Body wie der Eintritt).
- Tests: neu `test_additional_shares.py` (10 Tests), ein API-Test; 479 grün, ruff und pyright sauber.
- `Plan.md`: Abschnitt „Weitere Anteile“ ausgeführt, Höchstzahl an Anteilen unter „Offene Punkte“.

**Warum so:**

- **Vereinfachter Ablauf (b):** Die Zulassung durch den Vorstand ist rechtlich nötig und wird mit
  Datum festgehalten, ein eigener Zwischenstatus wie beim Antrag lohnt sich aber nicht.
- **Offen = gezeichnet minus gebucht:** Wie viel eingezahlt ist, steht im Hauptbuch. Das Mitglied
  speichert nur die Zeichnungen; es gibt kein zweites „bezahlt“-Event, das auseinanderlaufen könnte.
- **Warnung aus dem Vorgang:** `book()` legt die Warnung in einer Liste ab, weil eine innere
  Funktion eine Variable der äußeren nicht neu zuweisen kann (dafür bräuchte es `nonlocal`). Eine
  Liste darf sie dagegen verändern. So muss nach dem Buchen nichts neu geladen werden.
- **Abgleich nur mit den Anteilen aus dem Antrag:** Der Eintritt hängt allein an der ersten
  Einzahlung. Ohne die Korrektur würde nach Storno und Neubuchung eines Eintritts fälschlich
  „mehr eingezahlt als gezeichnet“ gemeldet oder die Neubuchung abgelehnt.

## 2026-11-19 – Schritt 5i, Teil 2: Weitere Anteile im Frontend

**Was:**

- `frontend/src/members.ts`: Interface `AdditionalSubscription`, Felder `additional_subscriptions`
  und `additional_shares_open`, Funktionen `subscribeAdditionalShares()` und `revokeAdditionalShares()`.
- `views/members/AdditionalSharesCard.vue` (neu), nach dem Vorbild von `NoticeCard.vue`: Tabelle
  der Zeichnungen (Zulassung, Anteile, „Zurücknehmen“), Hinweis auf noch offene Anteile, Knopf
  „Weitere Anteile zeichnen“ mit Anzahl und Datum der Zulassung. Die Mitgliederseite zeigt die
  Karte ab dem Eintritt.
- `accounts.ts`: `payAdditionalShares()`, Text „Weitere Anteile“ für die Buchungsart.
- `BookingForm.vue`: Buchungsart „Weitere Anteile“, nur solange Anteile offen sind, dann als erste
  Art vorausgewählt. Die Zahl der offenen Anteile reicht `AccountView.vue` als Prop `additionalOpen`
  aus der Detailansicht des Inhabers durch.
- Geprüft mit `npm run type-check`.

**Warum so:**

- **Eigene Karte statt Aktion im Kopf der Mitgliederseite:** Wie bei den Kündigungen gibt es eine
  Liste mit Einträgen, die sich einzeln zurücknehmen lassen. Die Karte hält das zusammen, und
  `MemberDetailView.vue` wächst nicht weiter.
- **Zeichnen am Mitglied, Einzahlen am Konto:** Die Zeichnung ist ein Beschluss über das Mitglied,
  die Einzahlung eine Buchung. Das folgt derselben Trennung wie Antrag und Eintritt.
- **Vorauswahl:** Sind weitere Anteile offen, ist die Einzahlung fast immer das, was gebucht werden
  soll.

## 2026-11-19 – Fehler: Umbuchung ließ sich in der Maske nicht buchen

**Was:** Nach der Eingabe des Zielkontos erschien kein Inhaber, und „Buchen“ blieb gesperrt. Ursache in
`BookingForm.vue`, `onTargetChange()`: `targetText.value.trim()`. Das Feld ist ein
`<input type="number">`, und dabei macht `v-model` aus der Eingabe von selbst eine Zahl, auch ohne
`.number` (nachgesehen in `node_modules/@vue/runtime-dom`: `castToNumber`). Eine Zahl hat kein
`.trim()`, die Funktion brach mit einem Fehler ab, bevor das Konto geladen war. Behoben: nur noch
`Number(targetText.value)`, ein leeres Feld ergibt 0 und wird abgewiesen.

**Wie gefunden:** Zuerst auf einer Kopie der Entwicklungsdatenbank im Backend dieselbe Umbuchung
(Konto 4 → 6) mit 1, 2 und 3 Anteilen ausgeführt: klappte. Dann mit `curl` geprüft, dass der laufende
Server den Endpunkt kennt (`401` = nicht angemeldet, statt `405` für einen unbekannten Pfad). Damit
blieb nur das Frontend.

**Lehre:** TypeScript hilft hier nicht: `ref('')` behauptet `string`, zur Laufzeit steht eine Zahl
darin. Bei Zahlenfeldern deshalb immer `Number(...)` verwenden und keine String-Methoden. Die
Backend-Tests prüfen die Maske nicht; das fällt nur beim Ausprobieren auf.

## 2026-11-19 – Schritt 6a: Mitgliederliste nach GenG (Backend)

**Was:**

- `uv add openpyxl` im Ordner `backend`: Bibliothek zum Schreiben von Excel-Dateien, trägt sich in
  `pyproject.toml` und `uv.lock` ein.
- Neues Modul `coop_manager/reports/`:
  - `services.py`: `shares_on()` zählt die Anteile eines Kontos zum Stichtag, `members_geng()`
    liefert die Zeilen der Liste (`GengRow`).
  - `excel.py`: baut die `.xlsx` nach dem Vorbild von `purchase-prices`: eine Spaltentabelle
    (Überschrift, Breite, Zahlenformat), oben Titel und „Stichtag: TT.MM.JJJJ“, fixierte Kopfzeile.
  - `api.py`: `GET /api/reports/members-geng?reference_date=2026-12-31` liefert die Datei mit
    `Content-Disposition: attachment`, damit der Browser sie speichert.
  - In `app.py` mit `app.include_router(reports_api.router)` eingehängt.
- `tests/test_reports.py` mit erfundenen Mitgliedern: Eintritt, Antragsteller, Kündigung bis
  31.12., Teilkündigung, Spende, Storno, Sortierung, Download und Rechte.
- Geprüft mit `uv run pytest`, `uv run ruff check .`, `uv run pyright`.

**Warum so:**

- **Ausscheidensbuchung erst ab 01.01.:** Sie hat Wertstellung 31.12., die Person zählt aber bis
  einschließlich 31.12. mit ihren Anteilen. Ohne Ausnahme stünde sie zum 31.12. mit 0 Anteilen da.
- **Wer 0 Anteile hat, fehlt:** Am Tag einer Spende ist die Person laut Status noch Mitglied, ihre
  Anteile sind aber schon weg. Statt einer weiteren Ausnahme wird sie einfach nicht aufgeführt.
- **Betrag = Anteile × Preis statt Saldo:** Nach einer Teilkündigung steckt im Saldo bis zur
  Auszahlung noch der Anspruch auf die gekündigten Anteile.
- **Pyright-Fehler:** `sheet.cell(...).column_letter` kennt Pyright nicht, weil eine Zelle auch eine
  verbundene Zelle (`MergedCell`) sein kann. `get_column_letter(index)` aus `openpyxl.utils` macht
  aus der Spaltennummer direkt den Buchstaben und ist ohnehin einfacher.

## 2026-11-19 – Schritt 6b: Seite „Reports“ im Frontend

**Was:**

- `frontend/src/views/reports/ReportsView.vue` (neu): Feld „Stichtag“ (vorbelegt mit heute) und
  ein Link „Mitgliederliste nach GenG“ auf `/api/reports/members-geng?reference_date=…`.
- `router.ts`: Route `/reports` für beide Buchhaltungsrollen. `App.vue`: Der Menüeintrag „Reports“,
  bisher ein Platzhalter, zeigt jetzt auf die Seite.
- Geprüft mit `npm run type-check`.

**Warum so:**

- **Ein Link statt `api()`:** `api()` erwartet JSON, die Liste ist aber eine Datei. Ein `<a href>`
  mit dem Attribut `download` lässt den Browser die Datei selbst speichern; das Session-Cookie
  schickt er mit. Ein CSRF-Token braucht ein GET nicht, es schützt nur ändernde Anfragen.
- **Nachteil:** Ist die Session abgelaufen, speichert der Browser die Fehlermeldung als Datei,
  statt zur Anmeldung zu wechseln. Das nehmen wir hin, solange es nicht stört.
- **`computed` für die Adresse:** Ändert sich der Stichtag, baut Vue den Link von selbst neu.

## 2026-11-19 – Schritt 6c: Liste zur Generalversammlung

**Was:**

- `reports/services.py`: `members_assembly()` mit `AssemblyRow`. Die Auswahl „Status passt und
  Anteile > 0“ steckt jetzt in `_holders()` und wird von beiden Listen genutzt. `sort_key()`
  sortiert Namen wie im Telefonbuch.
- `reports/excel.py` umgebaut: `_new_sheet()` legt Titel, Stichtag und Kopfzeile an, `_append()`
  hängt eine Zeile mit Zahlenformaten an. Dazu für die GV-Liste die Druckeinstellungen
  (`page_setup`, `print_options.gridLines`, `print_title_rows`).
- `reports/api.py`: `GET /api/reports/members-assembly?reference_date=…`.
- `ReportsView.vue`: zweiter Link.
- Tests in `tests/test_reports.py`; geprüft mit `uv run pytest`, `ruff`, `pyright`, `npm run type-check`.

**Warum so:**

- **Gemeinsames Grundgerüst erst jetzt:** Bei einer Liste lohnte es nicht, bei zweien wiederholte
  sich der Aufbau. Weitere Listen (Seriendruck) brauchen nur noch ihre Spaltentabelle.
- **Sortierung:** `sorted()` vergleicht Zeichencodes, „Ä“ (Code 196) käme hinter „Z“ (90).
  `casefold()` macht klein und aus „ß“ schon „ss“, die Umlaute ersetzen wir selbst.
- **Gitterlinien statt Rahmen:** `print_options.gridLines` druckt die Kästchen mit einer Zeile Code,
  Rahmen müsste man für jede Zelle einzeln setzen.

## 2026-11-19 – Schritt 6d: Seriendruck-Liste

**Was:**

- `reports/services.py`: `members_mailing()` mit `MailingRow`, auf Basis von `_holders()` wie die
  GV-Liste, dazu ohne „keine Post“. Die Briefanrede kommt aus `salutation()` in
  `members/addressing.py`, die es seit Schritt 4 gibt.
- `reports/excel.py`: `MAILING_COLUMNS` mit den Feldnamen des Altsystems und `members_mailing()`.
- `reports/api.py`: `GET /api/reports/members-mailing?reference_date=…`.
- `ReportsView.vue`: dritter Link. Tests in `tests/test_reports.py`.
- Die Feldnamen habe ich aus der Beschreibung in `Beispieldaten/` gelesen, nur die Spalten „Feld“
  und „Format“, ohne die Beispielwerte.

**Warum so:**

- **Keine Titelzeile:** Beim Seriendruck nimmt Word die erste Zeile einer Tabelle als Feldnamen.
  Stünde dort „Stichtag: …“, hießen die Felder falsch. Deshalb hier `jahr_report` als Spalte.
- **Alles zum Stichtag:** Anrede, `austritt` und `Verstorben` richten sich nach dem Status am
  Stichtag. Wer nach dem Stichtag stirbt, bekommt in einer Liste zu einem früheren Tag noch die
  normale Anrede, wie damals richtig.
- **`*row.address_lines`:** Der Stern packt das Tupel mit den sechs Zeilen in die Liste aus, als
  stünden die sechs Werte einzeln da.
- **Nachtrag Aufzählungspunkte:** Die Links auf der Seite „Reports“ stehen in einer `<ul>`, und der
  Browser zeigt davor Punkte und rückt ein. Behoben im Stil der Seite mit `list-style: none` und
  `padding-left: 0`. Wegen `scoped` gilt das nur für diese Seite.

## 2026-11-19 – Schritt 6e: Warnung bei nicht gebuchtem Ausscheiden

**Was:**

- `reports/services.py`: `warnings(db, day)` prüft mit `exits_due()` aus `accounts/exits.py`, ob
  zum 31.12. des Vorjahres des Stichtags noch Ausscheiden offen sind.
- `reports/excel.py`: `_new_sheet()` bekommt die Warnungen und schreibt sie dunkelrot in Zeile 3
  der GenG- und der GV-Liste.
- `reports/api.py`: `GET /api/reports/warnings?reference_date=…` liefert die Warnungen als JSON.
- Frontend: `src/reports.ts` (neu) mit `getReportWarnings()`. `ReportsView.vue` fragt mit `watch`
  bei jeder Änderung des Stichtags nach und zeigt jede Warnung in einem gelben Kasten.
- Tests in `tests/test_reports.py`; geprüft mit `uv run pytest`, `ruff`, `pyright`, `npm run type-check`.

**Warum so:**

- **Wiederverwenden statt neu rechnen:** `exits_due()` kennt schon alle, die zu einem 31.12.
  ausscheiden, und ob es gebucht ist; dieselbe Liste zeigt die Seite „Jahresende“.
- **Warnung auch in der Datei:** Einem Ausdruck sieht man später nicht mehr an, was auf der Seite
  stand.
- **`watch` mit `immediate: true`:** läuft einmal sofort beim Öffnen der Seite und danach bei jeder
  Änderung des Stichtags.

## 2026-11-19 – Schritt 6f (Backend): Auswertung der Vorgänge eines Geschäftsjahres

**Was:**

- Entscheidungen in `Plan.md` eingetragen (alle Buchungen, Spalte „Gegenkonto“, Umbuchung in zwei
  Zeilen, Vorzeichen aus Sicht des Mitgliedskontos).
- `reports/services.py`: `fiscal_year_events(db, year)` mit `EventRow`. Kündigungen, Todesfälle und
  Ausschlüsse kommen aus den Mitgliedsdaten (`_member_events`), alle Buchungen aus dem Hauptbuch
  (`_booking_row`); `BOOKING_LABELS` übersetzt die Buchungsart in den Text der Spalte „Vorgang“.
- `reports/excel.py`: `EVENT_COLUMNS` und `fiscal_year_events()` mit Autofilter auf der Kopfzeile.
  `_new_sheet()` kommt jetzt auch ohne Stichtag aus (`day=None`).
- `reports/api.py`: `GET /api/reports/fiscal-year-events?fiscal_year=2025`, Jahr geprüft wie auf
  der Seite „Jahresende“ (`YEAR_MIN`, `YEAR_MAX`).
- Tests in `tests/test_reports.py`; geprüft mit `uv run pytest`, `ruff`, `pyright`.

**Warum so:**

- **Jede Seite einer Buchung, die ein Mitgliedskonto ist, wird eine Zeile:** Die Schleife sieht sich
  Haben (Vorzeichen +) und Soll (Vorzeichen −) an. Das Genossenschaftskonto hat kein Mitglied und
  fällt dabei von selbst heraus; bei der Umbuchung sind beide Seiten Mitglieder, also zwei Zeilen.
- **Zurückgenommenes fehlt von allein:** Ein zurückgenommener Tod oder eine zurückgenommene
  Kündigung steht nach dem Abspielen der Events nicht mehr im Mitglied. Bei Buchungen bleibt das
  Original im Hauptbuch, deshalb filtern wir stornierte Buchungen und ihre Stornos wie in
  `shares_on()`.
- **Ausscheiden mit dem Wert der Anteile:** Die Ausscheidensbuchung bewegt nur Anteile (Betrag 0);
  das Geld bleibt als Anspruch auf dem Konto. Matthias will in der Liste aber Anteile und Betrag
  passend sehen. Deshalb rechnet `_booking_row` beim Ausscheiden Anteile × aktuellen Anteilspreis,
  statt das Buchungsmodell zu ändern; das hätte Anspruch, Auszahlung und Seite „Ansprüche“
  betroffen. Ebenso bekommt die Teilkündigung ihren Betrag.
- **Autofilter:** `sheet.auto_filter.ref = "A4:G…"` setzt in Excel die Filterpfeile in die
  Kopfzeile, damit man ohne eigene Tabellen je Vorgangsart filtern kann.
- **Fallstrick im Test:** In `get_ledger(db).bookings_of(account_number(db, member(db)))` lädt
  Python zuerst das Hauptbuch und legt erst danach das Mitglied an; das geladene Hauptbuch kennt
  die neue Buchung dann nicht. Deshalb erst das Mitglied anlegen, dann das Hauptbuch laden.

## 2026-11-19 – Schritt 6f (Frontend): Link zur Auswertung eines Geschäftsjahres

**Was:**

- `ReportsView.vue`: Abschnitt „Auswertung eines Geschäftsjahres“ mit Feld „Geschäftsjahr“
  (`<input type="number" v-model.number>`, vorbelegt mit dem Vorjahr) und dem Link auf
  `/api/reports/fiscal-year-events?fiscal_year=…`.
- Geprüft mit `npm run type-check`.

**Warum so:**

- **Eigenes Feld statt Stichtag:** Die Auswertung gilt immer für ein ganzes Jahr; der Stichtag
  gehört nur zu den drei Listen darüber.
- **`v-model.number`:** Ein Eingabefeld liefert immer Text. Mit `.number` wandelt Vue ihn in eine
  Zahl um, sodass `fiscalYear` vom Typ `number` bleibt und TypeScript zufrieden ist.
- **Gültigkeit wie auf der Seite „Jahresende“:** `isValidYear` nutzt dieselben Grenzen
  `YEAR_MIN`/`YEAR_MAX` aus `accounts.ts`; solange das Jahr ungültig ist (leer oder halb getippt),
  gibt es keinen Link.
- **Keine Warnung:** Die Auswertung listet, was gebucht ist; ein nicht gebuchtes Ausscheiden fehlt
  dann einfach in der Liste.
- **Nachtrag „Name Gegenkonto“:** Auf Matthias' Wunsch steht neben der Nummer des Gegenkontos
  auch sein Name. `_account_name()` in `reports/services.py` sucht ihn: erst unter den Mitgliedern
  (`by_account`), sonst ist es das Genossenschaftskonto, dessen Bezeichnung im Hauptbuch steht
  (`ledger.accounts[number].name`).

## 2026-11-19 – Schemaversion je Projektor

**Was:**

- `eventsource/projection.py`: Klassenattribut `version = 1` an `Projector`, neue Methode
  `drop_schema()` (`DROP TABLE IF EXISTS` für alle `tables`). Die Tabelle `projection_checkpoints`
  hat eine Spalte `version`. `Projections.create_schema()` vergleicht beim Start die gespeicherte
  mit der Version im Code; weichen sie ab, werden die Tabellen gelöscht und der Checkpoint auf 0
  gesetzt. Das folgende `catch_up()` in `prepare()` befüllt sie neu.
- Tests in `tests/test_eventsource.py`: gleiche Version behält die Daten, neue Version baut neu
  auf, andere Projektoren bleiben unberührt.
- Einmalig: Matthias hat `backend/data/projections.sqlite` gelöscht, weil die alte
  Checkpoint-Tabelle die neue Spalte noch nicht hatte. Probelauf mit einer Kopie des Event Stores
  im Scratchpad: zwei Starts, beide Projektoren mit Version 1, alle Mitglieder wieder da.
- Geprüft mit `uv run pytest`, `ruff`, `pyright`; offener Punkt in `Plan.md` erledigt.

**Warum so:**

- **`CREATE TABLE IF NOT EXISTS`** legt eine Tabelle nur an, wenn sie fehlt; eine neue Spalte im
  Code kommt in einer bestehenden Datei nie an. `ALTER TABLE` für jede Änderung wäre viel Arbeit;
  eine Projektion lässt sich ja jederzeit aus den Events neu berechnen, also löschen wir sie.
- **Version von Hand statt automatisch aus dem Schema-Text:** Eine Prüfsumme des Textes würde auch
  bei einem geänderten Kommentar neu aufbauen. Die Zahl ist einfach und sichtbar.
- **Je Projektor:** Ändert sich nur die Mitgliederliste, bleiben die Benutzer unberührt.
- **`executescript()` außerhalb der Transaktion:** Python schließt vor `executescript()` eine
  offene Transaktion ab; deshalb erst Löschen + Checkpoint in einer Transaktion, danach anlegen.
- **Fallstrick im Test:** `INSERT INTO party_list VALUES (?, ?)` ohne Spaltennamen scheitert, sobald
  die Tabelle eine dritte Spalte hat. Spalten immer ausdrücklich nennen.

## 2026-11-19 – Benutzerhandbuch als Word-Datei

**Was:**

- `Dokumentation/Benutzerhandbuch.docx`: Benutzerhandbuch für Buchhaltung und Vorstand, mit Logo
  auf der Titelseite und in der Kopfzeile, Farben aus dem Logo (Braun, Grün). Neun Kapitel von der
  Anmeldung über Mitglieder, Konto, Kündigung und Jahresende bis zu Reports, Benutzerverwaltung und
  Checklisten für typische Abläufe.
- `Dokumentation/handbuch/handbuch.js` erzeugt die Datei mit der npm-Bibliothek `docx`
  (`npm install`, dann `npm run build`). Das Logo kommt direkt aus `frontend/src/assets/img/`.
- `README.md`: Handbuch in der Dokumentationstabelle, Jahresauswertung in der Kurzfassung.

**Warum so:**

- **Erzeugt statt von Hand in Word:** Ändert sich die App, werden nur die Texte im Skript
  angepasst und die Datei neu gebaut; Aufbau und Formatierung bleiben einheitlich.
- **Bezeichnungen aus dem Code:** Knöpfe, Menüpunkte und Feldnamen sind aus den Vue-Dateien
  übernommen, damit das Handbuch genau das zeigt, was auf dem Bildschirm steht.
- **Eigener Ordner mit `package.json`:** Die Abhängigkeit `docx` gehört nicht ins Frontend.
  `node_modules/` ist per `.gitignore` ausgeschlossen.
- **Nicht gerendert:** Ohne LibreOffice Writer ließ sich die Datei hier nicht als PDF prüfen;
  die Formatprüfung des docx-Skills lief ohne Fehler. Das Aussehen also in Word prüfen.

## 2026-11-21 – Benutzerhandbuch: ein Leerzeichen nach der Kapitelnummer

**Was:** In `Dokumentation/handbuch/handbuch.js` stehen die 44 Überschriften jetzt mit einem statt
zwei Leerzeichen nach der Nummer (`1.1 Anmelden und abmelden`). Danach `npm run build` im Ordner
`Dokumentation/handbuch`, die neue `Benutzerhandbuch.docx` ist erzeugt.

**Wie:** Ein einziger Ersetzungsbefehl, der nur die Aufrufe `h1(…)`, `h2(…)` und `h3(…)` trifft:

```bash
sed -i -E "s/(h[123]\('[0-9.]+)  /\1 /" handbuch.js
```

- `-i` ändert die Datei direkt, `-E` schaltet erweiterte reguläre Ausdrücke ein.
- `(h[123]\('[0-9.]+)` findet Aufruf und Nummer und merkt sie sich als `\1`; die zwei Leerzeichen
  dahinter werden durch eines ersetzt.
- Geprüft mit `grep -cE "h[123]\('[0-9.]+  " handbuch.js` (Ergebnis 0) und einem Blick in die
  erzeugte Datei: `unzip -p Benutzerhandbuch.docx word/document.xml` zeigt den Text der Überschriften.

**Warum:** Wunsch von Matthias, ein Leerzeichen ist die übliche Schreibweise. Das Inhaltsverzeichnis
übernimmt die Überschriften und ist damit ebenfalls angepasst, sobald Word die Felder aktualisiert.

## 2026-11-21 – Menüeintrag „Konten“ entfernt

**Was:** In `frontend/src/App.vue` ist der Menüeintrag „Konten“ gelöscht. Er war seit dem
Layout-Commit `3cdca44` ein Platzhalter ohne eigene Seite; ein einzelnes Konto erreicht man über
Mitglied → Konto, das Genossenschaftskonto über „Gen.-Kto“. Damit entfällt auch die
Platzhalter-Technik:

- `to?: RouteLocationRaw` ist jetzt `to: RouteLocationRaw`, das Ziel ist also Pflicht.
- Im Template ist `v-if="entry.to"` am `RouterLink` weg und das `<a v-else>` für Einträge ohne Ziel
  gelöscht.
- Kommentare angepasst (Fachseiten nennen „Genossenschaftskonto“ statt „Konten“, Satz über
  Platzhalter gestrichen).

Geprüft mit `npm run type-check` (ohne Fehler). Das Benutzerhandbuch nennt „Konten“ nur allgemein,
nicht als Menüpunkt, und bleibt unverändert.

**Warum:** Ein Menüpunkt, der nichts tut, verwirrt. Ohne Platzhalter ist der Code einfacher, und
das Pflichtfeld `to` lässt TypeScript melden, wenn bei einem neuen Eintrag das Ziel fehlt: Ein
optionales Feld (`?`) darf fehlen, ein Pflichtfeld nicht.

## 2026-11-21 – Logo führt zur Startseite

**Was:** In `frontend/src/App.vue` ist der Rahmen um das Logo kein `div` mehr, sondern ein
`RouterLink` auf die Route `home` (Pfad `/`), mit Tooltip „Zur Startseite“. Im Benutzerhandbuch
(Abschnitt 1.3) steht dazu ein Satz, die Word-Datei ist mit `npm run build` neu erzeugt. Geprüft
mit `npm run type-check`.

**Warum so:**

- **`RouterLink` statt `<a href="/">`:** Der Link wird im Browser zwar zu `<a href="/">`, beim
  Klick wechselt Vue Router die Seite aber ohne die App neu zu laden, wie bei den Menüeinträgen.
- **Name statt Pfad:** `{ name: 'home' }` bleibt richtig, auch wenn sich der Pfad im Router ändert.
- **Klasse am Link:** `logo-container` sitzt jetzt am Link selbst. Das CSS greift unverändert, und
  es gibt kein zusätzliches Element.

## 2026-11-21 – Neuer Begrüßungstext auf der Startseite

**Was:** `frontend/src/views/HomeView.vue` zeigt jetzt „Hallo ‹Name›, willkommen in der
Mitgliederverwaltung.“ statt des Aufbau-Hinweises „hier entsteht die Mitgliederverwaltung …“. Der
Name kommt wie bisher aus `currentUser?.full_name`; die doppelten geschweiften Klammern `{{ … }}`
sind Vues Schreibweise, um einen Wert in den Text einzusetzen. Geprüft mit `npm run type-check`.

**Warum:** Die App ist fertig genug für den Betrieb, der Hinweis auf eine Baustelle passt nicht mehr.

## 2026-11-21 – Entscheidung: Fehlzahlungen nach dem Ausscheiden

**Was:** Offene Frage geklärt: Überweist jemand nach dem Ausscheiden noch Geld (z. B. ein
weiterlaufender Dauerauftrag), wird das nicht in der Mitgliederverwaltung gebucht, sondern in der
Finanzbuchhaltung zurücküberwiesen. Festgehalten in `Plan.md` (Abschnitt zu Einzahlung und
Rückzahlung) und als Hinweis im Benutzerhandbuch unter 4.3 „Die Buchungsarten“; Word-Datei mit
`npm run build` neu erzeugt. Am Code ändert sich nichts.

**Warum:** Die App führt nur Geschäftsguthaben, also was die Genossenschaft dem Mitglied aus
Anteilen schuldet. Eine Fehlzahlung ist Fremdgeld. Eine eigene Buchungsart dafür hätte Saldo,
Mitgliederliste nach GenG und Jahresauswertung verkompliziert. Heute lässt die App einen solchen
Eingang ohnehin nicht zu: Eintritt nur bis zu den gezeichneten Anteilen, Rückzahlung nur vor der
Mitgliedschaft, Auszahlung höchstens bis zum offenen Anspruch.

## 2026-11-21 – Schritt 8a: FastAPI liefert die Vue-App aus, API-Doku abschaltbar

**Was:**

- `config.py` und `.env.example`: zwei neue Einstellungen.
  - `CM_FRONTEND_DIR`: Ordner mit der gebauten Vue-App (`frontend/dist` nach `npm run build`).
    Leer heißt: keine Oberfläche ausliefern, in der Entwicklung macht das weiter Vite.
  - `CM_API_DOCS`: `true` schaltet `/docs`, `/redoc` und `/openapi.json` ein, Standard `false`.
- `app.py`:
  - `FastAPI(docs_url=…, redoc_url=…, openapi_url=…)`: ohne Doku stehen alle drei auf `None`.
  - Klasse `SpaStaticFiles`, abgeleitet von `StaticFiles`: liefert die angefragte Datei, und wenn
    es sie nicht gibt, `index.html`. Unter `/api/` bleibt ein 404 ein 404 (JSON).
  - `app.mount("/", SpaStaticFiles(...))` als Letztes in `create_app`.
- Tests in `test_app.py` (Startseite, Datei, Fallback, `/api` bleibt 404, `/healthz`, Pfade außerhalb
  des Ordners, Doku aus/an) und `test_config.py`.

**Ausprobiert:**

```bash
cd frontend && npm run build
cd ../backend && CM_FRONTEND_DIR=../frontend/dist uv run uvicorn coop_manager.app:app
```

`curl` auf `/`, `/members/5` (HTML), `/favicon.ico`, die JS-Datei unter `/assets/` (200),
`/api/gibtsnicht` (404 JSON), `/healthz` (200 JSON).

**Warum so:**

- **SPA-Fallback:** Der Router nutzt `createWebHistory()`, Adressen sehen aus wie `/members/5`.
  Lädt man sie neu, fragt der Browser den Server danach; diese Datei gibt es nicht. Der Server
  liefert deshalb `index.html`, und der Vue Router im Browser zeigt die richtige Seite.
- **`/api/` ausgenommen:** Sonst bekäme das Frontend bei einer falschen API-Adresse HTML statt
  einer Fehlermeldung.
- **Mount zuletzt:** Starlette prüft die Routen der Reihe nach. Was unter `/` eingehängt ist, fängt
  alles, deshalb kommt es nach den API-Routern.
- **`StaticFiles` statt eigener Dateizugriff:** Es prüft selbst, dass nur Dateien im Ordner
  ausgeliefert werden (kein `/../.env`).
- **Fallstrick:** `StaticFiles` wirft Starlettes `HTTPException`. FastAPIs gleichnamige Klasse ist
  eine Unterklasse davon, ein `except` mit ihr fängt die von Starlette also nicht. Darum der Import
  aus `starlette.exceptions`.
- **Doku standardmäßig aus:** sicher ab Werk; die strenge CSP sperrt die Swagger-Oberfläche ohnehin.
  Bei abgeschalteter Doku und ausgelieferter Oberfläche landet `/docs` wie jede unbekannte Adresse
  bei `index.html`.

## 2026-11-21 – Schritt 8b: Dockerfile und compose.yaml

**Was:**

- `Dockerfile` im Hauptordner, zwei Stufen:
  1. `node:24-slim` als Stufe „frontend“: `npm ci`, `npm run build`.
  2. `python:3.14-slim`: uv, Abhängigkeiten, Code aus `backend/src`, dazu nur `dist` aus Stufe 1
     nach `/app/frontend`. Benutzer `app` statt root, `CM_DATA_DIR=/data`,
     `CM_FRONTEND_DIR=/app/frontend`, Healthcheck auf `/healthz`, Start mit
     `uvicorn coop_manager.app:app --host 0.0.0.0 --port 8000 --no-proxy-headers`.
- `.dockerignore`: `Beispieldaten`, `.git`, `.env`, `data`, `.venv`, `node_modules`, `dist`, Tests,
  `Dokumentation` bleiben draußen.
- `compose.yaml`: `./data:/data:Z`, `user` aus `CM_UID`/`CM_GID`, `env_file: .env`, Port
  `${CM_BIND_ADDRESS:-127.0.0.1}:${CM_PORT:-8001}:8000`.
- `.env.example` um `CM_UID`, `CM_GID`, `CM_PORT`, `CM_BIND_ADDRESS` ergänzt, `README.md` um
  „Mit Docker starten“.

**Ausprobiert:**

```bash
docker compose build
docker run --rm coop-manager sh -c 'ls /app /app/frontend; id'   # Inhalt und Benutzer des Images
mkdir -p data && docker compose up -d
curl -s -o /dev/null -w '%{http_code}' http://localhost:8001/members/5   # 200, SPA-Fallback
docker compose run --rm app coop-manager set-share-price 50
docker compose run --rm app coop-manager create-cooperative-account
docker compose restart && docker compose ps    # nach ~30 s „healthy“, Daten noch da
```

Das Image ist 292 MB groß; darin liegen weder Node noch Beispieldaten.

**Docker-Begriffe:**

- **Image:** die fertige, unveränderliche Vorlage (Betriebssystem-Grundlage, Python, unser Code).
  **Container:** ein laufendes Exemplar davon. Was der Container schreibt, ist beim Löschen weg,
  außer es liegt in einem Volume.
- **Schicht (Layer):** Jede Zeile im Dockerfile wie `COPY` oder `RUN` erzeugt eine Schicht. Docker
  merkt sich jede; ändert sich die Eingabe nicht, nimmt es die gespeicherte. Darum werden erst nur
  die Lock-Dateien kopiert und die Abhängigkeiten installiert, danach der Code: Eine Codeänderung
  baut nur die letzten Schichten neu.
- **Mehrstufiger Build:** `FROM … AS frontend` ist eine Hilfsstufe. Mit `COPY --from=frontend`
  holt die letzte Stufe nur das Ergebnis heraus; alles andere aus der Hilfsstufe landet nicht im
  Image.
- **Volume:** ein Ordner des Hosts im Container, hier `./data` als `/data`. Die SQLite-Dateien
  überleben so jeden Neubau des Containers. `:Z` sagt SELinux (Fedora), dass der Container den
  Ordner benutzen darf.
- **Healthcheck:** Docker ruft alle 30 s `/healthz` auf und zeigt den Zustand in `docker compose ps`
  („starting“, „healthy“, „unhealthy“).
- **`docker compose run --rm app …`:** startet einen zweiten, kurzlebigen Container aus demselben
  Image mit demselben Volume, führt den Befehl aus und löscht ihn danach (`--rm`). So laufen die
  CLI-Befehle wie `create-admin`.

**Warum so:**

- **Ein Prozess:** Beim Start holen die Projektionen auf; zwei Prozesse würden das gleichzeitig tun.
- **`--no-proxy-headers`:** uvicorn wertet `X-Forwarded-*` sonst selbst aus (für 127.0.0.1). So
  entscheidet nur `CM_TRUSTED_PROXIES` in der App, an einer Stelle.
- **Port 8001:** Auf der Synology belegt `purchase-prices` schon 8000.
- **`.dockerignore` mit `Beispieldaten`:** Der Build-Kontext wird komplett an Docker geschickt;
  echte Mitgliederdaten sollen dort nicht einmal vorübergehend landen.
- **`CM_DATA_DIR` und `CM_FRONTEND_DIR` in `compose.yaml` fest:** Die lokale `.env` enthält Werte
  für die Entwicklung (`data`, `../frontend/dist`), die im Container falsch wären.

## 2026-11-21 – Schritt 8c: Backup-Befehl für den Event Store

**Was:**

- `db.py`: `backup_event_store(data_dir, target)` schreibt eine Kopie des Event Store und liefert
  die Zahl der Events.
- `cli.py`: Befehl `coop-manager backup [ziel]`, ohne Ziel nach
  `<CM_DATA_DIR>/backup/eventstore.sqlite`. Fehler enden mit „Sicherung fehlgeschlagen: …“ und
  Exit-Code 1.
- Tests in `test_cli.py`: eine einzige Datei im Modus `delete` mit den Events, Ersetzen einer
  älteren Kopie an einem eigenen Ziel, Abbruch ohne Event Store.
- `README.md`: Aufruf im Container ergänzt.

**Ausprobiert:**

```bash
uv run coop-manager backup                                   # lokal, 62 Events
docker compose build && docker compose up -d
docker exec coop-manager-app-1 coop-manager backup           # im laufenden Container
ls -l data/backup/
docker exec coop-manager-app-1 coop-manager backup /nicht/erlaubt/x.sqlite; echo $?   # 1
```

**Warum so:**

- **Nicht einfach kopieren:** Schreibt die App während des Kopierens, wäre die Kopie halb alt, halb
  neu. Im WAL-Modus (Write-Ahead Log) stehen neue Änderungen außerdem zunächst in
  `eventstore.sqlite-wal` und erst später in der Hauptdatei. Die **Backup-API** von SQLite
  (`source.backup(copy)`) liefert dagegen einen stimmigen Stand, auch im laufenden Betrieb.
- **`PRAGMA journal_mode = DELETE` in der Kopie:** Die Sicherung ist dann eine einzige Datei.
- **`PRAGMA integrity_check`:** SQLite prüft die Kopie selbst; nur eine gute Kopie ersetzt die alte.
- **Erst `.partial`, dann `replace`:** Umbenennen geschieht in einem Zug. Hyper Backup, das kurz
  danach läuft, sieht entweder die alte oder die neue Datei, nie eine halbe.
- **Prüfung, ob der Event Store existiert:** `sqlite3.connect` legt eine fehlende Datei einfach an.
  Bei einem falsch gesetzten `CM_DATA_DIR` würde sonst still eine leere Datenbank gesichert.
- **`docker exec` statt `docker compose run`:** `exec` führt den Befehl im schon laufenden Container
  aus, so wie später der Aufgabenplaner auf der Synology; `run` startete einen neuen Container.
- **Nur eine Kopie:** Die Versionen hält Hyper Backup vor, wie bei `purchase-prices`.

## 2026-11-21 – Schritt 8d, Teil 1: deploy.sh und DEPLOYMENT.md

**Was:**

- `deploy.sh`: überträgt den Code per `tar` über `ssh` nach `/volume1/IT-Systeme/Docker/coop-manager`
  auf `ds218-dls`, ersetzt dort `backend/` und `frontend/` und startet
  `docker compose up -d --build`. Host, Ordner und Docker-Aufruf lassen sich mit `CM_DEPLOY_HOST`,
  `CM_DEPLOY_DIR` und `CM_DEPLOY_DOCKER` überschreiben.
- `DEPLOYMENT.md`: Anleitung nach dem Vorbild `purchase-prices` mit den Werten für coop-manager
  (Subdomain `mitglieder.`, Port 8001, Container `coop-manager-app-1`), dazu Ersteinrichtung per
  CLI, Datensicherung mit Aufgabenplaner, Wiederherstellen, Updates und Fehlerbilder.
- `README.md` und `Plan.md` verweisen darauf.

**Geprüft:**

```bash
sh -n deploy.sh                       # nur Syntax prüfen, nichts ausführen
tar -c … | tar -C <scratch> -x        # genau die Dateiauswahl von deploy.sh entpacken
docker build -t coop-manager-deploytest <scratch>   # baut vollständig
curl … http://localhost:8001/api/me   # 401; /docs und /openapi.json liefern die Vue-App
```

Auf dem NAS ist noch nichts passiert; die Einrichtung (Teil 2) machen wir später gemeinsam und
tragen dabei echte Werte in `DEPLOYMENT.md` nach.

**Warum so:**

- **Ausdrückliche Dateiliste in `deploy.sh`:** Nur was zum Bauen gebraucht wird, geht aufs NAS.
  `Beispieldaten/`, `.env`, `data/`, `node_modules/` und `.venv/` können so nicht versehentlich
  mitwandern. Dass die Liste vollständig ist, zeigt der Testbau aus genau dieser Auswahl.
- **Bauen auf dem NAS:** Die DS218 ist ARM64, der Entwicklungsrechner x86. Ein dort gebautes Image
  passt ohne Umwege (sonst bräuchte es `docker buildx` für eine fremde Architektur).
- **Eigene ACL auf dem Projektordner:** `data/` enthält Mitgliederdaten; die Freigabe
  `IT-Systeme` würde sonst auch `Aufsichtsrat` und `users` Zugriff geben.
- **Leer starten:** Die Entwicklungsdaten sind erfunden, die echten Daten kommen mit der Migration.

## 2026-11-21 – NAS über Tailscale ansprechen

**Was:** Erreichbarkeit des NAS geprüft, nur lesend, per `ssh chef@ds218-dls-tail`: Tailscale
(100.65.237.75), `sudo` ohne Kennwort, ARM64, Docker 24.0.2 und Compose v2.20.1, Port 8001 frei,
Projektordner und DNS-Eintrag `mitglieder.` gibt es noch nicht (kommen in der Einrichtung).
`ds218-dls` allein lässt sich von außerhalb des Ladennetzes nicht auflösen. Deshalb nehmen
`deploy.sh` (Standard für `CM_DEPLOY_HOST`) und die `ssh`-Befehle in `DEPLOYMENT.md` jetzt
`chef@ds218-dls-tail`.

**Warum:** Über Tailscale klappt der Zugang von überall, im Ladennetz ebenso wie unterwegs. Wer es
anders braucht, setzt `CM_DEPLOY_HOST`.

## 2026-11-21 – Subdomain heißt mitgliederdb, DNS eingerichtet

**Was:** Matthias hat bei Strato den CNAME `mitgliederdb` → `work.dorfladen-schlichten.de`
angelegt (Schritt 2 in `DEPLOYMENT.md`). Die Adresse der App ist damit
`https://mitgliederdb.dorfladen-schlichten.de`, nicht `mitglieder.` wie zuerst geplant.
`DEPLOYMENT.md` und `Plan.md` sind angepasst; ältere Logbuch-Einträge bleiben, wie sie waren.

**Geprüft:**

```bash
dig +noall +answer mitgliederdb.dorfladen-schlichten.de A       # CNAME auf work., A 195.245.19.98
dig +noall +answer mitgliederdb.dorfladen-schlichten.de AAAA    # nur der CNAME, keine IPv6-Adresse
dig +noall +answer @shades14.rzone.de mitgliederdb.dorfladen-schlichten.de ANY   # direkt bei Strato
```

Mit `@nameserver` fragt `dig` direkt beim zuständigen Nameserver von Strato statt beim eigenen
Resolver; so sieht man den Stand ohne Zwischenspeicher.

Nebenbei: `mitglieder.dorfladen-schlichten.de` gibt es bei Strato ebenfalls, nur mit einem
MX-Eintrag (`smtpin.rzone.de`), ohne Bezug zur App.

## 2026-11-21 – NAS: Zertifikat geprüft, Projektordner mit eigenen Rechten

**Was:**

- Schritt 3 in `DEPLOYMENT.md`: Matthias hat im DSM das Let's-Encrypt-Zertifikat für
  `mitgliederdb.dorfladen-schlichten.de` abgerufen. Per `ssh` geprüft: richtiger Name, gültig bis
  19.02.2027, nicht Standardzertifikat, noch keinem Dienst zugeordnet (das kommt mit dem Reverse
  Proxy).
- Schritt 4: `/volume1/IT-Systeme/Docker/coop-manager` angelegt, mit `synoacltool` je ein Eintrag
  für `chef`, `administrators` und `IT-Admin` gesetzt, Vererbung abgeschaltet
  (`-del-archive … is_inherit`), danach `data/` angelegt.

**Gesehen:**

- Ein neuer Ordner erbt erst die Rechte der Freigabe `IT-Systeme`, darunter `Aufsichtsrat` und
  `group::` (`level:2` = von zwei Ebenen darüber geerbt).
- Mit `-add` kommen eigene Einträge dazu (`level:0` = direkt am Ordner gesetzt), die geerbten
  bleiben zunächst stehen.
- Erst `-del-archive … is_inherit` kappt die Vererbung; übrig sind die drei eigenen Einträge.
- `data/` erbt genau diese (`level:1` = vom Ordner direkt darüber). Alles, was später darin
  entsteht (`.env`, SQLite-Dateien), bekommt dieselben Rechte.
- Die Unix-Rechte zeigen weiter `rwxrwxrwx+`; bei einer Synology-Freigabe mit ACL zählt die ACL.

**Warum vor `.env` und `data/`:** Dateien erben die Rechte beim Anlegen. Hätte es `.env` schon
gegeben, hätte sie die alten, offenen Rechte behalten.

## 2026-11-21 – NAS: .env angelegt

**Was:** Schritt 5 in `DEPLOYMENT.md`: `.env` im Projektordner auf dem NAS angelegt, mit dem
Inhalt aus der Anleitung. Ausgeführt als ein kleines Skript über `ssh … 'sh -s' <<'REMOTE'`.

**Wie das Secret entsteht:** Im Heredoc `<<EOF` (ohne Anführungszeichen) ersetzt die Shell
`$(python3 -c "import secrets; …")` beim Schreiben der Datei, und zwar auf dem NAS, weil das ganze
Skript dort läuft. Das äußere `<<'REMOTE'` mit Anführungszeichen sorgt dafür, dass der eigene
Rechner nichts davon auswertet. Das Secret steht so nur in der Datei auf dem NAS, nicht im
Terminal und nicht auf dem Entwicklungsrechner. `test ! -e` verhindert, dass eine vorhandene
`.env` überschrieben wird.

**Geprüft:** alle Zeilen außer dem Secret angezeigt; per `grep -c` nur gezählt, dass genau eine
Zeile `CM_SECRET_KEY=` mit 64 Hex-Zeichen da ist; die Datei hat die drei eingeschränkten
ACL-Einträge geerbt (`level:1`).

## 2026-11-21 – NAS: erster Bau mit deploy.sh

**Was:** Schritt 7 in `DEPLOYMENT.md`: `./deploy.sh` vom Entwicklungsrechner aus. Übertragung per
`tar` über `ssh`, Bau auf dem NAS in gut 2 Minuten (mit dem Herunterladen der Grundlagen-Images
für Node und Python), danach Start des Containers `coop-manager-app-1` im Netz
`coop-manager_default`.

**Geprüft, auf dem NAS:**

```sh
$DK inspect -f '{{.State.Health.Status}}' coop-manager-app-1   # healthy, nach ~30 s
$DK inspect -f '{{.RestartCount}}' coop-manager-app-1          # 0
$DK logs --tail 10 coop-manager-app-1                          # „app started“, data_dir /data
curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8001/healthz   # 200
```

`/` und `/members/5` liefern die Vue-App, `/api/me` 401, `/docs` die Vue-App (Doku aus).
`eventstore.sqlite` und `projections.sqlite` in `data/` haben die eingeschränkten ACL-Einträge
geerbt. `purchase-prices` blieb `healthy`.

**Gelernt:** Die Ausgabe von `deploy.sh` nicht durch `tail` leiten: `tail` zeigt erst am Ende etwas,
während des Baus sieht man dann nicht, in welcher Stufe er steckt. Und „health: starting“ direkt
nach dem Start ist normal, die erste Prüfung läuft nach 30 s (`--interval=30s` im Dockerfile).

## 2026-11-21 – NAS: Reverse Proxy vertrauen, Fallstrick mit sed -i und ACL

**Was:** Schritt 8 in `DEPLOYMENT.md`. Gateway des Netzes `coop-manager_default` ausgelesen
(`172.19.0.1`; `purchase-prices` hat `172.18.0.1`), per `sed -i` in `.env` bei
`CM_TRUSTED_PROXIES` eingetragen, Container mit `docker compose up -d --force-recreate` neu erzeugt.

**Vorher/nachher**, mit `curl -H 'X-Forwarded-Proto: https' -H 'X-Forwarded-For: 203.0.113.5'`:

| | HSTS-Header | Absender im Log |
|---|---|---|
| vorher | keiner | `172.19.0.1` (Gateway) |
| nachher | `max-age=31536000; includeSubDomains` | `203.0.113.5` |

Damit glaubt die App den `X-Forwarded-*`-Headern, die von der Gateway-Adresse kommen, und nur
diesen. `203.0.113.5` ist eine für Dokumentation reservierte Adresse.

**Fallstrick:** `sed -i` schreibt eine neue Datei und benennt sie auf den alten Namen um. Die neue
Datei hatte **keine ACL** mehr: `ls -l` zeigte `rwxrwxrwx` ohne `+`, `synoacltool -get` meldete
„It's Linux mode“. Die `.env` mit dem Secret war damit etwa zwei Minuten lang für alle Benutzer des
NAS lesbar. Behoben mit `synoacltool -enforce-inherit .env`, danach wieder die drei Einträge mit
`level:1`. In `DEPLOYMENT.md` stehen jetzt der Befehl in Schritt 8, ein Warnhinweis und ein
Fehlerbild. Lehre: Nach jeder Änderung einer Datei im Projektordner mit `ls -l` auf das `+` achten.

## 2026-11-21 – NAS: Secret neu erzeugt

**Was:** Weil die `.env` kurz ohne ACL war, hat Matthias entschieden, `CM_SECRET_KEY` neu zu
erzeugen. Jetzt kostet das nichts, es gibt noch keine Benutzer und keine Sessions; später würde ein
Wechsel alle abmelden.

**Wie, ohne die ACL wieder zu verlieren:** Der neue Inhalt entsteht in einer Shell-Variablen
(`sed` ohne `-i`, nur Ausgabe) und wird mit `printf … > .env` in die **bestehende** Datei
geschrieben. `>` kürzt die Datei und schreibt hinein, sie bleibt dieselbe Datei (gleiche Inode-Nummer
vorher und nachher, `ls -i`) und behält damit ihre ACL. `sed -i` dagegen legt eine neue Datei an.

**Geprüft, ohne das Secret anzuzeigen:** Prüfsumme der Secret-Zeile vorher und nachher verschieden,
genau eine Zeile mit 64 Hex-Zeichen, übrige Zeilen unverändert, `ls -l` mit `+`, drei ACL-Einträge
mit `level:1`. Container neu erzeugt: `/healthz` ok, HSTS-Header da, keine Warnung „CM_SECRET_KEY
not set“ im Log.

## 2026-11-21 – NAS: Reverse Proxy und Prüfung von außen

**Was:** Schritt 9 hat Matthias im DSM eingerichtet (Reverse Proxy `mitgliederdb.…:443` →
`localhost:8001`, Zertifikat dem Dienst zugeordnet). Schritt 10 von außen über das Internet geprüft.

**Geprüft:**

- nginx-Konfiguration auf dem NAS (`awk '/mitgliederdb…/,/^}/' …ReverseProxy.conf`):
  `proxy_pass http://localhost:8001`, `X-Forwarded-For` und `X-Forwarded-Proto` werden gesetzt.
- Zertifikat (`openssl s_client`): `CN=mitgliederdb.dorfladen-schlichten.de`, Let's Encrypt.
- `curl` von außen: Startseite `HTTP/2 200` mit HSTS und CSP; `/members/5` 200 (SPA-Fallback),
  `/healthz` 200, `/api/me` 401, `/docs` und `/openapi.json` liefern die Vue-App (Doku aus).
- Container-Log: Absender ist die öffentliche IP des prüfenden Rechners, nicht das Gateway. Die
  ganze Kette Internet → DSM-nginx → Docker → App reicht die echte Adresse und `https` durch.
- `http://` (ohne s) zeigt die Standardseite der Web Station, wie bei `ek.`; die App ist darüber
  nicht erreichbar. `DEPLOYMENT.md` sagte dazu „404“, das ist korrigiert.

## 2026-11-21 – NAS: Ersteinrichtung

**Was:** Schritt 11 in `DEPLOYMENT.md`. Matthias hat den Admin selbst angelegt (Kennwort verdeckt,
deshalb `ssh -t` für ein echtes Terminal und `docker exec -it`). Danach per `docker exec` im
laufenden Container: `set-share-price 50`, `create-cooperative-account`, `show-settings`.

**Geprüft:** Im Event Store stehen genau drei Events: `user.registered`,
`settings.share-price-changed` und `account.opened`. Die SQLite-Dateien in `data/` haben weiter
die eingeschränkte ACL (`+`).

**Warum `-t` bei `ssh`:** Ohne `-t` gibt `ssh` dem Befehl auf dem NAS kein Terminal. `getpass`
kann die Eingabe dann nicht verdecken und bricht ab bzw. warnt. `-it` bei `docker exec` reicht das
Terminal weiter in den Container.

## 2026-11-21 – NAS: tägliche Sicherung, Schritt 8 abgeschlossen

**Was:** Schritt 12 in `DEPLOYMENT.md`. Matthias hat im DSM-Aufgabenplaner die Aufgabe
`coop-manager Sicherung` angelegt (root, täglich 20:00, E-Mail nur bei Fehler) und einmal von Hand
ausgeführt.

**Geprüft:**

- `data/backup/eventstore.sqlite` mit Zeitstempel der Ausführung, ACL eingeschränkt (`level:3`,
  drei Ebenen unter dem Projektordner geerbt).
- Kopie nur lesend geöffnet (`?mode=ro`): Modus `delete`, Integritätsprüfung `ok`, 4 Events. Das
  vierte ist ein Benutzer, den Matthias inzwischen in der Oberfläche angelegt hat (`actor` ist die
  ID des Admins, nicht `cli`).
- Aufgabe in `/usr/syno/etc/synoschedule.d/root/14.task`: `run hour=20`, `run min=0`,
  `week=1111111` (alle Tage), Befehl wie geplant.
- Hyper Backup („Synology C2“) sichert `/volume1` ohne `/photo/`, der Projektordner ist enthalten.

Damit ist Schritt 8 (Container, Backup, Deployment) abgeschlossen. Die App läuft unter
`https://mitgliederdb.dorfladen-schlichten.de`.

## 2026-11-21 – Technische Dokumentation

**Was:** `TECHNIK.md` im Hauptordner, als Markdown wie `DEPLOYMENT.md` (nur die Benutzer-Doku ist
Word). Inhalt: Überblick mit Bild der Kette Browser → Proxy → Container → SQLite, Verzeichnisse,
Schichten im Backend (`api` → `services` → `domain`, `projections`), Event Sourcing (Bausteine,
Streams mit Subject, alle Eventtypen, `save_all` mit Wiederholung bei `ConcurrencyError`,
Projektionen und Schemaversion, Ablauf beim Start), Datenbanken, API-Regeln mit Übersicht der
Endpunkte, Sicherheit, Frontend, Konfiguration (`CM_*`), CLI, Logging, Tests und Rezepte für häufige
Änderungen. `README.md` verweist darauf.

**Wie:** Aus dem Code zusammengetragen, nicht aus dem Gedächtnis: Eventtypen per `grep` auf
`@on("…")` und `_record("…")`, Routen per `grep` auf `@router`, Security-Header, Rollenprüfung im
Router und Cookie-Einstellungen direkt in den Dateien nachgesehen.

**Warum eigene Datei statt mehr `Plan.md`:** `Plan.md` hält Entscheidungen und ihre Gründe fest,
`TECHNIK.md` beschreibt den Ist-Zustand des Codes zum Nachschlagen. Ändert sich der Aufbau, wird
`TECHNIK.md` angepasst.

## 2026-11-21 – Migration 7a: Altdaten analysiert

**Was:** Die Access-Datei des Altsystems liegt in `Altdaten/DLS-MitgliederDB.accdb`. `Altdaten/`
steht wie `Beispieldaten/` in `.gitignore`. Analysiert, mit Matthias jeden Sonderfall
entschieden und die Regeln in `Plan.md` („Migration der Altdaten“) festgehalten. Die
Einzelfälle mit Nummern stehen nur lokal in `Altdaten/Entscheidungen.md`.

**Werkzeug `mdbtools`** (`sudo dnf install mdbtools`) liest Access-Dateien ohne Microsoft Access:

- `mdb-ver datei.accdb`: Format (hier `ACE12`, Access 2007 und neuer)
- `mdb-tables -1 datei.accdb`: Tabellen, eine je Zeile
- `mdb-count datei.accdb tabelle`: Zeilen einer Tabelle
- `mdb-schema datei.accdb postgres`: Spalten und Typen als SQL
- `mdb-queries datei.accdb abfrage`: SQL einer gespeicherten Abfrage
- `mdb-export -T '%Y-%m-%d %H:%M:%S' datei.accdb tabelle > tabelle.csv`: Tabelle als CSV. Ohne
  `-T` kommen Datumswerte im US-Format (`mm/dd/yy`); `-D` gilt nur für reine Datumsfelder, Access
  speichert aber alles als Zeitstempel.

**Excel-Export für die Durchsicht:** die drei CSV-Dateien mit einem kleinen Python-Skript und
`openpyxl` in `Altdaten/DLS-MitgliederDB-Export.xlsx` (ein Blatt je Tabelle, echte Datumswerte im
Format `JJJJ-MM-TT`, Filter, fixierte Kopfzeile). Ausgeführt mit
`uv run --no-project --with openpyxl python -I skript.py`: `--with` holt `openpyxl` nur für diesen
Aufruf, ohne es dem Projekt hinzuzufügen.

**Warum außerhalb des Repositorys:** CSV-Dateien und Hilfsskripte lagen in einem temporären
Ordner, ausgegeben wurden in der Analyse nur Zählungen und Muster. Echte Daten gehören nicht ins
Repository (`AGENTS.md`), auch nicht als Nummern mit Angaben wie „verstorben“; deshalb trennt
`Plan.md` die Regeln von der lokalen Liste der Einzelfälle.

**Ergebnis in Zahlen:** 309 Personen, davon 287 übernommen; 392 Historienzeilen, 44 Personen mit
echten Änderungen; 305 Buchungen, 1.120 Anteile, 56.000 €, jeder Saldo = Anteile × 50 €.

**Entscheidungen (Kurzform):** nur Personen mit Eintritt oder Buchung; nie Mitglied Gewordene
als „abgelehnt“; alter Eintritt bleibt; Ausscheiden aus Spende bzw. Umbuchung; Tod und Kündigung
ohne Ausscheiden über „Jahresende“ nachbuchen; Selbstbuchungen, Testbuchung und Widerrufe
entfallen; `kdnr`, Geburtsdatum, Bankdaten, weitere Telefonnummern entfallen; Historie als eigene
Events; Akteur `migration`. Neue Idee: Ansicht „Verlauf“ an der Mitgliederseite.

## 2026-11-21 – Migration 7b: Entwurf der Migration

**Was:** Aufbau des Migrationsskripts entworfen und in `Plan.md` („Migration der Altdaten“,
Abschnitt „Technik“) festgehalten. Kein Code in diesem Schritt.

**Wichtigste Entscheidung: normale Events statt eigener Migrationsevents.** Ursprünglich waren
eigene Typen wie `member.migrated` und `booking.migrated` angedacht. Dann müsste aber jede Stelle,
die auf `member.applied`, `member.paid-in` oder `booking.posted` reagiert (Mitglied, Hauptbuch,
Projektionen, Reports, Jahresende), auch die Migrationsevents verstehen; dieselbe Tatsache käme
auf zwei Wegen herein. Jetzt schreibt die Migration dieselben Events wie die App, erkennbar am
Akteur `migration`. Eigene Methoden am Mitglied (`Member.migrate`) lassen nur die Prüfungen weg,
die für Altfälle nicht passen.

**Historie:** die bestehenden Änderungsevents mit einem zusätzlichen Feld `valid_from`. Events
dürfen zusätzliche Felder tragen, die alte Handler nicht lesen; das ist die übliche Art,
Events abwärtskompatibel zu erweitern.

**Einzelfälle:** `Altdaten/migration.toml` (nicht im Repository). TOML ist ein Format für
Konfigurationsdateien; Python liest es seit 3.11 mit `tomllib` aus der Standardbibliothek. Kurz
geprüft mit `python3 -I -c "import tomllib; tomllib.load(open('Altdaten/migration.toml', 'rb'))"`.

**Aufbau:** Modul `migration/` mit `source.py`, `plan.py` (reine Funktionen), `run.py`,
`check.py` und CLI-Befehl `migrate` mit `--dry-run`. Umsetzung in drei Teilen (7c).

## 2026-11-21 – Migration 7c, Teil 1: Mitglied aus dem Altsystem anlegen

**Was:**

- `members/values.py`: `validate_address(address, required=True)`. Mit `required=False` (nur
  Migration) dürfen Straße, Postleitzahl und Ort fehlen; Längen und eine vorhandene deutsche
  Postleitzahl werden trotzdem geprüft.
- `members/domain.py`: Wertobjekt `PersonData` (Name, Anschrift, Kontakt, Adresszeilen,
  Briefanrede, „keine Post“, Hinweise), `Member.migrate` (legt an wie `apply`, aber mit den
  übernommenen Adresszeilen) und `member.migrate_version(data, valid_from)` für die Historie.
  Beide nutzen `_record_changes`, das für jeden geänderten Teil das normale Änderungsevent
  schreibt, bei der Historie mit dem zusätzlichen Feld `valid_from`. Die Prüfungen von Briefanrede
  und Hinweisen sind in `_clean_salutation` und `_clean_notes` gewandert, damit sie nur einmal
  im Code stehen.
- `tests/test_members_migration.py`: 12 Tests mit erfundenen Daten, darunter das Zusammenspiel mit
  den normalen Methoden (`admit` und `record_payment` am alten Eintritt ergeben genau dieses
  Eintrittsdatum) und die Projektion (migrierte Historie, Liste zeigt den aktuellen Stand, alle
  Events mit Akteur `migration`).
- `TECHNIK.md`: Absatz zur Migration bei den Events.

**Warum keine eigenen Methoden für Zulassung, Tod usw.:** Die normalen Methoden prüfen gegen
„heute“ (kein Datum in der Zukunft) und gegen den Status am fachlichen Datum. Altfälle liegen in
der Vergangenheit und haben einen passenden Status, also funktionieren sie unverändert. Nur das
Anlegen (übernommene Adresszeilen, fehlende Anschrift) und die Historie (`valid_from`) brauchten
etwas Neues.

**Python-Detail:** Ruff (`RUF009`) bemängelte `contact: Contact = Contact()` als Standardwert einer
Dataclass. Ein solcher Aufruf läuft einmal beim Laden des Moduls, alle Objekte teilen sich dann
dasselbe Objekt. Bei unveränderlichen Objekten ist das harmlos, bei Listen wäre es ein typischer
Fehler. `field(default_factory=Contact)` erzeugt für jedes Objekt ein eigenes.

**Geprüft:** `uv run pytest` (548 Tests), `ruff check`, `ruff format --check`, `pyright`.

## 2026-11-21 – Migration 7c, Teil 2: Altdaten einlesen und Migrationsplan rechnen

**Was:**

- `migration/source.py`: `load_decisions` liest `migration.toml` mit `tomllib` in `Decisions`;
  `load_legacy` liest die drei CSV-Dateien aus `mdb-export` mit dem Modul `csv` in Dataclasses
  (`LegacyPerson`, `LegacyBooking`). Datum per `datetime.fromisoformat` (liest „2014-11-01
  00:00:00“ aus dem Export und „2026-05-18“ aus einer Korrektur), 1899-12-30 wird leer, Beträge
  über `Decimal` in Cent (kein `float`, siehe `core/money.py`). Korrekturen gelten auch für die
  Historie.
- `migration/plan.py`: `make_plan` geht die Buchungen in der Reihenfolge Datum, alte ID durch,
  ordnet jeder eine Buchungsart zu und führt dabei den Bestand je Konto mit. Daraus ergeben sich
  erste Einzahlung, weitere Anteile, Spende und Umbuchung aller Anteile. Danach entsteht je
  Person ein `PersonPlan` mit Versionen, Daten und Notizen. Was nicht passt, kommt in `problems`.
- `members/domain.py`: `migrate_version` nimmt jetzt auch `valid_from=None` (aktueller Stand nach
  der letzten Version, Datum unbekannt).
- Tests: `test_migration_source.py` (6, schreibt CSV- und TOML-Dateien in `tmp_path`) und
  `test_migration_plan.py` (18, eine Regel je Test, dazu ein Durchlauf eines kleinen Plans mit den
  Methoden am Mitglied im Speicher).

**Probelauf auf den echten Daten** (nur gerechnet, nichts geschrieben, Ausgabe nur Zahlen):
287 Personen (276 Mitglieder, 11 abgelehnt), 288 Buchungen (264 Eintritt, 16 Umbuchung, 6 Spende,
2 weitere Anteile), 17 übersprungen, 57 Versionen der Historie, **0 Probleme**. Aufgerufen mit
`uv run python -` und einem kurzen Skript über die Standardeingabe; die CSV-Dateien lagen im
temporären Ordner außerhalb des Repositorys.

**Python-Details:**

- `sorted(..., key=lambda b: (b.day, b.id))`: Tupel werden Stelle für Stelle verglichen, also
  erst nach Datum, bei gleichem Datum nach ID.
- `if (plan := _booking(...)) is not None`: Der „Walross-Operator“ `:=` weist innerhalb eines
  Ausdrucks zu; so lässt sich in einer List Comprehension aufrufen und filtern, ohne doppelt zu
  rechnen.
- `dataclasses.replace(obj, notes=...)`: Kopie eines unveränderlichen (`frozen`) Objekts mit
  einem geänderten Feld.

**Geprüft:** `uv run pytest` (572 Tests), `ruff check`, `ruff format --check`, `pyright`.

## 2026-11-21 – Migration 7c, Teil 3: Lauf, Abgleich und Befehl `migrate`

**Was:**

- `migration/run.py`: `build` baut Nummernregister, Hauptbuch und Mitglieder mit den normalen
  Methoden im Speicher auf: je Person anlegen, Nummer und Konto vergeben, Historie,
  Zulassung und Zahlung bzw. Rücknahme, Kündigung, Tod; dann die Buchungen (vor „Weitere Anteile“
  die Zeichnung); zuletzt Spende bzw. Umbuchung aller Anteile. Lehnt eine Methode etwas ab, steht
  es mit Ort in `errors`. `save` speichert alles mit `db.save_all` in einer Transaktion, Akteur
  `migration`.
- `migration/check.py`: `compare` rechnet Saldo und Anteile je Konto aus **allen** alten
  Buchungen und vergleicht mit dem neuen Hauptbuch. Weil sich die übersprungenen Buchungen je
  Konto zu null aufheben, zeigt der Abgleich auch, dass beim Überspringen nichts verloren ging.
  `summary` liefert den Bericht in Zahlen.
- `cli.py`: Befehl `coop-manager migrate <csv-ordner> <migration.toml> [--dry-run]`. Reihenfolge:
  Plan, Aufbau, Abgleich, Bericht, Speichern. Bei Problemen, Fehlern oder Abweichungen Abbruch
  mit Rückgabecode 1 vor dem Speichern.
- `tests/test_migration_run.py`: 11 Tests von den CSV-Dateien bis in den Event Store, auch
  über die CLI (Probelauf, Speichern, Abbruch).

**Probelauf in einem Wegwerf-Datenverzeichnis** (`CM_DATA_DIR` im temporären Ordner, danach
gelöscht) mit den echten Daten: `create-cooperative-account`, dann `migrate … --dry-run`: keine
Probleme, Fehler oder Abweichungen; 249 Mitglieder, 11 abgelehnt, 27 ausgeschieden, Bestand 1.120
Anteile und 56.000 € wie im Altsystem. Danach echter Lauf: 1.911 Events mit Akteur `migration`,
82 davon mit `valid_from`; ein zweiter Aufruf wird abgelehnt („Es gibt schon Mitglieder“).

**Python-Details:**

- Ruff `B023`: Ein `lambda` in einer Schleife merkt sich die Variable, nicht ihren Wert. Wird es
  erst nach der Schleife aufgerufen, sehen alle Lambdas den letzten Wert, ein klassischer Fehler.
  Hier wurde es zwar sofort aufgerufen, aber `_attempt(built, ort, funktion, *argumente)` ist
  ohnehin klarer: Die Argumente werden beim Aufruf übergeben, nichts wird „eingefangen“.
- `sys.exit("Text")` gibt den Text auf stderr aus und beendet mit Rückgabecode 1; ein `finally`
  davor läuft trotzdem (hier: Datenbank schließen).

**Geprüft:** `uv run pytest` (583 Tests), `ruff check`, `ruff format --check`, `pyright`.

## 2026-11-21 – Migration 7d: Probelauf mit den echten Daten

**Was:**

1. CSV-Export dauerhaft nach `Altdaten/csv/` (von Git ausgeschlossen):
   `for t in mitglieder mitglieder_hist buchungen; do mdb-export -T '%Y-%m-%d %H:%M:%S'
   Altdaten/DLS-MitgliederDB.accdb $t > Altdaten/csv/$t.csv; done`
2. Eigenes Datenverzeichnis `Altdaten/probelauf/`, vorbereitet wie die Ersteinrichtung auf dem
   NAS. Echte Umgebungsvariablen gehen vor `.env`, deshalb reicht `export CM_DATA_DIR=…` für
   `set-share-price 50`, `create-cooperative-account`, `migrate … --dry-run` und `migrate …`.
   `.env` und `backend/data` bleiben unberührt.
3. Matthias hat dort einen Admin und einen Benutzer „Buchhaltung“ angelegt und die App mit
   `CM_DATA_DIR=$PWD/Altdaten/probelauf ./dev.sh` gestartet.

**Ergebnis:** keine Probleme, Fehler oder Abweichungen; 1.911 Events. Ein Vergleichsskript
(außerhalb des Repositorys, `members_geng` der App gegen
`Beispieldaten/20261025_DLS_Mitgliederliste-GenG.xlsx`) zum Stichtag 31.12.2025: Bei 249
Mitgliedern stimmen Name, Eintrittsdatum, Anteile und Betrag genau überein. Es fehlen nur die
5 offenen Fälle (13 Anteile), die das Altsystem noch führte.

**Frage von Matthias: Warum 55.350 € statt 56.000 €?** Im Hauptbuch stehen weiter 56.000 € und
1.120 Anteile auf den Mitgliedskonten. Die Summe auf der Seite zählt aber nur Personen, die heute
Mitglied sind, und die App berechnet den Status aus den Daten: Wer 2015 gestorben ist, ist seit dem
31.12.2015 ausgeschieden, auch wenn das Ausscheiden noch nicht gebucht ist. Die Differenz von 650 €
sind genau die 13 Anteile der 5 offenen Fälle (Tod 2015, 2016, 2017, 2021; Kündigung mit
Ausscheiden 31.12.2023). Mit der Buchung auf der Seite „Jahresende“ werden die Anteile ausgebucht;
die 650 € bleiben als offene Auseinandersetzungsansprüche auf den Konten, bis der Vorstand
über Auszahlung oder Ausbuchung wegen Verjährung entscheidet. So in 7a (Fall 4) beschlossen.

**Wiederholen:** `Altdaten/probelauf/` löschen und mit Schritt 2 neu beginnen.

## 2026-11-21 – Saldenliste, Teil 1: Backend (10a)

**Anlass:** Im Probelauf der Migration fragte Matthias, warum die Summe 55.350 € statt 56.000 €
war (siehe 7d). Gewünscht ist eine Abfrage aller Ansprüche aller Personen gegenüber der
Genossenschaft. Neuer Schritt 10 und Abschnitt „Saldenliste“ in `Plan.md`.

**Was:**

- `accounts/balances.py`: `account_balances(db, day, include_zero)` liefert eine `BalanceList`:
  je Mitgliedskonto Status, Anteile, Saldo, Geschäftsguthaben (Anteile × Preis),
  Auseinandersetzungsanspruch (Rest) und den Hinweis „Ausscheiden nicht gebucht“; dazu Summen
  und die Abstimmung gegen das Genossenschaftskonto (`balanced`).
- `balance_on` rechnet den Saldo zum Stichtag wie `shares_on` die Anteile. Beide nutzen
  `_counted` (Buchungen bis zum Stichtag, ohne stornierte samt Storno).
- `shares_on` ist aus `reports/services.py` nach `accounts/balances.py` umgezogen; die Reports
  importieren es von dort. Grund: `reports` hängt schon von `accounts` ab; umgekehrt gäbe es einen
  Importzyklus. Fachliches Rechnen am Hauptbuch gehört ohnehin zu den Konten.
- `GET /api/accounts/balances?day=…&include_zero=…` für beide Buchhaltungsrollen. Die Route steht
  vor `/{number}`, sonst hielte FastAPI „balances“ für eine Kontonummer.
- `tests/test_balances.py`: 9 Tests (Stichtag, nicht gebuchtes und gebuchtes Ausscheiden,
  Auszahlung, Storno, Summen und Abstimmung, API und Rollen).

**Gegenprobe am Probelauf-Bestand:** 254 Konten mit Saldo, 1.120 Anteile, 56.000 €, Konto 9999
−56.000 €, abgestimmt; „Ausscheiden nicht gebucht“ genau bei den 5 offenen Fällen.

**Geprüft:** `uv run pytest` (592 Tests), `ruff check`, `ruff format --check`, `pyright`.

## 2026-11-21 – Saldenliste, Teil 2: Seite „Salden“ (10b)

**Was:**

- `frontend/src/accounts.ts`: Schnittstellen `BalanceEntry` und `BalanceList` (passend zu den
  Dataclasses in `accounts/balances.py`) und `getBalances(day, includeZero)`. Die Abfrage baut
  `URLSearchParams` zusammen; es kodiert die Werte richtig und spart das Zusammenkleben von Text.
- `frontend/src/views/accounts/BalancesView.vue`: Stichtag und Häkchen „auch Konten mit Saldo 0“.
  `watch([day, includeZero], …, { immediate: true })` lädt beim Öffnen und bei jeder Änderung neu;
  ein Array beobachtet mehrere Werte zugleich. Darunter die Abstimmung (blau: passt, rot:
  Differenz), ein gelber Hinweis auf Konten mit nicht gebuchtem Ausscheiden mit Link zu
  „Jahresende“, die Tabelle und die Summenzeile mit den Summen aus dem Backend.
- `router.ts`: Route `/balances` für beide Buchhaltungsrollen; `App.vue`: Menüeintrag „Salden“.
- Benutzerhandbuch: Menüübersicht, neuer Abschnitt 6.5 „Salden aller Konten“ und ein Schritt im
  Jahresabschluss (9.4); neu erzeugt mit `npm run build` in `Dokumentation/handbuch`.

**Geprüft:** `npm run type-check`, `npm run build`. Ansicht im Probelauf-Bestand durch Matthias.

## 2026-11-21 – Saldenliste, Teil 3: Excel (10c)

**Was:**

- `reports/excel.py`: `account_balances(result)` mit `BALANCE_COLUMNS` (Nr., Name, Status,
  Anteile, Saldo, Geschäftsguthaben, Anspruch, Hinweis), aufgebaut wie die anderen Listen
  (`_new_sheet`: Titel, Stichtag, Hinweiszeile 3, Kopfzeile in Zeile 4, fixiert). Zeile 3 nennt
  eine Differenz zum Genossenschaftskonto oder die Zahl der Konten mit nicht gebuchtem
  Ausscheiden. Autofilter auf der Kopfzeile; darunter fett die Summenzeile und das
  Genossenschaftskonto mit „abgestimmt“ bzw. „NICHT abgestimmt“.
- `reports/api.py`: `GET /api/reports/account-balances?reference_date=…&include_zero=…`; die
  Daten kommen aus `accounts/balances.py` (10a), es wird nichts doppelt gerechnet.
- Frontend: Link „Saldenliste“ auf der Seite „Reports“ (Stichtag der Seite) und „Als Excel
  herunterladen“ auf der Seite „Salden“ (Stichtag und Häkchen der Seite).
- Tests in `tests/test_reports.py` (2): Aufbau mit Summen und Abstimmung; Hinweis bei nicht
  gebuchtem Ausscheiden.
- Benutzerhandbuch: 6.5 und 7.1 ergänzt, neu erzeugt.

**Gegenprobe am Probelauf-Bestand** (31.12.2025): Zeile 3 „5 Konten: Ausscheiden nicht gebucht“,
Summe 1.120 Anteile und 56.000 €, Genossenschaftskonto −56.000 €, „abgestimmt“.

**Geprüft:** `uv run pytest` (594 Tests), `ruff check`, `ruff format --check`, `pyright`;
`npm run type-check`, `npm run build`.

## 2026-11-21 – Migration 7e: Altdaten in der Produktion

**Was:** Die Migration lief direkt im laufenden Container auf dem NAS statt wie in 7b vorgeschlagen
lokal auf einer Kopie. Grund: `migrate` liest nur die CSV-Dateien und `migration.toml`, `mdbtools`
braucht es auf dem NAS nicht. So entfallen Container-Stopp, Kopieren und ACL-Nacharbeit, und es
läuft genau die ausgerollte Codeversion.

1. `./deploy.sh`: neuer Stand mit `migrate` und Saldenliste; danach `healthy`, `/healthz` ok.
   Gewartet mit einer `until`-Schleife auf `docker inspect -f '{{.State.Health.Status}}'`.
2. Keine Sicherung vorher: In der Produktion stand laut Matthias noch nichts Wichtiges.
3. CSV-Dateien und `migration.toml` per `tar | ssh` nach `data/import/`; die neuen Dateien erben
   die eingeschränkte ACL des Ordners (`+` in `ls -l`, `synoacltool -get`: chef, IT-Admin).
4. `docker exec … coop-manager migrate … --dry-run`: dieselben Zahlen wie lokal in 7d.
5. Nach Matthias' Go der echte Lauf: „Migration gespeichert: 1911 Events.“
6. Prüfung nur lesend (`sqlite3` mit `?mode=ro`, `account_balances`): 1.911 Events mit Akteur
   `migration`, 287 Personen in der Mitgliederliste, Saldenliste abgestimmt (1.120 Anteile,
   56.000 €, Konto 9999 −56.000 €), 5 Konten mit nicht gebuchtem Ausscheiden.
7. `rm -rf data/import` auf dem NAS.

**Offen für die Buchhaltung:** unter „Jahresende“ das Ausscheiden für 2015, 2016, 2017, 2021 und
2023 buchen; danach stehen die 650 € als offene Ansprüche unter „Ansprüche“.

**Dokumentiert:** `DEPLOYMENT.md` Abschnitt 13, `Plan.md` (Produktion, 7e erledigt).

## 2026-11-21 – Verlauf der Personendaten, Teil 1: Backend (11a)

**Vorher:** `Altdaten/probelauf/` und `Altdaten/csv/` gelöscht (Probelauf erledigt, Daten in der
Produktion). Als Archiv bleiben Access-Datei, Excel-Export, `migration.toml` und
`Entscheidungen.md`.

**Was:**

- `members/history.py`: `member_history(db, member_id)` geht die Events der Person der Reihe nach
  durch und merkt sich je Teil (Name, Anschrift, Kontakt, Adresszeilen, Briefanrede, Keine Post,
  Hinweise) den aktuellen Text. Jedes Änderungsevent ergibt eine Zeile mit Vorher und Nachher;
  `member.applied` liefert den Ausgangsstand. Status- und Buchungsevents werden übersprungen.
  Gültig ab: `valid_from` aus der Migration, beim Antrag das Antragsdatum, sonst leer (= Tag des
  Speicherns). Akteure werden zum Namen des Benutzers; `migration` und `cli` haben feste Namen.
- `GET /api/members/{id}/history` für beide Buchhaltungsrollen.
- `tests/test_members_history.py`: 8 Tests.
- `Plan.md`: Schritt 11 und Abschnitt „Verlauf der Personendaten“ (aus den möglichen
  Weiterentwicklungen übernommen); `TECHNIK.md`: Endpunkt und Modul.

**Warum keine Projektion:** Der Verlauf wird nur für eine Person auf Abruf gebraucht. Die Events
eines Streams zu lesen ist genau das, wofür Event Sourcing da ist; eine Lesetabelle wäre mehr Code
ohne Nutzen. Das ist ein schönes Beispiel dafür, dass die Events selbst die Historie *sind*.

**Python-Detail:** `entries[::-1]` ist ein Slice mit Schrittweite −1 und liefert eine umgedrehte
Kopie der Liste.

**Geprüft:** `uv run pytest` (602 Tests), `ruff check`, `ruff format --check`, `pyright`.

## 2026-11-21 – Verlauf der Personendaten, Teil 2: Karte „Verlauf“ (11b)

**Was:**

- `frontend/src/members.ts`: Schnittstelle `HistoryEntry`, `getHistory(memberId)` und
  `formatDateTime` (Ortszeit; `new Date(...)` rechnet die UTC-Zeit aus dem Backend selbst um,
  `toLocaleString('de-DE', …)` schreibt sie deutsch).
- `frontend/src/views/members/HistoryCard.vue`: eigene Komponente wie `NoticeCard`. Zugeklappt mit
  „Verlauf anzeigen“; erst beim Aufklappen wird geladen. Sie bekommt das ganze Mitglied als Prop:
  Nach jedem Speichern liefert die Seite ein neues Objekt, `watch` bemerkt das und lädt den
  offenen Verlauf neu. Tabelle: Gültig ab, Gespeichert, Von, Was, Vorher, Nachher; mehrzeilige
  Hinweise mit `white-space: pre-line`.
- `MemberDetailView.vue`: Karte unten auf der Seite.
- Benutzerhandbuch: Abschnitt 3.5 „Verlauf“, neu erzeugt.

**Geprüft:** `npm run type-check`, `npm run build`.
