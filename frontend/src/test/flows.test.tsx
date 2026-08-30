/**
 * Three flows, deliberately.
 *
 * Not one test per component. A snapshot of every card would inflate the
 * count without telling anyone whether the product works; these cover the
 * paths that carry real risk — the table's server round trip, the history
 * read, and the edit that has to make a change appear in that history.
 */

import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it } from 'vitest'

import EmployeeDetailPage from '../pages/EmployeeDetailPage'
import EmployeesPage from '../pages/EmployeesPage'
import { listRequests, patchRequests, resetRecording, server, setHistory } from './server'

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => server.resetHandlers())
afterAll(() => server.close())
beforeEach(() => resetRecording())

function renderEmployees() {
  return render(
    <MemoryRouter initialEntries={['/employees']}>
      <Routes>
        <Route path="/employees" element={<EmployeesPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

function renderDetail() {
  return render(
    <MemoryRouter initialEntries={['/employees/aaaaaaaa-0000-4000-8000-000000000001']}>
      <Routes>
        <Route path="/employees/:id" element={<EmployeeDetailPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('Flow 1: the employees table renders a server page', () => {
  it('shows the rows the API returned', async () => {
    renderEmployees()
    expect(await screen.findByText('Asha Rao')).toBeInTheDocument()
    expect(screen.getByText('Marco Bianchi')).toBeInTheDocument()
  })

  it('shows the normalised USD salary, not just the local amount', async () => {
    renderEmployees()
    await screen.findByText('Asha Rao')
    expect(screen.getByText('2,400,000.00 INR')).toBeInTheDocument()
    expect(screen.getByText('28,800.00')).toBeInTheDocument()
  })

  it('passes the search term through to the API', async () => {
    const user = userEvent.setup()
    renderEmployees()
    await screen.findByText('Asha Rao')

    await user.type(screen.getByLabelText('Search employees'), 'Rao{enter}')

    await waitFor(() => {
      expect(listRequests.at(-1)?.get('search')).toBe('Rao')
    })
  })

  it('passes a filter through and resets to the first page', async () => {
    const user = userEvent.setup()
    renderEmployees()
    await screen.findByText('Asha Rao')

    await user.click(screen.getByLabelText('Country'))
    await user.click(await screen.findByTitle('IN'))

    await waitFor(() => {
      const latest = listRequests.at(-1)
      expect(latest?.get('country')).toBe('IN')
      expect(latest?.get('page')).toBe('1')
    })
  })

  it('filters the visible rows to the server response', async () => {
    const user = userEvent.setup()
    renderEmployees()
    await screen.findByText('Marco Bianchi')

    await user.click(screen.getByLabelText('Country'))
    await user.click(await screen.findByTitle('IN'))

    await waitFor(() => {
      expect(screen.queryByText('Marco Bianchi')).not.toBeInTheDocument()
    })
    expect(screen.getByText('Asha Rao')).toBeInTheDocument()
  })
})

describe('Flow 2: the detail page shows salary history', () => {
  it('shows an intentional empty state when there are no changes', async () => {
    renderDetail()
    await user_clickHistory()
    expect(screen.getByText('No salary changes yet')).toBeInTheDocument()
  })

  it('lists a change once one exists', async () => {
    setHistory([
      {
        id: 'bbbbbbbb-0000-4000-8000-000000000001',
        old_amount: '2400000.00',
        old_currency: 'INR',
        new_amount: '3000000.00',
        new_currency: 'INR',
        changed_by: 'hr@acme.test',
        changed_at: '2026-08-30T10:00:00Z',
      },
    ])
    renderDetail()
    await user_clickHistory()

    // Scoped to the table: the record card shows the same salary, so an
    // unscoped query would match twice and pass for the wrong reason.
    const history = within(await screen.findByRole('table'))
    expect(history.getByText('2,400,000.00 INR')).toBeInTheDocument()
    expect(history.getByText('3,000,000.00 INR')).toBeInTheDocument()
    expect(history.getByText('hr@acme.test')).toBeInTheDocument()
  })
})

describe('Flow 3: a salary edit appears in history immediately', () => {
  it('posts the change and re-renders the history tab', async () => {
    const user = userEvent.setup()
    renderDetail()
    await user_clickHistory()

    // The demo starts here: nothing recorded yet.
    expect(screen.getByText('No salary changes yet')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Edit' }))
    const salary = await screen.findByLabelText('Salary amount')
    await user.clear(salary)
    await user.type(salary, '3000000.00')
    await user.click(screen.getByRole('button', { name: 'Save' }))

    await waitFor(() => {
      expect(patchRequests.at(-1)).toMatchObject({ salary_amount: '3000000.00' })
    })

    // ...and ends here, without a reload.
    await waitFor(() => {
      expect(screen.queryByText('No salary changes yet')).not.toBeInTheDocument()
    })
    const history = await screen.findByRole('table')
    expect(within(history).getByText('3,000,000.00 INR')).toBeInTheDocument()
  })
})

/** Open the History tab, waiting for the record to load first. */
async function user_clickHistory() {
  const user = userEvent.setup()
  await screen.findByText('Asha Rao')
  await user.click(screen.getByRole('tab', { name: /History/ }))
}
