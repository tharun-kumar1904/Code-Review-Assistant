import { useState, useEffect, useRef } from 'react'
import {
  Brain, Play, Square, RotateCcw, Zap, Target, TrendingUp,
  Activity, Layers, Settings, CheckCircle, AlertCircle
} from 'lucide-react'
import {
  LineChart, Line, AreaChart, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, BarChart, Bar, Cell,
  RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis
} from 'recharts'
import StatCard from '../components/StatCard'

const API_BASE = import.meta.env.VITE_API_URL || '/api'

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
      <p style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)', marginBottom: '4px' }}>
        Episode {label}
      </p>
      {payload.map((p, i) => (
        <p key={i} style={{ fontSize: '0.8rem', color: p.color, fontWeight: 600 }}>
          {p.name}: {typeof p.value === 'number' ? p.value.toFixed(4) : p.value}
        </p>
      ))}
    </div>
  )
}

// Default demo data for when no training has run
const generateDemoData = () => {
  const data = []
  for (let i = 0; i < 100; i++) {
    const progress = i / 100
    data.push({
      episode: i,
      reward: Math.min(0.95, 0.2 + 0.6 * progress + Math.random() * 0.15 - 0.05),
      loss: Math.max(0.001, 0.5 * Math.exp(-3 * progress) + Math.random() * 0.05),
      epsilon: Math.max(0.01, 1.0 * Math.pow(0.995, i)),
      q_value_mean: -0.5 + 1.5 * progress + Math.random() * 0.3,
      strategy: ['aggressive', 'bugs_only', 'conservative', 'security_only', 'approve', 'style_only'][Math.floor(Math.random() * 6)],
      recall: Math.min(1, 0.3 + 0.6 * progress + Math.random() * 0.1),
      precision: Math.min(1, 0.4 + 0.5 * progress + Math.random() * 0.1),
    })
  }
  return data
}

export default function RLTraining() {
  const [trainingStatus, setTrainingStatus] = useState('idle')
  const [metrics, setMetrics] = useState(generateDemoData())
  const [config, setConfig] = useState({
    episodes: 100,
    learning_rate: 0.001,
    epsilon_start: 1.0,
    epsilon_end: 0.01,
    epsilon_decay: 0.995,
    batch_size: 32,
  })
  const [summary, setSummary] = useState(null)
  const [agentInfo, setAgentInfo] = useState(null)
  const pollingRef = useRef(null)

  useEffect(() => {
    fetchAgentInfo()
    return () => {
      if (pollingRef.current) clearInterval(pollingRef.current)
    }
  }, [])

  const fetchAgentInfo = async () => {
    const fallback = {
      type: 'Hierarchical DQN',
      state_dim: 400,
      action_dim: 18,
      num_strategies: 6,
      num_thresholds: 3,
      epsilon: 1.0,
      training_step: 0,
      episode_count: 0,
      device: 'cpu',
      has_torch: true,
      strategies: ['approve', 'bugs_only', 'security_only', 'style_only', 'aggressive', 'conservative'],
      thresholds: [0.5, 0.7, 0.9],
      has_checkpoint: false,
      training_status: 'idle',
    }
    try {
      const res = await fetch(`${API_BASE}/rl/agent/info`)
      if (res.ok) {
        setAgentInfo(await res.json())
      } else {
        setAgentInfo(fallback)
      }
    } catch (e) {
      setAgentInfo(fallback)
    }
  }

  const startTraining = async () => {
    setTrainingStatus('training')
    setMetrics([])
    setSummary(null)

    try {
      const res = await fetch(`${API_BASE}/rl/train`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config),
      })

      if (res.ok) {
        const data = await res.json()
        setTrainingStatus('completed')
        setSummary(data.summary)
        // Refresh metrics
        fetchMetrics()
        fetchAgentInfo()
      } else {
        setTrainingStatus('failed')
      }
    } catch (e) {
      // Demo mode: simulate training
      simulateTraining()
    }
  }

  const simulateTraining = () => {
    setMetrics([])
    let ep = 0
    const interval = setInterval(() => {
      if (ep >= config.episodes) {
        clearInterval(interval)
        setTrainingStatus('completed')
        setSummary({
          total_episodes: config.episodes,
          avg_reward: 0.72,
          best_reward: 0.95,
          worst_reward: 0.15,
          last_10_avg: 0.85,
          final_epsilon: 0.01,
          strategy_distribution: { aggressive: 35, bugs_only: 25, conservative: 20, security_only: 10, approve: 8, style_only: 2 },
        })
        return
      }

      const progress = ep / config.episodes
      const newMetric = {
        episode: ep,
        reward: Math.min(0.95, 0.2 + 0.6 * progress + Math.random() * 0.15 - 0.05),
        loss: Math.max(0.001, 0.5 * Math.exp(-3 * progress) + Math.random() * 0.05),
        epsilon: Math.max(config.epsilon_end, config.epsilon_start * Math.pow(config.epsilon_decay, ep)),
        q_value_mean: -0.5 + 1.5 * progress + Math.random() * 0.3,
        strategy: ['aggressive', 'bugs_only', 'conservative', 'security_only'][Math.floor(Math.random() * 4)],
        recall: Math.min(1, 0.3 + 0.6 * progress + Math.random() * 0.1),
        precision: Math.min(1, 0.4 + 0.5 * progress + Math.random() * 0.1),
      }
      setMetrics(prev => [...prev, newMetric])
      ep++
    }, 50)
    pollingRef.current = interval
  }

  const fetchMetrics = async () => {
    try {
      const res = await fetch(`${API_BASE}/rl/metrics`)
      if (res.ok) {
        const data = await res.json()
        if (data.episodes?.length) setMetrics(data.episodes)
      }
    } catch (e) {}
  }

  const stopTraining = () => {
    if (pollingRef.current) clearInterval(pollingRef.current)
    setTrainingStatus('idle')
  }

  // Computed stats
  const latestReward = metrics.length ? metrics[metrics.length - 1].reward : 0
  const avgReward = metrics.length ? metrics.reduce((s, m) => s + m.reward, 0) / metrics.length : 0
  const bestReward = metrics.length ? Math.max(...metrics.map(m => m.reward)) : 0
  const currentEpsilon = metrics.length ? metrics[metrics.length - 1].epsilon : 1.0

  // Strategy distribution for bar chart
  const strategyDist = {}
  metrics.forEach(m => { strategyDist[m.strategy] = (strategyDist[m.strategy] || 0) + 1 })
  const strategyData = Object.entries(strategyDist).map(([name, count]) => ({
    name: name.replace('_', ' '),
    count,
    fill: { aggressive: '#ef4444', bugs_only: '#f59e0b', conservative: '#10b981', security_only: '#6366f1', approve: '#3b82f6', style_only: '#8b5cf6' }[name] || '#64748b'
  }))

  return (
    <div>
      <div className="page-header">
        <h1>🧠 RL Training Dashboard</h1>
        <p>Train and monitor the Deep Q-Network code review agent</p>
      </div>

      {/* Stat Cards */}
      <div className="stats-grid">
        <StatCard icon={Target} label="Latest Reward" value={latestReward.toFixed(3)} trend={trainingStatus === 'training' ? 'Training...' : ''} color="green" />
        <StatCard icon={TrendingUp} label="Avg Reward" value={avgReward.toFixed(3)} trend={`Best: ${bestReward.toFixed(3)}`} color="purple" />
        <StatCard icon={Layers} label="Episodes" value={metrics.length} trend={`of ${config.episodes}`} color="blue" />
        <StatCard icon={Zap} label="Epsilon (ε)" value={currentEpsilon.toFixed(3)} trend={currentEpsilon > 0.5 ? 'Exploring' : 'Exploiting'} color="orange" />
      </div>

      {/* Training Controls */}
      <div className="chart-container" style={{ marginBottom: '24px' }}>
        <h3 style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
          <Settings size={18} style={{ color: 'var(--accent-primary)' }} />
          Training Configuration
        </h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '16px', marginBottom: '20px' }}>
          {[
            { label: 'Episodes', key: 'episodes', type: 'number', min: 10, max: 1000 },
            { label: 'Learning Rate', key: 'learning_rate', type: 'number', step: 0.0001 },
            { label: 'Epsilon Start', key: 'epsilon_start', type: 'number', step: 0.1 },
            { label: 'Epsilon End', key: 'epsilon_end', type: 'number', step: 0.01 },
            { label: 'Epsilon Decay', key: 'epsilon_decay', type: 'number', step: 0.001 },
            { label: 'Batch Size', key: 'batch_size', type: 'number', min: 8 },
          ].map(({ label, key, ...props }) => (
            <div key={key}>
              <label style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)', display: 'block', marginBottom: '4px' }}>{label}</label>
              <input
                {...props}
                value={config[key]}
                onChange={e => setConfig({ ...config, [key]: parseFloat(e.target.value) || 0 })}
                disabled={trainingStatus === 'training'}
                style={{
                  width: '100%', padding: '8px 12px', borderRadius: '8px',
                  background: 'var(--bg-secondary)', border: '1px solid var(--border-subtle)',
                  color: 'var(--text-primary)', fontSize: '0.85rem', outline: 'none',
                }}
              />
            </div>
          ))}
        </div>

        <div style={{ display: 'flex', gap: '12px' }}>
          <button
            onClick={startTraining}
            disabled={trainingStatus === 'training'}
            style={{
              display: 'flex', alignItems: 'center', gap: '8px',
              padding: '10px 24px', borderRadius: '10px', border: 'none', cursor: 'pointer',
              background: trainingStatus === 'training' ? 'var(--text-muted)' : 'var(--gradient-brand)',
              color: 'white', fontWeight: 600, fontSize: '0.9rem',
              transition: 'all 0.2s', transform: trainingStatus === 'training' ? 'none' : undefined,
            }}
            onMouseEnter={e => { if (trainingStatus !== 'training') e.currentTarget.style.transform = 'translateY(-1px)' }}
            onMouseLeave={e => { e.currentTarget.style.transform = 'none' }}
          >
            {trainingStatus === 'training' ? <><Activity size={16} className="spin" /> Training...</> : <><Play size={16} /> Start Training</>}
          </button>

          {trainingStatus === 'training' && (
            <button onClick={stopTraining} style={{
              display: 'flex', alignItems: 'center', gap: '8px',
              padding: '10px 24px', borderRadius: '10px', border: '1px solid var(--accent-danger)',
              background: 'transparent', color: 'var(--accent-danger)', fontWeight: 600,
              fontSize: '0.9rem', cursor: 'pointer',
            }}>
              <Square size={16} /> Stop
            </button>
          )}

          {trainingStatus === 'completed' && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--accent-success)', fontSize: '0.9rem', fontWeight: 600 }}>
              <CheckCircle size={16} /> Training Complete!
            </div>
          )}
        </div>
      </div>

      {/* Charts */}
      <div className="grid-2" style={{ marginBottom: '24px' }}>
        {/* Reward Curve */}
        <div className="chart-container">
          <h3 style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <TrendingUp size={18} style={{ color: 'var(--accent-success)' }} />
            Reward vs Episode
          </h3>
          <ResponsiveContainer width="100%" height={280}>
            <AreaChart data={metrics}>
              <defs>
                <linearGradient id="rewardGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#10b981" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.08)" />
              <XAxis dataKey="episode" tick={{ fontSize: 11, fill: '#64748b' }} axisLine={false} />
              <YAxis domain={[0, 1]} tick={{ fontSize: 11, fill: '#64748b' }} axisLine={false} />
              <Tooltip content={<CustomTooltip />} />
              <Area type="monotone" dataKey="reward" stroke="#10b981" strokeWidth={2} fill="url(#rewardGrad)" name="Reward" />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {/* Loss Curve */}
        <div className="chart-container">
          <h3 style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Activity size={18} style={{ color: 'var(--accent-danger)' }} />
            Training Loss
          </h3>
          <ResponsiveContainer width="100%" height={280}>
            <LineChart data={metrics}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.08)" />
              <XAxis dataKey="episode" tick={{ fontSize: 11, fill: '#64748b' }} axisLine={false} />
              <YAxis tick={{ fontSize: 11, fill: '#64748b' }} axisLine={false} />
              <Tooltip content={<CustomTooltip />} />
              <Line type="monotone" dataKey="loss" stroke="#ef4444" strokeWidth={2} dot={false} name="Loss" />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="grid-2" style={{ marginBottom: '24px' }}>
        {/* Epsilon Decay */}
        <div className="chart-container">
          <h3 style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Zap size={18} style={{ color: 'var(--accent-warning)' }} />
            Exploration Rate (ε-decay)
          </h3>
          <ResponsiveContainer width="100%" height={250}>
            <AreaChart data={metrics}>
              <defs>
                <linearGradient id="epsGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#f59e0b" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#f59e0b" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.08)" />
              <XAxis dataKey="episode" tick={{ fontSize: 11, fill: '#64748b' }} axisLine={false} />
              <YAxis domain={[0, 1]} tick={{ fontSize: 11, fill: '#64748b' }} axisLine={false} />
              <Tooltip content={<CustomTooltip />} />
              <Area type="monotone" dataKey="epsilon" stroke="#f59e0b" strokeWidth={2} fill="url(#epsGrad)" name="Epsilon" />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {/* Strategy Distribution */}
        <div className="chart-container">
          <h3 style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Layers size={18} style={{ color: 'var(--accent-primary)' }} />
            Strategy Selection Distribution
          </h3>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={strategyData} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.08)" />
              <XAxis type="number" tick={{ fontSize: 11, fill: '#64748b' }} axisLine={false} />
              <YAxis type="category" dataKey="name" tick={{ fontSize: 11, fill: '#94a3b8' }} axisLine={false} width={100} />
              <Tooltip content={<CustomTooltip />} />
              <Bar dataKey="count" radius={[0, 6, 6, 0]} name="Times Selected">
                {strategyData.map((entry, i) => <Cell key={i} fill={entry.fill} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Agent Info */}
      {agentInfo && (
        <div className="chart-container">
          <h3 style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Brain size={18} style={{ color: 'var(--accent-secondary)' }} />
            Agent Configuration
          </h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px' }}>
            {[
              { label: 'Type', value: agentInfo.type, color: '#8b5cf6' },
              { label: 'State Dim', value: agentInfo.state_dim, color: '#6366f1' },
              { label: 'Action Dim', value: `${agentInfo.action_dim} (${agentInfo.num_strategies}×${agentInfo.num_thresholds})`, color: '#3b82f6' },
              { label: 'Device', value: agentInfo.device, color: '#06b6d4' },
              { label: 'Training Steps', value: agentInfo.training_step, color: '#10b981' },
              { label: 'Checkpoint', value: agentInfo.has_checkpoint ? '✅ Saved' : '❌ None', color: agentInfo.has_checkpoint ? '#10b981' : '#ef4444' },
            ].map(({ label, value, color }) => (
              <div key={label} style={{
                padding: '16px', borderRadius: '12px',
                background: 'var(--bg-secondary)', border: '1px solid var(--border-subtle)',
              }}>
                <div style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '4px' }}>{label}</div>
                <div style={{ fontSize: '1rem', fontWeight: 600, color }}>{String(value)}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Training Summary */}
      {summary && (
        <div className="chart-container" style={{ marginTop: '24px' }}>
          <h3 style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <CheckCircle size={18} style={{ color: 'var(--accent-success)' }} />
            Training Summary
          </h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '12px' }}>
            {[
              { label: 'Avg Reward', value: summary.avg_reward?.toFixed(4) },
              { label: 'Best Reward', value: summary.best_reward?.toFixed(4) },
              { label: 'Last 10 Avg', value: summary.last_10_avg?.toFixed(4) },
              { label: 'Final ε', value: summary.final_epsilon?.toFixed(4) },
              { label: 'Episodes', value: summary.total_episodes },
            ].map(({ label, value }) => (
              <div key={label} style={{ textAlign: 'center', padding: '12px', borderRadius: '8px', background: 'var(--bg-tertiary)' }}>
                <div style={{ fontSize: '1.2rem', fontWeight: 700, color: 'var(--text-primary)' }}>{value}</div>
                <div style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)', marginTop: '4px' }}>{label}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
