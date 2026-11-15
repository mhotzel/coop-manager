// Wer ist angemeldet? Ein einfaches Modul mit reaktivem Zustand, das sich alle Komponenten teilen.

import { ref } from 'vue'

import { api, ApiError, setCsrfToken } from './api'

// Die Rollen wie im Backend (users/domain.py).
export const ADMIN = 'admin'
export const ACCOUNTING = 'accounting'
export const ACCOUNTING_READONLY = 'accounting_readonly'

// Muss zu UserOut im Backend passen (users/schemas.py).
export interface User {
  id: string
  username: string
  full_name: string
  role: string
  active: boolean
}

// Muss zu Me im Backend passen.
interface Me {
  user: User
  csrf_token: string
}

// null heißt: niemand angemeldet. Ändert sich der Wert, zeichnet Vue alles neu, was ihn anzeigt.
export const currentUser = ref<User | null>(null)

function remember(me: Me | null): void {
  currentUser.value = me?.user ?? null
  setCsrfToken(me?.csrf_token ?? '')
}

// Beim Start: Gibt es noch eine gültige Session (Cookie)?
export async function loadMe(): Promise<void> {
  try {
    remember(await api<Me>('/api/me'))
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      remember(null)
    } else {
      throw error
    }
  }
}

export async function login(username: string, password: string): Promise<void> {
  remember(await api<Me>('/api/login', { method: 'POST', body: { username, password } }))
}

export async function logout(): Promise<void> {
  try {
    await api<void>('/api/logout', { method: 'POST' })
  } finally {
    remember(null) // auch wenn der Server nicht antwortet: hier im Browser abgemeldet
  }
}

// Eigenes Kennwort ändern; die Anmeldung bleibt bestehen.
export async function changeOwnPassword(currentPassword: string, newPassword: string): Promise<void> {
  await api<void>('/api/me/change-password', {
    method: 'POST',
    body: { current_password: currentPassword, new_password: newPassword },
  })
}

// Zum Anfang zurücksetzen, wenn das Backend die Session nicht mehr kennt (401).
export function forget(): void {
  remember(null)
}
