import { useEffect } from 'react'

const PRODUCT = 'ACME Salary Management'

/**
 * Names the browser tab after the page being shown.
 *
 * A router-driven app never reloads, so the tab keeps whatever index.html
 * shipped with unless something sets it. Each page states its own name and
 * this appends the product, so a person with several tabs open can tell them
 * apart and the back button's history reads as page names.
 *
 * Passing nothing -- the detail page before its record arrives -- leaves the
 * product name alone rather than showing a placeholder that would flash and
 * then change.
 */
export function useDocumentTitle(page?: string) {
  useEffect(() => {
    document.title = page ? `${page} · ${PRODUCT}` : PRODUCT
  }, [page])
}
