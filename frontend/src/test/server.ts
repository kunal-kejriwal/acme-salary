/**
 * MSW handlers standing in for the API.
 *
 * Deliberately shaped like the real responses — DRF's {count, results}
 * envelope and money as strings — so the tests exercise the same adapter code
 * the browser runs.
 */

import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'

import type { Employee, SalaryChange } from '../api/types'

const BASE = 'http://localhost:8000/api/v1'

export const ASHA: Employee = {
  id: 'aaaaaaaa-0000-4000-8000-000000000001',
  employee_code: 'ACME-00001',
  first_name: 'Asha',
  last_name: 'Rao',
  department: 'Engineering',
  job_title: 'Senior Engineer',
  country: 'IN',
  joined_on: '2021-04-01',
  salary_amount: '2400000.00',
  currency: 'INR',
  salary_usd: '28800.00',
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
}

export const MARCO: Employee = {
  ...ASHA,
  id: 'aaaaaaaa-0000-4000-8000-000000000002',
  employee_code: 'ACME-00002',
  first_name: 'Marco',
  last_name: 'Bianchi',
  department: 'Finance',
  job_title: 'Analyst',
  country: 'IT',
  salary_amount: '60000.00',
  currency: 'EUR',
  salary_usd: '64800.00',
}

const RAISE: SalaryChange = {
  id: 'bbbbbbbb-0000-4000-8000-000000000001',
  old_amount: '2400000.00',
  old_currency: 'INR',
  new_amount: '3000000.00',
  new_currency: 'INR',
  changed_by: 'hr@acme.test',
  changed_at: '2026-08-30T10:00:00Z',
}

/** Query strings the list endpoint was called with, in order. */
export const listRequests: URLSearchParams[] = []

/** Bodies the PATCH endpoint received, in order. */
export const patchRequests: Record<string, unknown>[] = []

/** Flipped by a test to make the history endpoint start returning a row. */
export let historyRows: SalaryChange[] = []

/** What the logout endpoint answers. 403 reproduces the CSRF failure. */
export let logoutStatus = 204

export function setLogoutStatus(status: number) {
  logoutStatus = status
}

export function setHistory(rows: SalaryChange[]) {
  historyRows = rows
}

export function resetRecording() {
  listRequests.length = 0
  patchRequests.length = 0
  historyRows = []
  logoutStatus = 204
}

export const handlers = [
  http.get(`${BASE}/auth/me/`, () =>
    HttpResponse.json({
      id: 1,
      username: 'hr@acme.test',
      email: 'hr@acme.test',
      first_name: '',
      last_name: '',
      is_staff: true,
    }),
  ),

  http.post(`${BASE}/auth/logout/`, () =>
    logoutStatus === 204
      ? new HttpResponse(null, { status: 204 })
      : HttpResponse.json({ detail: 'CSRF Failed' }, { status: logoutStatus }),
  ),

  http.get(`${BASE}/employees/`, ({ request }) => {
    const url = new URL(request.url)
    listRequests.push(url.searchParams)

    const country = url.searchParams.get('country')
    const results = country
      ? [ASHA, MARCO].filter((row) => row.country === country)
      : [ASHA, MARCO]

    return HttpResponse.json({
      count: results.length,
      next: null,
      previous: null,
      results,
    })
  }),

  http.get(`${BASE}/employees/:id/`, () => HttpResponse.json(ASHA)),

  http.get(`${BASE}/employees/:id/salary-history/`, () =>
    HttpResponse.json({
      count: historyRows.length,
      next: null,
      previous: null,
      results: historyRows,
    }),
  ),

  http.patch(`${BASE}/employees/:id/`, async ({ request }) => {
    patchRequests.push((await request.json()) as Record<string, unknown>)
    // The server records the change; the next history fetch shows it.
    setHistory([RAISE])
    return HttpResponse.json({ ...ASHA, salary_amount: '3000000.00', salary_usd: '36000.00' })
  }),
]

export const server = setupServer(...handlers)
