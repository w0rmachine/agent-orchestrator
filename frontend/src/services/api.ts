/**
 * Typed API client for AI Kanban Dashboard
 */

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

// Types
export type TaskStatus = 'radar' | 'runway' | 'flight' | 'blocked' | 'done'

export interface Task {
  id: string
  task_code: string
  title: string
  description: string
  status: TaskStatus
  priority: number | null
  tags: string[]
  location_tags: string[]
  environment_id: string | null
  parent_task_id: string | null
  ai_generated: boolean
  estimated_minutes: number | null
  order: number
  created_at: string
  updated_at: string
  completed_at: string | null
}

export interface Environment {
  id: string
  name: string
  repo_path: string
  git_url: string | null
  tech_stack: string[]
  default_branch: string
  created_at: string
}

export interface TaskCreate {
  task_code: string
  title: string
  description?: string
  status?: TaskStatus
  tags?: string[]
  location_tags?: string[]
  environment_id?: string | null
  parent_task_id?: string | null
}

export interface TaskUpdate {
  title?: string
  description?: string
  status?: TaskStatus
  priority?: number | null
  tags?: string[]
  location_tags?: string[]
  estimated_minutes?: number | null
}

// API Client
class ApiClient {
  private async request<T>(
    endpoint: string,
    options?: RequestInit
  ): Promise<T> {
    const response = await fetch(`${API_BASE}${endpoint}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
    })

    if (!response.ok) {
      const error = await response.json().catch(() => ({}))
      throw new Error(error.detail || `HTTP ${response.status}`)
    }

    return response.json()
  }

  // Tasks
  async getTasks(filters?: {
    status?: TaskStatus
    environment_id?: string
  }): Promise<Task[]> {
    const params = new URLSearchParams()
    if (filters?.status) params.append('status', filters.status)
    if (filters?.environment_id) params.append('environment_id', filters.environment_id)

    const query = params.toString() ? `?${params}` : ''
    return this.request<Task[]>(`/tasks/${query}`)
  }

  async getTask(id: string): Promise<Task> {
    return this.request<Task>(`/tasks/${id}`)
  }

  async createTask(data: TaskCreate): Promise<Task> {
    return this.request<Task>('/tasks/', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  async updateTask(id: string, data: TaskUpdate): Promise<Task> {
    return this.request<Task>(`/tasks/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    })
  }

  async deleteTask(id: string): Promise<void> {
    await this.request(`/tasks/${id}`, { method: 'DELETE' })
  }

  async moveTask(id: string, status: TaskStatus): Promise<Task> {
    return this.request<Task>(`/tasks/${id}/move?status=${status}`, {
      method: 'POST',
    })
  }

  // Environments
  async getEnvironments(): Promise<Environment[]> {
    return this.request<Environment[]>('/environments/')
  }

  async getEnvironment(id: string): Promise<Environment> {
    return this.request<Environment>(`/environments/${id}`)
  }

  async createEnvironment(data: Partial<Environment>): Promise<Environment> {
    return this.request<Environment>('/environments/', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  async updateEnvironment(
    id: string,
    data: Partial<Environment>
  ): Promise<Environment> {
    return this.request<Environment>(`/environments/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    })
  }

  async deleteEnvironment(id: string): Promise<void> {
    await this.request(`/environments/${id}`, { method: 'DELETE' })
  }
}

export const api = new ApiClient()
