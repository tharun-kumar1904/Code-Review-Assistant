import { BarChart3, Code2, Layers, Activity } from 'lucide-react'
import {
  LineChart, Line, AreaChart, Area, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar,
} from 'recharts'
import StatCard from '../components/StatCard'

const complexityTrend = [
  { month: 'Jan', complexity: 8.2, maintainability: 62 },
  { month: 'Feb', complexity: 9.1, maintainability: 58 },
  { month: 'Mar', complexity: 7.8, maintainability: 65 },
  { month: 'Apr', complexity: 7.2, maintainability: 68 },
  { month: 'May', complexity: 6.5, maintainability: 72 },
  { month: 'Jun', complexity: 6.8, maintainability: 70 },
  { month: 'Jul', complexity: 5.9, maintainability: 75 },
  { month: 'Aug', complexity: 5.4, maintainability: 78 },
]

const codeMetrics = [
  { metric: 'Readability', value: 82 },
  { metric: 'Testability', value: 68 },
  { metric: 'Reusability', value: 75 },
  { metric: 'Maintainability', value: 78 },
  { metric: 'Performance', value: 71 },
  { metric: 'Security', value: 65 },
]

const duplicationData = [
  { module: 'API', percentage: 3.2 },
  { module: 'Auth', percentage: 8.7 },
  { module: 'Models', percentage: 12.1 },
  { module: 'Utils', percentage: 5.4 },
  { module: 'Tests', percentage: 15.3 },
  { module: 'Config', percentage: 2.1 },
]

const locByLanguage = [
  { lang: 'Python', loc: 12400, color: '#3572A5' },
  { lang: 'JavaScript', loc: 8200, color: '#f1e05a' },
  { lang: 'TypeScript', loc: 5800, color: '#3178c6' },
  { lang: 'SQL', loc: 1200, color: '#e38c00' },
  { lang: 'YAML', loc: 800, color: '#cb171e' },
]

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div style={{
      background: 'rgba(17,24,39,0.95)', border: '1px solid var(--border-subtle)',
      borderRadius: '8px', padding: '12px', backdropFilter: 'blur(10px)',
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

export default function Insights() {
  return (
    <div>
      <div className="page-header">
        <h1>Repository Insights</h1>
        <p>Code quality metrics, complexity analysis, and health indicators</p>
      </div>

      {/* Stats */}
      <div className="stats-grid">
        <StatCard icon={BarChart3} label="Avg Complexity" value="5.4" trend="-0.5 this month" trendDir="down" color="purple" />
        <StatCard icon={Activity} label="Maintainability" value="78%" trend="+3% this month" color="green" />
        <StatCard icon={Layers} label="Code Duplication" value="6.2%" trend="-1.1% this month" trendDir="down" color="cyan" />
        <StatCard icon={Code2} label="Total LOC" value="28.4K" trend="+1.2K this month" color="blue" />
      </div>

      {/* Charts Row 1 */}
      <div className="grid-2" style={{ marginBottom: '24px' }}>
        {/* Complexity & Maintainability Trend */}
        <div className="chart-container">
          <h3 style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Activity size={18} style={{ color: 'var(--accent-primary)' }} />
            Complexity &amp; Maintainability Trend
          </h3>
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={complexityTrend}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.08)" />
              <XAxis dataKey="month" tick={{ fontSize: 12, fill: '#64748b' }} axisLine={false} />
              <YAxis tick={{ fontSize: 12, fill: '#64748b' }} axisLine={false} />
              <Tooltip content={<CustomTooltip />} />
              <Line type="monotone" dataKey="complexity" stroke="#ef4444" strokeWidth={2} dot={{ fill: '#ef4444', r: 3 }} name="Complexity" />
              <Line type="monotone" dataKey="maintainability" stroke="#10b981" strokeWidth={2} dot={{ fill: '#10b981', r: 3 }} name="Maintainability" />
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* Radar Chart */}
        <div className="chart-container">
          <h3 style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <BarChart3 size={18} style={{ color: 'var(--accent-secondary)' }} />
            Code Health Radar
          </h3>
          <ResponsiveContainer width="100%" height={260}>
            <RadarChart cx="50%" cy="50%" outerRadius="75%" data={codeMetrics}>
              <PolarGrid stroke="rgba(148,163,184,0.12)" />
              <PolarAngleAxis dataKey="metric" tick={{ fontSize: 11, fill: '#94a3b8' }} />
              <PolarRadiusAxis angle={30} domain={[0, 100]} tick={{ fontSize: 10, fill: '#64748b' }} />
              <Radar name="Score" dataKey="value" stroke="#6366f1" fill="#6366f1" fillOpacity={0.2} strokeWidth={2} />
            </RadarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Charts Row 2 */}
      <div className="grid-2">
        {/* Duplication by Module */}
        <div className="chart-container">
          <h3 style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Layers size={18} style={{ color: 'var(--accent-warning)' }} />
            Code Duplication by Module
          </h3>
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={duplicationData} barSize={32}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.08)" />
              <XAxis dataKey="module" tick={{ fontSize: 12, fill: '#64748b' }} axisLine={false} />
              <YAxis tick={{ fontSize: 12, fill: '#64748b' }} axisLine={false} unit="%" />
              <Tooltip content={<CustomTooltip />} />
              <Bar dataKey="percentage" fill="#f59e0b" radius={[6, 6, 0, 0]} name="Duplication %" />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* LOC by Language */}
        <div className="chart-container">
          <h3 style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Code2 size={18} style={{ color: 'var(--accent-cyan)' }} />
            Lines of Code by Language
          </h3>
          <div style={{ padding: '12px 0' }}>
            {locByLanguage.map(l => (
              <div key={l.lang} style={{ marginBottom: '16px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px', fontSize: '0.8rem' }}>
                  <span style={{ color: 'var(--text-secondary)', fontWeight: 500 }}>{l.lang}</span>
                  <span style={{ color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }}>{l.loc.toLocaleString()}</span>
                </div>
                <div style={{
                  width: '100%', height: '8px', background: 'rgba(148,163,184,0.08)',
                  borderRadius: '4px', overflow: 'hidden',
                }}>
                  <div style={{
                    width: `${(l.loc / 12400) * 100}%`, height: '100%',
                    background: l.color, borderRadius: '4px',
                    transition: 'width 1s ease',
                  }} />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
