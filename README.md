# coop-manager

Mitgliederverwaltung für eine Genossenschaft, entwickelt für die Unser Dorfladen Schlichten eG.
Sie löst die bisherige Access-Datenbank ab.

## Kurzfassung

- **Mitglieder:** Erfassung ab der Beitrittserklärung, Zulassung durch den Vorstand, Namens- und
  Adressänderungen mit Historie, Kündigung (auch einzelner Anteile), Ausschluss und Todesfälle.
- **Mitgliedskonten:** Buchungen nach doppelter Buchführung für Eintritt, Rückzahlung,
  Umbuchung, Ausscheiden, Auszahlung des Auseinandersetzungsguthabens und Storno.
- **Reports als Excel:** Mitgliederliste nach Genossenschaftsgesetz, Seriendruckdatei für
  Einladungen und Anwesenheitsliste für die Generalversammlung, jeweils zu einem Stichtag.
- **Benutzerverwaltung** mit den Rollen Admin, Buchhaltung und Buchhaltung lesend.
- **Technik:** Backend mit Python und FastAPI, Frontend als Single Page App mit Vue 3 und
  TypeScript. Alle Änderungen werden als Events in einem Event Store (SQLite) gespeichert, die
  Lesetabellen (Projektionen) liegen in einer eigenen SQLite-Datenbank. Betrieb im
  Docker-Container, auch auf einem Synology-NAS.

## Dokumentation

| Datei | Inhalt |
|---|---|
| [Konzeption.md](Konzeption.md) | Die ursprüngliche Beschreibung des Vorhabens: Ziele, Technik, Datenstrukturen, Buchungssätze, Reports. Sie bleibt als Ausgangspunkt erhalten und wird nicht fortgeschrieben. |
| [Plan.md](Plan.md) | Alle abgestimmten fachlichen und technischen Entscheidungen, das Vorgehen in Schritten, das Glossar Deutsch–Englisch sowie offene Punkte und mögliche Weiterentwicklungen. **Bei Abweichungen gilt der Plan vor der Konzeption.** |
| [Logbuch.md](Logbuch.md) | Chronik der Entwicklung: was in jedem Schritt gemacht wurde, mit welchen Werkzeugen und Befehlen und warum. Zum Nachvollziehen und Nachschlagen. |
| [AGENTS.md](AGENTS.md) | Arbeitsregeln für KI-Assistenten, die an diesem Projekt mitarbeiten. |

## Lizenz

Siehe [LICENSE](LICENSE).
