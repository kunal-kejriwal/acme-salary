import { Layout, Typography } from 'antd'

const { Header, Content } = Layout
const { Title, Paragraph } = Typography

/**
 * Application shell. Routing and the real pages (login, employees, imports,
 * dashboard) arrive in a later phase — this establishes the Ant Design layout
 * and proves the toolchain end to end.
 */
export default function App() {
  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header>
        <Title level={4} style={{ color: '#fff', margin: 0, lineHeight: '64px' }}>
          ACME Salary Management
        </Title>
      </Header>
      <Content style={{ padding: 24 }}>
        <Paragraph>Frontend shell. Pages land in a later phase.</Paragraph>
      </Content>
    </Layout>
  )
}
