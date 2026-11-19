// Reports: Die Listen selbst lädt der Browser über Links herunter (siehe ReportsView.vue).
// Hier nur, was als JSON kommt.

import { api } from './api'

// Hinweise zum Stichtag, z. B. ein noch nicht gebuchtes Ausscheiden; leer, wenn alles passt.
export function getReportWarnings(referenceDate: string): Promise<string[]> {
  return api<string[]>(`/api/reports/warnings?reference_date=${referenceDate}`)
}
