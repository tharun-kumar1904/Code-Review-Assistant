import { ShieldAlert, ShieldCheck, AlertTriangle, Info } from 'lucide-react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, PieChart, Pie, Cell
} from 'recharts'
import StatCard from '../components/StatCard'

const demoSecurityIssues = [
  {
    id: 1, vulnerability_type: 'SQL Injection', severity: 'critical',
    file_path: 'src/payments/processor.py', line_number: 47,
    description: 'User input directly interpolated into SQL query without parameterization.',
    remediation: 'Use parameterized queries or an ORM. Never use string formatting for SQL.',
    cwe_id: 'CWE-89', owasp_category: 'A03:2021 Injection',
  },
  {
    id: 2, vulnerability_type: 'Cross-Site Scripting (XSS)', severity: 'critical',
    file_path: 'src/components/CommentBox.jsx', line_number: 15,
    description: 'User content rendered via dangerouslySetInnerHTML without sanitization.',
    remediation: 'Use DOMPurify to sanitize HTML content before rendering.',
    cwe_id: 'CWE-79', owasp_category: 'A03:2021 Injection',
  },
  {
    id: 3, vulnerability_type: 'Hardcoded Secrets', severity: 'critical',
    file_path: 'src/payments/config.py', line_number: 12,
    description: 'Stripe API key hardcoded in source file.',
    remediation: 'Use environment variables or a secrets manager.',
    cwe_id: 'CWE-798', owasp_category: 'A07:2021',
  },
  {
    id: 4, vulnerability_type: 'Insecure Function', severity: 'high',
    file_path: 'src/utils/parser.py', line_number: 78,
    description: 'Use of eval() to parse user-provided expressions.',
    remediation: 'Use ast.literal_eval() or a safe parser library.',
    cwe_id: 'CWE-78', owasp_category: 'A03:2021 Injection',
  },
  {
    id: 5, vulnerability_type: 'Path Traversal', severity: 'high',
    file_path: 'src/api/download.py', line_number: 34,
    description: 'User-supplied filename used in file path without validation.',
    remediation: 'Validate paths and use os.path.realpath() to prevent traversal.',
    cwe_id: 'CWE-22', owasp_category: 'A01:2021',
  },
  {
    id: 6, vulnerability_type: 'Weak Cryptography', severity: 'medium',
    file_path: 'src/auth/hash.py', line_number: 9,
    description: 'MD5 used for password hashing, which is cryptographically weak.',
    remediation: 'Use bcrypt or Argon2 for password hashing.',
    cwe_id: 'CWE-327', owasp_category: 'A02:2021',
  },
  {
    id: 7, vulnerability_type: 'Insecure HTTP', severity: 'medium',
    file_path: 'src/integrations/webhook.py', line_number: 22,
    description: 'External API called over HTTP instead of HTTPS.',
    remediation: 'Always use HTTPS for external communications.',
    cwe_id: 'CWE-319', owasp_category: 'A02:2021',
  },
]

const severityChart = [
  { name: 'Critical', count: 3, color: '#ef4444' },
  { name: 'High', count: 2, color: '#f59e0b' },
  { name: 'Medium', count: 2, color: '#3b82f6' },
  { name: 'Low', count: 0, color: '#10b981' },
]

const categoryChart = [
  { name: 'Injection', count: 4 },
  { name: 'Auth', count: 1 },
  { name: 'Crypto', count: 2 },
  { name: 'Access', count: 1 },
  { name: 'Config', count: 2 },
]

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div style={{
      background: 'rgba(17,24,39,0.95)', border: '1px solid var(--border-subtle)',
      borderRadius: '8px', padding: '10px', backdropFilter: 'blur(10px)',
    }}>
      <p style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)' }}>{label}</p>
      {payload.map((p, i) => (
        <p key={i} style={{ fontSize: '0.8rem', color: p.color || '#6366f1', fontWeight: 600 }}>
          {p.value} issues
        </p>
      ))}
    </div>
  )
}

export default function Security() {
  const sevIcon = (s) => {
    if (s === 'critical') return <AlertTriangle size={14} style={{ color: '#ef4444' }} />
    if (s === 'high') return <AlertTriangle size={14} style={{ color: '#f59e0b' }} />
    return <Info size={14} style={{ color: '#3b82f6' }} />
  }

  return (
    <div>
      <div className="page-header">
        <h1>Security Analysis</h1>
        <p>Vulnerability detection and remediation tracking</p>
      </div>

      {/* Stats */}
      <div className="stats-grid">
        <StatCard icon={ShieldAlert} label="Total Vulnerabilities" value={7} trend="-2 vs last week" trendDir="down" color="red" />
        <StatCard icon={AlertTriangle} label="Critical Issues" value={3} color="orange" />
        <StatCard icon={ShieldCheck} label="Resolved" value={14} trend="+5 this week" color="green" />
      </div>

      {/* Charts */}
      <div className="grid-2" style={{ marginBottom: '24px' }}>
        <div className="chart-container">
          <h3>Severity Distribution</h3>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={severityChart} barSize={36}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.08)" />
              <XAxis dataKey="name" tick={{ fontSize: 12, fill: '#64748b' }} axisLine={false} />
              <YAxis tick={{ fontSize: 12, fill: '#64748b' }} axisLine={false} />
              <Tooltip content={<CustomTooltip />} />
              <Bar dataKey="count" radius={[6, 6, 0, 0]}>
                {severityChart.map((e, i) => <Cell key={i} fill={e.color} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
        <div className="chart-container">
          <h3>OWASP Categories</h3>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={categoryChart} layout="vertical" barSize={20}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.08)" />
              <XAxis type="number" tick={{ fontSize: 12, fill: '#64748b' }} axisLine={false} />
              <YAxis type="category" dataKey="name" tick={{ fontSize: 12, fill: '#64748b' }} axisLine={false} width={80} />
              <Tooltip content={<CustomTooltip />} />
              <Bar dataKey="count" fill="#6366f1" radius={[0, 6, 6, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Issues Table */}
      <div className="chart-container">
        <h3>Active Vulnerabilities</h3>
        <table className="data-table">
          <thead>
            <tr>
              <th>Vulnerability</th>
              <th>Severity</th>
              <th>File</th>
              <th>CWE</th>
              <th>Description</th>
              <th>Remediation</th>
            </tr>
          </thead>
          <tbody>
            {demoSecurityIssues.map(si => (
              <tr key={si.id}>
                <td style={{ fontWeight: 500, color: 'var(--text-primary)' }}>
                  {sevIcon(si.severity)} <span style={{ marginLeft: '6px' }}>{si.vulnerability_type}</span>
                </td>
                <td><span className={`badge ${si.severity}`}>{si.severity}</span></td>
                <td><span className="file-path">{si.file_path}:{si.line_number}</span></td>
                <td style={{ fontFamily: 'var(--font-mono)', fontSize: '0.75rem', color: 'var(--accent-cyan)' }}>{si.cwe_id}</td>
                <td style={{ fontSize: '0.8rem', maxWidth: '250px' }}>{si.description}</td>
                <td style={{ fontSize: '0.78rem', color: 'var(--accent-success)', maxWidth: '220px' }}>{si.remediation}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
