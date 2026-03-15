import { useEffect, useState, useRef } from 'react'

interface LogEntry {
  id: string
  timestamp: string
  level: 'info' | 'warning' | 'error'
  message: string
  session_id?: string
}

const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws'

export default function Activity() {
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [connected, setConnected] = useState(false)
  const logEndRef = useRef<HTMLDivElement>(null)
  const wsRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    // Connect to WebSocket
    const ws = new WebSocket(WS_URL)
    wsRef.current = ws

    ws.onopen = () => {
      setConnected(true)
    }

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data)

      if (data.type === 'log') {
        setLogs((prev) => [...prev, data.log].slice(-200))
      } else if (data.type === 'init' && data.logs) {
        setLogs(data.logs)
      }
    }

    ws.onclose = () => {
      setConnected(false)
    }

    return () => {
      ws.close()
    }
  }, [])

  useEffect(() => {
    // Auto-scroll to bottom
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [logs])

  const levelColors = {
    info: '#3a9fd8',
    warning: '#e8a020',
    error: '#d95f5f',
  }

  return (
    <div className="p-6">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="mb-4 flex items-center gap-3">
          <div
            className={`w-2 h-2 rounded-full ${
              connected ? 'bg-green animate-pulse' : 'bg-red'
            }`}
          />
          <h2 className="text-white text-xl font-bold">Live Activity Log</h2>
          <span className="ml-auto text-textDim text-xs font-mono">
            {logs.length} entries
          </span>
        </div>

        {/* Log Panel */}
        <div className="bg-surface border border-border rounded-lg overflow-hidden">
          <div className="h-[600px] overflow-y-auto p-4 font-mono text-xs">
            {logs.length === 0 ? (
              <div className="text-center text-textFaint py-20">
                No logs yet...
              </div>
            ) : (
              logs.map((log) => (
                <div
                  key={log.id}
                  className="flex gap-3 py-1 border-b border-textFaint/20 hover:bg-surfaceHi/50"
                >
                  <span className="text-textDim flex-shrink-0">
                    {new Date(log.timestamp).toLocaleTimeString('en-US', {
                      hour12: false,
                    })}
                  </span>
                  <span
                    className="flex-shrink-0 w-12 font-bold"
                    style={{ color: levelColors[log.level] }}
                  >
                    {log.level.toUpperCase()}
                  </span>
                  <span className="text-text flex-1">{log.message}</span>
                </div>
              ))
            )}
            <div ref={logEndRef} />
          </div>
        </div>
      </div>
    </div>
  )
}
