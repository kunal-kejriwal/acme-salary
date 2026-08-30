import { HistoryOutlined } from '@ant-design/icons'
import {
  Alert,
  Button,
  Card,
  Descriptions,
  Drawer,
  Empty,
  Form,
  Input,
  Select,
  Space,
  Spin,
  Table,
  Tabs,
  Tag,
  Typography,
} from 'antd'
import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import { ApiError } from '../api/client'
import { employees } from '../api/endpoints'
import { CURRENCIES, type Employee, type SalaryChange } from '../api/types'
import { dateTime, money, usd } from '../format'

const { Title } = Typography

export default function EmployeeDetailPage() {
  const { id = '' } = useParams()
  const navigate = useNavigate()

  const [employee, setEmployee] = useState<Employee>()
  const [history, setHistory] = useState<SalaryChange[]>([])
  const [loading, setLoading] = useState(true)
  const [editing, setEditing] = useState(false)

  /**
   * Reload the record and its history together.
   *
   * They are refetched as a pair on purpose: a salary edit changes both, and
   * the demo turns on the History tab filling in the moment the card updates.
   */
  const load = useCallback(async () => {
    const [record, changes] = await Promise.all([
      employees.get(id),
      employees.salaryHistory(id),
    ])
    setEmployee(record)
    setHistory(changes.results)
  }, [id])

  useEffect(() => {
    setLoading(true)
    load().finally(() => setLoading(false))
  }, [load])

  if (loading) {
    return (
      <div style={{ display: 'grid', placeItems: 'center', minHeight: 240 }}>
        <Spin />
      </div>
    )
  }

  if (!employee) {
    return <Alert type="error" message="Employee not found" showIcon />
  }

  return (
    <Space orientation="vertical" size="large" style={{ width: '100%' }}>
      <Space style={{ justifyContent: 'space-between', width: '100%' }}>
        <Space orientation="vertical" size={0}>
          <Title level={3} style={{ margin: 0 }}>
            {employee.first_name} {employee.last_name}
          </Title>
          <Typography.Text type="secondary">
            {employee.job_title} · {employee.department}
          </Typography.Text>
        </Space>
        <Space>
          <Button onClick={() => navigate('/employees')}>Back</Button>
          <Button type="primary" onClick={() => setEditing(true)}>
            Edit
          </Button>
        </Space>
      </Space>

      <Tabs
        items={[
          {
            key: 'record',
            label: 'Record',
            children: <RecordCard employee={employee} />,
          },
          {
            key: 'history',
            label: (
              <span>
                <HistoryOutlined /> History
                {history.length > 0 && <Tag style={{ marginLeft: 8 }}>{history.length}</Tag>}
              </span>
            ),
            children: <HistoryTable changes={history} />,
          },
        ]}
      />

      <EditDrawer
        employee={employee}
        open={editing}
        onClose={() => setEditing(false)}
        onSaved={async () => {
          setEditing(false)
          await load()
        }}
      />
    </Space>
  )
}

function RecordCard({ employee }: { employee: Employee }) {
  return (
    <Card>
      <Descriptions column={2} bordered size="small">
        <Descriptions.Item label="Employee code">
          {employee.employee_code}
        </Descriptions.Item>
        <Descriptions.Item label="Country">{employee.country}</Descriptions.Item>
        <Descriptions.Item label="Department">
          {employee.department}
        </Descriptions.Item>
        <Descriptions.Item label="Job title">{employee.job_title}</Descriptions.Item>
        <Descriptions.Item label="Joined">{employee.joined_on}</Descriptions.Item>
        <Descriptions.Item label="Currency">{employee.currency}</Descriptions.Item>
        <Descriptions.Item label="Salary (local)">
          {money(employee.salary_amount)} {employee.currency}
        </Descriptions.Item>
        <Descriptions.Item label="Salary (USD)">
          {usd(employee.salary_usd)}
        </Descriptions.Item>
      </Descriptions>
    </Card>
  )
}

const HISTORY_COLUMNS = [
  {
    title: 'Changed',
    dataIndex: 'changed_at',
    key: 'changed_at',
    render: (value: string) => dateTime(value),
  },
  {
    title: 'From',
    key: 'from',
    render: (_: unknown, row: SalaryChange) =>
      `${money(row.old_amount)} ${row.old_currency}`,
  },
  {
    title: 'To',
    key: 'to',
    render: (_: unknown, row: SalaryChange) =>
      `${money(row.new_amount)} ${row.new_currency}`,
  },
  { title: 'Changed by', dataIndex: 'changed_by', key: 'changed_by' },
]

function HistoryTable({ changes }: { changes: SalaryChange[] }) {
  if (changes.length === 0) {
    // Deliberate, not a fallback: a new hire has a salary, not a change, and
    // this is the state the demo shows filling in after the first edit.
    return (
      <Card>
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description={
            <Space orientation="vertical" size={4}>
              <Typography.Text strong>No salary changes yet</Typography.Text>
              <Typography.Text type="secondary">
                Every future pay change is recorded here — old and new amounts,
                who made it, and when.
              </Typography.Text>
            </Space>
          }
        />
      </Card>
    )
  }

  return (
    <Table<SalaryChange>
      rowKey="id"
      columns={HISTORY_COLUMNS}
      dataSource={changes}
      pagination={false}
    />
  )
}

function EditDrawer({
  employee,
  open,
  onClose,
  onSaved,
}: {
  employee: Employee
  open: boolean
  onClose: () => void
  onSaved: () => void
}) {
  const [form] = Form.useForm()
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (open) {
      form.setFieldsValue(employee)
      setError(null)
    }
  }, [open, employee, form])

  async function onFinish(values: Record<string, string>) {
    setSaving(true)
    setError(null)
    try {
      await employees.update(employee.id, values)
      onSaved()
    } catch (caught) {
      if (caught instanceof ApiError) {
        // Mirror the API's own field errors onto the form rather than
        // restating them in a second vocabulary.
        const fields = Object.entries(caught.fieldErrors).map(
          ([name, message]) => ({ name, errors: [message] }),
        )
        if (fields.length) form.setFields(fields)
        else setError(caught.detail)
      } else {
        setError('Could not save. Try again.')
      }
    } finally {
      setSaving(false)
    }
  }

  return (
    <Drawer
      title={`Edit ${employee.first_name} ${employee.last_name}`}
      open={open}
      onClose={onClose}
      destroyOnHidden
    >
      {error && (
        <Alert type="error" message={error} showIcon style={{ marginBottom: 16 }} />
      )}
      <Form form={form} layout="vertical" onFinish={onFinish} requiredMark={false}>
        <Form.Item label="First name" name="first_name">
          <Input />
        </Form.Item>
        <Form.Item label="Last name" name="last_name">
          <Input />
        </Form.Item>
        <Form.Item label="Department" name="department">
          <Input />
        </Form.Item>
        <Form.Item label="Job title" name="job_title">
          <Input />
        </Form.Item>
        <Form.Item label="Salary (local currency)" name="salary_amount">
          <Input aria-label="Salary amount" />
        </Form.Item>
        <Form.Item label="Currency" name="currency">
          <Select
            aria-label="Currency"
            options={CURRENCIES.map((code) => ({ label: code, value: code }))}
          />
        </Form.Item>
        <Button type="primary" htmlType="submit" loading={saving} block>
          Save
        </Button>
      </Form>
    </Drawer>
  )
}
