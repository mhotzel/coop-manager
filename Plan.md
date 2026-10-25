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
   (Backend mit `uv`, Frontend Vue 3 mit Vite)
2. Infrastruktur: Konfiguration, Logging, Security-Header, Layout, Theme
3. Benutzerverwaltung: Login, Login-Sperre, Anlage durch Admin, Kennwort ändern, deaktivieren, löschen
4. Mitglieder: Aggregat, Nummernvergabe, Suche, Bearbeitung, Adresszeilen und Briefanrede
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
  `colorscheme-dorfladen.css` aus `purchase-prices`, keine Komponentenbibliothek.
- **Repo-Struktur:** `backend/` (Paket `coop_manager`, Tests, `pyproject.toml`) und `frontend/`.
  Im Betrieb liefert FastAPI die gebaute SPA selbst aus: ein Container, gleiche Herkunft, kein
  CORS. Dockerfile in zwei Stufen (Node baut das Frontend, dann Python).
- **Module im Backend:** `core`, `users`, `members`, `accounts`, `reports`, `migration`, je mit
  `domain.py`, `services.py`, `projections.py`, `schemas.py` (Pydantic) und `api.py` (dünn).
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
- **Security-Header** setzt die App selbst, CSP `script-src 'self'`.
- **Betrieb:** Konfiguration über Umgebungsvariablen mit Präfix `CM_`, Logs als JSON-Zeilen auf
  stdout, `/healthz`, Backup des Event Stores per CLI-Befehl.
- **Werkzeuge:** Python 3.14, `uv`, `ruff` (Zeilenlänge 120), `pytest` (Domain, Services, API),
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
- **Anteilspreis** ist eine Systemeinstellung des Admins. Eine Änderung gilt nur für neue Buchungen.

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
