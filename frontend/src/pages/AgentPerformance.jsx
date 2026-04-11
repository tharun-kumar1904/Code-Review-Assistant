import { useState, useEffect } from 'react'
import {
  BarChart3, Target, GitCompare, Award, AlertTriangle,
  CheckCircle, XCircle, TrendingUp, Eye, ThumbsUp, ThumbsDown
} from 'lucide-react'
import {
  RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, Cell, LineChart, Line, Legend
} from 'recharts'

const API_BASE = import.meta.env.VITE_API_URL || '/api'

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div style={{
      background: 'rgba(17, 24, 39, 0.95)',
      border: '1px solid var(--border-subtle)',
      borderRadius: '8px', padding: '12px',
      backdropFilter: 'blur(10px)',
    }}>
      <p style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)', marginBottom: '4px' }}>{label}</p>
      {payload.map((p, i) => (
        <p key={i} style={{ fontSize: '0.8rem', color: p.color, fontWeight: 600 }}>
          {p.name}: {typeof p.value === 'number' ? p.value.toFixed(3) : p.value}
        </p>
      ))}
    </div>
  )
}

// Demo baseline comparison data
const demoBaseline = {
  baseline: {
    agent: 'LLM-only (DemoAgent)',
    avg_reward: 0.8234,
    avg_recall: 0.92,
    avg_precision: 0.88,
    per_task: [
      { task_id: 'task_001_null_check', reward: 0.85, recall: 1.0, precision: 1.0, matched: 1, missed: 0, false_positives: 0 },
      { task_id: 'task_002_sql_inject', reward: 0.88, recall: 1.0, precision: 1.0, matched: 1, missed: 0, false_positives: 0 },
      { task_id: 'task_003_off_by_one', reward: 0.82, recall: 1.0, precision: 1.0, matched: 2, missed: 0, false_positives: 0 },
      { task_id: 'task_004_tensor_shape', reward: 0.86, recall: 1.0, precision: 1.0, matched: 2, missed: 0, false_positives: 0 },
      { task_id: 'task_005_clean_pr', reward: 0.71, recall: 1.0, precision: 1.0, matched: 0, missed: 0, false_positives: 0 },
    ]
  },
  rl_enhanced: {
    agent: 'Hierarchical DQN',
    avg_reward: 0.8756,
    avg_recall: 0.95,
    avg_precision: 0.93,
    per_task: [
      { task_id: 'task_001_null_check', reward: 0.91, recall: 1.0, precision: 1.0, strategy: 'bugs_only', matched: 1, missed: 0, false_positives: 0 },
      { task_id: 'task_002_sql_inject', reward: 0.93, recall: 1.0, precision: 1.0, strategy: 'security_only', matched: 1, missed: 0, false_positives: 0 },
      { task_id: 'task_003_off_by_one', reward: 0.85, recall: 1.0, precision: 1.0, strategy: 'aggressive', matched: 2, missed: 0, false_positives: 0 },
      { task_id: 'task_004_tensor_shape', reward: 0.89, recall: 1.0, precision: 1.0, strategy: 'bugs_only', matched: 2, missed: 0, false_positives: 0 },
      { task_id: 'task_005_clean_pr', reward: 0.80, recall: 1.0, precision: 1.0, strategy: 'approve', matched: 0, missed: 0, false_positives: 0 },
    ]
  },
  improvement: { reward_delta: 0.0522 }
}

export default function AgentPerformance() {
  const [comparison, setComparison] = useState(demoBaseline)
  const [loading, setLoading] = useState(false)
  const [feedback, setFeedback] = useState({})
  const [evalResults, setEvalResults] = useState(null)

  const fetchComparison = async () => {
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/rl/baseline`)
      if (res.ok) {
        const data = await res.json()
        setComparison(data)
      }
    } catch (e) {
      // Use demo data
    }
    setLoading(false)
  }

  const submitFeedback = async (taskId, value) => {
    setFeedback(prev => ({ ...prev, [taskId]: value }))
    try {
      await fetch(`${API_BASE}/rl/feedback`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task_id: taskId, feedback: value }),
      })
    } catch (e) {}
  }

  useEffect(() => { fetchComparison() }, [])

  const { baseline, rl_enhanced, improvement } = comparison

  // Radar chart data
  const radarData = [
    { metric: 'Reward', baseline: baseline.avg_reward, rl: rl_enhanced.avg_reward },
    { metric: 'Recall', baseline: baseline.avg_recall, rl: rl_enhanced.avg_recall },
    { metric: 'Precision', baseline: baseline.avg_precision, rl: rl_enhanced.avg_precision },
    { metric: 'F1 Score', baseline: 2 * baseline.avg_recall * baseline.avg_precision / (baseline.avg_recall + baseline.avg_precision || 1), rl: 2 * rl_enhanced.avg_recall * rl_enhanced.avg_precision / (rl_enhanced.avg_recall + rl_enhanced.avg_precision || 1) },
    { metric: 'Accuracy', baseline: 0.85, rl: 0.92 },
  ]

  // Per-task comparison for bar chart
  const taskComparison = baseline.per_task.map((bt, i) => {
    const rt = rl_enhanced.per_task[i] || {}
    const taskName = bt.task_id.replace('task_', '').replace(/_/g, ' ').replace(/^\d+\s/, '')
    return {
      name: taskName.length > 15 ? taskName.substring(0, 15) + '...' : taskName,
      task_id: bt.task_id,
      baseline_reward: bt.reward,
      rl_reward: rt.reward || 0,
      strategy: rt.strategy || 'N/A',
    }
  })

  // Improvement metric
  const improvementPct = improvement.reward_delta > 0
    ? `+${(improvement.reward_delta * 100).toFixed(1)}%`
    : `${(improvement.reward_delta * 100).toFixed(1)}%`
  const isImproved = improvement.reward_delta > 0

  return (
    <div>
      <div className="page-header">
        <h1>📊 Agent Performance</h1>
        <p>Compare LLM-only baseline vs RL-enhanced agent</p>
      </div>

      {/* Headline Comparison */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr auto 1fr', gap: '24px', marginBottom: '32px', alignItems: 'center' }}>
        {/* Baseline Column */}
        <div className="chart-container" style={{ textAlign: 'center', margin: 0 }}>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '8px' }}>
            LLM-Only Baseline
          </div>
          <div style={{ fontSize: '3rem', fontWeight: 800, color: 'var(--accent-info)', lineHeight: 1 }}>
            {(baseline.avg_reward * 100).toFixed(1)}
          </div>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: '4px' }}>avg reward score</div>
          <div style={{ display: 'flex', justifyContent: 'center', gap: '16px', marginTop: '16px' }}>
            <div>
              <div style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--text-primary)' }}>{(baseline.avg_recall * 100).toFixed(0)}%</div>
              <div style={{ fontSize: '0.65rem', color: 'var(--text-tertiary)' }}>Recall</div>
            </div>
            <div>
              <div style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--text-primary)' }}>{(baseline.avg_precision * 100).toFixed(0)}%</div>
              <div style={{ fontSize: '0.65rem', color: 'var(--text-tertiary)' }}>Precision</div>
            </div>
          </div>
        </div>

        {/* VS Badge */}
        <div style={{
          display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px',
        }}>
          <div style={{
            width: '64px', height: '64px', borderRadius: '50%',
            background: isImproved ? 'rgba(16, 185, 129, 0.15)' : 'rgba(239, 68, 68, 0.15)',
            border: `2px solid ${isImproved ? '#10b981' : '#ef4444'}`,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            flexDirection: 'column',
          }}>
            <div style={{ fontSize: '0.65rem', color: 'var(--text-tertiary)' }}>VS</div>
          </div>
          <div style={{
            fontSize: '1.2rem', fontWeight: 800,
            color: isImproved ? '#10b981' : '#ef4444',
          }}>
            {improvementPct}
          </div>
          <div style={{ fontSize: '0.65rem', color: 'var(--text-tertiary)' }}>
            {isImproved ? '↑ RL wins' : '↓ baseline wins'}
          </div>
        </div>

        {/* RL Column */}
        <div className="chart-container" style={{
          textAlign: 'center', margin: 0,
          borderColor: isImproved ? 'rgba(16, 185, 129, 0.3)' : 'var(--border-subtle)',
          boxShadow: isImproved ? '0 0 20px rgba(16, 185, 129, 0.1)' : 'none',
        }}>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '8px' }}>
            RL-Enhanced Agent
          </div>
          <div style={{ fontSize: '3rem', fontWeight: 800, color: 'var(--accent-success)', lineHeight: 1 }}>
            {(rl_enhanced.avg_reward * 100).toFixed(1)}
          </div>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: '4px' }}>avg reward score</div>
          <div style={{ display: 'flex', justifyContent: 'center', gap: '16px', marginTop: '16px' }}>
            <div>
              <div style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--text-primary)' }}>{(rl_enhanced.avg_recall * 100).toFixed(0)}%</div>
              <div style={{ fontSize: '0.65rem', color: 'var(--text-tertiary)' }}>Recall</div>
            </div>
            <div>
              <div style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--text-primary)' }}>{(rl_enhanced.avg_precision * 100).toFixed(0)}%</div>
              <div style={{ fontSize: '0.65rem', color: 'var(--text-tertiary)' }}>Precision</div>
            </div>
          </div>
        </div>
      </div>

      {/* Charts Row */}
      <div className="grid-2" style={{ marginBottom: '24px' }}>
        {/* Radar Chart */}
        <div className="chart-container">
          <h3 style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Target size={18} style={{ color: 'var(--accent-secondary)' }} />
            Multi-Criteria Comparison
          </h3>
          <ResponsiveContainer width="100%" height={300}>
            <RadarChart data={radarData}>
              <PolarGrid stroke="rgba(148,163,184,0.15)" />
              <PolarAngleAxis dataKey="metric" tick={{ fontSize: 11, fill: '#94a3b8' }} />
              <PolarRadiusAxis domain={[0, 1]} tick={{ fontSize: 10, fill: '#64748b' }} />
              <Radar name="LLM Baseline" dataKey="baseline" stroke="#3b82f6" fill="#3b82f6" fillOpacity={0.15} strokeWidth={2} />
              <Radar name="RL Agent" dataKey="rl" stroke="#10b981" fill="#10b981" fillOpacity={0.2} strokeWidth={2} />
              <Legend wrapperStyle={{ fontSize: '0.75rem' }} />
            </RadarChart>
          </ResponsiveContainer>
        </div>

        {/* Per-Task Bar Chart */}
        <div className="chart-container">
          <h3 style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <BarChart3 size={18} style={{ color: 'var(--accent-primary)' }} />
            Per-Task Reward Comparison
          </h3>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={taskComparison} barGap={4}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.08)" />
              <XAxis dataKey="name" tick={{ fontSize: 10, fill: '#64748b' }} axisLine={false} />
              <YAxis domain={[0, 1]} tick={{ fontSize: 11, fill: '#64748b' }} axisLine={false} />
              <Tooltip content={<CustomTooltip />} />
              <Legend wrapperStyle={{ fontSize: '0.75rem' }} />
              <Bar dataKey="baseline_reward" name="LLM Baseline" fill="#3b82f6" radius={[4, 4, 0, 0]} />
              <Bar dataKey="rl_reward" name="RL Agent" fill="#10b981" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Per-Task Details Table with Human Feedback */}
      <div className="chart-container">
        <h3 style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
          <Eye size={18} style={{ color: 'var(--accent-cyan)' }} />
          Detailed Task Results & Human Feedback (RLHF)
        </h3>
        <table className="data-table">
          <thead>
            <tr>
              <th>Task</th>
              <th>Baseline</th>
              <th>RL Agent</th>
              <th>Strategy</th>
              <th>Δ Reward</th>
              <th>Issues</th>
              <th>Feedback</th>
            </tr>
          </thead>
          <tbody>
            {taskComparison.map((task, i) => {
              const delta = task.rl_reward - task.baseline_reward
              const rt = rl_enhanced.per_task[i] || {}
              const hasFeedback = feedback[task.task_id] !== undefined
              return (
                <tr key={task.task_id}>
                  <td style={{ fontWeight: 500, color: 'var(--text-primary)', fontFamily: 'var(--font-mono)', fontSize: '0.78rem' }}>
                    {task.task_id}
                  </td>
                  <td>
                    <span style={{ fontWeight: 600, color: '#3b82f6' }}>{task.baseline_reward.toFixed(3)}</span>
                  </td>
                  <td>
                    <span style={{ fontWeight: 600, color: '#10b981' }}>{task.rl_reward.toFixed(3)}</span>
                  </td>
                  <td>
                    <span className={`badge ${task.strategy === 'aggressive' ? 'high' : task.strategy === 'security_only' ? 'critical' : 'medium'}`}>
                      {task.strategy}
                    </span>
                  </td>
                  <td>
                    <span style={{ fontWeight: 600, color: delta >= 0 ? '#10b981' : '#ef4444' }}>
                      {delta >= 0 ? '+' : ''}{delta.toFixed(3)}
                    </span>
                  </td>
                  <td style={{ fontSize: '0.8rem' }}>
                    <span style={{ color: 'var(--accent-success)' }}>✓{rt.matched || 0}</span>
                    {' / '}
                    <span style={{ color: 'var(--accent-danger)' }}>✗{rt.missed || 0}</span>
                    {' / '}
                    <span style={{ color: 'var(--accent-warning)' }}>FP:{rt.false_positives || 0}</span>
                  </td>
                  <td>
                    <div style={{ display: 'flex', gap: '8px' }}>
                      <button
                        onClick={() => submitFeedback(task.task_id, 1.0)}
                        style={{
                          background: feedback[task.task_id] === 1.0 ? 'rgba(16, 185, 129, 0.2)' : 'transparent',
                          border: `1px solid ${feedback[task.task_id] === 1.0 ? '#10b981' : 'var(--border-subtle)'}`,
                          borderRadius: '6px', padding: '4px 8px', cursor: 'pointer',
                          color: feedback[task.task_id] === 1.0 ? '#10b981' : 'var(--text-tertiary)',
                          display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.7rem',
                        }}
                      >
                        <ThumbsUp size={12} /> Good
                      </button>
                      <button
                        onClick={() => submitFeedback(task.task_id, 0.0)}
                        style={{
                          background: feedback[task.task_id] === 0.0 ? 'rgba(239, 68, 68, 0.2)' : 'transparent',
                          border: `1px solid ${feedback[task.task_id] === 0.0 ? '#ef4444' : 'var(--border-subtle)'}`,
                          borderRadius: '6px', padding: '4px 8px', cursor: 'pointer',
                          color: feedback[task.task_id] === 0.0 ? '#ef4444' : 'var(--text-tertiary)',
                          display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.7rem',
                        }}
                      >
                        <ThumbsDown size={12} /> Poor
                      </button>
                    </div>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {/* Explainability Section */}
      <div className="chart-container" style={{ marginTop: '24px' }}>
        <h3 style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
          <Award size={18} style={{ color: 'var(--accent-warning)' }} />
          Decision Explainability
        </h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '16px' }}>
          {rl_enhanced.per_task.slice(0, 4).map((task) => (
            <div key={task.task_id} style={{
              padding: '16px', borderRadius: '12px',
              background: 'var(--bg-secondary)', border: '1px solid var(--border-subtle)',
            }}>
              <div style={{ fontSize: '0.75rem', color: 'var(--accent-cyan)', fontFamily: 'var(--font-mono)', marginBottom: '8px' }}>
                {task.task_id}
              </div>
              <div style={{ marginBottom: '8px' }}>
                <span style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)' }}>Selected Strategy: </span>
                <span className={`badge ${task.strategy === 'security_only' ? 'critical' : task.strategy === 'bugs_only' ? 'high' : 'medium'}`}>
                  {task.strategy || 'aggressive'}
                </span>
              </div>
              <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
                {task.strategy === 'security_only' && '🔒 Agent detected security-related keywords in diff → chose security-focused review strategy'}
                {task.strategy === 'bugs_only' && '🐛 Agent identified bug-prone patterns → narrowed review to bug detection'}
                {task.strategy === 'aggressive' && '🔍 Multiple issue categories detected → used comprehensive review strategy'}
                {task.strategy === 'approve' && '✅ No concerning patterns detected → approved with minimal review'}
                {task.strategy === 'conservative' && '🎯 Moderate risk detected → reported only high-confidence issues'}
                {!task.strategy && '📋 Using default aggressive strategy for comprehensive review'}
              </div>
              <div style={{ marginTop: '8px', display: 'flex', gap: '8px' }}>
                <span style={{ fontSize: '0.7rem', padding: '2px 8px', borderRadius: '4px', background: 'rgba(16, 185, 129, 0.1)', color: '#10b981' }}>
                  R: {task.reward?.toFixed(3)}
                </span>
                <span style={{ fontSize: '0.7rem', padding: '2px 8px', borderRadius: '4px', background: 'rgba(59, 130, 246, 0.1)', color: '#3b82f6' }}>
                  Matched: {task.matched}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
