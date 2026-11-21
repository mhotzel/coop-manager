# Technische Dokumentation

Wie coop-manager aufgebaut ist und wie die Teile zusammenspielen. Sie richtet sich an alle, die den
Code verstehen oder ändern wollen. Was fachlich gilt und warum etwas so entschieden wurde, steht in
`Plan.md`; wie die App entstanden ist, im `Logbuch.md`. Entwicklung starten: `DEV_HINTS.md`, Betrieb
auf der Synology: `DEPLOYMENT.md`.

## Überblick

```
Browser ──HTTPS──▶ DSM-Reverse-Proxy ──HTTP──▶ Container coop-manager (uvicorn, ein Prozess)
                   (nginx, Let's Encrypt)        │
                                                 ├─ /api/…    FastAPI: Befehle und Abfragen (JSON)
                                                 ├─ /healthz  Lebenszeichen
                                                 └─ /…        gebaute Vue-App (index.html, assets/)
                                                 │
                                                 ▼
                                     data/eventstore.sqlite   alle Events, einzige Quelle der Wahrheit
                                     data/projections.sqlite  Lesetabellen, jederzeit neu aufbaubar
                                     data/backup/             tägliche Kopie des Event Store
```

- **Backend:** Python 3.14, FastAPI, SQLite über das Standardmodul `sqlite3`. Kein ORM.
- **Frontend:** Vue 3 mit TypeScript, gebaut mit Vite, eigenes CSS, keine Komponentenbibliothek.
- **Speicherung:** Event Sourcing. Jede Änderung wird als Event gespeichert und nie verändert.
  Der aktuelle Zustand entsteht, indem die Events der Reihe nach angewendet werden.
- **Ein Container, eine Adresse:** FastAPI liefert API und Oberfläche aus, es gibt kein CORS.
  In der Entwicklung übernimmt Vite die Oberfläche und leitet `/api` an uvicorn weiter.

## Verzeichnisse

```
backend/
  pyproject.toml, uv.lock     Abhängigkeiten (uv), ruff, pyright, pytest
  src/coop_manager/
    app.py                    baut die FastAPI-App: Einstellungen, Middleware, Router, Oberfläche
    config.py                 Einstellungen aus CM_*-Umgebungsvariablen und .env
    db.py                     Database (beide SQLite-Verbindungen), prepare, Backup
    cli.py                    Kommandozeile `coop-manager …`
    logs.py, security.py      JSON-Logs; Security-Header und Reverse Proxy
    eventsource/              Event, Aggregate, EventStore, Projector (Infrastruktur, fachfrei)
    core/                     DomainError, NotFoundError, Geldbeträge (money.py)
    users/                    Benutzer, Anmeldung, Rollen, Zugriffsschutz
    members/                  Mitglieder, Nummernvergabe, Status, Adresszeilen, Verlauf
    accounts/                 Hauptbuch, Konten, Buchungsvorgänge, Ausscheiden, Ansprüche, Salden
    reports/                  Listen zum Stichtag und Jahresauswertung als Excel
    system_settings/          Anteilspreis
    migration/                Übernahme der Altdaten aus der Access-Datenbank (Schritt 7)
  tests/                      pytest, je Modul und Schicht
frontend/
  src/main.ts, App.vue        Start, Layout mit Kopfzeile und Menü
  src/router.ts               Seiten und Rollenprüfung vor jedem Seitenwechsel
  src/api.ts, auth.ts         Aufrufe ans Backend, angemeldeter Benutzer
  src/members.ts, accounts.ts, reports.ts, users.ts   Typen und Aufrufe je Fachbereich
  src/views/…                 die Seiten (eine .vue-Datei je Seite bzw. Karte)
  src/assets/                 CSS (Farben in colorscheme-dorfladen.css), Logo
Dokumentation/                Benutzerhandbuch (Word) und das Skript, das es erzeugt
Dockerfile, compose.yaml, .dockerignore, deploy.sh   Container und Deployment
```

## Backend: Schichten

Jedes Fachmodul (`users`, `members`, `accounts`, …) ist gleich aufgebaut. Ein Aufruf läuft von oben
nach unten:

| Datei | Aufgabe | Kennt |
|---|---|---|
| `api.py` | HTTP: Route, Rolle prüfen, Eingabe (Pydantic) annehmen, Ergebnis zurückgeben. Dünn, keine Fachlogik | services, schemas |
| `schemas.py` | Pydantic-Modelle für Ein- und Ausgabe der API | domain |
| `services.py` | ein Vorgang: Aggregate laden, Methode aufrufen, speichern, loggen | domain, db |
| `domain.py` | Aggregate mit den fachlichen Regeln; ändern sich nur über Events | eventsource, core |
| `projections.py` | Lesetabellen für Suche und Listen und die Abfragen darauf | eventsource |

`accounts/bookings.py` enthält die Buchungsvorgänge. Sie liegen in einer eigenen Datei, weil sie das
Mitglied brauchen und `members/services.py` schon `accounts/services.py` importiert (sonst ein
Importzyklus).

Fachliche Fehler wirft der Code als `DomainError` (bzw. `NotFoundError`) mit einer deutschen
Meldung für den Benutzer. `app.py` macht daraus `{"detail": "…"}` mit Status 400 bzw. 404. Das
Frontend zeigt `detail` an.

## Event Sourcing

### Die Bausteine (`eventsource/`)

- **`Event`** (`events.py`): unveränderlich, mit `type` (z. B. `member.admitted`), `subject` (der
  Stream, zu dem es gehört), `data` (JSON), `version` (Position im Stream), `id` (UUIDv7), `time`
  (UTC) und `actor` (wer es ausgelöst hat).
- **`Aggregate`** (`aggregate.py`): Basisklasse der Fachobjekte. Eine Methode prüft die Regeln und
  ruft `_record(typ, **daten)` auf. Das erzeugt das Event, wendet es sofort über den passenden
  Handler an und merkt es zum Speichern vor. Handler sind mit `@on("typ")` markiert und ändern nur
  den Zustand, sie prüfen nichts. `from_events()` baut ein Aggregat aus seinen gespeicherten Events.
- **`EventStore`** (`store.py`): Tabelle `events` in `eventstore.sqlite`. Events werden nur
  angehängt. `UNIQUE (subject, version)` verhindert, dass zwei Vorgänge gleichzeitig dieselbe
  Version schreiben. Der zweite bekommt einen `ConcurrencyError` (optimistische Sperre).
- **`Projector` und `Projections`** (`projection.py`): Ein Projektor hält Lesetabellen in
  `projections.sqlite` aktuell. `Projections.catch_up()` gibt jedem Projektor die Events seit seinem
  Checkpoint und speichert den neuen Checkpoint in derselben Transaktion.

```python
# So sieht ein Vorgang aus (vereinfacht, aus members/services.py):
member = get_member(db, member_id)          # Events lesen, Aggregat aufbauen
member.admit(decision_date, today)          # Regeln prüfen, Event „member.admitted“ aufzeichnen
db.save(member, actor)                      # Events anhängen, Projektionen nachziehen
```

### Streams (Aggregate)

| Aggregat | Subject | Inhalt |
|---|---|---|
| `User` | eine UUID je Benutzer | Anmeldename, Name, Kennwort-Hash (Argon2), Rolle, aktiv |
| `Member` | eine UUID je Person | Personendaten, Antrag, Zulassung, Zahlung, Kündigungen, Tod, Ausschluss, Spende, Übertragung, weitere Anteile |
| `MemberNumbers` | `member-numbers` | alle vergebenen Mitgliedsnummern |
| `Ledger` | `ledger` | das Hauptbuch: alle Konten (`account.opened`) und alle Buchungen (`booking.posted`) |
| `SystemSettings` | `system-settings` | Anteilspreis |

`MemberNumbers` und `Ledger` sind bewusst **ein einziger Stream**. Jede neue Nummer bzw. Buchung
wird so gegen alle bisherigen geprüft, und zwei gleichzeitige Vorgänge können sich nicht
überschreiben: Der zweite scheitert an der Version.

Was **nicht** gespeichert, sondern immer berechnet wird: der Status eines Mitglieds zu einem Tag
(`members/status.py`), Saldo und Anteile eines Kontos, der offene Auseinandersetzungsanspruch.

### Events

| Bereich | Eventtypen |
|---|---|
| Benutzer | `user.registered`, `user.name-changed`, `user.password-changed`, `user.role-changed`, `user.deactivated`, `user.reactivated`, `user.terminated` |
| Mitglied: Antrag und Mitgliedschaft | `member.applied`, `member.admitted`, `member.rejected`, `member.withdrawn`, `member.paid-in`, `member.paid-in-revoked` |
| Mitglied: Ausscheiden | `member.notice-given`, `member.partial-notice-given`, `member.notice-withdrawn`, `member.died`, `member.death-revoked`, `member.expelled`, `member.expulsion-lifted`, `member.shares-donated`, `member.donation-revoked`, `member.all-shares-transferred`, `member.transfer-revoked` |
| Mitglied: weitere Anteile | `member.additional-shares-subscribed`, `member.additional-shares-revoked` |
| Mitglied: Stammdaten | `member.name-changed`, `member.address-changed`, `member.contact-changed`, `member.address-lines-changed`, `member.salutation-changed`, `member.mail-preference-changed`, `member.notes-changed` |
| Nummern | `member-number.assigned` (im Stream `member-numbers`) |
| Hauptbuch | `account.opened`, `booking.posted` (mit `kind`: `subscription`, `refund`, `transfer`, `exit`, `loss_deduction`, `payout`, `limitation_writeoff`, `reversal`, `share_donation`, `additional_shares`) |
| Einstellungen | `settings.share-price-changed` |

Ein Event wird nie geändert oder gelöscht. Fehler werden mit einem Gegen-Event korrigiert
(z. B. `member.death-revoked`) bzw. bei Buchungen mit einem Storno (`booking.posted` der Art
`reversal`, das auf die ursprüngliche Buchung verweist).

**Migration aus dem Altsystem** (Schritt 7, siehe `Plan.md`): Sie schreibt dieselben Events wie
die App, erkennbar am Akteur `migration`. Neu sind nur zwei Methoden am Mitglied:
`Member.migrate` legt eine Person mit den übernommenen Adresszeilen an (die Anschrift darf
fehlen) und schreibt Briefanrede, „keine Post“ und Hinweise als eigene Änderungsevents;
`member.migrate_version` übernimmt eine spätere Version der Personendaten (`PersonData`) aus der
Historie. Deren Änderungsevents tragen zusätzlich das Feld `valid_from` (ab wann die Version im
Altsystem galt). Die Handler lesen es nicht; es ist für eine spätere Ansicht „Verlauf“ gedacht.

Das Modul `migration/` ist in Schritte geteilt: `source.py` liest die CSV-Dateien aus
`mdb-export` (`LegacyPerson`, `LegacyBooking`) und die Einzelfälle aus `migration.toml`
(`Decisions`); `plan.py` rechnet daraus mit reinen Funktionen den `MigrationPlan` (je Person ein
`PersonPlan`, je Buchung ein `BookingPlan`, übersprungene Personen und Buchungen, `problems`).
Geschrieben wird nichts, solange `problems` nicht leer ist. `run.py` baut daraus mit den
normalen Methoden Nummernregister, Hauptbuch und Mitglieder im Speicher auf (`build`, Fehler mit
Ort in `errors`), `check.py` gleicht Saldo und Anteile je Konto mit allen alten Buchungen ab
(`compare`) und fasst zusammen (`summary`), `run.save` speichert in einer Transaktion mit dem
Akteur `migration`. Der Befehl `migrate` (siehe Kommandozeile) ruft das der Reihe nach auf und
bricht vor dem Speichern ab, sobald es Probleme, Fehler oder Abweichungen gibt; er läuft nur, wenn
das Genossenschaftskonto da ist und es noch keine Mitglieder gibt.

### Mehrere Aggregate zusammen speichern

Manche Vorgänge ändern mehrere Streams. `Database.save_all([…], actor)` speichert sie in **einer**
Transaktion, alle oder keines:

- **Antrag** (`members/services.apply_for_membership`): `MemberNumbers` (Nummer vergeben),
  `Member` (Antrag) und `Ledger` (Konto mit derselben Nummer eröffnen). Ein Mitglied ohne Konto
  kann es so nicht geben.
- **Buchung** (`accounts/bookings._book`): `Ledger` (Buchung) und `Member` (z. B. `member.paid-in`,
  wenn die gezeichneten Anteile damit eingezahlt sind).

Scheitert das Speichern mit `ConcurrencyError`, weil jemand anderes gleichzeitig gespeichert hat,
lädt der Vorgang den neuen Stand und versucht es noch einmal, höchstens dreimal (`MAX_ATTEMPTS`).
So rechnet z. B. der Abgleich der Einzahlung nie mit einem veralteten Kontostand.

### Projektionen

| Projektor | Tabellen | Wofür |
|---|---|---|
| `UserList` (`users/projections.py`) | `users` | Anmeldung, Benutzerliste, Rolle und Aktiv-Status bei jeder Anfrage |
| `MemberList` (`members/projections.py`) | `members`, `partial_notices` | Suche (`search_text`, klein geschrieben mit `casefold`) und Mitgliederliste |

Dazu kommt `login_attempts` in `projections.sqlite`. Diese Tabelle entsteht **nicht** aus Events,
Fehlversuche beim Anmelden sind kein fachliches Ereignis.

Vorgänge über den ganzen Bestand (Jahresende, Reports) laden die Mitglieder direkt aus ihren Events
(`members/services.all_members`). Bei einigen hundert Mitgliedern ist das schnell genug und spart
weitere Projektionen.

**Schema einer Projektion ändern:** Im Projektor `schema` anpassen und **`version` um eins
erhöhen**, und `tables` muss alle Tabellen nennen. Beim nächsten Start löscht `Projections.create_schema()`
die Tabellen dieses Projektors, legt sie neu an und befüllt sie aus allen Events. Die anderen
Projektoren bleiben unberührt. Von Hand muss nichts gelöscht werden.

**Ablauf beim Start** (`app.lifespan` → `db.prepare`): Datenordner anlegen, Tabelle `events`
anlegen, Projektionen prüfen bzw. anlegen, `login_attempts` anlegen, Projektionen aufholen lassen.
Deshalb läuft die App in **einem** Prozess. Zwei Prozesse würden gleichzeitig aufholen.

## Datenbanken

| Datei | Inhalt | Sichern? |
|---|---|---|
| `eventstore.sqlite` | Tabelle `events`: alle Events | **ja**, sie ist die einzige Quelle der Wahrheit |
| `projections.sqlite` | Lesetabellen, `projection_checkpoints`, `login_attempts` | nein, entsteht beim Start neu, wenn sie fehlt |

Beide laufen im WAL-Modus (`PRAGMA journal_mode = WAL`), mit `busy_timeout` 5 s. Jede Anfrage
öffnet über `Depends(get_db)` eigene Verbindungen und schließt sie danach. Die Endpunkte sind
normale `def`-Funktionen (kein `async`), weil `sqlite3` blockiert. FastAPI führt sie in einem
Threadpool aus. Transaktionen steuert `eventsource.transaction()` (`BEGIN IMMEDIATE`). Verschachtelte
Aufrufe schließen sich der äußeren Transaktion an.

**Geldbeträge** sind überall ganze Cent (`int`): in Events, Datenbank und API. In Euro umgerechnet
wird nur an der Oberfläche und in der CLI (`core/money.py`). **Zeitstempel** sind UTC, fachliche Daten
(Wertstellung, Eintritt, …) reine Datumswerte ohne Uhrzeit.

## API

Alle Endpunkte liegen unter `/api` und sprechen JSON, Ausnahme sind die Excel-Downloads der Reports.

- **Abfragen** per `GET`, z. B. `GET /api/accounts/{number}`, `GET /api/users`.
- **Befehle** per `POST`, benannt nach der fachlichen Absicht wie die Methode am Aggregat, alle
  Daten im Body (auch die ID): `POST /api/members/admit` mit `{member_id, decision_date}`. Ein Befehl
  liefert das geänderte Objekt zurück. Kein REST mit `PUT`/`DELETE`.
- Pfade in kebab-case, JSON-Felder in snake_case.
- **Buchungen** nur über fachliche Vorgänge (`/api/accounts/subscribe`, `/refund`, `/transfer`,
  `/payout`, `/reverse`, …). Einen Endpunkt für eine freie Buchung gibt es nicht, und Beträge
  berechnet der Service aus Anteilen × Anteilspreis.

| Bereich | Präfix | Beispiele |
|---|---|---|
| Anmeldung, eigenes Konto | `/api` | `POST /login`, `POST /logout`, `GET /me`, `POST /me/change-password` |
| Benutzerverwaltung (Admin) | `/api/users` | `GET` (Liste), `GET /{id}`, `POST /register`, `POST /change-role`, `POST /deactivate` |
| Mitglieder | `/api/members` | `POST /search`, `GET /{id}`, `GET /{id}/history`, `POST /apply`, `POST /admit`, `POST /give-notice`, `POST /change-address` |
| Konten und Buchungen | `/api/accounts` | `GET /{number}`, `GET /claims`, `GET /balances?day=&include_zero=`, `GET /exits/{year}`, `POST /subscribe`, `POST /reverse`, `POST /post-exits` |
| Reports | `/api/reports` | `GET /warnings`, `GET /members-geng`, `GET /members-assembly`, `GET /members-mailing`, `GET /account-balances`, `GET /fiscal-year-events` |

Die vollständige Beschreibung erzeugt FastAPI selbst. Lokal mit `CM_API_DOCS=true` unter
http://localhost:8000/docs, im Betrieb ist sie abgeschaltet.

## Sicherheit

- **Anmeldung:** Kennwörter als Argon2-Hash (`pwdlib`). Nach dem Login liegen Benutzer-ID und
  CSRF-Token in einem **signierten Session-Cookie** (Starlette `SessionMiddleware`, Schlüssel
  `CM_SECRET_KEY`, HttpOnly, SameSite=Lax, Secure). Die Session läuft nach `CM_SESSION_TIMEOUT`
  Sekunden ohne Anfrage ab.
- **CSRF:** Jede schreibende Anfrage (`POST` usw.) muss das Token aus der Session im Header
  `X-CSRF-Token` mitschicken. Das Frontend bekommt es von `/api/login` bzw. `/api/me`.
- **Zugriff verweigert als Standard:** Jeder Endpunkt außer `PUBLIC_PATHS` (`/healthz`,
  `/api/login`) hängt an `current_user` oder `require_role(...)` (`users/access.py`). Der Test
  `test_access.py` prüft das für **alle** Routen, ein vergessener Schutz fällt also sofort auf.
  Benutzer, Rolle und Aktiv-Status werden bei jeder Anfrage frisch aus der Projektion gelesen.
  Deaktivieren und Rollenwechsel wirken damit sofort.
- **Rollen:** `admin` nur Benutzerverwaltung; `accounting` alle Fachfunktionen;
  `accounting_readonly` nur lesen. Der Vue-Router prüft die Rolle auch, das ist aber nur Komfort.
  Verbindlich ist das Backend.
- **Login-Sperre:** nach `CM_LOGIN_MAX_ATTEMPTS` Fehlversuchen ist der Benutzername für
  `CM_LOGIN_LOCKOUT_SECONDS` gesperrt, auch für unbekannte Namen. Die Fehlermeldung verrät nicht,
  ob es den Namen gibt.
- **Security-Header** (`security.py`) bei jeder Antwort: strenge CSP (`script-src 'self'`),
  `X-Frame-Options`, `nosniff` u. a., HSTS nur bei HTTPS.
- **Reverse Proxy:** `X-Forwarded-For` und `X-Forwarded-Proto` gelten nur von den Adressen in
  `CM_TRUSTED_PROXIES` (das Gateway des Compose-Netzes). uvicorn läuft deshalb mit
  `--no-proxy-headers`, die Entscheidung liegt an einer einzigen Stelle.

## Frontend

- **`api.ts`:** Die Funktion `api<T>(pfad, {method, body})` erledigt alle Aufrufe. Sie setzt JSON
  und CSRF-Token und macht aus Fehlern ein `ApiError` mit der deutschen Meldung des Backends. Bei
  401 ruft sie den Handler, der zur Anmeldung zurückführt.
- **`auth.ts`:** `currentUser` ist ein reaktiver Wert (`ref`), den alle Komponenten teilen. Ändert
  er sich, zeichnet Vue Menü und Seiten neu. `loadMe()` prüft beim Start, ob die Session noch gilt.
- **`router.ts`:** Alle Seiten mit `meta.roles`. Ein Navigation Guard (`beforeEach`) leitet
  Nicht-Angemeldete zur Anmeldung und Benutzer ohne passende Rolle zur Startseite.
  `createWebHistory()` sorgt für echte Pfade wie `/members/5`. Im Betrieb liefert FastAPI dafür bei
  unbekannten Pfaden `index.html` aus (SPA-Fallback in `app.py`, `SpaStaticFiles`).
- **`members.ts`, `accounts.ts`, `reports.ts`, `users.ts`:** TypeScript-Typen, die zu den
  Pydantic-Schemas des Backends passen müssen (jeweils mit Hinweis auf die Backend-Datei), und die
  Funktionen für die Aufrufe.
- **`views/`:** eine Komponente je Seite (Suche, Antrag, Mitglied, Konto, Jahresende, Ansprüche,
  Salden, Reports, Benutzer) und wiederverwendbare Teile (`NameFields`, `AddressFields`, `BookingForm`, …).
- **Geld in der Oberfläche:** Anzeige und Eingabe in Euro mit deutscher Schreibweise, an das Backend
  gehen ganze Cent bzw. Anteile.

## Konfiguration

Alle Einstellungen kommen aus Umgebungsvariablen mit Präfix `CM_` (`config.py`). Eine `.env` im
aktuellen Ordner oder darüber wird mitgelesen, echte Umgebungsvariablen gehen vor. Vorlage:
`.env.example`.

| Variable | Standard | Bedeutung |
|---|---|---|
| `CM_DATA_DIR` | `data` | Ordner für die beiden SQLite-Dateien (im Container `/data`) |
| `CM_LOG_LEVEL` | `INFO` | `DEBUG` … `CRITICAL` |
| `CM_SECRET_KEY` | leer | Schlüssel für das Session-Cookie. Leer: zufällig bei jedem Start, Warnung im Log |
| `CM_SESSION_TIMEOUT` | `1800` | Sekunden ohne Anfrage bis zur Abmeldung |
| `CM_SESSION_COOKIE_SECURE` | `true` | Cookie nur über HTTPS (Browser erlauben `http://localhost`) |
| `CM_LOGIN_MAX_ATTEMPTS`, `CM_LOGIN_LOCKOUT_SECONDS` | `3`, `900` | Login-Sperre |
| `CM_TRUSTED_PROXIES` | leer | Adressen, deren `X-Forwarded-*` gelten, mit Komma getrennt |
| `CM_COOPERATIVE_ACCOUNT_NAME` | `Unser Dorfladen Schlichten eG` | Bezeichnung von Konto 9999 |
| `CM_FRONTEND_DIR` | leer | gebaute Vue-App. Leer: keine Oberfläche (Entwicklung mit Vite) |
| `CM_API_DOCS` | `false` | `/docs`, `/redoc`, `/openapi.json` einschalten |
| `CM_UID`, `CM_GID`, `CM_PORT`, `CM_BIND_ADDRESS` | `1000`, `1000`, `8001`, `127.0.0.1` | nur `compose.yaml`: Benutzer im Container, Port und Adresse auf dem Host |

## Kommandozeile

`coop-manager` (`cli.py`, in der Entwicklung `uv run coop-manager …` aus `backend/`, im Container
`docker exec coop-manager-app-1 coop-manager …`):

| Befehl | Wirkung |
|---|---|
| `create-admin [--username] [--full-name]` | Admin anlegen, Kennwort wird verdeckt abgefragt |
| `set-share-price <betrag>` | Anteilspreis in Euro festlegen, z. B. `50` |
| `show-settings` | Anteilspreis anzeigen |
| `create-cooperative-account` | Konto 9999 der Genossenschaft anlegen (einmalig) |
| `backup [ziel]` | stimmige Kopie des Event Store, Standard `<CM_DATA_DIR>/backup/eventstore.sqlite` |
| `migrate <csv-ordner> <migration.toml> [--dry-run]` | Altdaten übernehmen (einmalig, Schritt 7); `--dry-run` prüft nur |

## Logging

Logs gehen als **eine JSON-Zeile je Eintrag** nach stdout (`logs.py`), auch die von uvicorn. Felder:
`time` (UTC), `level`, `logger`, `message` und alles, was der Code per `extra={…}` mitgibt. Fachliche
Vorgänge loggen auf Englisch mit IDs und `actor`, aber ohne Personendaten, z. B.
`{"message": "booking posted", "kind": "subscription", "account": 12, "actor": "…"}`.
Im Container: `docker logs coop-manager-app-1`.

## Tests und Prüfungen

```bash
cd backend
uv run pytest            # alle Tests (Domain, Services, API, CLI, App)
uv run ruff check        # Linter, u. a. Docstrings Pflicht außer in Tests
uv run ruff format       # Formatierung, Zeilenlänge 120
uv run pyright           # Typprüfung
cd ../frontend
npm run type-check       # TypeScript (vue-tsc)
```

- Die API-Tests nutzen `TestClient` mit einem eigenen Datenordner je Test (`tmp_path`, Fixtures in
  `tests/conftest.py`). Eine lokale `.env` wird dabei ignoriert.
- Testdaten sind **erfunden**. Echte Mitgliederdaten aus `Beispieldaten/` gehören nie in Tests.
- Frontend-Tests gibt es noch nicht.

## Häufige Änderungen

**Neue fachliche Aktion an einem Aggregat**
1. In `domain.py` eine Methode, die die Regeln prüft (`DomainError` mit deutscher Meldung) und
   `self._record("bereich.etwas-passiert", …)` aufruft. Dazu einen Handler mit
   `@on("bereich.etwas-passiert")`, der nur den Zustand setzt.
2. Betrifft es eine Lesetabelle: Handler im Projektor ergänzen. Ändert sich deren Schema, die
   `version` erhöhen.
3. In `services.py` eine Funktion: laden, Methode aufrufen, `db.save(…, actor)`, loggen.
4. In `schemas.py` das Eingabemodell, in `api.py` den Endpunkt mit `require_role(...)`.
5. Tests für Domain, Service und API, im Frontend Typ, Aufruf und Oberfläche, und das
   Benutzerhandbuch (`Dokumentation/handbuch/handbuch.js`) mitpflegen.

**Eventtyp umbenennen oder Event-Daten umbauen:** besser nicht. Gespeicherte Events bleiben, wie sie
sind. Ein neuer Eventtyp mit eigenem Handler ist sicherer, alte Events behalten ihren Handler.

**Neue Einstellung:** Feld in `Settings` und `load_settings()` (`config.py`), Zeile in
`.env.example`, Test in `test_config.py`, ggf. `DEPLOYMENT.md`.

**Neue Python- oder npm-Abhängigkeit:** `uv add <paket>` in `backend/` bzw. `npm install <paket>`
in `frontend/`. Die Lock-Dateien (`uv.lock`, `package-lock.json`) mit committen, Docker baut genau
danach.

## Bau und Betrieb

- **`Dockerfile`**, zwei Stufen: `node:24-slim` baut die Vue-App (`npm ci`, `npm run build`), das
  Image `python:3.14-slim` bekommt uv, die Abhängigkeiten aus `uv.lock`, den Code und nur die
  fertigen Dateien aus `dist`. Es läuft als Benutzer ohne Root-Rechte, mit Healthcheck auf
  `/healthz` und einem uvicorn-Prozess.
- **`compose.yaml`**: `./data` als `/data`, Port `127.0.0.1:8001`, Einstellungen aus `.env`.
- **`deploy.sh`**: überträgt eine feste Dateiliste per `tar` über `ssh` aufs NAS, dort
  `docker compose up -d --build`.
- **Sicherung:** täglich `coop-manager backup` per DSM-Aufgabenplaner, danach Hyper Backup.

Einrichtung, Updates, Wiederherstellen und Fehlerbilder: `DEPLOYMENT.md`.
