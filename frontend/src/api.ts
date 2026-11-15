// Alle Aufrufe ans Backend laufen über api(). Sie kümmert sich um JSON, das CSRF-Token
// und um Fehlermeldungen, damit das nicht in jeder Komponente neu geschrieben werden muss.

type Method = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'

interface Options {
  method?: Method
  body?: unknown
}

// Ein Fehler vom Backend: HTTP-Status und die deutsche Meldung aus {"detail": "..."}.
export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

// Kommt beim Login bzw. von /api/me und muss bei jeder schreibenden Anfrage mit.
let csrfToken = ''
// Wird aufgerufen, wenn das Backend 401 meldet, z. B. weil die Session abgelaufen ist.
let unauthorizedHandler: () => void = () => {}

export function setCsrfToken(token: string): void {
  csrfToken = token
}

export function onUnauthorized(handler: () => void): void {
  unauthorizedHandler = handler
}

// <T> ist ein Typparameter: Der Aufrufer sagt, welche Form die Antwort hat, z. B. api<Me>(...).
export async function api<T>(path: string, options: Options = {}): Promise<T> {
  const method = options.method ?? 'GET'
  const headers: Record<string, string> = {}
  if (options.body !== undefined) {
    headers['Content-Type'] = 'application/json'
  }
  if (method !== 'GET') {
    headers['X-CSRF-Token'] = csrfToken
  }

  const response = await fetch(path, {
    method,
    headers,
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
  })

  if (!response.ok) {
    const message = await errorMessage(response)
    if (response.status === 401) {
      unauthorizedHandler()
    }
    throw new ApiError(response.status, message)
  }
  if (response.status === 204) {
    return undefined as T // 204 No Content: Es gibt keinen Inhalt zum Lesen.
  }
  return (await response.json()) as T
}

async function errorMessage(response: Response): Promise<string> {
  if (response.status === 422) {
    return 'Die Eingaben sind unvollständig oder ungültig.'
  }
  try {
    const body: unknown = await response.json()
    if (typeof body === 'object' && body !== null && 'detail' in body && typeof body.detail === 'string') {
      return body.detail
    }
  } catch {
    // keine JSON-Antwort, z. B. vom Proxy, wenn das Backend nicht läuft
  }
  return `Der Server meldet einen Fehler (${response.status}).`
}
