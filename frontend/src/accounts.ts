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
