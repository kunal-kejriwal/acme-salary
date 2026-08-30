import { Button, Card, Input, Select, Space, Table, Typography } from 'antd'
import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import type { Page } from '../api/client'
import { employees } from '../api/endpoints'
import {
  emptyQuery,
  fromTableChange,
  toTablePagination,
  withFilters,
  withSearch,
  type AntPagination,
  type AntSorter,
  type TableQuery,
} from '../api/table'
import { CURRENCIES, type Employee } from '../api/types'
import { money } from '../format'

const { Title } = Typography

const COLUMNS = [
  { title: 'Code', dataIndex: 'employee_code', key: 'employee_code' },
  {
    title: 'Name',
    key: 'last_name',
    sorter: true,
    render: (_: unknown, row: Employee) => `${row.first_name} ${row.last_name}`,
  },
  { title: 'Department', dataIndex: 'department', key: 'department' },
  { title: 'Job title', dataIndex: 'job_title', key: 'job_title', sorter: true },
  { title: 'Country', dataIndex: 'country', key: 'country' },
  {
    title: 'Salary (local)',
    key: 'salary_amount',
    render: (_: unknown, row: Employee) =>
      `${money(row.salary_amount)} ${row.currency}`,
  },
  {
    title: 'Salary (USD)',
    dataIndex: 'salary_usd',
    key: 'salary_usd',
    sorter: true,
    render: (value: string) => money(value),
  },
  { title: 'Joined', dataIndex: 'joined_on', key: 'joined_on', sorter: true },
]

export default function EmployeesPage() {
  const navigate = useNavigate()
  const [query, setQuery] = useState<TableQuery>(emptyQuery)
  const [page, setPage] = useState<Page<Employee>>()
  const [loading, setLoading] = useState(true)
  const [searchDraft, setSearchDraft] = useState('')

  useEffect(() => {
    let current = true
    setLoading(true)
    employees
      .list(query)
      .then((result) => {
        if (current) setPage(result)
      })
      .finally(() => {
        if (current) setLoading(false)
      })
    return () => {
      current = false
    }
  }, [query])

  const options = useMemo(
    () => ({
      country: unique(page?.results.map((row) => row.country)),
      department: unique(page?.results.map((row) => row.department)),
      job_title: unique(page?.results.map((row) => row.job_title)),
    }),
    [page],
  )

  function setFilter(field: string, value: string | undefined) {
    setQuery((current) =>
      withFilters(current, { ...current.filters, [field]: value }),
    )
  }

  return (
    <Space orientation="vertical" size="large" style={{ width: '100%' }}>
      <Title level={3} style={{ margin: 0 }}>
        Employees
      </Title>

      <Card size="small">
        <Space wrap>
          <Input.Search
            placeholder="Name or employee code"
            allowClear
            style={{ width: 240 }}
            value={searchDraft}
            onChange={(event) => setSearchDraft(event.target.value)}
            onSearch={(value) =>
              setQuery((current) => withSearch(current, value || undefined))
            }
            aria-label="Search employees"
          />
          <FilterSelect
            label="Country"
            options={options.country}
            value={query.filters.country}
            onChange={(value) => setFilter('country', value)}
          />
          <FilterSelect
            label="Department"
            options={options.department}
            value={query.filters.department}
            onChange={(value) => setFilter('department', value)}
          />
          <FilterSelect
            label="Job title"
            options={options.job_title}
            value={query.filters.job_title}
            onChange={(value) => setFilter('job_title', value)}
          />
          <FilterSelect
            label="Currency"
            options={[...CURRENCIES]}
            value={query.filters.currency}
            onChange={(value) => setFilter('currency', value)}
          />
          <Input
            placeholder="Min USD"
            style={{ width: 110 }}
            aria-label="Minimum salary in USD"
            onBlur={(event) =>
              setFilter('salary_usd_min', event.target.value || undefined)
            }
          />
          <Input
            placeholder="Max USD"
            style={{ width: 110 }}
            aria-label="Maximum salary in USD"
            onBlur={(event) =>
              setFilter('salary_usd_max', event.target.value || undefined)
            }
          />
          <Button
            onClick={() => {
              setSearchDraft('')
              setQuery(emptyQuery)
            }}
          >
            Reset
          </Button>
        </Space>
      </Card>

      <Table<Employee>
        rowKey="id"
        columns={COLUMNS}
        dataSource={page?.results ?? []}
        loading={loading}
        pagination={toTablePagination(page, query)}
        onChange={(pagination, _filters, sorter) =>
          setQuery((current) =>
            fromTableChange(
              current,
              pagination as AntPagination,
              sorter as AntSorter | AntSorter[],
            ),
          )
        }
        onRow={(row) => ({
          onClick: () => navigate(`/employees/${row.id}`),
          style: { cursor: 'pointer' },
        })}
      />
    </Space>
  )
}

function FilterSelect({
  label,
  options,
  value,
  onChange,
}: {
  label: string
  options: string[]
  value: string | undefined
  onChange: (value: string | undefined) => void
}) {
  return (
    <Select
      allowClear
      placeholder={label}
      aria-label={label}
      style={{ width: 170 }}
      value={value}
      onChange={onChange}
      options={options.map((option) => ({ label: option, value: option }))}
    />
  )
}

function unique(values: (string | undefined)[] | undefined): string[] {
  return [...new Set((values ?? []).filter(Boolean) as string[])].sort()
}
