/**
 * Typed access to the ACME Salary API.
 *
 * Every network call goes through here, so auth, CSRF and error shape stay in
 * one place and the components stay dumb.
 */

// Relative by default: the API is served from the same origin as the app,
// via a proxy rewrite in vercel.json and the matching dev-server proxy in
// vite.config.ts. Same-origin is what makes the session and CSRF cookies
// first-party -- readable by JavaScript, unaffected by third-party cookie
// blocking, and safe under the default SameSite=Lax.
export const API_BASE_URL: string =
  import.meta.env.VITE_API_BASE_URL ?? '/api/v1'

/** DRF's page-number pagination envelope. */
export interface Page<T> {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}

export class ApiError extends Error {
  readonly status: number
  /** DRF's `{field: [messages]}` body, when it sent one. */
  readonly body?: Record<string, unknown>

  constructor(status: number, message: string, body?: Record<string, unknown>) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.body = body
  }

  /** The message worth putting in front of a person. */
  get detail(): string {
    const detail = this.body?.detail
    if (typeof detail === 'string') return detail
    const first = this.body && Object.values(this.body)[0]
    if (Array.isArray(first) && typeof first[0] === 'string') return first[0]
    return this.message
  }

  /** Per-field errors, flattened for Ant Design's form API. */
  get fieldErrors(): Record<string, string> {
    const errors: Record<string, string> = {}
    for (const [field, messages] of Object.entries(this.body ?? {})) {
      if (field === 'detail') continue
      if (Array.isArray(messages) && typeof messages[0] === 'string') {
        errors[field] = messages[0]
      } else if (typeof messages === 'string') {
        errors[field] = messages
      }
    }
    return errors
  }
}

const UNSAFE_METHODS = new Set(['POST', 'PUT', 'PATCH', 'DELETE'])

/**
 * Read Django's CSRF token out of the cookie.
 *
 * Django sets `csrftoken` un-HttpOnly precisely so a SPA can echo it back in
 * a header. The app calls `GET /auth/me` on load, which is decorated with
 * `ensure_csrf_cookie`, so the token exists before the first POST — including
 * the login POST, which is otherwise the one request with no prior GET.
 *
 * This only works same-origin. `document.cookie` exposes cookies for the
 * current document's domain and nothing else, so serving the SPA and the API
 * from different domains makes the token unreadable and every write fails
 * with "CSRF token missing". The proxy in vercel.json is what keeps this
 * function viable.
 */
export function getCsrfToken(): string | null {
  const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]*)/)
  return match ? decodeURIComponent(match[1]) : null
}

export async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const method = (init.method ?? 'GET').toUpperCase()
  const headers = new Headers(init.headers)

  if (init.body !== undefined && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }
  if (UNSAFE_METHODS.has(method)) {
    const token = getCsrfToken()
    if (token) headers.set('X-CSRFToken', token)
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    // The session cookie has to ride along, including cross-origin.
    credentials: 'include',
    ...init,
    method,
    headers,
  })

  if (!response.ok) {
    const body = await response.json().catch(() => undefined)
    throw new ApiError(
      response.status,
      `${response.status} ${response.statusText}`,
      body as Record<string, unknown> | undefined,
    )
  }

  return response.status === 204 ? (undefined as T) : ((await response.json()) as T)
}

/** Build a query string, dropping empty values so the URL stays readable. */
export function queryString(params: Record<string, unknown>): string {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === '') continue
    search.set(key, String(value))
  }
  const encoded = search.toString()
  return encoded ? `?${encoded}` : ''
}
