import { useState, useEffect } from 'react'
import {
  GitPullRequest, Bug, ShieldAlert, TrendingUp,
  Activity, Clock, Code2, Zap
} from 'lucide-react'
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, BarChart, Bar, PieChart, Pie, Cell
} from 'recharts'
import StatCard from '../components/StatCard'

/* ── Demo data (used when backend is unavailable) ─────────────────── */
const demoTrend = [
  { date: 'Jan', score: 72, issues: 18 },
  { date: 'Feb', score: 68, issues: 22 },
  { date: 'Mar', score: 75, issues: 15 },
  { date: 'Apr', score: 78, issues: 12 },
  { date: 'May', score: 82, issues: 9 },
  { date: 'Jun', score: 85, issues: 7 },
  { date: 'Jul', score: 79, issues: 11 },
  { date: 'Aug', score: 88, issues: 6 },
]

const demoSeverity = [
  { name: 'Critical', value: 4, color: '#ef4444' },
  { name: 'High', value: 12, color: '#f59e0b' },
  { name: 'Medium', value: 23, color: '#3b82f6' },
  { name: 'Low', value: 18, color: '#10b981' },
]

const demoRecentReviews = [
  { id: 1, pr: '#142 — Add payment processing', repo: 'acme/backend', score: 72, issues: 5, time: '2m ago' },
  { id: 2, pr: '#89 — Update auth middleware', repo: 'acme/api-gateway', score: 91, issues: 1, time: '15m ago' },
  { id: 3, pr: '#203 — Refactor database layer', repo: 'acme/core-lib', score: 65, issues: 8, time: '1h ago' },
  { id: 4, pr: '#55 — Add rate limiting', repo: 'acme/api-gateway', score: 88, issues: 2, time: '3h ago' },
  { id: 5, pr: '#77 — Fix XSS vulnerability', repo: 'acme/frontend', score: 45, issues: 12, time: '5h ago' },
]

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div style={{
      background: 'rgba(17, 24, 39, 0.95)',
      border: '1px solid var(--border-subtle)',
      borderRadius: '8px',
      padding: '12px',
      backdropFilter: 'blur(10px)',
    }}>
      <p style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)', marginBottom: '4px' }}>{label}</p>
      {payload.map((p, i) => (
        <p key={i} style={{ fontSize: '0.8rem', color: p.color, fontWeight: 600 }}>
          {p.name}: {p.value}
        </p>
      ))}
    </div>
  )
}

export default function Dashboard() {
  const [stats] = useState({
    totalReviews: 156,
    totalIssues: 342,
    securityAlerts: 28,
    avgScore: 78.5,
  })

  return (
    <div>
      <div className="page-header">
        <h1>Dashboard</h1>
        <p>Overview of AI code review activity and metrics</p>
      </div>

      {/* Stat Cards */}
      <div className="stats-grid">
        <StatCard
          icon={GitPullRequest} label="Total Reviews"
          value={stats.totalReviews} trend="+12 this week" color="purple"
        />
        <StatCard
          icon={Bug} label="Issues Found"
          value={stats.totalIssues} trend="+34 this week" trendDir="up" color="orange"
        />
        <StatCard
          icon={ShieldAlert} label="Security Alerts"
          value={stats.securityAlerts} trend="-3 vs last week" trendDir="down" color="red"
        />
        <StatCard
          icon={TrendingUp} label="Avg Quality Score"
          value={stats.avgScore} trend="+2.3 pts" color="green"
        />
      </div>

      {/* Charts Row */}
      <div className="grid-2" style={{ marginBottom: '24px' }}>
        {/* Quality Trend */}
        <div className="chart-container">
          <h3 style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Activity size={18} style={{ color: 'var(--accent-primary)' }} />
            Code Quality Trend
          </h3>
          <ResponsiveContainer width="100%" height={260}>
            <AreaChart data={demoTrend}>
              <defs>
                <linearGradient id="scoreGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#6366f1" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.08)" />
              <XAxis dataKey="date" tick={{ fontSize: 12, fill: '#64748b' }} axisLine={false} />
              <YAxis domain={[0, 100]} tick={{ fontSize: 12, fill: '#64748b' }} axisLine={false} />
              <Tooltip content={<CustomTooltip />} />
              <Area type="monotone" dataKey="score" stroke="#6366f1" strokeWidth={2} fill="url(#scoreGrad)" name="Quality Score" />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {/* Severity Distribution */}
        <div className="chart-container">
          <h3 style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Zap size={18} style={{ color: 'var(--accent-warning)' }} />
            Issue Severity Distribution
          </h3>
          <div style={{ display: 'flex', alignItems: 'center', gap: '32px' }}>
            <ResponsiveContainer width="50%" height={260}>
              <PieChart>
                <Pie
                  data={demoSeverity}
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={90}
                  paddingAngle={4}
                  dataKey="value"
                  stroke="none"
                >
                  {demoSeverity.map((entry, i) => (
                    <Cell key={i} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip content={<CustomTooltip />} />
              </PieChart>
            </ResponsiveContainer>
            <div style={{ flex: 1 }}>
              {demoSeverity.map((s) => (
                <div key={s.name} style={{
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                  padding: '8px 0', borderBottom: '1px solid var(--border-subtle)',
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <div style={{ width: 10, height: 10, borderRadius: '50%', background: s.color }} />
                    <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>{s.name}</span>
                  </div>
                  <span style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-primary)' }}>{s.value}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Recent Reviews */}
      <div className="chart-container">
        <h3 style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Clock size={18} style={{ color: 'var(--accent-cyan)' }} />
          Recent Reviews
        </h3>
        <table className="data-table">
          <thead>
            <tr>
              <th>Pull Request</th>
              <th>Repository</th>
              <th>Quality Score</th>
              <th>Issues</th>
              <th>Time</th>
            </tr>
          </thead>
          <tbody>
            {demoReviewsRows()}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function demoReviewsRows() {
  return demoRecentReviews.map((r) => {
    const cls = r.score >= 80 ? 'excellent' : r.score >= 60 ? 'good' : r.score >= 40 ? 'fair' : 'poor'
    const color = { excellent: '#10b981', good: '#3b82f6', fair: '#f59e0b', poor: '#ef4444' }[cls]
    return (
      <tr key={r.id}>
        <td style={{ fontWeight: 500, color: 'var(--text-primary)' }}>{r.pr}</td>
        <td><span className="file-path">{r.repo}</span></td>
        <td>
          <span style={{ fontWeight: 700, color, fontSize: '0.9rem' }}>{r.score}</span>
          <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>/100</span>
        </td>
        <td>
          <span className={`badge ${r.issues > 6 ? 'high' : r.issues > 3 ? 'medium' : 'low'}`}>
            {r.issues} issues
          </span>
        </td>
        <td style={{ fontSize: '0.8rem' }}>{r.time}</td>
      </tr>
    )
  })
}
