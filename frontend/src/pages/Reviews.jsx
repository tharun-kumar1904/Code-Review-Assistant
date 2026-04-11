import { useState } from 'react'
import { GitPullRequest, Search, Filter } from 'lucide-react'
import ReviewCard from '../components/ReviewCard'

const demoReviews = [
  {
    id: 1,
    quality_score: 72,
    total_issues: 5,
    critical_issues: 1,
    high_issues: 2,
    medium_issues: 1,
    low_issues: 1,
    analysis_duration: 12.4,
    llm_provider: 'openai',
    pull_request: {
      pr_number: 142,
      title: 'Add payment processing module',
      author: 'john-doe',
      repo: 'acme/backend',
    },
    comments: [
      {
        severity: 'critical',
        category: 'security',
        issue: 'SQL Injection vulnerability in payment query',
        file_path: 'src/payments/processor.py',
        line_number: 47,
        explanation: 'User-supplied payment ID is directly interpolated into the SQL query string using f-string formatting. An attacker could inject malicious SQL commands to access or modify payment records.',
        suggested_fix: 'Use parameterized queries:\ncursor.execute(\n  "SELECT * FROM payments WHERE id = %s",\n  (payment_id,)\n)',
      },
      {
        severity: 'high',
        category: 'security',
        issue: 'Hardcoded API key for payment gateway',
        file_path: 'src/payments/config.py',
        line_number: 12,
        explanation: 'The Stripe API key is hardcoded in the source file. If this code is committed to a repository, the key could be exposed to unauthorized users.',
        suggested_fix: 'Move the API key to environment variables:\nimport os\nSTRIPE_KEY = os.environ["STRIPE_API_KEY"]',
      },
      {
        severity: 'high',
        category: 'bug',
        issue: 'Race condition in concurrent payment processing',
        file_path: 'src/payments/processor.py',
        line_number: 89,
        explanation: 'Multiple threads can read and update the payment status simultaneously without locking, potentially leading to duplicate charges or lost transactions.',
        suggested_fix: 'Use database-level locking:\nwith db.begin():\n  payment = db.query(Payment).with_for_update().get(id)\n  payment.status = "processing"',
      },
      {
        severity: 'medium',
        category: 'performance',
        issue: 'N+1 query in payment history retrieval',
        file_path: 'src/payments/views.py',
        line_number: 34,
        explanation: 'Each payment record triggers a separate query to fetch the associated user, resulting in N+1 database queries when loading the payment history page.',
        suggested_fix: 'Use eager loading:\npayments = Payment.query.options(\n  joinedload(Payment.user)\n).all()',
      },
      {
        severity: 'low',
        category: 'style',
        issue: 'Inconsistent naming convention',
        file_path: 'src/payments/utils.py',
        line_number: 5,
        explanation: 'Function uses camelCase naming while the rest of the codebase uses snake_case, reducing readability and consistency.',
        suggested_fix: 'Rename from calculateTotal to calculate_total',
      },
    ],
  },
  {
    id: 2,
    quality_score: 91,
    total_issues: 1,
    critical_issues: 0,
    high_issues: 0,
    medium_issues: 1,
    low_issues: 0,
    analysis_duration: 8.2,
    llm_provider: 'openai',
    pull_request: {
      pr_number: 89,
      title: 'Update authentication middleware',
      author: 'jane-smith',
      repo: 'acme/api-gateway',
    },
    comments: [
      {
        severity: 'medium',
        category: 'performance',
        issue: 'JWT token verification on every request without caching',
        file_path: 'src/middleware/auth.py',
        line_number: 23,
        explanation: 'The JWT signature is verified by calling the identity provider on every single request, adding latency. Most tokens are valid and can be cached.',
        suggested_fix: 'Cache verified tokens with TTL:\nfrom functools import lru_cache\n\n@lru_cache(maxsize=1024)\ndef verify_token(token):\n  return jwt.decode(token, key, algorithms=["RS256"])',
      },
    ],
  },
  {
    id: 3,
    quality_score: 45,
    total_issues: 12,
    critical_issues: 3,
    high_issues: 4,
    medium_issues: 3,
    low_issues: 2,
    analysis_duration: 18.7,
    llm_provider: 'openai',
    pull_request: {
      pr_number: 77,
      title: 'Fix XSS vulnerability in comment renderer',
      author: 'alex-dev',
      repo: 'acme/frontend',
    },
    comments: [
      {
        severity: 'critical',
        category: 'security',
        issue: 'Unescaped HTML in user comments via dangerouslySetInnerHTML',
        file_path: 'src/components/CommentBox.jsx',
        line_number: 15,
        explanation: 'User-generated comment content is rendered using dangerouslySetInnerHTML without sanitization, allowing stored XSS attacks.',
        suggested_fix: 'Use DOMPurify to sanitize HTML:\nimport DOMPurify from "dompurify";\n<div dangerouslySetInnerHTML={{\n  __html: DOMPurify.sanitize(comment.body)\n}} />',
      },
      {
        severity: 'critical',
        category: 'security',
        issue: 'Missing CSRF token in form submission',
        file_path: 'src/components/CommentForm.jsx',
        line_number: 42,
        explanation: 'The comment submission form does not include a CSRF token, making it vulnerable to cross-site request forgery attacks.',
        suggested_fix: 'Include CSRF token in form:\n<input type="hidden" name="_csrf" value={csrfToken} />',
      },
    ],
  },
]

export default function Reviews() {
  const [searchTerm, setSearchTerm] = useState('')

  const filtered = demoReviews.filter(r =>
    r.pull_request.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
    r.pull_request.repo.toLowerCase().includes(searchTerm.toLowerCase())
  )

  return (
    <div>
      <div className="page-header">
        <h1>Code Reviews</h1>
        <p>AI-powered analysis results for pull requests</p>
      </div>

      {/* Search Bar */}
      <div style={{
        display: 'flex', gap: '12px', marginBottom: '24px', alignItems: 'center',
      }}>
        <div style={{
          flex: 1, display: 'flex', alignItems: 'center', gap: '10px',
          background: 'var(--bg-card)', border: '1px solid var(--border-subtle)',
          borderRadius: 'var(--radius-md)', padding: '10px 16px',
          backdropFilter: 'blur(12px)',
        }}>
          <Search size={18} style={{ color: 'var(--text-muted)' }} />
          <input
            type="text"
            placeholder="Search reviews by PR title or repository..."
            value={searchTerm}
            onChange={e => setSearchTerm(e.target.value)}
            style={{
              background: 'transparent', border: 'none', outline: 'none',
              color: 'var(--text-primary)', fontSize: '0.85rem',
              width: '100%', fontFamily: 'var(--font-sans)',
            }}
          />
        </div>
        <button style={{
          display: 'flex', alignItems: 'center', gap: '6px',
          background: 'var(--bg-card)', border: '1px solid var(--border-subtle)',
          borderRadius: 'var(--radius-md)', padding: '10px 16px',
          color: 'var(--text-secondary)', cursor: 'pointer', fontSize: '0.85rem',
          fontFamily: 'var(--font-sans)',
        }}>
          <Filter size={16} /> Filter
        </button>
      </div>

      {/* Summary */}
      <div style={{
        display: 'flex', gap: '16px', marginBottom: '20px',
        fontSize: '0.8rem', color: 'var(--text-tertiary)',
      }}>
        <span>{filtered.length} reviews</span>
        <span>•</span>
        <span>{filtered.reduce((a, r) => a + r.total_issues, 0)} total issues</span>
        <span>•</span>
        <span>Avg score: {Math.round(filtered.reduce((a, r) => a + r.quality_score, 0) / (filtered.length || 1))}</span>
      </div>

      {/* Review Cards */}
      {filtered.map(review => (
        <ReviewCard key={review.id} review={review} />
      ))}
    </div>
  )
}
