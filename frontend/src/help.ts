// Benutzerhandbuch vom Backend (handbook/api.py): nur nach Anmeldung, für jede Rolle.

import { api } from './api'

// Muss zu Handbook im Backend passen.
interface Handbook {
  html: string
}

export async function getHandbook(): Promise<string> {
  return (await api<Handbook>('/api/help')).html
}
