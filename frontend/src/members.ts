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
}

// Die Texte zu den Status wie in members/status.py. Schritt 5 bringt weitere dazu.
const STATUS_LABELS: Record<string, string> = {
  applicant: 'Antragsteller',
  rejected: 'abgelehnt',
}

export function statusLabel(status: string | null): string {
  if (status === null) {
    return '–'
  }
  return STATUS_LABELS[status] ?? status // unbekannter Status: lieber roh anzeigen als nichts
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
