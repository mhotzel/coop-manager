# Konzeption

## Grundsätzliche Dinge

Die Anwendung dient der Verwaltung von Genossenschaftsmitgliedern einer Genossenschaft.

Das Backend soll in Python entwickelt werden, entweder auf Basis von Flask oder Fast API. 
Das muss noch diskutiert werden.

Das Frontend soll auf Basis von Vue3 als Single Page App entstehen.

Es soll eine eigene Benutzerverwaltung haben, potenziell in einer Ausbaustufe aber auch ein Login
über oauth2 und JWT anbieten.

Die Datenspeicherung soll zu Beginn in einer sqlite3-Datenbank erfolgen. Die Daten sollen in 
einem EventStore gespeichert werden. Die Implementierung soll analog zu Projekt
[https://github.com/mhotzel/purchase-prices](https://github.com/mhotzel/purchase-prices) erfolgen.

Die Projektionen sollen in einer separaten sqlite3-DB gespeichert werden.

Die Anwendung soll Am Ende in einem Docker-Container laufen und mittels docker-compose gestartet
werden können. Sie soll potenziell auch auf einem Synology NAS deploybar sein. Details dazu, 
insbesondere zu den Problemen auf einem Synology NAS, können in diesem Projekt nachgelesen
werden: [https://github.com/mhotzel/purchase-prices](https://github.com/mhotzel/purchase-prices).

Als Farbschema sollen diese Farben herangezogen werden: 
[src/purchase_prices/static/css/themes](https://github.com/mhotzel/purchase-prices/tree/main/src/purchase_prices/static/css/themes)

Datensicherungen sollen über einen Export, der per Cron-Job gestartet werden kann, möglich sein in Form einer sqlite-DB. 
Siehe auch hierzu das Verfahren in Projekt 
[src/purchase_prices/static/css/themes](https://github.com/mhotzel/purchase-prices/tree/main/src/purchase_prices/static/css/themes).

## Fachlichkeit

Es sind grundsätzlich folgende Funktionen vorgesehen:
1. Mitgliederdaten verwalten, also Neuzugänge anlegen, Namens-
   und Adressänderungen, Todesfälle.
2. Mitglieder zeichnen Genossenschaftsanteile, ein Anteil hat einen Wert von derzeit 50 EUR. 
   Eine Person bzw. ein Antragsteller wird nur dann zum Mitglied, wenn sie auch Anteile zeichnet 
   und die Bezahlung des Anteils erfolgt ist, also ein Geldeingang vorliegt. Für Austritte gelten 
   Kündigungsfristen, die bei Kündigung zu beachten sind. Ein Austritt ist erst erfolgt, wenn die 
   Kündigungsfrist abgelaufen ist, der Genossenschaftsanteil ausgezahlt wurde und wenn der Austritt
   gemäß Satzung auch möglich ist. Die Überschreibung von Anteilen zwischen Mitgliedern ist möglich, 
   z.B. im Todesfall eines Mitglieds auf die Erben.
3. Es müssen 3 Arten von Auswertungen bzw. Reports möglich sein:
   1. Mitgliederliste gemäß Genossenschaftsgesetz
   2. Mitgliederliste als Basis für einen Seriendruck für Einladungen zu Versammlungen
   3. Mitgliederliste zur Auslage und Anwesenheitsdokumentation bei Veranstaltungen

### Datenstrukturen der Personen bzw. Antragssteller und Mitglieder

- Jedes Mitglied hat eine interne eindeutige ID. Dazu soll UUIDv7 genutzt werden.
- Jedes MItglied hat eine eindeutige Mitgliedsnummer als Ganzzahl. Diese soll aber an 
  der Oberfläche unveränderbar sein. Bei der Anlage eines Mitglieds soll diese Nummer
  automatisch ermittelt werden, indem die größte vergebene Nummer ermittelt und um 1 erhöht wird.
- Natürliche Personen haben einen Vor- und Nachnamen. Hat eine Person mehr rerer Vornamen
  sollen diese alle durch Leerzeichen getrennt im Vornamenfeld gespeichert werden.
- Juristische Personen haben keinen Vor- und Nachnamen, sondern einen Firmennamen. Zu juristischen Personen
  wird aber trotzdem ein Vor- und Nachname gespeichert, nämlich den des Ansprechpartners zur juristischen Person. 
- Zu den natürlichen Personen wird das Geschlecht gespeichert. Dazu kommen in Frage männlich (m), weiblich (w)
  und divers (d). Daraus kann potenziell die korrekte Briefanrede und die Anrede im Personendatensatz, 
  also zum Beispiel Herr, Frau und so weiter ermittelt werden. Mitglieder zu denen kein kein Geschlecht (m oder w) vorliegt, 
  oder das Geschlecht nicht belegt ist, werden mit "Liebes Mitglied" angesprochen. Juristische Personen werden immer mit
  "sehr geehrten Damen und Herren" angesprochen.
- Natürliche Personen können auch einen Titel haben, also zum Beispiel "Dr." oder "Prof."
- Die postalische Adresse, die jede Person haben muss, besteht aus folgenden Bausteinen:
  - Straße,
  - Hausnummer (optional),
  - Ort,
  - Postleitzahl und
  - Land (optional)
- Aus den Daten der Person und der postalischen Adresse werden die Adresszeilen automatisch per Button vorbelegt.
  Es werden also 6 Adresszeilen zusätzlich zur Person gespeichert. Bei Adressänderungen können die Zeilen ebenfalls 
  per Button neu generiert werden. Die Zeilen können manuell gepflegt werden.
- Weiterhin können zu jeder Person eine Telefonnummer und eine E-Mail-Adresse hinzerlegt werden.
- Weitere Daten zur Person sind:
  - Eintrittsdatum
  - Austrittsdatum
  - Kündigungsdatum
  - Sterbedatum
  - Ein Kennzeichen "keine Post" (Ja/Nein-Feld)
  - Hinweise (mehrzeiliges Textfeld)

### Kontodaten und Buchungen

- Jedes Mitglied hat genau ein Mitgliedskonto. Ein Mitgliedskonto gehört wiederum zu genau einer Person.
  Es ist also eine 1:1-Beziehung.
- Die Kontonummer wird analog zur Mitgliedsnummer eindeutig und aufsteigend 
  als Ganzzahl vergeben. Die technisch eindeutige ID eines Kontos wird wiederum analog zu eindeutigen ID des Mitglieds
  als UUIDv7 abgebildet. Konto-ID und Kontonummer werden aber separat vergeben.
- Buchungen auf dem Mitgliedskonto erfolgen nach dem Prinzip der doppelten Buchführung. Ein Buchungssatz besteht also aus
  - Soll-Kontonummer
  - Haben-Kontonummer
  - Buchungstext
  - einer eindeutigen ID auf Basis UUIDv7
  - einem Betrag in EUR mit zwei Nachkommastellen für Ct
  - einm Anzahl von Genossenschaftsanteilen als Ganzzahl, da keine Bruchteile von Anteilen vorkommen dürfen
  - Buchungstag, welches der Tag der Buchung in der Anwendung ist
  - Wertstellungstag, also dem Tag, an dem die Buchung fachlich gültig ist. Dies ist z.B. relevant, wenn die Aufzeichnung
    des Vorganges Tage später nach dem Zahlungseingang des Betrags auf dem Konto der Genossenschaft erfolgt.
- Haben-Buchungen werden als positive Beträge im Konto dargestellt, Soll-Buchungen als negative Beträge.
- Der Saldo des jeweiligen Kontos ergibt sich aus der Differenz aller positiven und negativen Beträge.
- Der Saldo kann bei Mitgliedskonten fachlich nicht negativ werden. Einzig das Pseudokonto, welches an der speziellen
  Person der Genossenschaft selbst hängt, kann und muss negativ werden.

**Buchungssätze**

1. Eintritt
  - Soll-Konto: Genossenschafts-Pseudokonto (vorbelegt)
  - Haben-Konto: Mitgliedskonto
  - Buchungsdatum: vorbelegt mit dem jeweiligen Tagesdatum
  - Anzahl Anteile
  - Betrag: vorbelegt durch Berechnung des Betrags aus der Anzahl der Anteile multipliziert mit dem Preis eines Anteils
2. Austritt
  - Soll-Konto: Mitgliedskonto
  - Haben-Konto: Genossenschafts-Pseudokonto (vorbelegt)
  - Buchungsdatum: vorbelegt mit dem jeweiligen Tagesdatum
  - Anzahl Anteile
  - Betrag: vorbelegt durch Berechnung des Betrags aus der Anzahl der Anteile multipliziert mit dem Preis eines Anteils
3. Umbuchungen
  - Soll-Konto: Mitgliedskonto
  - Haben-Konto: Mitgliedskonto
  - Buchungsdatum: vorbelegt mit dem jeweiligen Tagesdatum
  - Anzahl Anteile
  - Betrag: vorbelegt durch Berechnung des Betrags aus der Anzahl der Anteile multipliziert mit dem Preis eines Anteils

Der Betrag bzw. Preis eines Anteils soll in der Anwendung konfigurierbar sein.

### Reports

  - Die Reports werden in Form von Excel-Dateien erzeugt.

## Benutzerverwaltung

Benutzer werden durch den Administrator angelegt. Dazu bekommt jeder Benutzer einmalig ein initiales Kennwort,
was der Administrator dem Benutzer im Anschluss auf anderen Wegen zukommen lässt. 
Jeder Benutzer kann sein Kennwort selbstständig ändern. 
Benutzer können durch den Administrator deaktiviert und auch gelöscht werden.

## KI-Integration

Die Anwendung soll in einer Ausbaustufe auch einen MCP-Server bereitstellen, der per API remote angesprochen werden kann. 
Dazu muss es möglich sein, für Benutzer einen API-Key zu erzeugen, der mit einer Ablaufzeit versehen ist und durch den Nutzer und den
Admin verlängert werden kann.