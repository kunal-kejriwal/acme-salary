/**
 * The browser tab names the page you are on.
 *
 * Shipped production reading `frontend` -- Vite's scaffold default, never
 * changed. That is invisible in development, where one tab is open on
 * localhost, and obvious to anyone who opens the deployed app beside their
 * other work.
 *
 * The static title is asserted against index.html rather than the DOM,
 * because that file is the only place it exists: jsdom's document.title comes
 * from the test environment, so a component test cannot see the regression
 * that actually shipped.
 */

import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it } from 'vitest'

// Vite inlines the file as a string. Read through the bundler rather than
// node:fs so this stays browser-typed code, like the rest of src/.
import indexHtml from '../../index.html?raw'
import EmployeeDetailPage from '../pages/EmployeeDetailPage'
import EmployeesPage from '../pages/EmployeesPage'
import { resetRecording, server } from './server'

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => server.resetHandlers())
afterAll(() => server.close())

beforeEach(() => {
  resetRecording()
  // So a passing assertion cannot be the previous test's leftover.
  document.title = 'not set by the app'
})

describe('The static document title', () => {
  it('is not the scaffold default', () => {
    expect(indexHtml).not.toMatch(/<title>\s*frontend\s*<\/title>/)
  })

  it('names the product', () => {
    expect(indexHtml).toContain('<title>ACME Salary Management</title>')
  })
})

describe('The tab title follows the route', () => {
  it('names the employees list', async () => {
    render(
      <MemoryRouter initialEntries={['/employees']}>
        <Routes>
          <Route path="/employees" element={<EmployeesPage />} />
        </Routes>
      </MemoryRouter>,
    )

    await screen.findByText('Asha Rao')
    expect(document.title).toBe('Employees · ACME Salary Management')
  })

  it('names the employee once the record has loaded', async () => {
    render(
      <MemoryRouter initialEntries={['/employees/aaaaaaaa-0000-4000-8000-000000000001']}>
        <Routes>
          <Route path="/employees/:id" element={<EmployeeDetailPage />} />
        </Routes>
      </MemoryRouter>,
    )

    await screen.findByText('Asha Rao')
    expect(document.title).toBe('Asha Rao · ACME Salary Management')
  })
})
