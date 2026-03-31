import { useState } from 'react'
import { ChevronDown, ChevronRight, FileCode } from 'lucide-react'

export default function ReviewCard({ review }) {
  const [expanded, setExpanded] = useState(false)

  const scoreClass = review.quality_score >= 80 ? 'excellent'
    : review.quality_score >= 60 ? 'good'
    : review.quality_score >= 40 ? 'fair' : 'poor'

  return (
    <div className="review-card animate-in">
      <div className="review-card-header" onClick={() => setExpanded(!expanded)}>
        <div className="review-card-title">
          <div className={`quality-score ${scoreClass}`}>
            {Math.round(review.quality_score)}
          </div>
          <div>
            <h4>{review.pull_request?.title || `PR #${review.pull_request?.pr_number}`}</h4>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '4px', fontSize: '0.75rem', color: 'var(--text-tertiary)' }}>
              <span>{review.pull_request?.repo}</span>
              <span>•</span>
              <span>by {review.pull_request?.author}</span>
              <span>•</span>
              <span>{review.analysis_duration ? `${review.analysis_duration.toFixed(1)}s` : ''}</span>
            </div>
          </div>
        </div>
        <div className="review-card-meta">
          {review.critical_issues > 0 && <span className="badge critical">{review.critical_issues} Critical</span>}
          {review.high_issues > 0 && <span className="badge high">{review.high_issues} High</span>}
          {review.medium_issues > 0 && <span className="badge medium">{review.medium_issues} Medium</span>}
          {review.low_issues > 0 && <span className="badge low">{review.low_issues} Low</span>}
          <span style={{ color: 'var(--text-muted)', marginLeft: '8px' }}>
            {expanded ? <ChevronDown size={18} /> : <ChevronRight size={18} />}
          </span>
        </div>
      </div>

      {expanded && review.comments && (
        <div className="review-card-body">
          {review.comments.map((comment, i) => (
            <div key={i} className="issue-item">
              <h5>
                <span className={`badge ${comment.severity}`}>{comment.severity}</span>
                <span className={`badge`} style={{ background: 'rgba(99,102,241,0.1)', color: 'var(--accent-primary)' }}>{comment.category}</span>
                {comment.issue}
              </h5>
              <div className="file-path" style={{ marginBottom: '8px' }}>
                <FileCode size={12} style={{ display: 'inline', verticalAlign: 'middle', marginRight: '4px' }} />
                {comment.file_path}{comment.line_number ? `:${comment.line_number}` : ''}
              </div>
              {comment.explanation && (
                <p className="explanation">
                  <strong>Why:</strong> {comment.explanation}
                </p>
              )}
              {comment.suggested_fix && (
                <div className="suggested-fix">
                  💡 {comment.suggested_fix}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
