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
