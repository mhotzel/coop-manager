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
6. Reports: die drei Excel-Listen zum Stichtag
7. Migration der Altdaten (falls gewünscht, offen)
8. Container, Backup per Cron, Deployment auf der Synology
9. Ausbaustufe: API-Keys, MCP-Server, OAuth2/JWT

## Entscheidungen

### Architektur

- **Backend: FastAPI**, weil das Backend für die SPA nur JSON liefert (Pydantic-Validierung,
  OpenAPI-Beschreibung, OAuth2 und MCP später einfach anzubinden).
- **Event Sourcing in schlank** wie in `purchase-prices`: Aggregate mit Methoden und einfache
  Service-Funktionen, keine Command- oder Query-Busse. `eventstore.sqlite` ist die einzige Quelle
  der Wahrheit, Projektionen in `projections.sqlite` mit Checkpoint pro Projektor, synchron nach
  jedem Speichern. Fachliche Regeln prüft der Service, bevor das Event entsteht. Ein Prozess.
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
- **Geldbeträge** als ganze Cent (`int`) in Events und Datenbank, Umrechnung nur an der Oberfläche.
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

### Mitgliedschaft und Status

- Statusmodell der Mitgliedschaft:

  ```
  Antragsteller ─Zulassung + Geldeingang─▶ Mitglied ─Kündigung─▶ gekündigt ─Ende GJ (Frist)─▶ ausgeschieden
       └─Ablehnung durch den Vorstand / Rücknahme─▶ abgelehnt
                                 ├─Ausschlussbeschluss─▶ ausgeschlossen ─Ende GJ─▶ ausgeschieden
                                 ├─Tod─▶ verstorben (Erben, § 77 GenG) ─Ende GJ─▶ ausgeschieden
                                 └─Übertragung aller Anteile (Umbuchung)─▶ ausgeschieden
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
- **Mitglieds- und Kontonummer werden bei der Erfassung des Antrags vergeben** (höchste Nummer + 1).
  Lücken durch abgelehnte Anträge sind zulässig. Für die Migration der Altdaten ist eine manuelle
  Vergabe möglich (nicht in der Oberfläche); die App prüft dabei die Eindeutigkeit.

### Tod eines Mitglieds

- Rechtslage: Die Mitgliedschaft geht auf die Erben über und endet zum Schluss des Geschäftsjahres
  des Todes (§ 77 Abs. 1 GenG). Eine Fortsetzung durch die Erben (§ 77 Abs. 2) sieht die Satzung
  nicht vor.
- **Vorgang „Tod erfassen“** mit Sterbedatum: Status „verstorben“, Ausscheiden automatisch zum
  31.12. des Todesjahres; eine laufende Kündigung mit späterem Termin wird gegenstandslos.
- **Anschrift der Erben** wird von Hand in den Adresszeilen gepflegt, es gibt keinen eigenen
  Erbenvertreter-Datensatz. Der Vorgang „Tod erfassen“ zeigt dem Erfasser einen Hinweis, wie die
  Adresszeilen umzustellen sind, und führt zu ihnen.
- **Erbe tritt ein:** Er wird als neues Mitglied erfasst (Antrag, Zulassung), das Guthaben wird
  umgebucht. Der Verstorbene scheidet mit der Umbuchung ohne Anspruch aus.
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
- **Pflichtangabe Stornogrund.**
- Jede Buchung kann nur einmal storniert werden, ein Storno nicht. In der Kontoansicht sind
  Original und Storno als Paar gekennzeichnet und per Filter ausblendbar.
- **Statusauswirkung:** Fehlt durch ein Storno die Grundlage eines Status (z. B. der Geldeingang),
  setzt die App den Status nicht still zurück, sondern warnt; der Mitarbeiter klärt den Vorgang.

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
  Ersteinrichtung angelegt, Nummer und Bezeichnung („Unser Dorfladen Schlichten eG“) kommen aus
  der Konfiguration; bei der Migration wird es auf das alte Konto 9999 abgebildet.
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
- **Ausschluss** (Satzung 6.2–6.4): Beschluss des Vorstands mit Datum, Widerspruch beim
  Aufsichtsrat binnen sechs Wochen.
- **Daten werden abgeleitet, nicht gepflegt:** Eintrittsdatum aus der Wertstellung der ersten
  Eintrittsbuchung, Kündigungsdatum und Ausscheidensdatum aus dem Vorgang „Kündigung erfassen“.
  Sterbedatum wird manuell erfasst. In der Maske sind diese Felder nur lesbar, Änderungen laufen
  über eigene Aktionen (z. B. „Kündigung erfassen“, „Kündigung zurücknehmen“) und erzeugen Events.
- **Reports wählen nach dem Status zum Stichtag** aus, nicht nach „Saldo > 0“.

### Auseinandersetzung

- Je Kündigung (auch Teilkündigung) entsteht ein **Auseinandersetzungsanspruch**:
  `offen → (teilweise) ausgezahlt → ausgezahlt`.
- **Die Auszahlungsfähigkeit (Mindestkapital, Satzung 6.6) prüft die App nicht.** Ob und wie viel
  ausgezahlt werden darf, stellt der Mitarbeiter im Einzelfall fest.
- **Teilauszahlungen** (Bruchteile des Anspruchs) müssen möglich sein, ebenso Kürzungen um
  Verlustvorträge (Satzung 6.5). Für diese Buchungen gilt „Betrag = Anteile × Anteilspreis“ nicht.
- **Verjährung** (Satzung 2.7) überwacht die App nicht. Sie bietet eine **Liste der offenen
  Ansprüche** mit Ausscheidensdatum; die Ausbuchung erfolgt von Hand.

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
  | Storno | wie Original | wie Original | Korrektur |

- Der „Austritt“ aus `Konzeption.md` ist damit in **Ausscheiden** und **Auszahlung** aufgeteilt.
  Sind Saldo und Anteile 0, ist der Austritt abgeschlossen.
- **Vorgang „Ausscheiden zum Jahresende buchen“:** Die Buchhaltung startet ihn nach dem 31.12. Er
  zeigt alle zu diesem Termin fälligen Kündigungen, Todesfälle und Ausschlüsse und bucht nach
  Bestätigung mit Wertstellung 31.12. Kein automatischer Lauf. Reports zu einem Stichtag, für den
  das Ausscheiden noch nicht gebucht ist, zeigen eine Warnung.
- **Eingabe:** Wo Betrag und Anteile nötig sind, wird eins von beiden eingegeben und das andere
  berechnet; ein Betrag muss ein Vielfaches des Anteilspreises sein. Die Maske zeigt nur die
  Felder, die die Buchungsart braucht.

### Migration der Altdaten (Schritt 7)

- **Altsystem:** Access-Datenbank mit eigener VBA-Logik. Die Excel-Listen in `Beispieldaten/`
  sind Reports daraus, nicht der vollständige Bestand. Quelle der Migration ist die Access-Datei
  selbst (gelesen mit `mdbtools`) oder ein Export jeder einzelnen Tabelle.
- **Übernommen werden alle Personen einschließlich Ausgetretener, die komplette Historie der
  Personendaten und alle Buchungen.**
- **Eigene Migrationsevents** (z. B. `member.migrated`, `member.migrated-change` je
  Historienzeile mit Gültig-von, `booking.migrated`). Die Daten werden übernommen, wie sie im
  Altsystem stehen; Eintritts-, Kündigungs-, Austritts- und Sterbedatum kommen direkt aus den
  Feldern, fehlende Angaben wie das Zulassungsdatum werden aus dem Eintrittsdatum abgeleitet.
- Akteur `migration`, Eventzeit = Zeitpunkt der Migration, das fachliche Datum steht in den Daten.
- Ausnahmen nur für die Migration: manuelle Nummernvergabe, keine Prüfung „Betrag = Anteile ×
  Preis“. Konten, deren Werte nicht zum neuen Buchungsmodell passen, listet das Skript als
  Prüffälle auf.
- **Ablauf:** wiederholbares Migrationsskript für Probeläufe, automatischer Abgleich der Salden und
  Anteile je Konto zwischen alt und neu, Umstellung zu einem Stichtag.

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
| Soll / Haben | `debit` / `credit` |
| Buchungstag / Wertstellung | `booking_date` / `value_date` |
| Saldo | `balance` |
| Eintritt (Buchung) | `subscription` |
| Rückzahlung | `refund` |
| Umbuchung | `transfer` |
| Kündigung, Teilkündigung, Kündigungsfrist | `notice`, `partial_notice`, `notice_period` |
| Ausschluss | `expulsion` |
| Ausscheiden | `exit` |
| Auseinandersetzungsanspruch | `settlement_claim` |
| Kürzung Verlustvortrag | `loss_deduction` |
| Auszahlung | `payout` |
| Ausbuchung Verjährung | `limitation_writeoff` |
| Storno | `reversal` |
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

Status der Mitgliedschaft: `applicant`, `rejected`, `member`, `notice_given`, `expelled`,
`deceased`, `exited`.

## Offene Punkte

- Access-Datei bzw. Tabellenexporte des Altsystems bereitstellen (in `Beispieldaten/`).

## Mögliche Weiterentwicklungen

- **Eintrittsgeld** (Satzung 2.3), falls die Generalversammlung eines beschließt: eigene
  Buchungsart ohne Anteile, Zuführung zu den Rücklagen.
- **Rückvergütung** (Satzung 2.6) über die Mitgliedskonten.
- Mehrere Rollen je Benutzer statt mehrerer Benutzerkonten je Person.
- Späteste Absendung der Einladung zur GV aus dem GV-Datum berechnen (Satzung 3.1: zwei Wochen
  plus zwei Werktage).
- API-Keys mit Ablaufdatum, MCP-Server, Login über OAuth2/JWT (siehe `Konzeption.md`).
- Eine Bibliothek ohne eigenes Styling (z. B. Reka UI) für schwierige Bausteine wie Dialoge,
  Datumsauswahl oder Auswahl mit Suche, falls sie selbst gebaut zu aufwendig oder nicht barrierefrei
  genug werden. Gestaltet wird weiter mit den eigenen Farbvariablen.
