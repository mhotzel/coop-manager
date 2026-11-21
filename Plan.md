# Plan: coop-manager – Mitgliederverwaltung der Unser Dorfladen Schlichten eG

Neubau der Mitgliederverwaltung als Webanwendung. Grundlage ist `Konzeption.md`, die Bildschirm-
entwürfe und Beispiellisten liegen in `Beispieldaten/` (nicht im Repository). Dieses Dokument hält
alle abgestimmten Entscheidungen fest und wird laufend ergänzt.

## Ausgangslage und Ziele

- **Vorbild:** Architektur, Event Store, Projektionen, Backup und Deployment wie im Projekt
  `purchase-prices` (github.com/mhotzel/purchase-prices, lokal `../purchase-prices`).
- **Betrieb:** im Container mit `docker compose`, Zielsystem Synology-NAS (siehe
  `purchase-prices/DEPLOYMENT.md`).
- **Rechtsgrundlage:** Satzung v11 vom 30.06.2015 (geltende Fassung),
  https://www.dorfladen-schlichten.de/wp-content/uploads/2015/10/2015-06-30_Satzung-Dorfladen-Schlichten_v11.pdf,
  dazu das Genossenschaftsgesetz (GenG).
- **Versionsverwaltung:** privates Repository github.com/mhotzel/coop-manager, Branch `main`.

## Vorgehen

1. Fundament: Event Store und Projektionen aus `purchase-prices` übernehmen, Projektstruktur
   (Backend mit `uv`, Frontend Vue 3 mit Vite) – erledigt
   - 1a: Backend-Grundgerüst mit `uv`
   - 1b: Frontend-Grundgerüst mit Vite, Vue 3 und TypeScript
   - 1c: Events, Aggregate und Event Store
   - 1d: Projektionen
   - 1e: Anbindung an FastAPI
2. Infrastruktur: Konfiguration, Logging, Security-Header, Layout, Theme – erledigt
   - 2a: Konfiguration (`CM_*`)
   - 2b: Logging als JSON-Zeilen auf stdout
   - 2c: Security-Header
   - 2d: Layout und Theme im Frontend
3. Benutzerverwaltung: Login, Login-Sperre, Anlage durch Admin, Kennwort ändern, deaktivieren, löschen
   – erledigt
   - 3a: Aggregat `User` mit Events, Prüfungen und Kennwort-Hash
   - 3b: Projektion, Services mit Login-Sperre, CLI `create-admin`
   - 3c: Login über die API: Session-Cookie, CSRF, Zugriffsprüfung je Rolle
   - 3d: Login im Frontend mit Vue Router
   - 3e: Benutzerverwaltung durch den Admin, auch Kennwort neu setzen
   - 3f: Eigenes Kennwort ändern
4. Mitglieder: Aggregat, Nummernvergabe, Suche, Bearbeitung, Adresszeilen und Briefanrede – erledigt
   - 4a: Aggregat `Member` mit Personendaten und Änderungsbefehlen, Adresszeilen und Briefanrede
   - 4b: Nummernvergabe, Zulassung und Ablehnung, Projektion und Suche, Services
   - 4c: API mit Befehlen und Abfragen
   - 4d: Frontend: Suche, Antrag, Detail- und Bearbeitungsseite
5. Konten und Buchungen: Eintritt, Kündigung, Austritt/Auszahlung, Umbuchung, Kontoansicht
   - 5a: Anteilspreis als Systemeinstellung, vorerst per CLI
   - 5b: Konten und Hauptbuch (Aggregat `Ledger`)
     - Teil 1: Konten eröffnen (Mitgliedskonto mit dem Antrag, Genossenschaftskonto per CLI)
     - Teil 2: Buchungen, Saldo und Anteile je Konto
   - 5c: Eintritt und Rückzahlung, Status „Mitglied“
     - Teil 1: Domäne und Services (Eintritt, Rückzahlung, `member.paid-in`, Status „Mitglied“ mit
       Eintrittsdatum), Projektion, Tests
     - Teil 2: API-Endpunkte für Buchungen und Kontostand
   - 5d: Frontend: Kontoansicht und Buchungsmaske
     - Teil 1: Kontoansicht (auch Genossenschaftskonto im Menü), Konto-Link am Mitglied
     - Teil 2: Buchungsmaske für Eintritt und Rückzahlung
   - 5e: Storno
     - Teil 1: Domäne und Service (Vorgang Storno mit Prüfungen und Pflichtgrund, Geldeingang am
       Mitglied zurücknehmen bzw. neu festhalten), Referenz im Event `booking.posted`, Tests
     - Teil 2: API `POST /api/accounts/reverse` mit `{booking_id, reason}`, Kontoansicht mit
       „storniert durch“ bzw. „Storno zu“ je Buchung
     - Teil 3: Frontend: Knopf „Stornieren“ je Buchung (nur Buchhaltung), Abfrage des Grundes,
       Kennzeichnung der Paare, Filter „Stornierte ausblenden“
   - 5f: Kündigung, Teilkündigung, Tod und Ausschluss (aufgeteilt nach Vorgang, Stand 2026-11-18)
     - Teil 1: Kündigung und Teilkündigung in Domäne, Status, Service und API
     - Teil 2: Kündigung im Frontend, einschließlich „Kündigung zurücknehmen“
     - Teil 3: Tod erfassen, mit Hinweis auf die Adresszeilen der Erben
     - Teil 4: Ausschluss erfassen und aufheben (Widerspruch beim Aufsichtsrat erfolgreich)
   - 5g: „Ausscheiden zum Jahresende buchen“
     - Teil 1: Domäne, Service und API (Liste der Fälligen, Buchen, Storno öffnet wieder)
     - Teil 2: Seite „Jahresende“ im Frontend
   - 5h: Umbuchung, Auszahlung, Verlustvortrag, Verjährung, Liste offener Ansprüche
     - Teil 1: Auszahlung, Kürzung Verlustvortrag, Ausbuchung Verjährung (Backend und Maske)
     - Teil 2: Seite „Offene Ansprüche“
     - Teil 3: Umbuchung zwischen Mitgliedskonten (Stand 2026-11-19)
       - a: Domäne, Service, Storno zwischen zwei Mitgliedskonten, API, Tests
       - b: Frontend: Buchungsart „Umbuchung“ in der Buchungsmaske mit Anzeige des Zielkontoinhabers,
         Datum auf der Mitgliederseite
   - 5i: Weitere Anteile zeichnen und einzahlen (für bestehende Mitglieder, Stand 2026-11-19)
     - Teil 1: Zeichnung am Mitglied, Buchungsart „Weitere Anteile“, Abgleich, API, Tests
     - Teil 2: Frontend: Aktion an der Mitgliederseite, Buchungsart in der Buchungsmaske
   - 5j: Ausscheiden mit Spende des Anteils (Stand 2026-11-18)
     - Teil 1: Domäne, Buchungsart, Service, Storno, API, Tests
     - Teil 2: Frontend: Buchungsart „Spende Anteil“ in der Buchungsmaske des Kontos (nicht als
       Aktion am Mitglied, Stand 2026-11-19), Datum der Spende auf der Mitgliederseite
6. Reports: die drei Excel-Listen zum Stichtag
   - 6a: Mitgliederliste nach GenG (Backend: Abfrage, Excel, API)
   - 6b: Frontend: Seite „Reports“ mit Stichtag und Download
   - 6c: Liste zur Generalversammlung (Anwesenheit, Unterschrift)
   - 6d: Seriendruck-Liste
   - 6e: Warnung, wenn zum Stichtag ein Ausscheiden noch nicht gebucht ist
   - 6f: Auswertung der Vorgänge eines Geschäftsjahres (Stand 2026-11-19), siehe unten
7. Migration der Altdaten (siehe Abschnitt „Migration der Altdaten“)
   - 7a: Access-Datei analysieren, Einzelfälle mit Matthias entscheiden (erledigt 2026-11-21)
   - 7b: Migrationsevents und Aufbau des Skripts (erledigt 2026-11-21)
   - 7c: Migrationsskript als CLI-Befehl, Tests mit erfundenen Daten (erledigt 2026-11-21)
     - Teil 1: `Member.migrate` und Historie mit `valid_from` (erledigt 2026-11-21)
     - Teil 2: `source.py` und `plan.py` (erledigt 2026-11-21)
     - Teil 3: `run.py`, `check.py`, CLI-Befehl `migrate` (erledigt 2026-11-21)
   - 7d: Probeläufe lokal mit Abgleich der Salden und Anteile (erledigt 2026-11-21)
   - 7e: Migration auf dem NAS
8. Container, Backup per Cron, Deployment auf der Synology
   (Stand 2026-11-19: vor der technischen Doku; Doku als Markdown wie `purchase-prices/DEPLOYMENT.md`)
   - 8a: FastAPI liefert die gebaute Vue-App aus, `/docs` und `/redoc` im Betrieb aus (erledigt 2026-11-21)
   - 8b: Dockerfile (zwei Stufen) und `compose.yaml`, lokal getestet (erledigt 2026-11-21)
   - 8c: Backup-Befehl für den Event Store (erledigt 2026-11-21)
   - 8d: Synology: Cron-Job für das Backup, `deploy.sh`, `DEPLOYMENT.md` (erledigt 2026-11-21,
     App läuft unter `https://mitgliederdb.dorfladen-schlichten.de`)
9. Ausbaustufe: API-Keys, MCP-Server, OAuth2/JWT
10. Saldenliste (gewünscht 2026-11-21, siehe Abschnitt „Saldenliste“)
   - 10a: Backend: `accounts/balances.py`, `GET /api/accounts/balances`, Tests (erledigt 2026-11-21)
   - 10b: Frontend: Seite „Salden“ mit Stichtag, Tabelle und Summenzeile, Menüeintrag (erledigt 2026-11-21)
   - 10c: Excel „Saldenliste“ auf der Seite „Reports“

## Entscheidungen

### Architektur

- **Backend: FastAPI**, weil das Backend für die SPA nur JSON liefert (Pydantic-Validierung,
  OpenAPI-Beschreibung, OAuth2 und MCP später einfach anzubinden).
- **Event Sourcing in schlank** wie in `purchase-prices`: Aggregate mit Methoden und einfache
  Service-Funktionen, keine Command- oder Query-Busse. `eventstore.sqlite` ist die einzige Quelle
  der Wahrheit, Projektionen in `projections.sqlite` mit Checkpoint pro Projektor, synchron nach
  jedem Speichern. Fachliche Regeln prüft der Service, bevor das Event entsteht. Ein Prozess.
- **Schemaversion je Projektor** (Stand 2026-11-19): Jeder Projektor hat eine `version`, die
  Checkpoint-Tabelle merkt sich, mit welcher Version seine Tabellen angelegt wurden. Weicht sie beim
  Start ab, werden seine Tabellen gelöscht, neu angelegt und aus allen Events neu befüllt; die
  anderen Projektoren bleiben unberührt. **Wer das `schema` eines Projektors ändert, erhöht seine
  `version`.** Grund: `CREATE TABLE IF NOT EXISTS` ändert eine bestehende Tabelle nicht, und
  `projections.sqlite` soll im Betrieb nicht von Hand gelöscht werden müssen.
- **KISS:** Der Code soll so einfach sein, dass Matthias ihn selbst durchschaut.
- **Frontend: Vue 3 mit TypeScript und Vite**, eigenes CSS auf Basis von `style.css` und
  `colorscheme-dorfladen.css` aus `purchase-prices`, keine Komponentenbibliothek. Svelte wurde
  erwogen (Stand 2026-11-15): kürzere Syntax, aber kleineres Ökosystem, für eine reine SPA der Umweg
  über SvelteKit und viele veraltete Anleitungen seit Svelte 5. Gegen eine fertig gestaltete
  Bibliothek spricht das einheitliche Aussehen mit `purchase-prices` und die zusätzliche
  Abhängigkeit (bei Svelte meist samt Tailwind).
- **Repo-Struktur:** `backend/` (Paket `coop_manager`, Tests, `pyproject.toml`) und `frontend/`.
  Im Betrieb liefert FastAPI die gebaute SPA selbst aus: ein Container, gleiche Herkunft, kein
  CORS. Dockerfile in zwei Stufen (Node baut das Frontend, dann Python).
- **Module im Backend:** `core`, `users`, `members`, `accounts`, `reports`, `migration`, je mit
  `domain.py`, `services.py`, `projections.py`, `schemas.py` (Pydantic) und `api.py` (dünn).
- **Event Sourcing liegt in `coop_manager/eventsource/`**, nicht unter `core`: Es ist Infrastruktur
  ohne `domain.py`, `services.py` usw. und bleibt so leicht mit `purchase-prices` vergleichbar.
- **Jedes Event speichert seinen Auslöser (`actor`):** den angemeldeten Benutzer, bei der Migration
  `migration`. Das Aggregate kennt ihn nicht, er wird erst beim Speichern über
  `save(..., actor=...)` gesetzt. So bleibt nachvollziehbar, wer welche Änderung gemacht hat.
- **Datenbankzugriff über `Depends(get_db)`:** Jeder Request öffnet eigene Verbindungen und schließt
  sie danach. Endpunkte sind normale `def`-Funktionen, weil `sqlite3` blockiert; deshalb laufen die
  Verbindungen mit `check_same_thread=False`.
- **API nach Befehlen und Abfragen (aufgabenorientiert, wie bei DDD/CQRS):** Abfragen lesen per
  `GET` (`GET /api/users`, `GET /api/users/{id}`). Befehle ändern per `POST`, heißen nach der
  fachlichen Absicht wie die Methode am Aggregat und tragen alle Daten im JSON-Body, auch die ID:
  `POST /api/users/register`, `POST /api/users/change-role` mit `{user_id, role}`. Pfade in
  kebab-case, JSON-Felder in snake_case. Ein Befehl liefert das geänderte Objekt zurück. Kein
  REST mit `PUT`/`DELETE`, weil dabei die fachliche Absicht verloren geht.
- **Menü und Seiten nach Rolle:** Der Admin sieht nur die Benutzerverwaltung, die Buchhaltung die
  Fachfunktionen. Der Router prüft die Rolle ebenfalls, verbindlich ist aber die Prüfung im Backend.
- **Alle Fachlogik im Backend**, auch Adresszeilen, Briefanrede und Nummernvergabe; das Frontend
  zeigt an und ruft die API auf.
- **Sprache:** Code, Events und Bezeichner englisch nach dem Glossar unten, Oberfläche und
  Dokumentation deutsch.

### Technische Regeln

- **Zeitstempel intern immer in UTC**, Anzeige in Europe/Berlin. Fachliche Daten (Buchungstag,
  Wertstellung, Eintrittsdatum usw.) sind reine Datumswerte ohne Uhrzeit.
- **Geldbeträge** als ganze Cent (`int`) in Events, Datenbank und API, Umrechnung nur an der
  Oberfläche. Eingabe dort in deutscher Schreibweise: Komma als Dezimaltrenner, Punkte als
  Tausendertrenner, richtig gruppiert („1.500,50“). „150.50“ ist ungültig.
- **Login:** signiertes HttpOnly-Session-Cookie mit Timeout, CSRF-Token im Header. Standard ist
  „Zugriff verweigert“, Rollen je Endpoint; Rollen und Aktiv-Status bei jedem Request frisch
  gelesen; Login-Sperre und einheitliche Fehlermeldung; Ersteinrichtung per CLI `create-admin`.
  Session läuft nach 30 Minuten ohne Anfrage ab (`CM_SESSION_TIMEOUT`). Fehlt `CM_SECRET_KEY`,
  erzeugt die App einen zufälligen Schlüssel und warnt im Log. „Zugriff verweigert“ sichert ein
  Test ab, der alle Routen auf `current_user` bzw. `require_role` prüft (Ausnahmen in
  `PUBLIC_PATHS`). Fachliche Fehler kommen als `{"detail": "..."}` mit 400 bzw. 404.
- **Security-Header** setzt die App selbst, CSP `script-src 'self'`. Die CSP bleibt streng, auch
  wenn sie die Swagger-Oberfläche unter `/docs` sperrt; `/docs` und `/redoc` werden im Betrieb
  abgeschaltet. HSTS nur bei HTTPS. `X-Forwarded-*` gilt nur von Adressen aus
  `CM_TRUSTED_PROXIES` (uvicorns `ProxyHeadersMiddleware`).
- **API-Dokumentation nur auf Wunsch** (Stand 2026-11-21): `/docs`, `/redoc` und `/openapi.json`
  gibt es nur mit `CM_API_DOCS=true`; Standard ist aus, lokal in der `.env` einschalten.
- **Die gebaute Vue-App liefert FastAPI selbst aus** (Stand 2026-11-21), ein Server, eine Adresse:
  `CM_FRONTEND_DIR` zeigt auf den Ordner aus `npm run build`; leer heißt keine Oberfläche
  (Entwicklung mit Vite). Eingehängt wird er als Letztes unter `/`, API-Routen haben Vorrang.
  Unbekannte Pfade liefern `index.html` (SPA-Fallback, wegen `createWebHistory`), außer unter
  `/api/`, dort bleibt es beim 404 als JSON. Eigene Cache-Header vorerst nicht.
- **Container** (Stand 2026-11-21) nach dem Vorbild `purchase-prices`: `Dockerfile` im Hauptordner
  mit zwei Stufen (Node baut die Vue-App, ins Python-Image kommt nur `dist`), `compose.yaml` mit
  `./data` als Volume, Benutzer aus `CM_UID`/`CM_GID`. **Ein uvicorn-Prozess**, weil beim Start die
  Projektionen aufholen; `--no-proxy-headers`, damit allein `CM_TRUSTED_PROXIES` über
  `X-Forwarded-*` entscheidet. **Port 8001** auf dem Host (`CM_PORT`), weil `purchase-prices` auf der
  Synology 8000 belegt; standardmäßig nur an `127.0.0.1`, HTTPS macht der Reverse Proxy.
  `.dockerignore` hält u. a. `Beispieldaten/` und `.env` aus dem Build heraus.
- **Datensicherung** (Stand 2026-11-21) wie bei `purchase-prices`: `coop-manager backup [ziel]`
  schreibt eine stimmige Kopie des Event Store, Standard `<CM_DATA_DIR>/backup/eventstore.sqlite`:
  über die Backup-API von SQLite (auch im laufenden Betrieb), als eine Datei ohne WAL, erst nach dem
  Integritätscheck unter dem endgültigen Namen. Nur der Event Store, die Projektionen entstehen
  daraus neu. Eine Kopie, die jedes Mal ersetzt wird; ältere Stände hält Hyper Backup vor. Fehlt der
  Event Store, bricht der Befehl ab, statt eine leere Datei zu sichern. Fehler enden mit Exit-Code 1,
  damit der Aufgabenplaner benachrichtigt. Aufruf im Container: `docker exec coop-manager-app-1
  coop-manager backup`.
- **Betrieb auf der Synology** (Stand 2026-11-21), Anleitung in `DEPLOYMENT.md`: dasselbe NAS
  `ds218-dls` wie `purchase-prices`, Ordner `/volume1/IT-Systeme/Docker/coop-manager` mit eigener
  ACL (nur `chef`, `administrators`, `IT-Admin`), Adresse `https://mitgliederdb.dorfladen-schlichten.de`
  (CNAME auf `work.`, Let's Encrypt, DSM-Reverse-Proxy auf `localhost:8001`). Start **leer**, die
  Altdaten kommen mit der Migration. Sicherung täglich 20:00 per DSM-Aufgabenplaner, Hyper Backup
  um 20:30. `deploy.sh` überträgt eine ausdrückliche Dateiliste per `tar` über `ssh`, gebaut wird
  auf dem NAS (ARM64).
- **Python über uv:** uv verwaltet das Python selbst (`uv python install`), damit ein Upgrade der
  Distribution die Umgebung nicht bricht.
- **Betrieb:** Konfiguration über Umgebungsvariablen mit Präfix `CM_` (eine vorhandene `.env` wird
  automatisch gelesen, echte Umgebungsvariablen gehen vor), Logs als JSON-Zeilen auf stdout,
  `/healthz`, Backup des Event Stores per CLI-Befehl.
- **Werkzeuge:** Python 3.14, `uv`, `ruff` (Zeilenlänge 120, Docstrings Pflicht außer in Tests),
  `pyright` (Modus `standard`, `reportDeprecated` als Warnung), `pytest` (Domain, Services, API),
  `openpyxl` für die Reports. Frontend-Tests vorerst nicht, später bei Bedarf Vitest.

### Arbeitsweise

- Jeder Teil wird gemeinsam Schritt für Schritt entwickelt: Claude erzeugt den Code und erklärt
  dabei, was passiert und warum, auch die Grundlagen von FastAPI, Vue und TypeScript.
- Jeder Schritt endet mit Tests und einem Commit.

### Geschäftsjahr und Fristen

- **Geschäftsjahr = Kalenderjahr.**
- **Kündigungsfrist (Satzung 6.1):** zwei Jahre zum Ende des Geschäftsjahres. Das Ausscheiden
  erfolgt zum frühesten 31.12., der mindestens zwei Jahre nach Eingang der Kündigung liegt
  (Eingang 15.03.2026 → Ausscheiden 31.12.2028). Die App berechnet das Datum, es kann
  überschrieben werden.
- **Überschreiben des Ausscheidensdatums** (Stand 2026-11-18): Es muss ein 31.12. sein und nach
  dem Eingang der Kündigung liegen; früher als die Frist ist erlaubt (z. B. nach Vereinbarung mit
  dem Vorstand), solche Fälle prüft der Vorstand ohnehin.
- **Ausgeschieden ab dem 01.01.** (Stand 2026-11-18): Bis einschließlich 31.12. ist die Person
  noch gekündigt bzw. verstorben oder ausgeschlossen und zählt mit ihren Anteilen; ab dem
  Folgetag ist sie ausgeschieden. Reports zum Stichtag 31.12. zeigen sie also noch.

### Mitgliedschaft und Status

- Statusmodell der Mitgliedschaft:

  ```
  Antragsteller ─Zulassung + Geldeingang─▶ Mitglied ─Kündigung─▶ gekündigt ─Ende GJ (Frist)─▶ ausgeschieden
       └─Ablehnung durch den Vorstand / Rücknahme─▶ abgelehnt
                                 ├─Ausschlussbeschluss─▶ ausgeschlossen ─Ende GJ─▶ ausgeschieden
                                 ├─Tod─▶ verstorben (Erben, § 77 GenG) ─Ende GJ─▶ ausgeschieden
                                 ├─Übertragung aller Anteile (Umbuchung)─▶ ausgeschieden
                                 └─Spende des Anteils (sofort, ohne Frist)─▶ ausgeschieden
  ```

- **Antragsteller:** Die Person wird mit Eingang der Beitrittserklärung erfasst, mit Datum und
  Zahl der gezeichneten Anteile.
- **Zulassung durch den Vorstand (§ 15 GenG)** ist ein eigener Schritt mit Beschlussdatum.
  Mitglied wird die Person erst, wenn Zulassung und Geldeingang vorliegen, in beliebiger
  Reihenfolge. **Eintrittsdatum ist das spätere der beiden Daten.**
- **Das Mitgliedskonto wird schon mit dem Antrag angelegt** (auch Antragsteller haben ein Konto),
  damit eine Einzahlung vor der Zulassung sofort als Eintrittsbuchung erfasst werden kann. Die
  Anteile zählen in Listen und Reports erst ab der Mitgliedschaft.
- **Einzahlung und gezeichnete Anteile müssen übereinstimmen.** Weicht der Betrag ab, zeigt die
  App eine Warnung, und die Mitgliedschaft kommt erst zustande, wenn der Vorgang geklärt ist und
  Betrag und Anteile übereinstimmen. Lässt er sich nicht klären, wird zurückgezahlt und die
  Mitgliedschaft kommt nicht zustande.
- **Rückzahlung** bei Ablehnung oder ungeklärter Zahlung ist eine eigene Buchungsart:
  Soll Mitgliedskonto, Haben Pseudokonto.
- **Fehlzahlungen ohne Bezug zu Anteilen** (Stand 2026-11-21), auch nach dem Ausscheiden (z. B. ein
  weiterlaufender Dauerauftrag), werden nicht in der Mitgliederverwaltung gebucht, sondern in der
  Finanzbuchhaltung zurücküberwiesen. Die App führt nur Geschäftsguthaben; Fremdgeld auf dem
  Mitgliedskonto würde Saldo und Reports verfälschen. Es gibt dafür keine eigene Buchungsart.
- **Mitglieds- und Kontonummer werden bei der Erfassung des Antrags vergeben** (höchste Nummer + 1).
  Lücken durch abgelehnte Anträge sind zulässig. Für die Migration der Altdaten ist eine manuelle
  Vergabe möglich (nicht in der Oberfläche); die App prüft dabei die Eindeutigkeit.

### Ausscheiden mit Spende des Anteils

- **Bewusste Entscheidung (Stand 2026-11-18):** Ein Mitglied kann ausscheiden, indem es sein
  ganzes Guthaben der Genossenschaft spendet, **ohne Kündigungsfrist** und nicht nur zum 31.12.
  Rechtlich ist das umstritten (Kündigungsfrist nach Satzung 6.1 und § 65 GenG); Matthias hat es
  trotzdem so entschieden. Die App bildet den Vorgang ab, ob er im Einzelfall zulässig ist,
  verantwortet der Vorstand.
- **Nur ganz:** immer alle Anteile und der ganze Saldo, keine Teilspende.
- **Nur bei Mitgliedern**, auch gekündigten, am Tag der Spende. Nicht bei Antragstellern,
  Verstorbenen, Ausgeschlossenen oder schon Ausgeschiedenen.
- **Datum:** frühestens am Eintrittsdatum, höchstens heute; liegt schon ein Ausscheiden gebucht
  vor (Teilkündigung), muss es danach liegen. Ausgeschieden ist die Person **ab dem Folgetag**,
  wie bei den anderen Vorgängen.
- **Buchung** „Spende Anteil“: Soll Mitgliedskonto an Haben Genossenschaftskonto, ganzer Saldo und
  alle Anteile. Danach steht das Konto auf 0, es entsteht **kein Auseinandersetzungsanspruch**.
  Am Mitglied wird zusätzlich `member.shares-donated` mit dem Datum festgehalten, beides wird mit
  `save_all` gespeichert (wie der Geldeingang, Variante A).
- **Laufende Kündigungen und Teilkündigungen werden gegenstandslos** und bleiben stehen (wie beim
  Tod). Nach der Spende ist keine neue Kündigung mehr möglich.
- **Storno** der Spendenbuchung nimmt das Ausscheiden zurück (`member.donation-revoked`); eine
  frühere Kündigung gilt dann wieder.
- Fällt die Spende auf einen 31.12., erscheint sie nicht auf der Seite „Jahresende“, denn auf dem
  Konto ist nichts mehr auszubuchen.

### Umbuchung (Übertragung von Anteilen)

- **Allgemein, nicht nur für Erben** (Stand 2026-11-19): Anteile lassen sich auch unter Lebenden
  auf ein anderes Mitgliedskonto übertragen (§ 76 GenG).
- **Umfang:** frei wählbare Zahl von Anteilen, eins bis alle. Betrag = Anteile × aktueller Preis.
  Ein offener Anspruch aus einer früheren Teilkündigung bleibt beim Abgebenden. Anteile aus
  laufenden Teilkündigungen lassen sich nur mit allen anderen zusammen übertragen.
- **Buchung** „Umbuchung“: Soll abgebendes an Haben empfangendes Mitgliedskonto. Das
  Genossenschaftskonto ist nicht wählbar, das eigene Konto auch nicht.
- **Abgeben** dürfen Mitglieder, auch gekündigte, und Verstorbene, bei diesen auch nach dem 31.12.
  des Todesjahres (Tod erst später bekannt). Nicht Ausgeschlossene und Ausgeschiedene. Die
  Wertstellung liegt nach einem gebuchten Ausscheiden.
- **Empfangen** dürfen Mitglieder und zugelassene Antragsteller, die noch nicht eingezahlt haben.
  Beim Antragsteller (z. B. dem Erben) zählt die Umbuchung wie die Einzahlung und wird mit den
  gezeichneten Anteilen abgeglichen; passt sie, ist er Mitglied (Eintritt = das spätere von
  Zulassung und Wertstellung). Bei Mitgliedern gibt es keinen Abgleich; ihre gezeichneten Anteile
  bleiben, wie sie sind (siehe 5i).
- **Alle Anteile übertragen:** Die Person scheidet am Tag der Umbuchung aus, ausgeschieden ab dem
  Folgetag wie bei der Spende (Event `member.all-shares-transferred`). Laufende Kündigungen werden
  gegenstandslos, danach ist keine neue Kündigung möglich.
- **Ausscheiden schon gebucht** (z. B. Tod erst nach dem Jahresende bekannt, Jahresende schon
  gebucht): Erst die Ausscheidensbuchung stornieren, dann umbuchen. Ein „Umbuchen des Anspruchs“
  gibt es nicht.
- **Storno** macht beide Konten rückgängig. Hat der Abgebende danach wieder Anteile, entfällt sein
  Ausscheiden (`member.transfer-revoked`). Ist der Empfänger durch die Umbuchung Mitglied
  geworden, wird abgeglichen; er ist dann wieder Antragsteller, mit Warnung.

### Tod eines Mitglieds

- Rechtslage: Die Mitgliedschaft geht auf die Erben über und endet zum Schluss des Geschäftsjahres
  des Todes (§ 77 Abs. 1 GenG). Eine Fortsetzung durch die Erben (§ 77 Abs. 2) sieht die Satzung
  nicht vor.
- **Vorgang „Tod erfassen“** mit Sterbedatum: Status „verstorben“, Ausscheiden automatisch zum
  31.12. des Todesjahres; eine laufende Kündigung mit späterem Termin wird gegenstandslos.
- **Nur bei Mitgliedern** (auch gekündigten), Stand 2026-11-18. Stirbt ein Antragsteller, wird der
  Antrag zurückgenommen, der Grund steht in den Hinweisen.
- **Gegenstandslose Kündigungen bleiben stehen** (Stand 2026-11-18) und sind in der Kündigungskarte
  als „gegenstandslos (Tod)“ markiert; sie werden nicht automatisch zurückgenommen.
- **Erfassung des Todes zurücknehmen** (Stand 2026-11-18): nur für Fehlerfassungen (falsches
  Mitglied, falsches Datum), Event `member.death-revoked`. Ein falsches Datum wird so korrigiert:
  zurücknehmen und neu erfassen.
- **Anschrift der Erben** wird von Hand in den Adresszeilen gepflegt, es gibt keinen eigenen
  Erbenvertreter-Datensatz. Der Vorgang „Tod erfassen“ zeigt dem Erfasser einen Hinweis, wie die
  Adresszeilen umzustellen sind, und führt zu ihnen.
- **Erbe tritt ein** (bestätigt 2026-11-19): Er wird als neue Person erfasst (Antrag über die
  geerbten Anteile, Zulassung), die Anteile werden umgebucht und damit der Saldo. Der Verstorbene
  scheidet mit der Umbuchung ohne Anspruch aus (siehe „Umbuchung“).
- **Kein Eintritt:** Zum 31.12. entsteht der Auseinandersetzungsanspruch der Erben, die Auszahlung
  läuft wie bei einer Kündigung.
- **Tod wird erst nach dem 31.12. bekannt:** Das Ausscheiden gilt rückwirkend, eine Umbuchung auf
  einen Erben bleibt erlaubt.
- **Seriendruck zur GV im Todesjahr:** Verstorbene erhalten immer einen Eintrag (an die
  Adresszeilen), außer bei „keine Post“.
- **Erbnachweis:** wird vorerst im Feld „Hinweise“ festgehalten.
- **Briefanrede bei Status „verstorben“:** immer „Sehr geehrte Damen und Herren“.

### Buchungen und Storno

- **Buchungen sind unveränderlich** und liegen wie alles im Event Store. Korrekturen nur über
  Storno- bzw. Korrekturbuchungen.
- **Storno:** Gegenbuchung mit vertauschten Konten, gleichem Betrag und gleichen Anteilen, Text
  „Storno zu …“. Sie führt die **UUIDv7 der Originalbuchung** als Referenz mit.
- **Pflichtangabe Stornogrund.** Er steht im Buchungstext (Stand 2026-11-18), z. B.
  „Storno zu „Eintritt“: Zahlung falsch zugeordnet“; ein eigenes Feld gibt es nicht.
- Jede Buchung kann nur einmal storniert werden, ein Storno nicht. In der Kontoansicht sind
  Original und Storno als Paar gekennzeichnet und per Filter ausblendbar. „Storniert durch“
  leitet das Frontend aus der Referenz `reverses` ab (Stand 2026-11-18). Stornieren geht auf
  jedem Konto, auch auf dem Genossenschaftskonto; der Grund wird vorerst per Browser-Dialog
  abgefragt.
- **Wertstellung des Stornos = Wertstellung der Originalbuchung** (Stand 2026-11-18). Das Storno
  hebt die Buchung zum selben Stichtag auf, Reports zu einem Stichtag stimmen damit auch
  rückwirkend. Buchungstag ist wie immer der Tag der Erfassung.
- **Statusauswirkung (Stand 2026-11-18):** Ein Storno passt den Geldeingang am Mitglied an, und
  zwar **nie still**, sondern immer mit einer deutlichen Warnung in der Antwort:
  - Sind die gezeichneten Anteile vor dem Storno voll eingezahlt und danach nicht mehr (Storno
    eines Eintritts), wird der Geldeingang mit einem Gegen-Event zu `member.paid-in`
    zurückgenommen (Arbeitsname `member.paid-in-revoked`). Der Status fällt von „Mitglied“ auf
    „Antragsteller“ zurück, die Zulassung bleibt bestehen, das Eintrittsdatum entfällt.
  - Sind sie erst nach dem Storno voll eingezahlt (Storno einer Rückzahlung), wird wie bei einem
    Eintritt `member.paid-in` festgehalten, mit der Wertstellung des Stornos.
  - Der Mitarbeiter klärt den Vorgang danach, z. B. mit einer neuen, richtigen Buchung.

### Benutzer und Rollen

- **Admin:** nur Systemeinstellungen und Benutzerverwaltung, kein Zugriff auf die Fachfunktionen.
- **Buchhaltung:** die Rolle der normalen Benutzer, alle Fachfunktionen einschließlich Storno.
- **Buchhaltung lesend:** alle Fachdaten und Reports ansehen, nichts ändern (z. B. Aufsichtsrat).
- **Ein Benutzer hat genau eine Rolle.** Wer mehrere Rollen braucht, bekommt mehrere Benutzerkonten.
- **Der Admin kann das Kennwort eines Benutzers neu setzen**, etwa wenn es vergessen wurde.
- **Kennwörter** werden mit Argon2 über `pwdlib` gehasht (von der FastAPI-Doku empfohlen).
- **Session:** `SessionMiddleware` von Starlette, signiertes Cookie mit nur der Benutzer-ID darin,
  Schlüssel aus `CM_SECRET_KEY`. Rolle und Aktiv-Status werden bei jeder Anfrage aus der Projektion
  gelesen; ein deaktivierter Benutzer verliert so sofort den Zugriff.
- **Anteilspreis** ist eine Systemeinstellung des Admins. Eine Änderung gilt nur für neue Buchungen.
- **Systemeinstellungen per Event Sourcing** im Aggregat `SystemSettings` mit einem einzigen Stream
  `system-settings`, Event `settings.share-price-changed` (Betrag in Cent). So ist nachvollziehbar,
  wer wann welchen Wert gesetzt hat. Nicht zu verwechseln mit `config.Settings` (technische
  Konfiguration aus der `.env`). Ohne Event ist der Anteilspreis nicht festgelegt, Buchungen mit
  Betrag sind dann nicht möglich.
- **Vorerst nur per Kommandozeile:** `coop-manager set-share-price 50,00` und `show-settings`, wie
  `create-admin`. Die Seite „Einstellungen“ für den Admin kommt später.

### Mitglieder im Modell (Schritt 4)

- **Abgrenzung:** Schritt 4 umfasst Personendaten, Antrag (Datum, gezeichnete Anteile, Nummer),
  Zulassung und Ablehnung/Rücknahme, Suche, Bearbeitung, Adresszeilen und Briefanrede. Konto,
  Buchungen und damit der Übergang zum Mitglied sowie Kündigung, Tod, Ausschluss und Ausscheiden
  folgen in Schritt 5.
- **Eindeutige Mitgliedsnummer über ein eigenes Aggregat `MemberNumbers`** mit einem einzigen
  Stream: Jede Vergabe ist ein Event. Vergeben zwei Anträge gleichzeitig, scheitert der zweite an
  der Versionsprüfung (`ConcurrencyError`) und versucht es mit der nächsten Nummer erneut. Auch
  manuell vergebene Nummern (Migration) laufen darüber.
- **Status wird zum Stichtag berechnet, nicht gespeichert:** Gespeichert werden nur Fakten
  (Antrag, Zulassung, Ablehnung, später Eintrittsbuchung, Kündigung, Sterbedatum).
  `status(stichtag)` leitet den Status daraus ab. Es gibt kein Event zum Jahreswechsel.
- **Suche per `POST /api/members/search`** mit `{query}`: Ausnahme von „Abfragen per GET“, damit
  Namen nicht im Access-Log stehen. Jedes Suchwort muss passen. Ein Wort nur aus Ziffern trifft die
  Mitgliedsnummer genau oder den Anfang der Postleitzahl, andere Wörter irgendwo in Namen, Firma,
  Straße oder Ort, ohne Rücksicht auf Groß-/Kleinschreibung.
- **Zulassung, Ablehnung, Rücknahme:** Der Vorstand kann nur ablehnen, solange er nicht zugelassen
  hat. Die Person kann auch nach der Zulassung zurücknehmen, solange sie nicht Mitglied ist. Beides
  führt zum Status „abgelehnt“, bleibt aber als eigenes Event unterscheidbar.
- **Kein Datum in der Zukunft für Zulassung, Ablehnung und Rücknahme:** Erfasst wird, was
  geschehen ist, das Datum liegt also zwischen Antrag und heute. Ein Datum in der Zukunft führte
  zu einem widersprüchlichen Bild („abgelehnt am“ morgen, Status heute noch „Antragsteller“). Das
  Antragsdatum ist davon ausgenommen. „Heute“ übergibt die API an das Aggregat, wie beim Status.
- **Änderungen nach fachlicher Absicht:** eigene Befehle und Events für Name, Anschrift, Kontakt,
  Adresszeilen, abweichende Briefanrede, „keine Post“ und Hinweise, kein allgemeines
  „Daten ändern“.
- **Die Art der Person** (natürlich/juristisch) wird beim Antrag festgelegt und ist danach nicht
  änderbar. Bei einem Fehler wird der Antrag zurückgenommen und neu erfasst.
- **Rechte an der Mitglieder-API:** Lesen (Suche, Detailansicht) dürfen `accounting` und
  `accounting_readonly`, ändern (alle Befehle) nur `accounting`, der Admin gar nichts.
- **Detailansicht mit berechneten Angaben:** `GET /api/members/{id}` liefert neben den gespeicherten
  Daten den Status heute, die erzeugte Briefanrede, `generated_address_lines` und `warnings`
  (Adresszeilen passen nicht zu Name/Anschrift, Zeile über 35 Zeichen). Jeder Befehl antwortet
  mit dieser Detailansicht, so erscheinen die Warnungen direkt nach dem Speichern; Speichern bleibt
  trotzdem möglich.
- **„Adresszeilen erzeugen“ ist kein eigener Befehl:** Das Frontend übernimmt
  `generated_address_lines` in die Felder (mit Rückfrage, wenn die Zeilen von Hand geändert wurden)
  und speichert mit `change-address-lines`. Erzeugt werden die Zeilen im Backend.
- **Ablehnung oder Rücknahme in der Detailansicht:** Beide setzen `rejection_date`, `withdrawn`
  sagt, welches von beiden es war (`true` = Rücknahme durch die Person).
- **Eine Detailseite statt eigener Bearbeitungsseite:** Die Detailseite ist in Abschnitte
  gegliedert (Antrag, Name, Anschrift, Kontakt, Post, Hinweise). In 4d-4 wird jeder Abschnitt
  für sich bearbeitet und mit seinem eigenen Befehl gespeichert. Ein großes Formular passte nicht
  zu den Befehlen nach fachlicher Absicht.

### Adresszeilen und Briefanrede

- **Sechs Adresszeilen** als Anschriftzone nach DIN 5008, leere Zeilen werden zusammengeschoben:

  | Zeile | Natürliche Person | Juristische Person |
  |---|---|---|
  | 1 | „Herrn“ / „Frau“ (bei „d“ oder ohne Geschlecht leer) | Firmenname |
  | 2 | [Titel] alle Vornamen Nachname | z. H. Herrn/Frau [Titel] Vorname Nachname (falls erfasst) |
  | 3 | Straße Hausnummer | Straße Hausnummer |
  | 4 | PLZ Ort | PLZ Ort |
  | 5 | LAND in Großbuchstaben, nur außerhalb Deutschlands | LAND |
  | 6 | – | – |

- Button „Adresszeilen erzeugen“ überschreibt die Zeilen, nach Rückfrage, falls sie von Hand
  geändert wurden. Die Zeilen sind immer von Hand pflegbar.
- Warnung beim Speichern, wenn Name oder Adresse geändert wurden, die Zeilen aber nicht neu
  erzeugt (Speichern bleibt möglich), und bei Zeilen über 35 Zeichen.
- **Briefanrede** wird nicht gespeichert, sondern beim Report erzeugt: „Sehr geehrter Herr
  [Titel] Nachname“, „Sehr geehrte Frau [Titel] Nachname“, bei „d“ oder ohne Angabe „Liebes
  Mitglied“, bei juristischen Personen und Verstorbenen „Sehr geehrte Damen und Herren“.
- **Abweichende Briefanrede:** optionales Feld, das die erzeugte Anrede überschreibt
  (z. B. „Liebe Familie Hotzel“).
- `name_mitgl` in Listen: „Nachname, Vorname(n)“ bzw. Firmenname.

### Nummern und Konten

- **Mitgliedsnummer und Kontonummer werden getrennt gespeichert.** Im Altsystem sind beide
  identisch (`PersNr`). Neue Mitglieder bekommen nach Möglichkeit für beide dieselbe Nummer.
- **Das Konto der Genossenschaft (Pseudokonto) behält die Nummer 9999.** Es ist ein reines Konto
  ohne Personendatensatz und erscheint deshalb in keiner Mitgliederliste. Erreicht die
  Mitgliedsnummer irgendwann 9999, wird die Nummer übersprungen.
- **Kontoart:** `Mitgliedskonto` oder `Genossenschaftskonto`. Das Genossenschaftskonto gibt es
  genau einmal, es wird an der Kontoart erkannt, nicht an der Nummer. Es wird bei der
  Ersteinrichtung per CLI `create-cooperative-account` angelegt. Die **Nummer 9999 steht fest im
  Code** (Stand 2026-11-17), nur die Bezeichnung („Unser Dorfladen Schlichten eG“) kommt aus der
  Konfiguration (`CM_COOPERATIVE_ACCOUNT_NAME`); bei der Migration wird es auf das alte Konto 9999
  abgebildet.
- **Regeln am Genossenschaftskonto:** Vorbelegung der Gegenseite bei Eintritt, Austritt und
  Rückzahlung; nur dieses Konto darf negativ werden; bei Umbuchungen nicht wählbar; erscheint
  nicht in der Mitgliedersuche, in der Kontenauswahl mit eigener Bezeichnung.
- **Nummernvergabe:** nächste Nummer = höchste vergebene Mitglieds- oder Kontonummer + 1 (ohne
  Genossenschaftskonto), belegte Nummern werden übersprungen. So sind Mitglieds- und Kontonummer
  gleich, solange keine abweichenden Nummern manuell vergeben wurden.
- **Ausscheiden und Auszahlung sind getrennt.** Mit Ablauf der Frist ist das Mitglied
  ausgeschieden (kein Stimmrecht, keine Einladung zur GV), auch wenn das Guthaben noch nicht
  ausgezahlt ist. Das Mindestkapital (Satzung 6.6) betrifft nur die Auszahlung.
- **Teilkündigung** einzelner Anteile ist möglich (Satzung 6.1). Die Person bleibt Mitglied, die
  gekündigten Anteile werden zum Ende des Geschäftsjahres zum Auseinandersetzungsanspruch.
- **Hinweis „teilgekündigt“** (Stand 2026-11-18): Der Status bleibt „Mitglied“, aber Suche und
  Mitgliedsseite zeigen daneben „teilgekündigt“, solange eine Teilkündigung läuft (bis zu ihrem
  31.12.). Ist die Mitgliedschaft gekündigt, entfällt der Hinweis, der Status sagt genug.
- **Ausschluss** (Satzung 6.2–6.4): Beschluss des Vorstands mit Datum, Widerspruch beim
  Aufsichtsrat binnen sechs Wochen.
- **Ausschluss erfassen** (Stand 2026-11-18): nur bei Mitgliedern, auch gekündigten; Status
  „ausgeschlossen“ ab dem Beschluss, Ausscheiden zum 31.12. des Beschlussjahres (§ 68 GenG).
  Kündigungen mit späterem Termin werden gegenstandslos (wie beim Tod). Die Widerspruchsfrist
  überwacht die App nicht. Stirbt die Person vor dem 31.12., lässt sich der Tod noch erfassen.
- **Ausschluss aufheben** (Stand 2026-11-18): Gibt der Aufsichtsrat einem Widerspruch statt, wird
  der Ausschluss mit einem eigenen Vorgang aufgehoben, mit dem Datum des Beschlusses (Event
  `member.expulsion-lifted`); auch für Fehlerfassungen. Der Ausschluss gilt danach als nie
  geschehen, auch wenn das Jahresende schon vorbei ist; eine frühere Kündigung gilt wieder.
- **Daten werden abgeleitet, nicht gepflegt:** Eintrittsdatum aus der Wertstellung der ersten
  Eintrittsbuchung, Kündigungsdatum und Ausscheidensdatum aus dem Vorgang „Kündigung erfassen“.
  Sterbedatum wird manuell erfasst. In der Maske sind diese Felder nur lesbar, Änderungen laufen
  über eigene Aktionen (z. B. „Kündigung erfassen“, „Kündigung zurücknehmen“) und erzeugen Events.
- **Reports wählen nach dem Status zum Stichtag** aus, nicht nach „Saldo > 0“.

### Auseinandersetzung

- Mit dem gebuchten Ausscheiden entsteht ein **Auseinandersetzungsanspruch**:
  `offen → (teilweise) ausgezahlt → ausgezahlt`. **Er wird je Konto aus dem Saldo abgeleitet**
  (Stand 2026-11-18), nicht je Kündigung gespeichert: Saldo größer als Anteile × Preis heißt
  offener Anspruch, Auszahlungen (5h) mindern den Saldo. Für die Liste der offenen Ansprüche
  zählt das Datum der letzten Ausscheidensbuchung.
- **Die Auszahlungsfähigkeit (Mindestkapital, Satzung 6.6) prüft die App nicht.** Ob und wie viel
  ausgezahlt werden darf, stellt der Mitarbeiter im Einzelfall fest.
- **Teilauszahlungen** (Bruchteile des Anspruchs) müssen möglich sein, ebenso Kürzungen um
  Verlustvorträge (Satzung 6.5). Für diese Buchungen gilt „Betrag = Anteile × Anteilspreis“ nicht.
- **Auszahlung, Kürzung und Ausbuchung** (Stand 2026-11-18): Soll Mitgliedskonto an Haben
  Genossenschaftskonto, Betrag ohne Anteile, höchstens der offene Anspruch. Die Wertstellung muss
  **nach dem letzten gebuchten Ausscheiden** liegen, damit kein Stichtag einen negativen Anspruch
  zeigt; vor der Ausscheidensbuchung (5g) ist also keine Auszahlung möglich. Die **Ausbuchung
  wegen Verjährung nimmt immer den ganzen Rest**. Kein Abgleich mit dem Geldeingang.
- **Verjährung** (Satzung 2.7) überwacht die App nicht. Sie bietet eine **Liste der offenen
  Ansprüche** mit Ausscheidensdatum; die Ausbuchung erfolgt von Hand.
- **Liste der offenen Ansprüche** (Stand 2026-11-18): Seite „Ansprüche“ mit Nummer, Name, Status,
  Ausscheidensdatum (letzte Ausscheidensbuchung) und offenem Anspruch, das älteste Ausscheiden
  zuerst, mit Summe. **Nur Konten mit gebuchtem Ausscheiden**, sonst hätte nach einer Senkung des
  Anteilspreises jedes Mitglied rechnerisch einen Anspruch. Keine Spalte „Jahre seit
  Ausscheiden“, das Datum reicht.

### Hauptbuch

- **Ein Aggregat `Ledger` mit einem einzigen Stream für alle Buchungen** (Variante A, Stand
  2026-11-17), wie `MemberNumbers`. Jede neue Buchung lässt sich so gegen alle bisherigen prüfen,
  etwa ob eine Rückzahlung den Saldo übersteigt. Zwei gleichzeitige Buchungen scheitern an der
  Versionsprüfung (`ConcurrencyError`). Für die Größe des Dorfladens ist die Länge des Streams
  kein Problem. Verworfen: je Buchung ein Aggregat, weil Prüfungen über mehrere Buchungen dann
  umständlich werden.
- **Auch die Konten liegen im `Ledger`-Stream** (Event `account.opened` mit Nummer, Kontoart,
  Mitglieds-ID bzw. Bezeichnung). So prüft jede Buchung direkt, ob es ihre Konten gibt. Der Antrag
  speichert Nummernregister, Mitglied und Hauptbuch zusammen (`save_all`), ein Mitglied ohne
  Konto kann es nicht geben.
- **Grundregeln jeder Buchung** (Stand 2026-11-17, im `Ledger`): bekannte Buchungsart; beide Konten
  existieren und sind verschieden; Betrag (Cent) und Anteile nicht negativ und nicht beide 0;
  Buchungstext Pflicht; **Wertstellung nicht nach dem Buchungstag**; Buchungstag ist der Tag der
  Erfassung. Ein Mitgliedskonto darf weder beim Saldo noch bei den Anteilen ins Minus gehen.
  Regeln der einzelnen Buchungsart (z. B. „Betrag = Anteile × Preis“, erlaubte Konten) prüfen die
  Vorgänge ab 5c.
- **Vorzeichen:** Haben zählt auf dem Konto positiv, Soll negativ, für Betrag und Anteile
  gleichermaßen (Eintritt: Soll Genossenschaftskonto an Haben Mitgliedskonto).
- **Saldo und Anteile werden aus den Buchungen berechnet**, nicht gespeichert. Jede Buchung hat
  eine eigene UUIDv7 (Referenz für das Storno), Event `booking.posted`.
- **Zahlung am Mitglied festhalten (Variante A, Stand 2026-11-17, vorläufig):** Bringt eine
  Eintritts- oder Rückzahlungsbuchung die Anteile auf dem Konto genau auf die gezeichneten, zeichnet
  der Service am Mitglied zusätzlich `member.paid-in` mit der Wertstellung auf; beides wird mit
  `save_all` gemeinsam gespeichert. Der Status bleibt so aus den Events des Mitglieds berechenbar.
  Ein Storno der Eintrittsbuchung (5e) braucht dann ein Gegen-Event am Mitglied (siehe „Buchungen
  und Storno“, Statusauswirkung). Verworfen vorerst:
  Variante B, den Status direkt aus den Buchungen abzuleiten (Projektion verarbeitet
  `booking.posted`). Ein späterer Wechsel zu B ist möglich, weil die Buchungen alle Informationen
  enthalten; die `member.paid-in`-Events würden dann ignoriert.
- **Weitere Anteile:** Ein Mitglied darf später weitere Anteile zeichnen und einzahlen (Stand
  2026-11-17). Umsetzung in 5i (Stand 2026-11-19):
  - **Ein Vorgang „Weitere Anteile zeichnen“** mit Anzahl und Datum der Zulassung durch den
    Vorstand (§ 15b GenG), Event `member.additional-shares-subscribed`; kein eigener Zwischenstatus
    wie beim Antrag. Nur bei Mitgliedern, nicht gekündigt. Zurücknehmen nur bei Fehlerfassung und
    nur, solange die Anteile nicht eingezahlt sind (`member.additional-shares-revoked`).
  - **Eigene Buchungsart „Weitere Anteile“** (`additional_shares`), nicht „Eintritt“, damit die
    Jahresauswertung beides trennen kann. Betrag = Anteile × Preis, höchstens die offenen Anteile
    (gezeichnet, noch nicht gebucht); weniger geht mit Warnung. Wertstellung nicht vor der Zulassung.
    Die Anteile zählen ab der Wertstellung. Storno ohne Auswirkung auf die Mitgliedschaft.
  - **Gezeichnete Anteile insgesamt** = Antrag plus weitere Zeichnungen. Per Umbuchung erhaltene
    Anteile zählen nicht als gezeichnet.
  - **Abgleich beim Eintritt** zählt nur Anteile ohne die Buchungen „Weitere Anteile“; sonst
    stört eine spätere Zeichnung, wenn ein Eintritt storniert und neu gebucht wird.
- **Die API bucht nur über fachliche Vorgänge** (Stand 2026-11-17): Es gibt keinen Endpunkt, der
  frei eine Buchung mit beliebigen Konten, Beträgen und Anteilen anlegt. Jeder Endpunkt ruft einen
  Service für einen Vorgang (Eintritt, Rückzahlung, später Storno, Umbuchung usw.), der dessen
  Regeln prüft; `Ledger.post_booking` prüft darunter nur, was für jede Buchung gilt.
- **Konten werden in der API über die Kontonummer angesprochen** (Stand 2026-11-17):
  `GET /api/accounts/{number}` (auch 9999), Befehle `POST /api/accounts/subscribe` und
  `/refund` mit `{account_number, shares, value_date, text}`. Einen Betrag nimmt die API nicht
  an, der Service berechnet ihn. Die Kontoansicht enthält den aktuellen Anteilspreis für die
  Buchungsmaske.
- **Rückzahlung zum aktuellen Anteilspreis** (Stand 2026-11-17, vorerst), wie jede neue Buchung.
  Hat jemand zu einem früheren Preis eingezahlt, kann der Betrag abweichen; das nehmen wir als
  seltenen Randfall hin.

### Buchungsarten

- **Das Konto weist Anteile und Saldo getrennt aus:** Anteile = aktuell gehaltene Anteile, Saldo =
  was die Genossenschaft dem Mitglied schuldet. Ohne Kündigung gilt Saldo = Anteile × Preis,
  ist der Saldo größer, besteht ein offener Auseinandersetzungsanspruch.
- Gegenseite ist immer das Genossenschaftskonto, außer bei der Umbuchung:

  | Buchungsart | Betrag | Anteile | Anlass |
  |---|---|---|---|
  | Eintritt | = Anteile × Preis | ✔ | Geldeingang |
  | Rückzahlung | = Anteile × Preis | ✔ | Antrag abgelehnt oder Zahlung ungeklärt |
  | Umbuchung | = Anteile × Preis | ✔ | Übertragung zwischen Mitgliedskonten, z. B. auf Erben |
  | Ausscheiden | 0 | ✔ | gekündigte Anteile verlassen zum 31.12. den Bestand |
  | Kürzung Verlustvortrag | frei | 0 | Satzung 6.5 |
  | Auszahlung | frei, höchstens offener Anspruch | 0 | auch Teilauszahlung |
  | Ausbuchung Verjährung | Rest | 0 | Satzung 2.7, Zuführung zur Rücklage |
  | Spende Anteil | ganzer Saldo | alle | Ausscheiden ohne Frist, Guthaben an die Genossenschaft |
  | Storno | wie Original | wie Original | Korrektur |

- Der „Austritt“ aus `Konzeption.md` ist damit in **Ausscheiden** und **Auszahlung** aufgeteilt.
  Sind Saldo und Anteile 0, ist der Austritt abgeschlossen.
- **Vorgang „Ausscheiden zum Jahresende buchen“:** Die Buchhaltung startet ihn nach dem 31.12. Er
  zeigt alle zu diesem Termin fälligen Kündigungen, Todesfälle und Ausschlüsse und bucht nach
  Bestätigung mit Wertstellung 31.12. Kein automatischer Lauf. Reports zu einem Stichtag, für den
  das Ausscheiden noch nicht gebucht ist, zeigen eine Warnung (kommt mit den Reports, Schritt 6).
  Entscheidungen (Stand 2026-11-18):
  - **Eine Ausscheidensbuchung je Konto und 31.12.**, auch wenn volles Ausscheiden und
    Teilkündigungen zusammenfallen. Volles Ausscheiden bucht alle Anteile des Kontos aus,
    Teilkündigungen ihre Anteile. Konten ohne Anteile (z. B. nach Umbuchung auf Erben) entfallen.
  - **Ob gebucht ist, steht im Hauptbuch:** eine nicht stornierte Ausscheidensbuchung des Kontos
    mit diesem Termin; kein eigenes Event am Mitglied. Ein Storno öffnet das Ausscheiden wieder.
  - **Nur für abgeschlossene Jahre** (Jahr vor dem heutigen). Bis einschließlich 31.12. kann sich
    noch etwas ändern, z. B. eine zurückgenommene Kündigung.
  - Alle offenen Ausscheiden eines Jahres werden zusammen gebucht, alle oder keines.
- **Eingabe:** Wo Betrag und Anteile nötig sind, wird eins von beiden eingegeben und das andere
  berechnet; ein Betrag muss ein Vielfaches des Anteilspreises sein. Die Maske zeigt nur die
  Felder, die die Buchungsart braucht.

### Saldenliste (Schritt 10)

- **Zweck** (gewünscht 2026-11-21): alle Ansprüche aller Personen gegenüber der Genossenschaft auf
  einen Blick, abgestimmt gegen das Genossenschaftskonto. Anlass war der Probelauf der Migration:
  Die Summe der heutigen Mitglieder (55.350 €) wich von den 56.000 € im Hauptbuch ab, weil fünf
  Personen rechnerisch ausgeschieden waren, ihr Ausscheiden aber noch nicht gebucht war.
- **Eine Zeile je Mitgliedskonto** mit Saldo ≠ 0 (wahlweise alle), nach Mitgliedsnummer: Nummer,
  Name, Status zum Stichtag, Anteile, **Saldo** (ganzes Guthaben), davon **Geschäftsguthaben**
  (Anteile × Anteilspreis) und davon **Auseinandersetzungsanspruch** (Saldo − Geschäftsguthaben).
  Alle Personen mit Konto zählen, auch Antragsteller und Ausgeschiedene.
- **Hinweis „Ausscheiden nicht gebucht“**, wenn die Person zum Stichtag ausgeschieden ist, aber
  noch Anteile hat (dann auf der Seite „Jahresende“ buchen).
- **Stichtag** (Vorgabe heute): Buchungen mit Wertstellung bis zum Stichtag, stornierte samt Storno
  nicht; die Ausscheidensbuchung zum 31.12. wirkt wie bei den Reports erst ab dem 01.01.
- **Summenzeile und Abstimmung:** Summen über alle Konten; die Summe der Salden plus der Saldo des
  Genossenschaftskontos muss 0 ergeben, sonst Warnung.
- Lesen dürfen „Buchhaltung“ und „Buchhaltung lesend“. Dazu eine Excel-Datei auf der Seite „Reports“.

### Reports zum Stichtag (Schritt 6)

- **Excel mit `openpyxl`**, aufgebaut wie in `purchase-prices`: Titel, darunter einmalig
  „Stichtag: TT.MM.JJJJ“, dann Kopfzeile und Zeilen. Kein eigenes Feld für das Jahr des Stichtags.
- **Wer in der Liste steht** (Stand 2026-11-19): wer zum Stichtag den Status „Mitglied“,
  „gekündigt“, „verstorben“ oder „ausgeschlossen“ hat, also eingetreten und noch nicht
  ausgeschieden ist, **und Anteile hält**. Wer am Stichtag 0 Anteile hat, z. B. am Tag einer Spende
  des Anteils oder der Übertragung aller Anteile, fehlt.
- **Anteile zum Stichtag:** alle Buchungen mit Wertstellung bis einschließlich Stichtag; stornierte
  Buchungen und ihre Stornos fallen heraus. **Ausnahme:** Die Ausscheidensbuchung zum 31.12. wirkt
  im Report erst ab dem 01.01., weil die Person bis einschließlich 31.12. mit ihren Anteilen zählt.
  Das gilt auch für Teilkündigungen.
- **Betrag** = Anteile × Anteilspreis, nicht der Saldo: Nach einer Teilkündigung enthält der Saldo
  bis zur Auszahlung auch den Anspruch auf die gekündigten Anteile.
- **Mitgliederliste nach GenG** (6a): Nr., Name („Nachname, Vornamen“ bzw. Firma), Anschrift
  einzeilig („Straße Hausnummer, PLZ Ort“), Eintritt, Betrag, Anteile; nach Mitgliedsnummer.
  Herunterladen dürfen beide Buchhaltungsrollen.
- **Liste zur Generalversammlung** (6c, Stand 2026-11-19): Nr., Mitglied, Adresse (einzeilig),
  Vertreten durch, Unterschrift. Stichtag = Tag der Versammlung. Darin steht, wer abstimmen darf:
  Status „Mitglied“, „gekündigt“ (bis zum Ausscheiden) und „verstorben“ (für die Erben), mit
  Anteilen. **Ausgeschlossene nicht**, sie dürfen ab dem Beschluss nicht mehr teilnehmen (§ 68 GenG).
  **Nach Namen sortiert** (DIN 5007: „Ä“ wie „A“, „ß“ wie „ss“), weil man am Eingang nach dem Namen
  sucht. „Vertreten durch“ bleibt leer und wird von Hand ausgefüllt. Druck: A4 quer, eine
  Seitenbreite, Gitterlinien, Kopfzeile auf jeder Seite, höhere Zeilen für die Unterschrift.
- **Seriendruck-Liste** (6d, Stand 2026-11-19): Feldnamen wie im Altsystem, damit die Word-Vorlagen
  weiter passen: `PersNr`, `name_mitgl`, `Land` (wie gespeichert, leer = Deutschland), `PLZ`, `Ort`,
  `Strasse`, `HausNr`, `BriefAnrede`, `AdrZeile1`–`AdrZeile6`, `austritt`, `summe_anteile`,
  `anz_anteile`, `jahr_report`, `Verstorben`. **Ohne Titel und Stichtagszeile**, denn Word liest
  die erste Zeile als Feldnamen; das Jahr des Stichtags steht deshalb in `jahr_report`.
  Dieselben Personen wie in der GV-Liste, **ohne „keine Post“**; nach Mitgliedsnummer.
  `austritt` = wirksames Ausscheiden, wenn die Person zum Stichtag gekündigt oder verstorben ist,
  `Verstorben` = Sterbedatum, wenn sie zum Stichtag verstorben ist; sonst beides leer.
- **Warnung bei nicht gebuchtem Ausscheiden** (6e, Stand 2026-11-19): Geprüft wird nur der letzte
  31.12. vor dem Stichtag; ältere Jahre sind normalerweise gebucht. Sind dort noch Ausscheiden
  offen (wie auf der Seite „Jahresende“), zeigt die Seite „Reports“ einen Hinweis, und GenG- und
  GV-Liste tragen ihn in Zeile 3 (dunkelrot), damit er auch auf dem Ausdruck steht. Die
  Seriendruck-Liste nicht, dort muss Zeile 1 die Feldnamen enthalten. Grund: Eine nicht gebuchte
  Teilkündigung ließe Anteile und Betrag zu hoch erscheinen; wer ganz ausscheidet, fehlt dagegen
  ohnehin, das ergibt der Status.

### Auswertung der Vorgänge eines Geschäftsjahres (Schritt 6)

- **Anforderung (Stand 2026-11-19):** Excel-Auswertung der Vorgänge eines Geschäftsjahres:
  Eintritte, weitere Anteile, Kündigungen und Teilkündigungen, Todesfälle, Ausschlüsse, Spenden,
  Ausscheiden, Auszahlungen, Umbuchungen.
- **Format:** Excel, wie die anderen Reports.
- **Zeitraum:** immer ein ganzes Geschäftsjahr (= Kalenderjahr), kein freier Zeitraum.
- **Maßgebliches Datum:** bei Kündigungen der Eingang der Kündigung, bei Todesfällen das
  Sterbedatum, bei Ausschlüssen der Beschluss des Vorstands, bei Buchungen die Wertstellung.
- **Eine gemeinsame Liste** mit der Spalte „Vorgang“ zum Filtern in Excel, nicht je Vorgangsart
  eine eigene Tabelle.
- **Zeilen:** Vorgang, Mitgliedsnummer, Name, Datum, Anteile, Betrag. **Keine Summen.**
- **Weggelassen:** stornierte Buchungen sowie zurückgenommene Kündigungen, Todesfälle und
  Ausschlüsse.
- **Entscheidungen zu 6f (Stand 2026-11-19):**
  - **Alle Buchungen** des Jahres kommen in die Liste, auch Rückzahlung, Kürzung Verlustvortrag und
    Ausbuchung Verjährung; nur stornierte Buchungen und ihre Stornos nicht.
  - **Eintritt und Weitere Anteile** zählen mit der Buchung (Einzahlung), nicht mit Zulassung oder
    Zeichnung. Erben, die über eine Umbuchung Mitglied werden, erscheinen als Umbuchung.
  - **Spalte „Gegenkonto“:** bei Buchungen die Nummer des anderen Kontos (meist 9999, das
    Genossenschaftskonto), bei Kündigung, Todesfall und Ausschluss leer. Daneben die Spalte **„Name
    Gegenkonto“**: Name des Mitglieds bzw. Bezeichnung des Genossenschaftskontos.
  - **Umbuchung in zwei Zeilen**, je eine für das abgebende und das empfangende Konto, jeweils mit
    dem anderen als Gegenkonto. So zeigt ein Filter auf eine Mitgliedsnummer alle Bewegungen.
  - **Vorzeichen aus Sicht des Mitgliedskontos:** Zugänge positiv, Abgänge negativ.
  - **Anteile und Betrag passen in jeder Zeile zusammen** (Betrag = Anteile × Preis), außer bei
    Auszahlung, Kürzung und Ausbuchung, die nur Geld bewegen. Beim **Ausscheiden** zeigt die Liste
    deshalb den Wert der Anteile zum aktuellen Anteilspreis, obwohl die Buchung Betrag 0 hat (das
    Geld bleibt als Anspruch auf dem Konto, siehe Buchungsarten). Das Buchungsmodell bleibt so.
  - Bei der Teilkündigung stehen die gekündigten Anteile und ihr Wert; bei Kündigung, Todesfall
    und Ausschluss bleiben Anteile und Betrag leer.
  - Sortiert nach Datum, dann nach Mitgliedsnummer; Autofilter auf der Kopfzeile.

### Migration der Altdaten (Schritt 7)

- **Altsystem:** Access-Datenbank mit eigener VBA-Logik. Die Excel-Listen in `Beispieldaten/`
  sind Reports daraus, nicht der vollständige Bestand.
- **Quelle** (Stand 2026-11-21): `Altdaten/DLS-MitgliederDB.accdb`, gelesen mit `mdbtools`.
  `Altdaten/` ist wie `Beispieldaten/` per `.gitignore` ausgeschlossen. Drei Tabellen:
  `mitglieder` (aktueller Stand je Person, Schlüssel `persnr`, 9999 = Genossenschaftskonto),
  `mitglieder_hist` (Schnappschüsse der Personendaten mit `last_update`) und `buchungen`
  (Soll-Konto an Haben-Konto, Anteile, Betrag, Datum, Text). Die gespeicherten Abfragen des
  Altsystems werden nicht gebraucht.
- **Einzelfälle:** Die Entscheidungen zu einzelnen Personen und Buchungen (mit Nummern) stehen
  in `Altdaten/Entscheidungen.md`, nicht im Repository, weil sie aus echten Daten stammen. Hier
  stehen nur die Regeln.
- **Analyse am 2026-11-21** mit Matthias, Ergebnis: Alle Salden sind Anteile × 50 €, kein Konto
  ist negativ. Die Entscheidungen im Einzelnen:

**Personen**

- **Übernommen werden Personen mit Eintritt oder mit mindestens einer Buchung**, einschließlich
  Ausgetretener. Nicht übernommen werden reine Kontakte ohne Eintritt und Buchung (Vereine,
  Interessenten), Platzhalter- und Testdatensätze sowie das Genossenschaftskonto als Person.
- **„Abgelehnt“ (Rücknahme)** werden Personen, die nie Mitglied wurden: Einzahlung als Spende
  vereinnahmt (2014/15), Beitritt widerrufen mangels Geldeingang, Eintritt ohne jede Buchung. Das
  gilt auch, wenn das Altsystem ein Eintrittsdatum hat. Der Text der zugehörigen Buchungen kommt
  mit Datum und Betrag in die Hinweise.
- **Eintrittsdatum:** Der Eintritt aus dem Altsystem bleibt unverändert, auch wenn das Geld erst
  später einging (meist das Datum der Beitrittserklärung). Antrags-, Zulassungs- und
  Eintrittsdatum werden darauf gesetzt; die Einzahlung behält ihr Buchungsdatum. Die Regel „das
  spätere von Zulassung und Geldeingang“ gilt nur für neue Beitritte. Kein Fall überschreitet eine
  Jahresgrenze, Bestände zum 31.12. ändern sich dadurch nicht.
- **Ausscheiden durch Spende oder Umbuchung aller Anteile** ergibt sich wie in der App aus der
  Buchung (Tag der Buchung). Ein abweichendes oder fehlendes Austrittsdatum im Altsystem spielt
  keine Rolle; ein abweichendes kommt in die Hinweise.
- **Tod und Kündigung ohne gebuchtes Ausscheiden:** Sterbe- und Kündigungsdatum werden übernommen.
  Die Migration erfindet keine Ausscheidensbuchungen; das Ausscheiden zum jeweiligen 31.12. wird
  danach über die Seite „Jahresende“ gebucht. Danach stehen diese Konten mit ihrem Guthaben in der
  Liste der offenen Ansprüche. Mitglieder und Anteile sinken dadurch gegenüber den Listen des
  Altsystems, das kein automatisches Ausscheiden kannte.
- **Offensichtliche Fehler werden bei der Migration korrigiert** (Datum im falschen Feld, falsches
  Geschlecht); die Fälle stehen in `Altdaten/Entscheidungen.md`.

**Felder**

| Altsystem | App |
|---|---|
| `persnr` | Mitgliedsnummer (manuell vergeben) |
| `firma` | Firmenname; gefüllt = juristische Person, Name = Ansprechpartner |
| `geschlecht`, `titel`, `vorname`, `name` | Name |
| `strasse`, `hausnr`, `plz`, `ort`, `land` | Anschrift (darf bei der Migration fehlen) |
| `telefon1`, `email` | Kontakt; ungültige E-Mail-Adressen entfallen ohne Notiz |
| `adrzeile1`–`adrzeile6` | Adresszeilen, wie sie sind (Abweichungen zeigt die App als Hinweis) |
| `briefanrede` | abweichende Briefanrede, nur wenn sie von der erzeugten abweicht; leer = erzeugt |
| `keinepost`, `hinweise` | keine Post, Hinweise |
| `eintritt`, `kündigung`, `verstorben` | Daten der Mitgliedschaft (siehe oben) |
| `austritt` | entfällt, das Ausscheiden ergibt sich aus Buchungen bzw. Kündigung und Tod |
| `kdnr`, `angelegt`, `geboren`, Bankdaten, `telefon2`, `telefon3`, `fax` | entfallen |

Das Datum 1899-12-30 ist der Nullwert von Access und gilt als leer.

**Historie**

- `member.migrated` mit dem ältesten Stand aus `mitglieder_hist` (`last_update` 1900 = Anfangsstand
  bei Einführung der Historie im Altsystem), danach je weiterer Version ein
  `member.migrated-change` mit „gültig ab“ = `last_update`. Weicht der aktuelle Stand von der
  letzten Version ab, folgt eine letzte Änderung ohne bekanntes Datum.
- Änderungen an Eintritt, Kündigung, Austritt und Tod in der Historie werden nicht als Versionen
  übernommen; diese Daten kommen aus dem aktuellen Stand bzw. den Buchungen.
- Eine Ansicht des Verlaufs gibt es noch nicht (siehe „Mögliche Weiterentwicklungen“).

**Buchungen**

| Altsystem | App |
|---|---|
| 9999 an Mitglied | Einzahlung bzw. weitere Anteile |
| Mitglied an 9999 („Spende“) | Spende Anteil |
| Mitglied an Mitglied | Umbuchung |
| Soll = Haben (Notiz zu Spende statt Beitritt, Fehlerfassung) | entfällt |
| 9999 an 9999 („Testbuchung“) | entfällt |
| Beitritt und Widerruf mangels Geldeingang | entfallen beide (heben sich auf) |

- Das Skript führt eine feste Liste der übersprungenen Buchungen mit Begründung und gibt sie bei
  jedem Lauf aus.

**Technik**

- **Normale Events statt eigener Migrationsevents** (Entscheidung 7b, 2026-11-21; ersetzt die
  frühere Idee `member.migrated`/`booking.migrated`): Die Migration schreibt dieselben Events wie
  die App (`member.applied`, `member.admitted`, `member.paid-in`, `member.withdrawn`,
  `member.died`, `member.notice-given`, `member.shares-donated`, `member.all-shares-transferred`,
  `booking.posted` mit den bestehenden Buchungsarten usw.). Grund: Projektionen, Status, Reports
  und Jahresende funktionieren ohne Änderung, und nach der Migration lässt sich normal
  weiterarbeiten (Storno, Umbuchung). Zwei Wege für dieselbe Tatsache wären eine Fehlerquelle.
- **Akteur aller Events ist `migration`** (bestätigt 2026-11-21); daran sind migrierte Events
  erkennbar. Eventzeit = Zeitpunkt der Migration, das fachliche Datum steht in den Daten.
- **Eigene Methoden am Mitglied** (z. B. `Member.migrate`) schreiben diese Events ohne die
  Prüfungen, die für Altfälle nicht passen (offener Antrag, Pflichtanschrift, Datum nicht in der
  Zukunft u. Ä.). Die normalen Vorgänge bleiben unverändert.
- **Je Person:** Nummer vergeben, Konto eröffnen, `member.applied` mit dem ältesten Stand.
  Mitglieder: `member.admitted` und `member.paid-in`, Antrags-, Zulassungs- und Zahlungsdatum =
  alter Eintritt (damit das Eintrittsdatum gleich bleibt). „Abgelehnt“: `member.withdrawn`. Dazu
  je nach Fall `member.died`, `member.notice-given` (Ausscheiden zum Ende der Frist),
  `member.shares-donated` bzw. `member.all-shares-transferred` am Tag der Buchung. Gezeichnete
  Anteile = erste Einzahlung bzw. empfangene Umbuchung; bei „abgelehnt“ die Anteile der
  Notizbuchung, sonst 1.
- **Buchungen** in der Reihenfolge Datum, dann alte ID (damit der Saldo bei Umbuchungen am selben
  Tag reicht); Wertstellung = altes Datum, Text = alter Buchungstext. Erste Einzahlung = Eintritt;
  eine spätere Einzahlung = „Weitere Anteile“ mit Zeichnung am Buchungstag.
- **Historie** mit den bestehenden Änderungsevents (`member.name-changed`,
  `member.address-changed`, `member.address-lines-changed`, `member.notes-changed` usw.), dazu
  ein zusätzliches Feld **`valid_from`** mit dem alten `last_update`. Die App ignoriert es vorerst;
  die spätere Ansicht „Verlauf“ zeigt `valid_from`, wo vorhanden, sonst die Eventzeit.
- **Einzelfälle** liest das Skript aus `Altdaten/migration.toml` (TOML, `tomllib`, nicht im
  Repository): nicht übernommene Personen, „abgelehnte“ Personen, übersprungene Buchungen mit
  Grund und Korrekturen einzelner Felder (überschreiben die Spalten des Altsystems, im aktuellen
  Stand und in allen Versionen der Historie, Stand 2026-11-21). Tests nutzen eigene, erfundene
  Daten.
- **Der Plan ist streng** (7c Teil 2): Jede Person und jede Buchung wird zugeordnet oder steht in
  `migration.toml` als übersprungen; alles andere ist ein Problem, und dann wird nichts
  geschrieben. Eine Spende muss alle Anteile umfassen. Eine Kündigung wird nur übernommen, wenn
  die Person am Eingangstag noch Mitglied war, sonst kommt sie als Notiz in die Hinweise.
- **Aufbau:** Modul `migration/` mit `source.py` (liest die CSV-Dateien aus `mdb-export`),
  `plan.py` (reine Funktionen, die ganze Fachlogik), `run.py` (schreibt mit Akteur `migration` in
  einer Transaktion) und `check.py` (Abgleich Saldo und Anteile je Konto, Prüffälle,
  übersprungene Buchungen). CLI: `coop-manager migrate <csv-ordner> <migration.toml>
  [--dry-run]`; ohne `--dry-run` bricht er ab, wenn es schon Mitglieder gibt.
- **Produktion (7e, Vorschlag):** lokal auf einer Kopie der NAS-Sicherung migrieren (dort gibt
  es kein `mdbtools`), prüfen und bei gestopptem Container zurückkopieren.
- Ausnahmen nur für die Migration: manuelle Nummernvergabe, keine Prüfung „Betrag = Anteile ×
  Preis“, Anschrift darf fehlen. Konten, deren Werte nicht zum neuen Buchungsmodell passen, listet
  das Skript als Prüffälle auf.
- **Ablauf:** wiederholbares Migrationsskript für Probeläufe, automatischer Abgleich der Salden und
  Anteile je Konto zwischen alt und neu, Umstellung zu einem Stichtag. Access-Datei und
  Excel-Export bleiben als Archiv erhalten.

## Glossar

| Deutsch | Englisch im Code |
|---|---|
| Mitglied / Antragsteller | `member` / `applicant` |
| Beitrittserklärung | `membership_application` |
| Zulassung / Ablehnung | `admission` / `rejection` |
| Geschäftsanteil, Anteilspreis | `share`, `share_price` |
| Mitgliedsnummer, Kontonummer | `member_number`, `account_number` |
| Mitgliedskonto / Genossenschaftskonto | `member_account` / `cooperative_account` |
| Buchung, Buchungstext | `booking`, `text` |
| Hauptbuch | `Ledger` |
| Soll / Haben | `debit` / `credit` |
| Buchungstag / Wertstellung | `booking_date` / `value_date` |
| Saldo | `balance` |
| Eintritt (Buchung) | `subscription` |
| Rückzahlung | `refund` |
| Umbuchung | `transfer`, `transfer_all_shares` |
| Kündigung, Teilkündigung, Kündigungsfrist | `notice`, `partial_notice`, `notice_period` |
| Ausschluss | `expulsion` |
| Ausscheiden | `exit` |
| Auseinandersetzungsanspruch | `settlement_claim` |
| Saldenliste | `BalanceList` (`account_balances`) |
| Geschäftsguthaben | `share_capital` |
| Kürzung Verlustvortrag | `loss_deduction` |
| Auszahlung | `payout` |
| Ausbuchung Verjährung | `limitation_writeoff` |
| Storno | `reversal` |
| Spende des Anteils | `share_donation`, `donate_shares` |
| Weitere Anteile (zeichnen, einzahlen) | `additional_shares`, `subscribe_additional_shares` |
| verstorben, Sterbedatum, Erben | `deceased`, `date_of_death`, `heirs` |
| natürliche / juristische Person | `natural_person` / `legal_entity` |
| Firmenname, Ansprechpartner | `company_name`, `contact_person` |
| Titel, Geschlecht | `title`, `gender` |
| Adresszeilen, Briefanrede | `address_lines`, `salutation` |
| keine Post, Hinweise | `no_mail`, `notes` |
| Geschäftsjahr, Stichtag | `fiscal_year`, `reference_date` |
| Generalversammlung | `general_meeting` |
| Rollen Admin / Buchhaltung / Buchhaltung lesend | `admin` / `accounting` / `accounting_readonly` |
| Daten der Mitgliedschaft (Antrag, Zulassung, …) | `MembershipDates` |
| Systemeinstellungen | `SystemSettings` |

Status der Mitgliedschaft: `applicant`, `rejected`, `member`, `notice_given`, `expelled`,
`deceased`, `exited`.

## Offene Punkte

- **Höchstzahl an Anteilen je Mitglied:** Steht in der Satzung eine Grenze? Bis zur Klärung prüft
  die App keine.

## Mögliche Weiterentwicklungen

- **Eintrittsgeld** (Satzung 2.3), falls die Generalversammlung eines beschließt: eigene
  Buchungsart ohne Anteile, Zuführung zu den Rücklagen.
- **Rückvergütung** (Satzung 2.6) über die Mitgliedskonten.
- **Ansicht „Verlauf“ an der Mitgliederseite** (gewünscht 2026-11-21): frühere Stände der
  Personendaten mit Datum, einschließlich der migrierten Historie des Altsystems.
- **Seite „Einstellungen“ für den Admin**, um den Anteilspreis in der Oberfläche zu ändern (bisher
  nur per CLI).
- Mehrere Rollen je Benutzer statt mehrerer Benutzerkonten je Person.
- Späteste Absendung der Einladung zur GV aus dem GV-Datum berechnen (Satzung 3.1: zwei Wochen
  plus zwei Werktage).
- API-Keys mit Ablaufdatum, MCP-Server, Login über OAuth2/JWT (siehe `Konzeption.md`).
- Eine Bibliothek ohne eigenes Styling (z. B. Reka UI) für schwierige Bausteine wie Dialoge,
  Datumsauswahl oder Auswahl mit Suche, falls sie selbst gebaut zu aufwendig oder nicht barrierefrei
  genug werden. Gestaltet wird weiter mit den eigenen Farbvariablen.
