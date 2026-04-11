export default function StatCard({ icon: Icon, label, value, trend, trendDir, color = 'purple' }) {
  return (
    <div className="stat-card animate-in">
      <div className={`stat-icon ${color}`}>
        <Icon size={24} />
      </div>
      <div className="stat-info">
        <h3>{label}</h3>
        <div className="stat-value">{value}</div>
        {trend && (
          <div className={`stat-trend ${trendDir || 'up'}`}>
            {trendDir === 'down' ? '↓' : '↑'} {trend}
          </div>
        )}
      </div>
    </div>
  )
}
