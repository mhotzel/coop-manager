// Erzeugt Dokumentation/Benutzerhandbuch.docx (Benutzerhandbuch der Mitgliederverwaltung).
//
// Aufruf aus diesem Ordner:  npm install  (einmalig)  und dann  npm run build
// Die Texte stehen unten im Abschnitt „Inhalt“; **fett** und [[Knopf]] (braun, fett) gehen im Text.
const fs = require('fs')
const path = require('path')
const {
  Document, Packer, Paragraph, TextRun, ImageRun, Header, Footer, AlignmentType, HeadingLevel,
  Table, TableRow, TableCell, WidthType, BorderStyle, ShadingType, LevelFormat, PageNumber,
  TableOfContents, PageBreak, TabStopType,
} = require('docx')

const OUT = process.argv[2] ?? path.join(__dirname, '..', 'Benutzerhandbuch.docx')
const BROWN = '544741'
const GREEN = '8EBE44'
const LIGHT_GREEN = 'EEF5E3'
const GREY = 'F2F0EF'
const FONT = 'Arial'
// Dasselbe Logo wie in der App.
const logo = fs.readFileSync(path.join(__dirname, '..', '..', 'frontend', 'src', 'assets', 'img', 'dlslogo.png'))
const LOGO_RATIO = 385 / 1772

// ---------- Bausteine ----------

// Text mit **fett** und „Knopf“-Hervorhebung über [[Knopf]].
function runs(text, extra = {}) {
  const parts = text.split(/(\*\*[^*]+\*\*|\[\[[^\]]+\]\])/)
  return parts.filter((s) => s !== '').map((s) => {
    if (s.startsWith('**')) return new TextRun({ text: s.slice(2, -2), bold: true, ...extra })
    if (s.startsWith('[[')) return new TextRun({ text: s.slice(2, -2), bold: true, color: BROWN, ...extra })
    return new TextRun({ text: s, ...extra })
  })
}

const p = (text, opts = {}) => new Paragraph({ children: runs(text), spacing: { after: 120 }, ...opts })
const h1 = (text) => new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun(text)], pageBreakBefore: true })
const h2 = (text) => new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun(text)] })
const h3 = (text) => new Paragraph({ heading: HeadingLevel.HEADING_3, children: [new TextRun(text)] })
const bullets = (items) => items.map((t) => new Paragraph({ numbering: { reference: 'bullets', level: 0 }, children: runs(t), spacing: { after: 60 } }))

let stepInstance = 0
function steps(items) {
  stepInstance += 1 // jede Liste beginnt wieder bei 1
  return items.map((t) => new Paragraph({
    numbering: { reference: 'steps', level: 0, instance: stepInstance }, children: runs(t), spacing: { after: 60 },
  }))
}

// Hinweiskasten: grün hinterlegt mit grünem Rand links.
function note(text, title = 'Hinweis') {
  return new Paragraph({
    children: [new TextRun({ text: `${title}: `, bold: true, color: BROWN }), ...runs(text)],
    shading: { type: ShadingType.CLEAR, fill: LIGHT_GREEN, color: 'auto' },
    border: { left: { style: BorderStyle.SINGLE, size: 24, color: GREEN, space: 8 } },
    indent: { left: 200, right: 200 },
    spacing: { before: 120, after: 160 },
  })
}

const TABLE_WIDTH = 9026 // A4 mit 2,54 cm Rand
const cellBorder = { style: BorderStyle.SINGLE, size: 4, color: 'BFB8B4' }
const borders = { top: cellBorder, bottom: cellBorder, left: cellBorder, right: cellBorder }

function table(header, rows, widths) {
  const total = widths.reduce((a, b) => a + b, 0)
  const scaled = widths.map((w) => Math.round((w / total) * TABLE_WIDTH))
  scaled[scaled.length - 1] += TABLE_WIDTH - scaled.reduce((a, b) => a + b, 0)
  const cell = (text, i, head) => new TableCell({
    borders,
    width: { size: scaled[i], type: WidthType.DXA },
    shading: head ? { type: ShadingType.CLEAR, fill: BROWN, color: 'auto' } : undefined,
    margins: { top: 60, bottom: 60, left: 100, right: 100 },
    children: [new Paragraph({ children: runs(text, head ? { bold: true, color: 'FFFFFF' } : {}) })],
  })
  return new Table({
    width: { size: TABLE_WIDTH, type: WidthType.DXA },
    columnWidths: scaled,
    rows: [
      new TableRow({ tableHeader: true, children: header.map((t, i) => cell(t, i, true)) }),
      ...rows.map((r) => new TableRow({ children: r.map((t, i) => cell(t, i, false)) })),
    ],
  })
}
const gap = () => new Paragraph({ children: [], spacing: { after: 60 } })

// ---------- Inhalt ----------

const content = []
const add = (...items) => items.forEach((i) => (Array.isArray(i) ? content.push(...i) : content.push(i)))

// 1 Einführung
add(
  h1('1 Einführung'),
  p('Die Mitgliederverwaltung ersetzt die bisherige Access-Datenbank. Sie verwaltet die Mitglieder der Unser Dorfladen Schlichten eG von der Beitrittserklärung bis zur Auszahlung des Auseinandersetzungsguthabens, führt für jedes Mitglied ein Konto mit allen Buchungen und erstellt die Listen, die die Genossenschaft braucht.'),
  p('Dieses Handbuch beschreibt die Arbeit mit der Oberfläche Schritt für Schritt. Wo es auf Regeln aus Satzung und Genossenschaftsgesetz ankommt, stehen sie in Hinweiskästen dabei. Knöpfe und Menüpunkte sind **braun und fett** gesetzt, etwa [[Speichern]].'),
  h2('1.1 Anmelden und abmelden'),
  steps([
    'Die Adresse der Mitgliederverwaltung im Browser öffnen.',
    'Benutzername und Kennwort eingeben und anmelden.',
    'Zum Schluss oben rechts auf [[Abmelden]] klicken, besonders an gemeinsam genutzten Rechnern.',
  ]),
  p('Das eigene Kennwort ändert man oben rechts über [[Kennwort ändern]]. Nach mehreren falschen Kennwörtern hintereinander wird der Benutzername für eine Weile gesperrt; danach geht es wieder.'),
  h2('1.2 Rollen'),
  p('Jeder Benutzer hat genau eine Rolle. Sie bestimmt, welche Menüpunkte er sieht und was er ändern darf.'),
  table(['Rolle', 'Darf'], [
    ['**Buchhaltung**', 'Alles rund um Mitglieder, Konten und Reports: Anträge erfassen, zulassen, buchen, stornieren, Kündigungen erfassen, Jahresende buchen, Listen herunterladen.'],
    ['**Buchhaltung lesend**', 'Alles ansehen und alle Listen herunterladen, aber nichts ändern. Knöpfe zum Ändern fehlen.'],
    ['**Admin**', 'Nur die Benutzerverwaltung: Benutzer anlegen, Rollen vergeben, Kennwörter setzen, deaktivieren. Mitglieder und Konten sieht der Admin nicht.'],
  ], [1, 3]),
  gap(),
  h2('1.3 Aufbau der Oberfläche'),
  p('Oben stehen das Logo, der angemeldete Benutzer und die Knöpfe [[Kennwort ändern]] und [[Abmelden]]. Links steht das Menü (auf dem Handy hinter „☰ Menü“):'),
  table(['Menüpunkt', 'Inhalt'], [
    ['[[Mitglieder]]', 'Suche nach Mitgliedern, neuer Antrag, von dort zu Mitglied und Konto.'],
    ['[[Gen.-Kto]]', 'Das Genossenschaftskonto (Nummer 9999), die Gegenseite fast aller Buchungen.'],
    ['[[Jahresende]]', 'Ausscheiden zum 31.12. buchen.'],
    ['[[Ansprüche]]', 'Liste der offenen Auseinandersetzungsansprüche.'],
    ['[[Reports]]', 'Listen als Excel-Datei: Mitgliederliste nach GenG, Generalversammlung, Seriendruck, Vorgänge eines Geschäftsjahres.'],
    ['[[Benutzer]]', 'Benutzerverwaltung (nur Admin).'],
  ], [1, 3]),
  gap(),
  p('Meldungen erscheinen oben auf der jeweiligen Seite: **rot** für Fehler (nichts wurde gespeichert), **gelb** für Warnungen (gespeichert, aber bitte prüfen) und **blau** für Bestätigungen.'),
)

// 2 Grundbegriffe
add(
  h1('2 Grundbegriffe'),
  h2('2.1 Status einer Person'),
  p('Jede Person hat zu jedem Tag einen Status. Er ergibt sich aus den erfassten Daten (Antrag, Zulassung, Geldeingang, Kündigung usw.) und wird nicht von Hand gesetzt.'),
  table(['Status', 'Bedeutung'], [
    ['Antragsteller', 'Beitrittserklärung erfasst; Zulassung oder Geldeingang fehlen noch.'],
    ['Mitglied', 'Zugelassen und eingezahlt. Das Eintrittsdatum ist das spätere der beiden Daten.'],
    ['abgelehnt', 'Der Vorstand hat den Antrag abgelehnt oder die Person hat ihn zurückgenommen.'],
    ['gekündigt', 'Die Kündigung ist eingegangen; bis zum 31.12. des Ausscheidensjahres bleibt die Person Mitglied mit allen Rechten.'],
    ['verstorben', 'Tod erfasst; die Mitgliedschaft geht bis zum 31.12. des Todesjahres auf die Erben über.'],
    ['ausgeschlossen', 'Ausschluss durch Beschluss des Vorstands; Ausscheiden zum 31.12. des Beschlussjahres.'],
    ['ausgeschieden', 'Ab dem 1.1. nach dem Ausscheiden, nach einer Spende des Anteils oder der Übertragung aller Anteile ab dem Folgetag.'],
  ], [1, 3]),
  gap(),
  p('Neben dem Status kann der Hinweis „teilgekündigt“ stehen: Dann läuft eine Teilkündigung einzelner Anteile, die Person bleibt aber Mitglied.'),
  h2('2.2 Anteile, Saldo und Anspruch'),
  bullets([
    '**Anteile:** die Geschäftsanteile, die das Mitglied gerade hält.',
    '**Saldo:** was die Genossenschaft dem Mitglied schuldet, in Euro.',
    '**Anteilspreis:** der Preis eines Anteils; er wird bei der Einrichtung festgelegt und auf dem Konto angezeigt.',
    '**Offener Anspruch** (Auseinandersetzungsanspruch): Saldo minus Anteile × Anteilspreis. Er entsteht, wenn Anteile ausscheiden; das Geld bleibt bis zur Auszahlung auf dem Konto.',
  ]),
  p('Solange niemand gekündigt hat, gilt Saldo = Anteile × Anteilspreis.'),
  h2('2.3 Geschäftsjahr und Fristen'),
  bullets([
    'Das **Geschäftsjahr** ist das Kalenderjahr.',
    'Die **Kündigungsfrist** beträgt zwei Jahre zum Ende eines Geschäftsjahres (Satzung 6.1). Beispiel: Eingang 15.03.2026, Ausscheiden 31.12.2028. Die App schlägt das Jahr vor; es kann geändert werden.',
    'Bis einschließlich 31.12. zählt eine ausscheidende Person mit ihren Anteilen, **ausgeschieden ist sie ab dem 1.1.**',
  ]),
  h2('2.4 Wertstellung und Buchungstag'),
  p('Jede Buchung hat zwei Daten. Die **Wertstellung** ist der Tag, an dem die Buchung fachlich gilt, zum Beispiel der Tag des Geldeingangs auf der Bank. Der **Buchungstag** („Gebucht am“) ist der Tag, an dem sie in der App erfasst wurde. Listen und Salden zu einem Stichtag richten sich immer nach der Wertstellung.'),
  note('Nichts wird gelöscht. Jede Änderung wird mit Benutzer und Zeitpunkt gespeichert. Falsche Buchungen werden storniert, falsch erfasste Vorgänge (Kündigung, Tod, Ausschluss, Zeichnung) zurückgenommen.'),
)

// 3 Mitglieder
add(
  h1('3 Mitglieder'),
  h2('3.1 Mitglied suchen'),
  steps([
    'Im Menü [[Mitglieder]] wählen.',
    'Einen Suchbegriff eingeben: Name, Ort, Straße, Mitgliedsnummer oder Postleitzahl. Groß- und Kleinschreibung spielt keine Rolle.',
    'Auf [[Suchen]] klicken. Die Treffer zeigen Nummer, Name, Anschrift und Status.',
    'Auf den Namen klicken, um das Mitglied zu öffnen.',
  ]),
  p('Es werden höchstens 50 Treffer angezeigt; bei mehr Treffern die Suche verfeinern.'),
  h2('3.2 Neuen Antrag erfassen'),
  p('Mit dem Eingang der Beitrittserklärung wird die Person als Antragsteller erfasst. Dabei entstehen Mitgliedsnummer und Konto (beide Nummern sind gleich).'),
  steps([
    'Unter [[Mitglieder]] auf [[Neuer Antrag]] klicken.',
    '**Art der Person** wählen: natürliche Person oder Firma bzw. Verein (juristische Person).',
    'Name bzw. Firma und Ansprechpartner, Anschrift und, falls vorhanden, Telefon und E-Mail eintragen.',
    'Unter **Antrag** das Datum der Beitrittserklärung und die Zahl der gezeichneten Anteile eintragen.',
    'Auf [[Antrag speichern]] klicken. Die App zeigt das neue Mitglied mit seiner Nummer.',
  ]),
  note('Die Adresszeilen für Briefe und die Briefanrede erzeugt die App beim Speichern aus Name und Anschrift. Sie lassen sich danach von Hand anpassen (siehe 3.4).'),
  h2('3.3 Zulassen, ablehnen, Rücknahme'),
  p('Über die Aufnahme entscheidet der Vorstand (§ 15 GenG). Auf der Seite des Antragstellers stehen dafür Knöpfe bereit:'),
  table(['Knopf', 'Wann', 'Datum'], [
    ['[[Zulassen]]', 'Der Vorstand hat die Aufnahme beschlossen.', 'Tag des Beschlusses'],
    ['[[Ablehnen]]', 'Der Vorstand hat die Aufnahme abgelehnt.', 'Tag des Beschlusses'],
    ['[[Rücknahme]]', 'Die Person zieht ihren Antrag zurück (auch, wenn ein Antragsteller stirbt; Grund in die Hinweise schreiben).', 'Tag der Rücknahme'],
  ], [1, 2.5, 1.2]),
  gap(),
  p('Nach dem Klick fragt die App nach dem Datum; mit [[Bestätigen]] wird es gespeichert. **Mitglied wird die Person erst, wenn Zulassung und Geldeingang vorliegen**, in beliebiger Reihenfolge. Den Geldeingang erfasst die Eintrittsbuchung auf dem Konto (siehe 4.3).'),
  note('Wurde schon eingezahlt und dann abgelehnt, meldet die App, dass das Geld zurückgezahlt werden muss. Das geschieht mit der Buchung „Rückzahlung“.'),
  h2('3.4 Daten ändern'),
  p('Die Seite eines Mitglieds ist in Karten gegliedert. Jede Karte hat einen Knopf [[Bearbeiten]]; die Änderung wird mit [[Speichern]] übernommen oder mit [[Abbrechen]] verworfen. Alle Änderungen bleiben mit Datum in der Historie erhalten.'),
  table(['Karte', 'Inhalt und Hinweise'], [
    ['Name bzw. Firma', 'Titel, Vornamen, Nachname, Geschlecht bzw. Firma und Ansprechpartner. Die Adresszeilen ändern sich dabei nicht von selbst, bitte danach prüfen.'],
    ['Anschrift', 'Straße, Hausnummer, PLZ, Ort, Land (leer = Deutschland). Auch hier danach die Adresszeilen prüfen.'],
    ['Kontakt', 'Telefon und E-Mail.'],
    ['Adresszeilen', 'Sechs Zeilen für das Anschriftenfeld von Briefen und den Seriendruck. Zu lange Zeilen werden markiert. [[Adresszeilen erzeugen]] baut sie neu aus Name und Anschrift.'],
    ['Briefanrede und Post', 'Die Anrede wird aus Name und Geschlecht erzeugt; eine abweichende Anrede kann eingetragen werden (leer = erzeugen). **Keine Post** [[Setzen]] bzw. [[Aufheben]]: Die Person fehlt dann in der Seriendruck-Liste.'],
    ['Hinweise', 'Freier Text, z. B. Absprachen oder Besonderheiten.'],
  ], [1, 3]),
  gap(),
  p('Mit [[Konto anzeigen]] geht es von der Mitgliedsseite zum Konto, mit [[Zur Suche]] zurück zur Suche.'),
)

// 4 Konto und Buchungen
add(
  h1('4 Konto und Buchungen'),
  h2('4.1 Die Kontoansicht'),
  p('Das Konto zeigt oben Saldo, Anteile, einen offenen Anspruch (falls vorhanden), die gezeichneten Anteile, Geldeingang, Eintritt und den aktuellen Anteilspreis. Darunter folgen die Maske **Neue Buchung** und die Liste aller **Buchungen** mit Wertstellung, Buchungstag, Art, Text, Gegenkonto, Anteilen und Betrag. Ein Klick auf das Gegenkonto öffnet dieses Konto. Mit **Stornierte ausblenden** verschwinden stornierte Buchungen samt Storno aus der Liste.'),
  p('Das Genossenschaftskonto (Menü [[Gen.-Kto]]) zeigt alle Buchungen aus Sicht der Genossenschaft.'),
  h2('4.2 Eine Buchung erfassen'),
  steps([
    'Das Konto des Mitglieds öffnen.',
    'Unter **Neue Buchung** die **Buchungsart** wählen. Angeboten werden nur Arten, die gerade passen (z. B. Auszahlung nur bei offenem Anspruch).',
    'Die **Wertstellung** eintragen (nicht in der Zukunft).',
    '**Anteile** oder **Betrag** eintragen; das jeweils andere Feld rechnet die App mit dem Anteilspreis aus. Ein Betrag muss ein Vielfaches des Anteilspreises sein.',
    'Optional einen **Buchungstext** eintragen; leer bleibt der Name der Buchungsart.',
    'Auf [[Buchen]] klicken.',
  ]),
  h2('4.3 Die Buchungsarten'),
  table(['Buchungsart', 'Wofür', 'Anteile / Betrag'], [
    ['Eintritt', 'Geldeingang der Einzahlung aus dem Antrag.', 'Anteile × Preis'],
    ['Weitere Anteile', 'Einzahlung später gezeichneter Anteile (siehe 4.5).', 'Anteile × Preis'],
    ['Rückzahlung', 'Geld zurück bei Ablehnung oder ungeklärter Zahlung.', 'Anteile × Preis'],
    ['Umbuchung', 'Anteile auf ein anderes Mitgliedskonto übertragen, z. B. auf Erben (siehe 4.6).', 'Anteile × Preis'],
    ['Spende Anteil', 'Mitglied scheidet aus und spendet sein ganzes Guthaben (siehe 4.7).', 'alle Anteile, ganzer Saldo'],
    ['Auszahlung', 'Auszahlung des offenen Anspruchs, auch in Teilbeträgen (siehe 6).', 'nur Betrag'],
    ['Kürzung Verlustvortrag', 'Minderung des Anspruchs um anteilige Verluste (Satzung 6.5).', 'nur Betrag'],
    ['Ausbuchung Verjährung', 'Verjährter Restanspruch geht an die Genossenschaft (Satzung 2.7).', 'ganzer Rest'],
    ['Ausscheiden', 'Wird nicht hier, sondern auf der Seite **Jahresende** gebucht (siehe 5.5).', 'nur Anteile'],
    ['Storno', 'Macht eine falsche Buchung rückgängig (siehe 4.8).', 'wie das Original'],
  ], [1.3, 2.7, 1.3]),
  gap(),
  h2('4.4 Eintritt buchen und Abgleich'),
  p('Geht das Geld eines Antragstellers ein, wird es als **Eintritt** gebucht, Wertstellung = Tag des Geldeingangs. Dabei gleicht die App die eingezahlten mit den gezeichneten Anteilen ab:'),
  bullets([
    '**Stimmen sie überein**, ist der Geldeingang erfasst. Liegt auch die Zulassung vor, ist die Person ab dem späteren der beiden Daten Mitglied.',
    '**Ist es zu wenig**, meldet die App z. B. „2 von 3 gezeichneten Anteilen eingezahlt“. Mitglied wird die Person erst, wenn der Rest eingeht (zweite Eintrittsbuchung).',
    '**Ist es zu viel**, meldet die App das ebenfalls; der Vorgang ist zu klären, notfalls mit einer Rückzahlung.',
  ]),
  note('Eine Einzahlung vor der Zulassung ist möglich und wird ganz normal als Eintritt gebucht. Mitglied wird die Person dann mit der Zulassung.'),
  h2('4.5 Weitere Anteile'),
  p('Ein Mitglied kann später weitere Anteile zeichnen. Das geschieht in zwei Schritten:'),
  steps([
    'Auf der Mitgliedsseite in der Karte **Weitere Anteile** auf [[Weitere Anteile zeichnen]] klicken, Zahl der Anteile und Datum der Zulassung durch den Vorstand eintragen, [[Zeichnung speichern]].',
    'Wenn das Geld eingeht, auf dem Konto die Buchungsart **Weitere Anteile** wählen und buchen. Die Karte zeigt, wie viele Anteile noch nicht eingezahlt sind.',
  ]),
  p('Zeichnen kann nur, wer Mitglied und nicht gekündigt ist. Eine falsch erfasste Zeichnung lässt sich mit [[Zurücknehmen]] entfernen, solange sie nicht eingezahlt ist.'),
  h2('4.6 Umbuchung'),
  p('Mit einer Umbuchung überträgt ein Mitglied Anteile auf ein anderes Mitgliedskonto (§ 76 GenG), etwa auf Erben oder an Familienangehörige.'),
  steps([
    'Das Konto des **abgebenden** Mitglieds öffnen.',
    'Buchungsart **Umbuchung** wählen und unter **Auf Konto** die Nummer des empfangenden Kontos eintragen. Die App zeigt den Inhaber zur Kontrolle an.',
    'Wertstellung und Zahl der Anteile eintragen, [[Buchen]].',
  ]),
  bullets([
    '**Empfangen** können Mitglieder und zugelassene Antragsteller, die noch nicht eingezahlt haben. Beim Antragsteller zählt die Umbuchung wie seine Einzahlung; passen die Anteile, ist er Mitglied.',
    '**Werden alle Anteile übertragen**, scheidet der Abgebende am Tag der Umbuchung aus (ausgeschieden ab dem Folgetag). Laufende Kündigungen werden gegenstandslos.',
  ]),
  h2('4.7 Spende des Anteils'),
  p('Ein Mitglied kann ausscheiden, indem es sein ganzes Guthaben der Genossenschaft spendet, ohne Kündigungsfrist. Buchungsart **Spende Anteil** wählen; die App zeigt an, wie viele Anteile und welcher Saldo gespendet werden. Nach dem Buchen steht das Konto auf 0, und die Person ist ab dem Folgetag ausgeschieden. Es entsteht kein Anspruch.'),
  note('Ob eine Spende ohne Kündigungsfrist im Einzelfall zulässig ist, entscheidet der Vorstand. Die App bildet den Vorgang nur ab.', 'Achtung'),
  h2('4.8 Storno'),
  steps([
    'In der Buchungsliste bei der falschen Buchung auf [[Stornieren]] klicken.',
    'Den Grund eingeben (Pflicht) und bestätigen.',
    'Danach die richtige Buchung neu erfassen.',
  ]),
  p('Das Storno bucht die Gegenbuchung mit derselben Wertstellung wie das Original; beide bleiben sichtbar und sind als storniert markiert. Hängen an der Buchung weitere Folgen, zeigt die App eine gelbe Warnung, zum Beispiel wenn der Geldeingang dadurch wieder entfällt und die Person nicht mehr Mitglied ist, oder wenn nach dem Storno einer Spende oder Umbuchung das Ausscheiden zurückgenommen wird.'),
)

// 5 Ausscheiden
add(
  h1('5 Kündigung, Tod, Ausschluss und Ausscheiden'),
  h2('5.1 Kündigung der Mitgliedschaft'),
  steps([
    'Auf der Mitgliedsseite in der Karte **Kündigungen** auf [[Mitgliedschaft kündigen]] klicken.',
    'Das Datum des **Eingangs der Kündigung** eintragen. Die App schlägt das Jahr des Ausscheidens nach der Kündigungsfrist vor (zwei Jahre zum Jahresende).',
    'Das Jahr bei Bedarf ändern, etwa nach einer Vereinbarung mit dem Vorstand, und [[Kündigung speichern]].',
  ]),
  p('Der Status wird „gekündigt“. Bis zum 31.12. des Ausscheidensjahres bleibt die Person Mitglied, steht in allen Listen und ist stimmberechtigt.'),
  h2('5.2 Teilkündigung'),
  p('Mit [[Teilkündigung]] kündigt ein Mitglied nur einen Teil seiner Anteile (§ 67b GenG). Eingetragen werden Eingang, Ausscheidensjahr und die Zahl der gekündigten Anteile; mindestens ein Anteil muss bleiben. Die Person bleibt Mitglied und erhält den Hinweis „teilgekündigt“.'),
  p('Eine falsch erfasste oder vom Mitglied zurückgezogene Kündigung wird in der Tabelle mit [[Zurücknehmen]] entfernt. Gegenstandslos gewordene Kündigungen (z. B. nach einem Tod) bleiben stehen und sind entsprechend markiert.'),
  h2('5.3 Tod eines Mitglieds'),
  steps([
    'Auf der Mitgliedsseite auf [[Tod erfassen]] klicken, das Sterbedatum eintragen und [[Bestätigen]].',
    'Die App weist darauf hin, die **Adresszeilen auf die Erben umzustellen**, z. B. „An die Erben von …“ mit deren Anschrift. Mit [[Adresszeilen bearbeiten]] geht es direkt dorthin.',
  ]),
  p('Die Mitgliedschaft geht auf die Erben über und endet zum 31.12. des Todesjahres (§ 77 GenG). Die Briefanrede lautet ab jetzt „Sehr geehrte Damen und Herren“. Eine laufende Kündigung mit späterem Termin wird gegenstandslos.'),
  p('**Möchte ein Erbe Mitglied werden**, wird er als neue Person mit einem Antrag über die geerbten Anteile erfasst und zugelassen. Danach werden die Anteile vom Konto des Verstorbenen auf sein Konto umgebucht (siehe 4.6). Der Erbe ist damit Mitglied, der Verstorbene scheidet ohne Anspruch aus.'),
  p('**Möchte kein Erbe eintreten**, scheidet der Verstorbene zum 31.12. aus; der Anspruch steht den Erben zu und wird wie bei einer Kündigung ausgezahlt.'),
  p('Ein falsch erfasster Tod (falsches Mitglied oder Datum) wird mit [[Erfassung des Todes zurücknehmen]] korrigiert und gegebenenfalls neu erfasst.'),
  h2('5.4 Ausschluss'),
  p('Hat der Vorstand den Ausschluss beschlossen (Satzung 6.2 bis 6.4), auf [[Ausschließen]] klicken und das Datum des Beschlusses eintragen. Die Person scheidet zum 31.12. des Beschlussjahres aus und ist ab dem Beschluss nicht mehr stimmberechtigt.'),
  p('Das Mitglied kann binnen sechs Wochen beim Aufsichtsrat Widerspruch einlegen; die App überwacht diese Frist nicht. Gibt der Aufsichtsrat dem Widerspruch statt, wird der Ausschluss mit [[Ausschluss aufheben]] und dem Datum des Aufsichtsratsbeschlusses aufgehoben. Der Ausschluss gilt dann als nie geschehen.'),
  h2('5.5 Ausscheiden zum Jahresende buchen'),
  p('Kündigungen, Teilkündigungen, Todesfälle und Ausschlüsse werden zum 31.12. wirksam. Die gekündigten Anteile verlassen dann den Bestand, und es entsteht der Anspruch auf das Guthaben. Diese Ausscheidensbuchungen werden **einmal im Jahr nach dem 31.12.** gebucht, üblicherweise im Januar.'),
  steps([
    'Im Menü [[Jahresende]] wählen. Vorbelegt ist das Vorjahr.',
    'Die Liste prüfen: Nummer, Name, Grund (Kündigung, Teilkündigung, Tod, Ausschluss), Anteile, Anspruch und ob schon gebucht ist.',
    'Auf [[Ausscheiden buchen]] klicken. Alle offenen Ausscheiden des Jahres werden zusammen mit Wertstellung 31.12. gebucht.',
  ]),
  note('Für das laufende Jahr zeigt die Seite nur eine Vorschau; gebucht werden kann erst nach dem 31.12. Solange das Ausscheiden zum letzten 31.12. nicht gebucht ist, warnen die Reports, dass Anteile und Beträge zu hoch sein können.'),
  p('Die Ausscheidensbuchung bucht nur die Anteile aus; der Betrag bleibt als offener Anspruch auf dem Konto. Muss eine Ausscheidensbuchung korrigiert werden (z. B. weil ein Tod erst später bekannt wurde und ein Erbe die Anteile übernimmt), wird sie auf dem Konto storniert.'),
)

// 6 Auseinandersetzung
add(
  h1('6 Auseinandersetzung: Ansprüche auszahlen'),
  h2('6.1 Offene Ansprüche'),
  p('Im Menü [[Ansprüche]] stehen alle Konten mit gebuchtem Ausscheiden und offenem Anspruch, das älteste Ausscheiden zuerst, mit Summe. Ein Klick auf den Betrag öffnet das Konto.'),
  h2('6.2 Auszahlung'),
  steps([
    'Das Konto öffnen und die Buchungsart **Auszahlung** wählen.',
    'Wertstellung (Tag der Überweisung) und Betrag eintragen. Teilbeträge sind möglich, höchstens der offene Anspruch.',
    'Auf [[Buchen]] klicken. Die Überweisung selbst erfolgt wie bisher über die Bank.',
  ]),
  note('Ob ausgezahlt werden darf (Mindestkapital, Satzung 6.6), prüft die App nicht. Das stellt der Vorstand im Einzelfall fest. Eine Auszahlung ist erst nach der Ausscheidensbuchung möglich.'),
  h2('6.3 Kürzung Verlustvortrag'),
  p('Wird der Anspruch um anteilige Verluste gekürzt (Satzung 6.5), die Buchungsart **Kürzung Verlustvortrag** mit dem Kürzungsbetrag buchen.'),
  h2('6.4 Ausbuchung wegen Verjährung'),
  p('Ist ein Anspruch verjährt (Satzung 2.7), bucht **Ausbuchung Verjährung** den ganzen Rest an die Genossenschaft. Die Verjährung überwacht die App nicht; die Liste der offenen Ansprüche mit dem Ausscheidensdatum hilft, sie im Blick zu behalten.'),
  p('Sind Saldo und Anteile 0, ist die Auseinandersetzung abgeschlossen.'),
)

// 7 Reports
add(
  h1('7 Reports'),
  p('Im Menü [[Reports]] gibt es vier Listen als Excel-Datei. Ein Klick auf den Namen lädt die Datei herunter.'),
  h2('7.1 Listen zum Stichtag'),
  p('Die ersten drei Listen gelten für einen **Stichtag** (vorbelegt: heute). Es zählen die Buchungen mit Wertstellung bis zum Stichtag und der Status an diesem Tag.'),
  table(['Liste', 'Inhalt'], [
    ['Mitgliederliste nach GenG', 'Alle Mitglieder einschließlich Gekündigter, Verstorbener und Ausgeschlossener bis zu ihrem Ausscheiden: Nr., Name, Anschrift, Eintritt, Betrag und Anteile (§ 30 GenG). Nach Mitgliedsnummer.'],
    ['Liste zur Generalversammlung', 'Alle Stimmberechtigten nach Namen sortiert, mit Spalten für „Vertreten durch“ und die Unterschrift; zum Ausdrucken quer auf A4. Ausgeschlossene fehlen. Stichtag = Tag der Versammlung.'],
    ['Seriendruck-Liste', 'Dieselben Personen wie zur Generalversammlung, ohne „keine Post“, mit Adresszeilen und Briefanrede für die Einladung. Die Spaltennamen entsprechen dem Altsystem, damit die Word-Vorlagen weiter passen.'],
  ], [1.2, 3]),
  gap(),
  note('Ist das Ausscheiden zum letzten 31.12. noch nicht gebucht, erscheint auf der Seite ein gelber Hinweis; GenG-Liste und Liste zur Generalversammlung tragen ihn auch in Zeile 3. Dann zuerst unter [[Jahresende]] buchen.'),
  h2('7.2 Vorgänge eines Geschäftsjahres'),
  p('Unter **Auswertung eines Geschäftsjahres** das Jahr eintragen (vorbelegt: Vorjahr) und **Vorgänge im Geschäftsjahr** herunterladen. Die Liste enthält alle Vorgänge des Jahres in einer Tabelle, mit Filter in der Kopfzeile:'),
  bullets([
    'Kündigungen und Teilkündigungen (Datum des Eingangs), Todesfälle (Sterbedatum) und Ausschlüsse (Beschluss),',
    'alle Buchungen (Datum der Wertstellung) mit Gegenkonto und dessen Namen; eine Umbuchung steht in zwei Zeilen, je eine für beide Konten,',
    'Anteile und Betrag aus Sicht des Mitgliedskontos: Zugänge positiv, Abgänge negativ. Beim Ausscheiden zeigt die Liste den Wert der Anteile.',
  ]),
  p('Stornierte Buchungen und zurückgenommene Vorgänge fehlen. Summen enthält die Liste nicht; sie lassen sich in Excel mit dem Filter bilden.'),
)

// 8 Benutzer
add(
  h1('8 Benutzerverwaltung (Admin)'),
  p('Im Menü [[Benutzer]] sieht der Admin alle Benutzer mit Rolle und Status.'),
  bullets([
    '[[Neuer Benutzer]]: Benutzername, Name, Kennwort und Rolle eintragen, [[Anlegen]].',
    'Ein Klick auf den Benutzernamen öffnet ihn. Dort lassen sich der Name ändern ([[Name ändern]]), die Rolle wechseln ([[Rolle ändern]]) und ein neues Kennwort setzen ([[Kennwort setzen]]), etwa wenn jemand seines vergessen hat.',
    '[[Deaktivieren]] sperrt die Anmeldung, [[Reaktivieren]] hebt das wieder auf. [[Löschen]] entfernt den Benutzer endgültig.',
  ]),
  note('Für Personen, die nur vorübergehend nicht mitarbeiten, besser deaktivieren als löschen. Die Änderungen, die ein Benutzer gemacht hat, bleiben in jedem Fall mit seinem Namen gespeichert.'),
)

// 9 Abläufe
add(
  h1('9 Typische Abläufe im Überblick'),
  h2('9.1 Neues Mitglied'),
  steps([
    'Beitrittserklärung geht ein: [[Mitglieder]] > [[Neuer Antrag]] erfassen.',
    'Vorstand beschließt: auf der Mitgliedsseite [[Zulassen]] mit Beschlussdatum.',
    'Geld geht ein: auf dem Konto **Eintritt** mit Wertstellung = Geldeingang buchen.',
    'Status prüfen: „Mitglied“. Bei einer gelben Warnung den Betrag klären.',
  ]),
  h2('9.2 Kündigung bis Auszahlung'),
  steps([
    'Kündigung geht ein: [[Mitgliedschaft kündigen]] mit Eingangsdatum; Ausscheidensjahr prüfen.',
    'Im Januar nach dem Ausscheidensjahr: [[Jahresende]] > [[Ausscheiden buchen]].',
    'Nach Freigabe durch den Vorstand: [[Ansprüche]] > Konto öffnen > **Auszahlung** buchen.',
  ]),
  h2('9.3 Todesfall mit Erben, die eintreten'),
  steps([
    'Beim Verstorbenen [[Tod erfassen]] und die Adresszeilen auf die Erben umstellen.',
    'Den Erben als [[Neuer Antrag]] über die geerbten Anteile erfassen und [[Zulassen]].',
    'Auf dem Konto des Verstorbenen alle Anteile per **Umbuchung** auf das Konto des Erben übertragen.',
    'Prüfen: Der Erbe ist Mitglied, der Verstorbene ist ausgeschieden, sein Konto steht auf 0.',
  ]),
  h2('9.4 Jahresabschluss im Januar'),
  steps([
    '[[Jahresende]]: Ausscheiden zum 31.12. des Vorjahres buchen.',
    '[[Reports]]: Mitgliederliste nach GenG zum 31.12. herunterladen; die gelbe Warnung darf nicht mehr erscheinen.',
    '[[Reports]]: Vorgänge im Geschäftsjahr für das Vorjahr herunterladen und ablegen.',
    '[[Ansprüche]]: offene Ansprüche prüfen, Auszahlungen und Verjährungen vormerken.',
  ]),
  h2('9.5 Vor der Generalversammlung'),
  steps([
    '[[Reports]]: Seriendruck-Liste zum Tag der Versammlung für die Einladung herunterladen.',
    'Am Tag der Versammlung die Liste zur Generalversammlung mit diesem Stichtag ausdrucken.',
  ]),
)

// ---------- Titelseite und Dokument ----------

const title = [
  new Paragraph({ children: [], spacing: { before: 2400 } }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    children: [new ImageRun({ type: 'png', data: logo, transformation: { width: 420, height: Math.round(420 * LOGO_RATIO) }, altText: { title: 'Logo', description: 'Dorfladen Schlichten', name: 'Logo' } })],
  }),
  new Paragraph({ children: [], spacing: { after: 900 } }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 }, children: [new TextRun({ text: 'Mitgliederverwaltung', font: FONT, size: 56, bold: true, color: BROWN })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 600 }, children: [new TextRun({ text: 'Benutzerhandbuch', font: FONT, size: 40, color: GREEN })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: 'Unser Dorfladen Schlichten eG', font: FONT, size: 24 })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: 'Stand: November 2026', font: FONT, size: 22, color: '7A6E68' })] }),
  new Paragraph({ children: [new PageBreak()] }),
  new Paragraph({ children: [new TextRun({ text: 'Inhalt', font: FONT, size: 32, bold: true, color: BROWN })], spacing: { after: 200 } }),
  new TableOfContents('Inhalt', { hyperlink: true, headingStyleRange: '1-2' }),
]

const header = new Header({
  children: [new Paragraph({
    tabStops: [{ type: TabStopType.RIGHT, position: TABLE_WIDTH }],
    border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: GREEN, space: 4 } },
    children: [
      new ImageRun({ type: 'png', data: logo, transformation: { width: 130, height: Math.round(130 * LOGO_RATIO) }, altText: { title: 'Logo', description: 'Dorfladen Schlichten', name: 'Logo' } }),
      new TextRun({ text: '\tMitgliederverwaltung – Benutzerhandbuch', font: FONT, size: 16, color: BROWN }),
    ],
  })],
})
const footer = new Footer({
  children: [new Paragraph({
    alignment: AlignmentType.CENTER,
    children: [new TextRun({ children: ['Seite ', PageNumber.CURRENT, ' von ', PageNumber.TOTAL_PAGES], font: FONT, size: 16, color: '7A6E68' })],
  })],
})

const doc = new Document({
  creator: 'Unser Dorfladen Schlichten eG',
  title: 'Mitgliederverwaltung – Benutzerhandbuch',
  features: { updateFields: true },
  styles: {
    default: { document: { run: { font: FONT, size: 21 } } },
    paragraphStyles: [
      { id: 'Heading1', name: 'Heading 1', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { font: FONT, size: 34, bold: true, color: BROWN },
        paragraph: { spacing: { before: 0, after: 240 }, keepNext: true, outlineLevel: 0,
          border: { bottom: { style: BorderStyle.SINGLE, size: 12, color: GREEN, space: 4 } } } },
      { id: 'Heading2', name: 'Heading 2', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { font: FONT, size: 26, bold: true, color: BROWN },
        paragraph: { spacing: { before: 280, after: 120 }, keepNext: true, outlineLevel: 1 } },
      { id: 'Heading3', name: 'Heading 3', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { font: FONT, size: 22, bold: true, color: GREEN },
        paragraph: { spacing: { before: 200, after: 80 }, keepNext: true, outlineLevel: 2 } },
    ],
  },
  numbering: {
    config: [
      { reference: 'bullets', levels: [{ level: 0, format: LevelFormat.BULLET, text: '•', alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: 540, hanging: 270 } }, run: { color: GREEN } } }] },
      { reference: 'steps', levels: [{ level: 0, format: LevelFormat.DECIMAL, text: '%1.', alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: 540, hanging: 360 } }, run: { bold: true, color: BROWN } } }] },
    ],
  },
  sections: [
    { properties: { page: { margin: { top: 1440, bottom: 1440, left: 1440, right: 1440 } } }, children: title },
    { properties: { page: { margin: { top: 1700, bottom: 1440, left: 1440, right: 1440 } } }, headers: { default: header }, footers: { default: footer }, children: content },
  ],
})

Packer.toBuffer(doc).then((buf) => fs.writeFileSync(OUT, buf))
