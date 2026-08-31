/**
 * Sign out clears the local session whatever the server answers.
 *
 * Reproduces a production failure. `signOut` awaited the logout POST and then
 * cleared state; when the POST was rejected the rejection propagated, the
 * state was never cleared, the navigation never ran, and nothing was shown.
 * The button appeared inert.
 *
 * The underlying 403 had its own cause — cross-origin cookies, fixed by the
 * Vercel proxy — but a sign-out that only works when the network cooperates
 * is the wrong shape regardless. An expired session answers 403 too, and that
 * is the case where someone most wants the button to work.
 */

import { act, renderHook, waitFor } from '@testing-library/react'
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it } from 'vitest'

import { AuthProvider, useAuth } from '../auth/AuthContext'
import { resetRecording, server, setLogoutStatus } from './server'

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => server.resetHandlers())
afterAll(() => server.close())
beforeEach(() => resetRecording())

/** A signed-in session, settled past the initial /auth/me. */
async function signedIn() {
  const { result } = renderHook(() => useAuth(), { wrapper: AuthProvider })
  await waitFor(() => expect(result.current.loading).toBe(false))
  expect(result.current.user?.username).toBe('hr@acme.test')
  return result
}

describe('Sign out', () => {
  it('clears the session when the server accepts', async () => {
    const result = await signedIn()

    await act(async () => {
      await result.current.signOut()
    })

    expect(result.current.user).toBeNull()
  })

  it('still clears the session when the server rejects', async () => {
    // 403 is what a CSRF failure and an already-expired session both return.
    setLogoutStatus(403)
    const result = await signedIn()

    await act(async () => {
      await result.current.signOut()
    })

    expect(result.current.user).toBeNull()
  })

  it('does not reject, so the caller can navigate afterwards', async () => {
    // The button awaits signOut() and then navigates. A rejection here left
    // the person on a page that still looked signed in.
    setLogoutStatus(403)
    const result = await signedIn()

    await act(async () => {
      await expect(result.current.signOut()).resolves.toBeUndefined()
    })
  })

  it('survives the server being unreachable', async () => {
    setLogoutStatus(500)
    const result = await signedIn()

    await act(async () => {
      await result.current.signOut()
    })

    expect(result.current.user).toBeNull()
  })
})
