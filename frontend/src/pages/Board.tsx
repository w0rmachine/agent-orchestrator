import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  DndContext,
  DragEndEvent,
  DragOverlay,
  DragStartEvent,
  PointerSensor,
  useSensor,
  useSensors,
} from '@dnd-kit/core'
import { useState } from 'react'
import { api, Task, TaskStatus } from '../services/api'
import TaskCard from '../components/TaskCard'
import Column from '../components/Column'

const COLUMNS: { id: TaskStatus; label: string; icon: string; color: string }[] = [
  { id: 'radar', label: 'RADAR', icon: '⊙', color: '#445a78' },
  { id: 'runway', label: 'RUNWAY', icon: '═', color: '#e8a020' },
  { id: 'flight', label: 'FLIGHT', icon: '↑', color: '#2dcc7a' },
  { id: 'blocked', label: 'BLOCKED', icon: '⚠', color: '#d95f5f' },
  { id: 'done', label: 'DONE', icon: '✓', color: '#2abfbf' },
]

export default function Board() {
  const queryClient = useQueryClient()
  const [activeTask, setActiveTask] = useState<Task | null>(null)

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        distance: 8,
      },
    })
  )

  // Fetch all tasks
  const { data: tasks = [], isLoading } = useQuery({
    queryKey: ['tasks'],
    queryFn: () => api.getTasks(),
  })

  // Move task mutation
  const moveTaskMutation = useMutation({
    mutationFn: ({ id, status }: { id: string; status: TaskStatus }) =>
      api.moveTask(id, status),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tasks'] })
    },
  })

  const handleDragStart = (event: DragStartEvent) => {
    const task = tasks.find((t) => t.id === event.active.id)
    setActiveTask(task || null)
  }

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event
    setActiveTask(null)

    if (!over) return

    const taskId = active.id as string
    const newStatus = over.id as TaskStatus

    const task = tasks.find((t) => t.id === taskId)
    if (!task || task.status === newStatus) return

    // Optimistic update
    queryClient.setQueryData<Task[]>(['tasks'], (old = []) =>
      old.map((t) => (t.id === taskId ? { ...t, status: newStatus } : t))
    )

    moveTaskMutation.mutate({ id: taskId, status: newStatus })
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-textDim font-mono">Loading...</div>
      </div>
    )
  }

  // Group tasks by status
  const tasksByStatus = COLUMNS.reduce((acc, col) => {
    acc[col.id] = tasks
      .filter((t) => t.status === col.id && !t.parent_task_id)
      .sort((a, b) => a.order - b.order)
    return acc
  }, {} as Record<TaskStatus, Task[]>)

  return (
    <div className="min-h-screen bg-bg p-4">
      {/* Header */}
      <div className="mb-6 pb-4 border-b border-border">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full border-2 border-amber bg-amberDim flex items-center justify-center">
            <span className="text-amber text-sm">⊙</span>
          </div>
          <div>
            <h1 className="text-white text-2xl font-black tracking-tight">
              AI<span className="text-amber">·</span>KANBAN
            </h1>
            <p className="text-textDim text-xs font-mono tracking-wider">
              ADHD-FRIENDLY TASK OPERATING SYSTEM
            </p>
          </div>
        </div>
      </div>

      {/* Kanban Board */}
      <DndContext
        sensors={sensors}
        onDragStart={handleDragStart}
        onDragEnd={handleDragEnd}
      >
        <div className="-mx-4 px-4 overflow-x-auto pb-4">
          <div className="flex gap-4 min-w-max">
            {COLUMNS.map((column) => (
              <Column
                key={column.id}
                id={column.id}
                label={column.label}
                icon={column.icon}
                color={column.color}
                tasks={tasksByStatus[column.id]}
              />
            ))}
          </div>
        </div>

        <DragOverlay>
          {activeTask ? (
            <div className="rotate-3">
              <TaskCard task={activeTask} />
            </div>
          ) : null}
        </DragOverlay>
      </DndContext>
    </div>
  )
}
