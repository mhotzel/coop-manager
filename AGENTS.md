# Hinweise für KI-Assistenten

- **Fachlichkeit:** `Konzeption.md` ist die ursprüngliche Beschreibung. Verbindlich sind die
  Entscheidungen in `Plan.md`, sie gehen der Konzeption vor. Neue Entscheidungen werden dort
  eingetragen, offene Fragen unter „Offene Punkte“, Ideen unter „Mögliche Weiterentwicklungen“.
- **Logbuch:** Jeder Arbeitsschritt wird in `Logbuch.md` festgehalten: was gemacht wurde, mit
  welchen Werkzeugen und Befehlen, und warum. Es dient Matthias als Lern- und Nachschlagewerk.
- **Arbeitsweise:** Gemeinsam in kleinen Schritten entwickeln und dabei erklären, was passiert
  und warum (FastAPI, Vue, TypeScript, Event Sourcing, Werkzeuge). Nicht mehrere Schritte auf
  einmal vorauslaufen. Code nach KISS, so einfach, dass Matthias ihn selbst durchschaut. Vor
  jedem Schritt erst erklären, was geplant ist (Befehle, Dateien, Gründe), und auf Matthias'
  Freigabe warten.
- **Git:** Commit erst nach Abnahme eines Schritts durch Matthias. Gepusht wird nur auf
  ausdrückliche Anweisung. Commit-Nachrichten auf Deutsch.
- **Sprache:** Code, Events und Bezeichner englisch nach dem Glossar in `Plan.md`, Oberfläche,
  Dokumentation und Kommentare für Matthias auf Deutsch.
- **Vorbild:** Event Store, Projektionen, Backup und Deployment wie im Projekt `purchase-prices`
  (lokal `../purchase-prices`).
- **Datenschutz:** `Beispieldaten/` enthält echte Mitgliederdaten und ist per `.gitignore`
  ausgeschlossen. Daraus nichts in das Repository, in Tests oder Fixtures übernehmen; Testdaten
  sind erfunden.
