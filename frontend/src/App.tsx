import { useState } from 'react'
import Board from './pages/Board'
import Activity from './pages/Activity'
import Stats from './pages/Stats'
import Environments from './pages/Environments'

type Page = 'board' | 'activity' | 'stats' | 'environments'

export default function App() {
  const [currentPage, setCurrentPage] = useState<Page>('board')

  const pages = [
    { id: 'board' as const, label: 'Board', icon: '◈' },
    { id: 'activity' as const, label: 'Activity', icon: '◎' },
    { id: 'stats' as const, label: 'Stats', icon: '▸' },
    { id: 'environments' as const, label: 'Environments', icon: '⚙' },
  ]

  return (
    <div className="min-h-screen bg-bg">
      {/* Top Navigation */}
      <nav className="bg-surface border-b border-border px-6 py-3">
        <div className="flex items-center gap-6">
          {pages.map((page) => (
            <button
              key={page.id}
              onClick={() => setCurrentPage(page.id)}
              className={`
                flex items-center gap-2 px-4 py-2 rounded-md font-mono text-xs
                transition-all
                ${
                  currentPage === page.id
                    ? 'bg-amber/20 text-amber border border-amber/40'
                    : 'text-textDim hover:text-text hover:bg-surfaceHi'
                }
              `}
            >
              <span>{page.icon}</span>
              <span className="font-bold tracking-wider">{page.label.toUpperCase()}</span>
            </button>
          ))}
        </div>
      </nav>

      {/* Page Content */}
      <main>
        {currentPage === 'board' && <Board />}
        {currentPage === 'activity' && <Activity />}
        {currentPage === 'stats' && <Stats />}
        {currentPage === 'environments' && <Environments />}
      </main>
    </div>
  )
}
