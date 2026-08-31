import { Column } from '@ant-design/plots'
import { Card, Col, Row, Spin, Statistic, Typography } from 'antd'
import { useEffect, useState } from 'react'

import { analytics } from '../api/endpoints'
import type { SalaryByGroup, SalarySummary } from '../api/types'
import { compactUsd, usd } from '../format'
import { useDocumentTitle } from '../useDocumentTitle'

const { Title, Text } = Typography

export default function DashboardPage() {
  useDocumentTitle('Dashboard')
  const [summary, setSummary] = useState<SalarySummary>()
  const [byCountry, setByCountry] = useState<SalaryByGroup[]>([])
  const [byDepartment, setByDepartment] = useState<SalaryByGroup[]>([])
  const [byTitle, setByTitle] = useState<SalaryByGroup[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([
      analytics.summary(),
      analytics.byCountry(),
      analytics.byDepartment(),
      analytics.byTitle(),
    ])
      .then(([total, country, department, title]) => {
        setSummary(total)
        setByCountry(country)
        setByDepartment(department)
        setByTitle(title)
      })
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return (
      <div style={{ display: 'grid', placeItems: 'center', minHeight: 320 }}>
        <Spin />
      </div>
    )
  }

  return (
    <div>
      <Title level={3} style={{ marginTop: 0 }}>
        Dashboard
      </Title>
      <Text type="secondary">
        All salary figures normalized to USD at the seeded exchange rates.
      </Text>

      <Row gutter={[16, 16]} style={{ marginTop: 24 }}>
        <StatCard title="Headcount" value={summary?.headcount.toLocaleString()} />
        <StatCard title="Total annual cost (USD)" value={usd(summary?.total_usd)} />
        <StatCard title="Average salary (USD)" value={usd(summary?.average_usd)} />
        <StatCard title="Median salary (USD)" value={usd(summary?.median_usd)} />
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 8 }}>
        <Col xs={24} lg={12}>
          <GroupChart title="Median salary by country (USD)" data={byCountry} />
        </Col>
        <Col xs={24} lg={12}>
          <GroupChart title="Median salary by department (USD)" data={byDepartment} />
        </Col>
        <Col xs={24}>
          <GroupChart title="Median salary by job title (USD)" data={byTitle} />
        </Col>
      </Row>
    </div>
  )
}

function StatCard({ title, value }: { title: string; value?: string }) {
  return (
    <Col xs={24} sm={12} lg={6}>
      <Card>
        <Statistic title={title} value={value ?? '—'} />
      </Card>
    </Col>
  )
}

/**
 * One chart for all three breakdowns.
 *
 * The API keys every grouped row as `group`, so country, department and job
 * title share a component instead of three near-copies.
 *
 * It plots the median rather than the mean: a handful of very senior salaries
 * drags a group's average somewhere no one in that group actually sits.
 */
function GroupChart({ title, data }: { title: string; data: SalaryByGroup[] }) {
  return (
    <Card title={title}>
      <Column
        data={data.map((row) => ({
          group: row.group,
          median: Number(row.median_usd),
          headcount: row.headcount,
        }))}
        xField="group"
        yField="median"
        height={280}
        axis={{
          y: { labelFormatter: (value: number) => compactUsd(value) },
          x: { labelAutoRotate: true },
        }}
        tooltip={{
          items: [
            { channel: 'y', name: 'Median', valueFormatter: (v: number) => usd(v) },
            { field: 'headcount', name: 'Headcount' },
          ],
        }}
      />
    </Card>
  )
}
