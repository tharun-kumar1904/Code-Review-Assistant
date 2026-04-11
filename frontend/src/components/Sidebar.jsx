import { NavLink, useLocation } from 'react-router-dom'
import {
  LayoutDashboard, GitPullRequest, ShieldAlert,
  BarChart3, Bot, Settings, Zap, Brain, Award
} from 'lucide-react'

const navItems = [
  { path: '/', label: 'Dashboard', icon: LayoutDashboard },
  { path: '/reviews', label: 'Reviews', icon: GitPullRequest },
  { path: '/security', label: 'Security', icon: ShieldAlert },
  { path: '/insights', label: 'Insights', icon: BarChart3 },
]

const rlNavItems = [
  { path: '/rl-training', label: 'RL Training', icon: Brain },
  { path: '/agent-performance', label: 'Agent Performance', icon: Award },
]

export default function Sidebar() {
  const location = useLocation()

  return (
    <aside style={{
      width: 'var(--sidebar-width)',
      height: '100vh',
      position: 'fixed',
      left: 0,
      top: 0,
      background: 'rgba(10, 14, 26, 0.95)',
      borderRight: '1px solid var(--border-subtle)',
      backdropFilter: 'blur(20px)',
      display: 'flex',
      flexDirection: 'column',
      zIndex: 100,
    }}>
      {/* Brand */}
      <div style={{
        padding: '24px 20px',
        borderBottom: '1px solid var(--border-subtle)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{
            width: '40px',
            height: '40px',
            borderRadius: 'var(--radius-md)',
            background: 'var(--gradient-brand)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: '0 0 20px rgba(99, 102, 241, 0.3)',
          }}>
            <Bot size={22} color="white" />
          </div>
          <div>
            <h1 style={{
              fontSize: '0.95rem',
              fontWeight: 700,
              color: 'var(--text-primary)',
              lineHeight: 1.2,
            }}>AI Code Review</h1>
            <p style={{
              fontSize: '0.7rem',
              color: 'var(--text-tertiary)',
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
            }}>
              <Zap size={10} /> Intelligent PR Reviewer
            </p>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav style={{ padding: '16px 12px', flex: 1 }}>
        <p style={{
          fontSize: '0.65rem',
          fontWeight: 600,
          color: 'var(--text-muted)',
          textTransform: 'uppercase',
          letterSpacing: '0.08em',
          padding: '0 8px',
          marginBottom: '8px',
        }}>Navigation</p>

        {navItems.map(({ path, label, icon: Icon }) => {
          const isActive = location.pathname === path
          return (
            <NavLink
              key={path}
              to={path}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '12px',
                padding: '10px 14px',
                borderRadius: 'var(--radius-sm)',
                fontSize: '0.85rem',
                fontWeight: isActive ? 600 : 400,
                color: isActive ? 'var(--text-primary)' : 'var(--text-secondary)',
                background: isActive ? 'rgba(99, 102, 241, 0.1)' : 'transparent',
                borderLeft: isActive ? '2px solid var(--accent-primary)' : '2px solid transparent',
                marginBottom: '4px',
                transition: 'all var(--transition-fast)',
                textDecoration: 'none',
              }}
              onMouseEnter={(e) => {
                if (!isActive) {
                  e.currentTarget.style.background = 'var(--bg-hover)'
                  e.currentTarget.style.color = 'var(--text-primary)'
                }
              }}
              onMouseLeave={(e) => {
                if (!isActive) {
                  e.currentTarget.style.background = 'transparent'
                  e.currentTarget.style.color = 'var(--text-secondary)'
                }
              }}
            >
              <Icon size={18} />
              {label}
            </NavLink>
          )
        })}
      </nav>

      {/* RL Navigation */}
      <nav style={{ padding: '0 12px 16px' }}>
        <p style={{
          fontSize: '0.65rem',
          fontWeight: 600,
          color: 'var(--text-muted)',
          textTransform: 'uppercase',
          letterSpacing: '0.08em',
          padding: '0 8px',
          marginBottom: '8px',
        }}>AI Engine</p>

        {rlNavItems.map(({ path, label, icon: Icon }) => {
          const isActive = location.pathname === path
          return (
            <NavLink
              key={path}
              to={path}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '12px',
                padding: '10px 14px',
                borderRadius: 'var(--radius-sm)',
                fontSize: '0.85rem',
                fontWeight: isActive ? 600 : 400,
                color: isActive ? 'var(--text-primary)' : 'var(--text-secondary)',
                background: isActive ? 'rgba(139, 92, 246, 0.1)' : 'transparent',
                borderLeft: isActive ? '2px solid var(--accent-secondary)' : '2px solid transparent',
                marginBottom: '4px',
                transition: 'all var(--transition-fast)',
                textDecoration: 'none',
              }}
              onMouseEnter={(e) => {
                if (!isActive) {
                  e.currentTarget.style.background = 'var(--bg-hover)'
                  e.currentTarget.style.color = 'var(--text-primary)'
                }
              }}
              onMouseLeave={(e) => {
                if (!isActive) {
                  e.currentTarget.style.background = 'transparent'
                  e.currentTarget.style.color = 'var(--text-secondary)'
                }
              }}
            >
              <Icon size={18} />
              {label}
            </NavLink>
          )
        })}
      </nav>

      {/* Footer */}
      <div style={{
        padding: '16px 20px',
        borderTop: '1px solid var(--border-subtle)',
        marginTop: 'auto',
      }}>
        <div style={{
          background: 'var(--gradient-card)',
          border: '1px solid var(--border-subtle)',
          borderRadius: 'var(--radius-md)',
          padding: '14px',
          textAlign: 'center',
        }}>
          <p style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)', marginBottom: '4px' }}>
            Powered by
          </p>
          <p style={{
            fontSize: '0.8rem',
            fontWeight: 600,
            background: 'var(--gradient-brand)',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
          }}>
            GPT-4o • Claude • Gemini
          </p>
        </div>
      </div>
    </aside>
  )
}
