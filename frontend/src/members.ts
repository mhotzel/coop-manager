// Die Mitgliederverwaltung im Backend (members/api.py): Abfragen und Befehle.

import { ref } from 'vue'

import { api } from './api'

// Muss zu MemberRow im Backend passen (members/projections.py).
export interface MemberRow {
  id: string
  member_number: number
  person_type: string
  list_name: string
  street: string
  postal_code: string
  city: string
  status: string | null // null: Das Antragsdatum liegt in der Zukunft.
  partial_notice: boolean // heute läuft eine Teilkündigung
}

// Muss zu PersonName, Address und Contact im Backend passen (members/values.py).
export interface PersonName {
  company_name: string
  title: string
  first_names: string
  last_name: string
  gender: string
}

export interface Address {
  street: string
  house_number: string
  postal_code: string
  city: string
  country: string // leer = Deutschland
}

export interface Contact {
  phone: string
  email: string
}

// Muss zu Notice im Backend passen (members/domain.py).
export interface Notice {
  id: string
  kind: string // NOTICE oder PARTIAL_NOTICE
  notice_date: string // Eingang der Kündigung
  exit_date: string // Ausscheiden zum 31.12.
  shares: number | null // nur bei der Teilkündigung
}

export const NOTICE = 'notice' // Kündigung der Mitgliedschaft: alle Anteile
export const PARTIAL_NOTICE = 'partial_notice' // Teilkündigung einzelner Anteile

// Muss zu MemberDetail im Backend passen (members/schemas.py). Datumsangaben kommen als Text
// im Format "2026-11-02" (ISO 8601) und gehen auch so zurück.
export interface MemberDetail {
  id: string
  member_number: number
  person_type: string
  name: PersonName
  address: Address
  contact: Contact
  address_lines: string[]
  salutation_override: string // abweichende Briefanrede, leer = erzeugt
  no_mail: boolean
  notes: string
  application_date: string
  shares_subscribed: number
  admission_date: string | null
  rejection_date: string | null // Ablehnung oder Rücknahme
  withdrawn: boolean // true: Rücknahme durch die Person
  payment_date: string | null // Geldeingang: gezeichnete Anteile voll eingezahlt
  // Berechnet, nicht gespeichert:
  status: string | null
  entry_date: string | null // das spätere von Zulassung und Geldeingang
  notices: Notice[] // laufende Kündigungen und Teilkündigungen
  notice_date: string | null // Eingang der Kündigung der Mitgliedschaft
  exit_date: string | null // Ausscheiden aus der Kündigung der Mitgliedschaft
  partial_notice: boolean // heute läuft eine Teilkündigung
  salutation: string
  generated_address_lines: string[]
  warnings: string[]
}

export const NATURAL_PERSON = 'natural_person'
export const LEGAL_ENTITY = 'legal_entity'

// Die Texte wie in members/values.py.
export const PERSON_TYPE_LABELS: Record<string, string> = {
  natural_person: 'natürliche Person',
  legal_entity: 'juristische Person',
}

// Die Reihenfolge ist auch die der Auswahlliste im Formular.
export const GENDER_LABELS: Record<string, string> = {
  '': 'keine Angabe',
  w: 'weiblich',
  m: 'männlich',
  d: 'divers',
}

export function personTypeLabel(personType: string): string {
  return PERSON_TYPE_LABELS[personType] ?? personType
}

export function genderLabel(gender: string): string {
  return GENDER_LABELS[gender] ?? gender
}

// Die Texte zu den Status wie in members/status.py. Schritt 5 bringt weitere dazu.
const STATUS_LABELS: Record<string, string> = {
  applicant: 'Antragsteller',
  member: 'Mitglied',
  rejected: 'abgelehnt',
  notice_given: 'gekündigt',
  exited: 'ausgeschieden',
}

export function statusLabel(status: string | null): string {
  if (status === null) {
    return '–'
  }
  return STATUS_LABELS[status] ?? status // unbekannter Status: lieber roh anzeigen als nichts
}

// Farbe des Status-Tags: grün für Mitglieder, orange für abgelehnt und gekündigt, sonst blau.
export function statusTagClass(status: string): string {
  if (status === 'member') {
    return 'success'
  }
  return status === 'rejected' || status === 'notice_given' ? 'warning' : 'info'
}

// Hinweis „teilgekündigt“ neben dem Status. Nur bei Mitgliedern: Ist die Mitgliedschaft schon
// gekündigt, sagt der Status genug.
export function showPartialNotice(status: string | null, partialNotice: boolean): boolean {
  return partialNotice && status === 'member'
}

// "2026-11-02" → "02.11.2026". Bewusst ohne new Date(): Das liest den Text als Mitternacht in
// UTC, und je nach Zeitzone des Browsers käme dann der Vortag heraus.
export function formatDate(isoDate: string | null): string {
  if (isoDate === null) {
    return '–'
  }
  const [year, month, day] = isoDate.split('-')
  return `${day}.${month}.${year}`
}

// Das heutige Datum als "2026-11-16" in der Zeitzone des Browsers. toISOString() ginge nicht:
// Es rechnet in UTC, kurz nach Mitternacht wäre das noch gestern.
export function todayIso(): string {
  const now = new Date()
  const month = String(now.getMonth() + 1).padStart(2, '0') // getMonth zählt ab 0
  const day = String(now.getDate()).padStart(2, '0')
  return `${now.getFullYear()}-${month}-${day}`
}

// Der letzte Suchbegriff. Er steht hier im Modul und nicht in der Komponente, damit er erhalten
// bleibt, wenn man die Suchseite verlässt und zurückkommt. In die Adresse (?q=…) gehört er nicht:
// Beim Neuladen ginge die Adresse an den Server und der Name stünde im Access-Log.
export const lastQuery = ref('')

// Das Backend liefert höchstens so viele Treffer (search_members in members/projections.py).
export const SEARCH_LIMIT = 50

// POST statt GET, damit die Suchbegriffe nicht im Access-Log stehen.
export function searchMembers(query: string): Promise<MemberRow[]> {
  return api<MemberRow[]>('/api/members/search', { method: 'POST', body: { query } })
}

export function getMember(memberId: string): Promise<MemberDetail> {
  // encodeURIComponent, damit Sonderzeichen in der ID den Pfad nicht verändern können.
  return api<MemberDetail>(`/api/members/${encodeURIComponent(memberId)}`)
}

// Befehle: Jeder antwortet mit der neuen Detailansicht.

export function admit(memberId: string, decisionDate: string): Promise<MemberDetail> {
  return api<MemberDetail>('/api/members/admit', {
    method: 'POST',
    body: { member_id: memberId, decision_date: decisionDate },
  })
}

export function reject(memberId: string, decisionDate: string): Promise<MemberDetail> {
  return api<MemberDetail>('/api/members/reject', {
    method: 'POST',
    body: { member_id: memberId, decision_date: decisionDate },
  })
}

export function withdraw(memberId: string, withdrawalDate: string): Promise<MemberDetail> {
  return api<MemberDetail>('/api/members/withdraw', {
    method: 'POST',
    body: { member_id: memberId, withdrawal_date: withdrawalDate },
  })
}

// --- Kündigung ---

// Ausscheiden nach der Frist: 31.12. des übernächsten Jahres (wie default_exit_date im Backend).
// Nur der Vorschlag im Formular; ohne Angabe rechnet das Backend genauso.
export function defaultExitYear(noticeDate: string): number {
  return Number(noticeDate.slice(0, 4)) + 2
}

export function giveNotice(memberId: string, noticeDate: string, exitDate: string): Promise<MemberDetail> {
  return api<MemberDetail>('/api/members/give-notice', {
    method: 'POST',
    body: { member_id: memberId, notice_date: noticeDate, exit_date: exitDate },
  })
}

export function givePartialNotice(
  memberId: string,
  shares: number,
  noticeDate: string,
  exitDate: string,
): Promise<MemberDetail> {
  return api<MemberDetail>('/api/members/give-partial-notice', {
    method: 'POST',
    body: { member_id: memberId, shares, notice_date: noticeDate, exit_date: exitDate },
  })
}

export function withdrawNotice(memberId: string, noticeId: string): Promise<MemberDetail> {
  return api<MemberDetail>('/api/members/withdraw-notice', {
    method: 'POST',
    body: { member_id: memberId, notice_id: noticeId },
  })
}

export function applyForMembership(application: {
  person_type: string
  name: PersonName
  address: Address
  contact: Contact
  application_date: string
  shares_subscribed: number
}): Promise<MemberDetail> {
  return api<MemberDetail>('/api/members/apply', { method: 'POST', body: application })
}

export function changeName(memberId: string, name: PersonName): Promise<MemberDetail> {
  return api<MemberDetail>('/api/members/change-name', { method: 'POST', body: { member_id: memberId, name } })
}

export function changeAddress(memberId: string, address: Address): Promise<MemberDetail> {
  return api<MemberDetail>('/api/members/change-address', { method: 'POST', body: { member_id: memberId, address } })
}

export function changeContact(memberId: string, contact: Contact): Promise<MemberDetail> {
  return api<MemberDetail>('/api/members/change-contact', { method: 'POST', body: { member_id: memberId, contact } })
}

export function changeAddressLines(memberId: string, addressLines: string[]): Promise<MemberDetail> {
  return api<MemberDetail>('/api/members/change-address-lines', {
    method: 'POST',
    body: { member_id: memberId, address_lines: addressLines },
  })
}

export function changeSalutation(memberId: string, salutation: string): Promise<MemberDetail> {
  return api<MemberDetail>('/api/members/change-salutation', {
    method: 'POST',
    body: { member_id: memberId, salutation },
  })
}

export function changeMailPreference(memberId: string, noMail: boolean): Promise<MemberDetail> {
  return api<MemberDetail>('/api/members/change-mail-preference', {
    method: 'POST',
    body: { member_id: memberId, no_mail: noMail },
  })
}

export function changeNotes(memberId: string, notes: string): Promise<MemberDetail> {
  return api<MemberDetail>('/api/members/change-notes', { method: 'POST', body: { member_id: memberId, notes } })
}
