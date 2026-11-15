// Die Benutzerverwaltung im Backend (users/api.py): Abfragen per GET, Befehle per POST.

import { api } from './api'
import type { User } from './auth'

export interface Role {
  value: string
  label: string
}

export function listUsers(): Promise<User[]> {
  return api<User[]>('/api/users')
}

export function getUser(userId: string): Promise<User> {
  // encodeURIComponent, damit Sonderzeichen in der ID den Pfad nicht verändern können.
  return api<User>(`/api/users/${encodeURIComponent(userId)}`)
}

export function listRoles(): Promise<Role[]> {
  return api<Role[]>('/api/users/roles')
}

export function registerUser(username: string, fullName: string, password: string, role: string): Promise<User> {
  return api<User>('/api/users/register', {
    method: 'POST',
    body: { username, full_name: fullName, password, role },
  })
}

export function changeFullName(userId: string, fullName: string): Promise<User> {
  return api<User>('/api/users/change-full-name', { method: 'POST', body: { user_id: userId, full_name: fullName } })
}

export function changeRole(userId: string, role: string): Promise<User> {
  return api<User>('/api/users/change-role', { method: 'POST', body: { user_id: userId, role } })
}

export function changePassword(userId: string, password: string): Promise<User> {
  return api<User>('/api/users/change-password', { method: 'POST', body: { user_id: userId, password } })
}

export function deactivate(userId: string): Promise<User> {
  return api<User>('/api/users/deactivate', { method: 'POST', body: { user_id: userId } })
}

export function reactivate(userId: string): Promise<User> {
  return api<User>('/api/users/reactivate', { method: 'POST', body: { user_id: userId } })
}

export function terminate(userId: string): Promise<void> {
  return api<void>('/api/users/terminate', { method: 'POST', body: { user_id: userId } })
}

// Deutscher Name einer Rolle; unbekannte Werte bleiben, wie sie sind.
export function roleLabel(roles: Role[], value: string): string {
  return roles.find((role) => role.value === value)?.label ?? value
}
