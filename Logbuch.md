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
