import { useQuery } from '@tanstack/react-query'
import { api } from '../services/api'

export default function Stats() {
  const { data: tasks = [] } = useQuery({
    queryKey: ['tasks'],
    queryFn: () => api.getTasks(),
  })

  // Calculate statistics
  const stats = {
    total: tasks.length,
    radar: tasks.filter((t) => t.status === 'radar').length,
    runway: tasks.filter((t) => t.status === 'runway').length,
    flight: tasks.filter((t) => t.status === 'flight').length,
    blocked: tasks.filter((t) => t.status === 'blocked').length,
    done: tasks.filter((t) => t.status === 'done').length,
    aiGenerated: tasks.filter((t) => t.ai_generated).length,
    totalEstimatedTime: tasks
      .filter((t) => t.status !== 'done' && t.estimated_minutes)
      .reduce((sum, t) => sum + (t.estimated_minutes || 0), 0),
    avgPriority:
      tasks.filter((t) => t.priority).reduce((sum, t) => sum + (t.priority || 0), 0) /
        tasks.filter((t) => t.priority).length || 0,
  }

  const statCards = [
    { label: 'Total Tasks', value: stats.total, color: '#b8c8dc' },
    { label: 'In Radar', value: stats.radar, color: '#445a78' },
    { label: 'In Runway', value: stats.runway, color: '#e8a020' },
    { label: 'In Flight', value: stats.flight, color: '#2dcc7a' },
    { label: 'Blocked', value: stats.blocked, color: '#d95f5f' },
    { label: 'Completed', value: stats.done, color: '#2abfbf' },
    { label: 'AI Generated', value: stats.aiGenerated, color: '#8b67d4' },
    {
      label: 'Est. Time Remaining',
      value: `${Math.floor(stats.totalEstimatedTime / 60)}h ${
        stats.totalEstimatedTime % 60
      }m`,
      color: '#3a9fd8',
    },
  ]

  return (
    <div className="p-6">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <h2 className="text-white text-2xl font-bold mb-6">
          Productivity Statistics
        </h2>

        {/* Stats Grid */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          {statCards.map((stat) => (
            <div
              key={stat.label}
              className="bg-surface border border-border rounded-lg p-4"
              style={{ borderTopColor: stat.color, borderTopWidth: 2 }}
            >
              <div className="text-textDim text-xs font-mono mb-1">
                {stat.label}
              </div>
              <div
                className="text-3xl font-bold font-mono"
                style={{ color: stat.color }}
              >
                {stat.value}
              </div>
            </div>
          ))}
        </div>

        {/* Progress Bars */}
        <div className="bg-surface border border-border rounded-lg p-6">
          <h3 className="text-white text-lg font-bold mb-4">
            Task Distribution
          </h3>

          {[
            { label: 'Radar', value: stats.radar, color: '#445a78' },
            { label: 'Runway', value: stats.runway, color: '#e8a020' },
            { label: 'Flight', value: stats.flight, color: '#2dcc7a' },
            { label: 'Blocked', value: stats.blocked, color: '#d95f5f' },
            { label: 'Done', value: stats.done, color: '#2abfbf' },
          ].map((item) => (
            <div key={item.label} className="mb-4 last:mb-0">
              <div className="flex justify-between items-center mb-1">
                <span className="text-textDim text-xs font-mono">
                  {item.label}
                </span>
                <span
                  className="text-xs font-bold font-mono"
                  style={{ color: item.color }}
                >
                  {item.value} ({Math.round((item.value / stats.total) * 100)}%)
                </span>
              </div>
              <div className="h-2 bg-border rounded-full overflow-hidden">
                <div
                  className="h-full transition-all duration-500"
                  style={{
                    width: `${(item.value / stats.total) * 100}%`,
                    backgroundColor: item.color,
                  }}
                />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
