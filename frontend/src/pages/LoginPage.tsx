import { Alert, Button, Card, Form, Input, Typography } from 'antd'
import { useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'

import { ApiError } from '../api/client'
import { useAuth } from '../auth/AuthContext'

const { Title, Paragraph } = Typography

interface Credentials {
  username: string
  password: string
}

export default function LoginPage() {
  const { signIn } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  // Send people back where they were headed before the redirect.
  const destination =
    (location.state as { from?: string } | null)?.from ?? '/employees'

  async function onFinish({ username, password }: Credentials) {
    setError(null)
    setSubmitting(true)
    try {
      await signIn(username, password)
      navigate(destination, { replace: true })
    } catch (caught) {
      // Surface the API's own wording rather than inventing a second
      // vocabulary for the same failure.
      setError(
        caught instanceof ApiError ? caught.detail : 'Could not sign in. Try again.',
      )
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'grid',
        placeItems: 'center',
        padding: 24,
        background: '#f5f5f5',
      }}
    >
      <Card style={{ width: 380 }}>
        <Title level={4} style={{ marginBottom: 4 }}>
          ACME Salary Management
        </Title>
        <Paragraph type="secondary" style={{ marginTop: 0 }}>
          Sign in to continue.
        </Paragraph>

        {error && (
          <Alert
            type="error"
            message={error}
            showIcon
            style={{ marginBottom: 16 }}
          />
        )}

        <Form layout="vertical" onFinish={onFinish} requiredMark={false}>
          <Form.Item
            label="Username"
            name="username"
            rules={[{ required: true, message: 'Username is required' }]}
          >
            <Input autoFocus autoComplete="username" />
          </Form.Item>
          <Form.Item
            label="Password"
            name="password"
            rules={[{ required: true, message: 'Password is required' }]}
          >
            <Input.Password autoComplete="current-password" />
          </Form.Item>
          <Button type="primary" htmlType="submit" block loading={submitting}>
            Sign in
          </Button>
        </Form>
      </Card>
    </div>
  )
}
