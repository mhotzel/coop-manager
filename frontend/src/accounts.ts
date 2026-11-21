// Konten und Buchungen im Backend (accounts/api.py). Beträge kommen immer als ganze Cent.

import { api } from './api'

// Das Konto der Genossenschaft hat immer diese Nummer (accounts/domain.py).
export const COOPERATIVE_ACCOUNT_NUMBER = 9999

// Muss zu Booking im Backend passen (accounts/domain.py).
export interface Booking {
  id: string
  kind: string // eine der Buchungsarten, siehe BOOKING_KIND_LABELS
  debit: number // Kontonummer Soll
  credit: number // Kontonummer Haben
  amount: number // Betrag in Cent, immer positiv
  shares: number
  text: string
  booking_date: string // Tag, an dem gebucht wurde
  value_date: string // Tag, an dem die Buchung fachlich gilt
  reverses: string | null // nur beim Storno: die ID der stornierten Buchung
}

// Muss zu AccountView im Backend passen (accounts/schemas.py).
export interface AccountView {
  number: number
  kind: string // 'member_account' oder 'cooperative_account'
  member_id: string | null // Inhaber; beim Genossenschaftskonto null
  // Berechnet, nicht gespeichert:
  balance: number // Saldo in Cent, Haben positiv
  shares: number
  share_price: number | null // aktueller Anteilspreis in Cent; null, solange keiner gesetzt ist
  claim: number // offener Auseinandersetzungsanspruch in Cent: Saldo minus Anteile × Preis
  bookings: Booking[] // die älteste zuerst
}

// Die Texte wie im Plan (Buchungsarten).
const BOOKING_KIND_LABELS: Record<string, string> = {
  subscription: 'Eintritt',
  refund: 'Rückzahlung',
  transfer: 'Umbuchung',
  exit: 'Ausscheiden',
  loss_deduction: 'Kürzung Verlustvortrag',
  payout: 'Auszahlung',
  limitation_writeoff: 'Ausbuchung Verjährung',
  share_donation: 'Spende Anteil',
  additional_shares: 'Weitere Anteile',
  reversal: 'Storno',
}

export function bookingKindLabel(kind: string): string {
  return BOOKING_KIND_LABELS[kind] ?? kind
}

// 10000 → "100,00 €", -150 → "-1,50 €". Wie format_euro im Backend (core/money.py): mit ganzen
// Cent gerechnet, ohne Kommazahlen, damit nie ein Rundungsfehler entsteht.
export function formatEuro(cents: number): string {
  const sign = cents < 0 ? '-' : ''
  const absolute = Math.abs(cents)
  const euros = Math.floor(absolute / 100)
  const rest = String(absolute % 100).padStart(2, '0')
  return `${sign}${euros},${rest} €`
}

// Die Buchung aus Sicht eines Kontos: Haben zählt positiv, Soll negativ (wie balance() im Backend).
export function signedFor(accountNumber: number, booking: Booking): { amount: number; shares: number } {
  const sign = booking.credit === accountNumber ? 1 : -1
  return { amount: sign * booking.amount, shares: sign * booking.shares }
}

// Das andere Konto der Buchung, aus Sicht von accountNumber.
export function counterAccount(accountNumber: number, booking: Booking): number {
  return booking.credit === accountNumber ? booking.debit : booking.credit
}

export function getAccount(accountNumber: number): Promise<AccountView> {
  return api<AccountView>(`/api/accounts/${accountNumber}`)
}

// --- Buchungsmaske ---

// Muss zu ShareBooking im Backend passen (accounts/schemas.py). Einen Betrag gibt es hier bewusst
// nicht: Der Server rechnet ihn selbst aus (Anteile × aktueller Anteilspreis).
export interface ShareBooking {
  account_number: number
  shares: number
  value_date: string // JJJJ-MM-TT
  text: string | null // null = Standardtext „Eintritt“ bzw. „Rückzahlung“
}

// Muss zu BookingResponse im Backend passen: das Konto nach der Buchung und ggf. eine Warnung.
// Die Buchung gilt auch mit Warnung; die Warnung ist ein Hinweis für die Buchhaltung.
export interface BookingResponse {
  account: AccountView
  warning: string | null
}

export function subscribe(command: ShareBooking): Promise<BookingResponse> {
  return api<BookingResponse>('/api/accounts/subscribe', { method: 'POST', body: command })
}

// Einzahlung später gezeichneter Anteile; gleicher Befehl wie beim Eintritt.
export function payAdditionalShares(command: ShareBooking): Promise<BookingResponse> {
  return api<BookingResponse>('/api/accounts/pay-additional-shares', { method: 'POST', body: command })
}

export function refund(command: ShareBooking): Promise<BookingResponse> {
  return api<BookingResponse>('/api/accounts/refund', { method: 'POST', body: command })
}

// --- Storno ---

// Muss zu ReverseBooking im Backend passen. Das Konto ergibt sich aus der Buchung, der Grund ist
// Pflicht und landet im Buchungstext. Die Antwort enthält immer das Mitgliedskonto.
export interface ReverseBooking {
  booking_id: string
  reason: string
}

export function reverse(command: ReverseBooking): Promise<BookingResponse> {
  return api<BookingResponse>('/api/accounts/reverse', { method: 'POST', body: command })
}

// --- Buchungen, die den Anspruch mindern (Auszahlung, Verlustvortrag, Verjährung) ---

// Muss zu ClaimBooking im Backend passen: Betrag frei, höchstens der offene Anspruch, ohne Anteile.
export interface ClaimBooking {
  account_number: number
  amount: number // in Cent
  value_date: string
  text: string | null // null = Standardtext
}

export function payout(command: ClaimBooking): Promise<BookingResponse> {
  return api<BookingResponse>('/api/accounts/payout', { method: 'POST', body: command })
}

export function deductLoss(command: ClaimBooking): Promise<BookingResponse> {
  return api<BookingResponse>('/api/accounts/deduct-loss', { method: 'POST', body: command })
}

// Immer der ganze Rest; deshalb ohne Betrag.
export function writeOff(command: Omit<ClaimBooking, 'amount'>): Promise<BookingResponse> {
  return api<BookingResponse>('/api/accounts/write-off', { method: 'POST', body: command })
}

// --- Umbuchung auf ein anderes Mitgliedskonto ---

// Muss zu ShareTransfer im Backend passen. Den Betrag rechnet der Server (Anteile × Preis).
export interface ShareTransfer {
  account_number: number // abgebendes Konto
  target_account_number: number // empfangendes Konto
  shares: number
  value_date: string
  text: string | null // null = Standardtext „Umbuchung“
}

// Antwortet mit dem abgebenden Konto.
export function transfer(command: ShareTransfer): Promise<BookingResponse> {
  return api<BookingResponse>('/api/accounts/transfer', { method: 'POST', body: command })
}

// --- Ausscheiden mit Spende des Anteils ---

// Muss zu ShareDonation im Backend passen. Ohne Anteile und Betrag: gespendet wird immer das ganze
// Guthaben (alle Anteile, ganzer Saldo) an das Genossenschaftskonto. Die Person scheidet damit aus.
export interface ShareDonation {
  account_number: number
  value_date: string // Tag der Spende, zugleich Ausscheiden
  text: string | null // null = Standardtext „Spende Anteil“
}

export function donate(command: ShareDonation): Promise<BookingResponse> {
  return api<BookingResponse>('/api/accounts/donate', { method: 'POST', body: command })
}

// Eingabe im Betragsfeld → ganze Cent, oder null, wenn die Eingabe kein Betrag ist.
// Deutsche Schreibweise: Komma trennt die Cent ab, Punkte trennen Tausender.
// Erlaubt: "1500", "1.500", "1.500,00", "150,5", auch mit Leerzeichen und €-Zeichen.
// Tausenderpunkte müssen richtig stehen (immer drei Ziffern danach); "150.50" ist also ungültig
// und wird nicht stillschweigend zu 15.050 €.
export function parseEuro(text: string): number | null {
  const cleaned = text.replace('€', '').trim()
  // ^ und $: der ganze Text muss passen. Euro entweder mit Tausenderpunkten (1–3 Ziffern, dann
  // Gruppen aus Punkt und drei Ziffern) oder ohne Punkte; danach optional Komma und 1–2 Ziffern Cent.
  const match = /^(\d{1,3}(?:\.\d{3})+|\d+)(?:,(\d{1,2}))?$/.exec(cleaned)
  if (match === null) {
    return null
  }
  const euros = Number((match[1] ?? '').replaceAll('.', ''))
  // padEnd: "5" heißt 50 Cent, nicht 5 Cent.
  const cents = Number((match[2] ?? '0').padEnd(2, '0'))
  return euros * 100 + cents
}

// Wie viele Anteile ergibt ein Betrag? null, wenn er nicht glatt im Anteilspreis aufgeht.
export function sharesForAmount(cents: number, sharePrice: number): number | null {
  if (sharePrice <= 0 || cents % sharePrice !== 0) {
    return null
  }
  return cents / sharePrice
}

// --- Ausscheiden zum Jahresende ---

// Muss zu ExitEntry im Backend passen (accounts/exits.py): ein Konto, das zum 31.12. Anteile abgibt.
export interface ExitEntry {
  member_id: string
  member_number: number
  account_number: number
  name: string
  reasons: string[] // siehe EXIT_REASON_LABELS
  full: boolean // alle Anteile, die Mitgliedschaft endet
  shares: number
  balance: number // Saldo in Cent: der Auseinandersetzungsanspruch
  booked: boolean
}

// Die Gründe aus members/domain.py (NOTICE, PARTIAL_NOTICE, EXIT_REASON_…).
const EXIT_REASON_LABELS: Record<string, string> = {
  notice: 'Kündigung',
  partial_notice: 'Teilkündigung',
  deceased: 'Tod',
  expelled: 'Ausschluss',
}

export function exitReasonsLabel(reasons: string[]): string {
  return reasons.map((reason) => EXIT_REASON_LABELS[reason] ?? reason).join(', ')
}

// Wie im Backend (YEAR_MIN, YEAR_MAX in accounts/schemas.py).
export const YEAR_MIN = 1900
export const YEAR_MAX = 2200

export function getExits(year: number): Promise<ExitEntry[]> {
  return api<ExitEntry[]>(`/api/accounts/exits/${year}`)
}

export function postExits(year: number): Promise<ExitEntry[]> {
  return api<ExitEntry[]>('/api/accounts/post-exits', { method: 'POST', body: { year } })
}

// --- Offene Ansprüche ---

// Muss zu ClaimEntry im Backend passen (accounts/claims.py).
export interface ClaimEntry {
  member_id: string
  member_number: number
  account_number: number
  name: string
  status: string | null
  exit_date: string // letztes gebuchtes Ausscheiden
  claim: number // offener Anspruch in Cent
}

export function getClaims(): Promise<ClaimEntry[]> {
  return api<ClaimEntry[]>('/api/accounts/claims')
}

// --- Saldenliste ---

// Muss zu BalanceEntry im Backend passen (accounts/balances.py). Beträge in Cent.
export interface BalanceEntry {
  member_id: string
  member_number: number
  account_number: number
  name: string
  status: string | null // zum Stichtag
  shares: number
  balance: number // Saldo: das ganze Guthaben gegenüber der Genossenschaft
  share_capital: number // davon Geschäftsguthaben: Anteile × Anteilspreis
  claim: number // davon Auseinandersetzungsanspruch: Saldo − Geschäftsguthaben
  exit_not_booked: boolean // ausgeschieden, aber noch Anteile: auf der Seite „Jahresende“ buchen
}

// Muss zu BalanceList im Backend passen; die Summen gehen über alle Konten.
export interface BalanceList {
  day: string
  entries: BalanceEntry[]
  total_shares: number
  total_balance: number
  total_share_capital: number
  total_claim: number
  cooperative_balance: number // Saldo des Genossenschaftskontos, normalerweise −total_balance
  balanced: boolean
}

// URLSearchParams setzt die Abfrage zusammen und kodiert die Werte richtig, z. B. „?day=…&include_zero=true“.
export function getBalances(day: string, includeZero: boolean): Promise<BalanceList> {
  const query = new URLSearchParams({ day, include_zero: String(includeZero) })
  return api<BalanceList>(`/api/accounts/balances?${query}`)
}
