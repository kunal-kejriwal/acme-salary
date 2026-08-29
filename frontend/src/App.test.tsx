import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import App from './App'

describe('App shell', () => {
  it('renders the application title', () => {
    render(<App />)
    expect(screen.getByText('ACME Salary Management')).toBeInTheDocument()
  })
})
