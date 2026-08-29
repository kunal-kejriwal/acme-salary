/**
 * Typed access to the ACME Salary API.
 *
 * Every network call in the app goes through here, so auth handling, error
 * shape and the base URL stay in one place (CLAUDE.md: "keep API access in a
 * typed client module").
 */

export const API_BASE_URL: string =
  import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1'

export class ApiError extends Error {
  // Written out longhand rather than as constructor parameter properties,
  // which the tsconfig's erasableSyntaxOnly disallows.
  readonly status: number
  readonly body?: unknown

  constructor(status: number, message: string, body?: unknown) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.body = body
  }
}

export async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    // Session auth: the sessionid cookie has to ride along.
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...init.headers },
    ...init,
  })

  if (!response.ok) {
    const body = await response.json().catch(() => undefined)
    throw new ApiError(response.status, `${response.status} ${response.statusText}`, body)
  }

  return response.status === 204 ? (undefined as T) : ((await response.json()) as T)
}
