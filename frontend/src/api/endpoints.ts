/** The API surface, one function per endpoint. */

import { queryString, request, type Page } from './client'
import { toRequestParams, type TableQuery } from './table'
import type {
  Employee,
  EmployeeInput,
  SalaryByGroup,
  SalaryChange,
  SalarySummary,
  User,
} from './types'

// --- auth ------------------------------------------------------------------

export const auth = {
  /**
   * Who is signed in, or null.
   *
   * Also the app's CSRF bootstrap: the endpoint is `ensure_csrf_cookie`, so
   * calling it on load leaves a token in place before any POST — including
   * the login POST, which has no earlier GET of its own.
   */
  async me(): Promise<User | null> {
    try {
      return await request<User>('/auth/me/')
    } catch {
      return null
    }
  },

  login: (username: string, password: string) =>
    request<User>('/auth/login/', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    }),

  logout: () => request<void>('/auth/logout/', { method: 'POST' }),
}

// --- employees -------------------------------------------------------------

export const employees = {
  list: (query: TableQuery) =>
    request<Page<Employee>>(`/employees/${queryString(toRequestParams(query))}`),

  get: (id: string) => request<Employee>(`/employees/${id}/`),

  update: (id: string, changes: Partial<EmployeeInput>) =>
    request<Employee>(`/employees/${id}/`, {
      method: 'PATCH',
      body: JSON.stringify(changes),
    }),

  create: (employee: EmployeeInput) =>
    request<Employee>('/employees/', {
      method: 'POST',
      body: JSON.stringify(employee),
    }),

  remove: (id: string) => request<void>(`/employees/${id}/`, { method: 'DELETE' }),

  salaryHistory: (id: string) =>
    request<Page<SalaryChange>>(`/employees/${id}/salary-history/`),
}

// --- analytics -------------------------------------------------------------

export const analytics = {
  summary: () => request<SalarySummary>('/analytics/summary/'),
  byCountry: () => request<SalaryByGroup[]>('/analytics/by-country/'),
  byDepartment: () => request<SalaryByGroup[]>('/analytics/by-department/'),
  byTitle: () => request<SalaryByGroup[]>('/analytics/by-title/'),
}
