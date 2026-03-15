import { useQuery } from '@tanstack/react-query'
import { api } from '../services/api'

export default function Environments() {
  const { data: environments = [], isLoading } = useQuery({
    queryKey: ['environments'],
    queryFn: () => api.getEnvironments(),
  })

  const { data: tasks = [] } = useQuery({
    queryKey: ['tasks'],
    queryFn: () => api.getTasks(),
  })

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-textDim font-mono">Loading...</div>
      </div>
    )
  }

  return (
    <div className="p-6">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="mb-6 flex items-center justify-between">
          <h2 className="text-white text-2xl font-bold">Environments</h2>
          <button className="px-4 py-2 bg-amber/20 text-amber border border-amber/40 rounded-md text-sm font-mono hover:bg-amber/30 transition-colors">
            + ADD ENVIRONMENT
          </button>
        </div>

        {/* Environments List */}
        {environments.length === 0 ? (
          <div className="bg-surface border border-border rounded-lg p-12 text-center">
            <p className="text-textDim font-mono text-sm">
              No environments configured yet.
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            {environments.map((env) => {
              const envTasks = tasks.filter((t) => t.environment_id === env.id)
              const taskStats = {
                total: envTasks.length,
                active: envTasks.filter((t) => t.status === 'flight').length,
                blocked: envTasks.filter((t) => t.status === 'blocked').length,
                done: envTasks.filter((t) => t.status === 'done').length,
              }

              return (
                <div
                  key={env.id}
                  className="bg-surface border border-border rounded-lg p-6 hover:border-borderHi transition-colors"
                >
                  <div className="flex items-start justify-between mb-4">
                    <div className="flex-1">
                      <h3 className="text-white text-lg font-bold mb-1">
                        {env.name}
                      </h3>
                      <p className="text-textDim text-sm font-mono mb-2">
                        {env.repo_path}
                      </p>
                      {env.git_url && (
                        <p className="text-textDim text-xs">
                          {env.git_url}
                        </p>
                      )}
                    </div>
                    <div className="flex gap-2">
                      {env.tech_stack.map((tech) => (
                        <span
                          key={tech}
                          className="px-2 py-1 bg-blueDim text-blue border border-blue/30 rounded text-xs font-mono"
                        >
                          {tech}
                        </span>
                      ))}
                    </div>
                  </div>

                  {/* Task Stats */}
                  <div className="flex gap-6 pt-4 border-t border-border">
                    <div>
                      <span className="text-textDim text-xs font-mono">
                        Total Tasks
                      </span>
                      <div className="text-text text-lg font-bold font-mono">
                        {taskStats.total}
                      </div>
                    </div>
                    <div>
                      <span className="text-textDim text-xs font-mono">
                        Active
                      </span>
                      <div className="text-green text-lg font-bold font-mono">
                        {taskStats.active}
                      </div>
                    </div>
                    <div>
                      <span className="text-textDim text-xs font-mono">
                        Blocked
                      </span>
                      <div className="text-red text-lg font-bold font-mono">
                        {taskStats.blocked}
                      </div>
                    </div>
                    <div>
                      <span className="text-textDim text-xs font-mono">
                        Done
                      </span>
                      <div className="text-teal text-lg font-bold font-mono">
                        {taskStats.done}
                      </div>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
