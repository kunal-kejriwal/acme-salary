/** Shapes the API returns. Money always arrives as a string, never a number. */

export interface User {
  id: number
  username: string
  email: string
  first_name: string
  last_name: string
  is_staff: boolean
}

export interface Employee {
  id: string
  employee_code: string
  first_name: string
  last_name: string
  department: string
  job_title: string
  country: string
  joined_on: string
  salary_amount: string
  currency: string
  salary_usd: string
  created_at: string
  updated_at: string
}

/** The writable subset. `salary_usd` is derived server-side. */
export type EmployeeInput = Omit<
  Employee,
  'id' | 'salary_usd' | 'created_at' | 'updated_at'
>

export interface SalaryChange {
  id: string
  old_amount: string
  old_currency: string
  new_amount: string
  new_currency: string
  changed_by: string
  changed_at: string
}

export interface SalarySummary {
  headcount: number
  total_usd: string
  average_usd: string
  median_usd: string
}

/** All three breakdowns share this shape, so one chart renders any of them. */
export interface SalaryByGroup {
  group: string
  headcount: number
  average_usd: string
  median_usd: string
  min_usd: string
  max_usd: string
}

export const CURRENCIES = [
  'INR',
  'USD',
  'GBP',
  'EUR',
  'SGD',
  'BRL',
  'JPY',
  'AUD',
] as const
