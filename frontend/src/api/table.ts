/**
 * The one place Ant Design's Table vocabulary meets DRF's.
 *
 * Table speaks {current, pageSize, sorter, filters}; the API speaks
 * {page, ordering, country, ...}. Translating in both directions here keeps
 * every page component free of query-parameter trivia, and gives the mapping
 * a single place to be tested.
 */

import type { Page } from './client'

/** What a page component holds and hands back to the table. */
export interface TableQuery {
  page: number
  pageSize: number
  /** API field name, prefixed with `-` for descending. */
  ordering?: string
  filters: Record<string, string | undefined>
  search?: string
}

export const DEFAULT_PAGE_SIZE = 25

export const emptyQuery: TableQuery = {
  page: 1,
  pageSize: DEFAULT_PAGE_SIZE,
  filters: {},
}

/** Ant Design's sorter argument, narrowed to what we use. */
export interface AntSorter {
  field?: string | string[]
  columnKey?: string
  order?: 'ascend' | 'descend' | null
}

export interface AntPagination {
  current?: number
  pageSize?: number
}

/** Translate a Table `onChange` into our query shape. */
export function fromTableChange(
  query: TableQuery,
  pagination: AntPagination,
  sorter: AntSorter | AntSorter[],
): TableQuery {
  const active = Array.isArray(sorter) ? sorter[0] : sorter
  const key =
    active?.columnKey ??
    (Array.isArray(active?.field) ? active?.field[0] : active?.field)

  let ordering: string | undefined
  if (active?.order && key) {
    ordering = active.order === 'descend' ? `-${key}` : String(key)
  }

  const pageSize = pagination.pageSize ?? query.pageSize
  // A page-size change invalidates the current offset; going back to page 1
  // is less surprising than landing somewhere unrelated.
  const page =
    pageSize === query.pageSize ? (pagination.current ?? 1) : 1

  return { ...query, page, pageSize, ordering }
}

/** Translate our query shape into API request parameters. */
export function toRequestParams(query: TableQuery): Record<string, unknown> {
  const params: Record<string, unknown> = {
    page: query.page,
    ordering: query.ordering,
    search: query.search,
  }
  for (const [field, value] of Object.entries(query.filters)) {
    params[field] = value
  }
  return params
}

/** Translate a DRF page into Ant Design's pagination config. */
export function toTablePagination(page: Page<unknown> | undefined, query: TableQuery) {
  return {
    current: query.page,
    pageSize: query.pageSize,
    total: page?.count ?? 0,
    showSizeChanger: false,
    showTotal: (total: number) => `${total.toLocaleString()} employees`,
  }
}

/**
 * Reset to the first page whenever the result set changes underneath.
 *
 * Editing a filter while on page 7 of the old result set otherwise lands on
 * page 7 of the new one, which is usually empty.
 */
export function withFilters(
  query: TableQuery,
  filters: Record<string, string | undefined>,
): TableQuery {
  return { ...query, filters, page: 1 }
}

export function withSearch(query: TableQuery, search: string | undefined): TableQuery {
  return { ...query, search, page: 1 }
}
