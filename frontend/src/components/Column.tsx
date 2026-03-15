import { useDroppable } from '@dnd-kit/core'
import { SortableContext, verticalListSortingStrategy } from '@dnd-kit/sortable'
import { Task } from '../services/api'
import TaskCard from './TaskCard'

interface ColumnProps {
  id: string
  label: string
  icon: string
  color: string
  tasks: Task[]
}

export default function Column({ id, label, icon, color, tasks }: ColumnProps) {
  const { setNodeRef, isOver } = useDroppable({ id })

  return (
    <div className="flex-shrink-0 w-80 flex flex-direction flex-col bg-bgAlt rounded-lg border border-border overflow-hidden">
      {/* Column Header */}
      <div
        className="px-4 py-3 border-b border-border flex items-center gap-2"
        style={{ backgroundColor: `${color}0d` }}
      >
        <span className="text-sm" style={{ color }}>
          {icon}
        </span>
        <span
          className="font-mono text-xs font-bold tracking-widest"
          style={{ color }}
        >
          {label}
        </span>
        <span
          className="ml-auto text-xs font-bold font-mono px-2 py-0.5 rounded-full"
          style={{
            backgroundColor: `${color}25`,
            color,
          }}
        >
          {tasks.length}
        </span>
      </div>

      {/* Task List */}
      <div
        ref={setNodeRef}
        className={`flex-1 p-2 min-h-[400px] ${
          isOver ? 'bg-surfaceHi' : ''
        } transition-colors`}
      >
        <SortableContext
          items={tasks.map((t) => t.id)}
          strategy={verticalListSortingStrategy}
        >
          {tasks.length === 0 ? (
            <div className="text-center py-8 text-textFaint text-xs font-mono">
              — empty —
            </div>
          ) : (
            tasks.map((task) => <TaskCard key={task.id} task={task} />)
          )}
        </SortableContext>
      </div>
    </div>
  )
}
