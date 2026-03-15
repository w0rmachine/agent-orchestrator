import { useSortable } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { Task } from '../services/api'

interface TaskCardProps {
  task: Task
}

export default function TaskCard({ task }: TaskCardProps) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: task.id })

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  }

  const priorityColor = {
    1: '#d95f5f',
    2: '#e8a020',
    3: '#3a9fd8',
    4: '#445a78',
    5: '#1e2e45',
  }[task.priority || 3]

  return (
    <div
      ref={setNodeRef}
      style={style}
      {...attributes}
      {...listeners}
      className="bg-surface border border-border hover:border-borderHi rounded-md p-3 mb-2 cursor-move transition-all hover:shadow-lg"
    >
      {/* Task Code & Priority */}
      <div className="flex items-start gap-2 mb-2">
        <span className="text-[9px] text-textDim font-mono flex-shrink-0">
          {task.task_code}
        </span>
        {task.priority && (
          <span
            className="w-1.5 h-1.5 rounded-full flex-shrink-0 mt-0.5"
            style={{ backgroundColor: priorityColor }}
          />
        )}
        <span className="text-xs text-text flex-1 leading-tight">
          {task.title}
        </span>
      </div>

      {/* Tags */}
      {task.tags.length > 0 && (
        <div className="flex flex-wrap gap-1 mt-2">
          {task.tags.map((tag) => (
            <span
              key={tag}
              className="text-[8px] px-1.5 py-0.5 rounded bg-blueDim text-blue border border-blue/30 font-mono uppercase tracking-wide"
            >
              #{tag}
            </span>
          ))}
        </div>
      )}

      {/* Metadata */}
      <div className="flex items-center gap-2 mt-2 text-[9px] text-textDim font-mono">
        {task.ai_generated && (
          <span className="text-purple">AI</span>
        )}
        {task.estimated_minutes && (
          <span>
            {Math.floor(task.estimated_minutes / 60)}h{' '}
            {task.estimated_minutes % 60}m
          </span>
        )}
      </div>
    </div>
  )
}
