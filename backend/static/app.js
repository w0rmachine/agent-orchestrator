/**
 * Radar·Runway — ADHD-friendly task manager
 * Frontend JavaScript (vanilla, no framework)
 */

// Configuration
const API_BASE = window.location.origin;

// Utility functions
async function apiCall(method, path, data = null) {
    const options = {
        method,
        headers: {
            'Content-Type': 'application/json',
        },
    };

    if (data) {
        options.body = JSON.stringify(data);
    }

    const response = await fetch(`${API_BASE}${path}`, options);

    if (!response.ok) {
        throw new Error(`API Error: ${response.status} ${response.statusText}`);
    }

    const contentType = response.headers.get('content-type');
    if (contentType && contentType.includes('application/json')) {
        return await response.json();
    }

    return response;
}

// Task operations
const Tasks = {
    async create(title, description = '', tags = [], location = 'radar') {
        return apiCall('POST', '/tasks', {
            title,
            description,
            tags,
            location,
        });
    },

    async update(taskId, updates) {
        return apiCall('PATCH', `/tasks/${taskId}`, updates);
    },

    async delete(taskId) {
        return apiCall('DELETE', `/tasks/${taskId}`);
    },

    async move(taskId, location, status = null) {
        const data = { location };
        if (status) {
            data.status = status;
        }
        return apiCall('POST', `/tasks/${taskId}/move`, data);
    },

    async analyze(taskIds) {
        return apiCall('POST', '/tasks/reevaluate', {
            task_ids: taskIds,
        });
    },

    async get(taskId) {
        return apiCall('GET', `/tasks/${taskId}`);
    },

    async list(location = null, status = null) {
        let path = '/tasks';
        const params = new URLSearchParams();
        if (location) params.append('location', location);
        if (status) params.append('status', status);
        if (params.toString()) {
            path += '?' + params.toString();
        }
        return apiCall('GET', path);
    },
};

// UI State
const UI = {
    currentTask: null,

    async openTaskModal(taskId) {
        this.currentTask = await Tasks.get(taskId);
        this.renderTaskModal(this.currentTask);
        const modal = document.getElementById('task-modal');
        modal.classList.remove('hidden');
    },

    closeTaskModal() {
        const modal = document.getElementById('task-modal');
        modal.classList.add('hidden');
        this.currentTask = null;
    },

    renderTaskModal(task) {
        const modal = document.getElementById('modal-body');
        const priorityNames = {
            0: 'Critical',
            1: 'High',
            2: 'Medium',
            3: 'Low',
            4: 'Backlog',
        };

        let html = `
            <div class="modal-header">
                <h2>${task.id}: ${task.title}</h2>
                <button class="btn-close" onclick="UI.closeTaskModal()">&times;</button>
            </div>
            <div class="modal-body">
        `;

        if (task.tags.length > 0) {
            html += `<div class="task-tags">
                ${task.tags.map((t) => `<span class="tag">${t}</span>`).join('')}
            </div>`;
        }

        if (task.description) {
            html += `
                <div class="task-section">
                    <h3>Description</h3>
                    <p>${escapeHtml(task.description)}</p>
                </div>
            `;
        }

        if (task.location === 'runway') {
            if (task.priority !== null) {
                html += `
                    <div class="task-section">
                        <h3>Priority</h3>
                        <p>P${task.priority} (${priorityNames[task.priority]})</p>
                    </div>
                `;
            }

            if (task.complexity !== null) {
                html += `
                    <div class="task-section">
                        <h3>Complexity</h3>
                        <p>${task.complexity} story points</p>
                    </div>
                `;
            }

            if (task.estimated_minutes !== null) {
                const hours = Math.floor(task.estimated_minutes / 60);
                const mins = task.estimated_minutes % 60;
                const timeStr = hours > 0 ? `${hours}h ${mins}m` : `${mins}m`;
                html += `
                    <div class="task-section">
                        <h3>Estimated Time</h3>
                        <p>${timeStr}</p>
                    </div>
                `;
            }

            if (task.ai_notes) {
                html += `
                    <div class="task-section">
                        <h3>AI Notes</h3>
                        <p>${escapeHtml(task.ai_notes)}</p>
                    </div>
                `;
            }

            html += `
                <div class="task-section">
                    <h3>Status</h3>
                    <select id="status-select" onchange="UI.updateStatus('${task.id}')">
                        <option value="todo" ${task.status === 'todo' ? 'selected' : ''}>To Do</option>
                        <option value="in_progress" ${task.status === 'in_progress' ? 'selected' : ''}>In Progress</option>
                        <option value="done" ${task.status === 'done' ? 'selected' : ''}>Done</option>
                    </select>
                </div>
            `;
        } else {
            html += `
                <div class="task-actions">
                    <button class="btn btn-primary" onclick="UI.analyzeTask('${task.id}')">
                        Analyze with AI
                    </button>
                </div>
            `;
        }

        html += `
                <div class="task-actions">
                    <button class="btn btn-secondary" onclick="UI.deleteTask('${task.id}')">Delete</button>
                </div>
            </div>
        `;

        modal.innerHTML = html;
    },

    async updateStatus(taskId) {
        const select = document.getElementById('status-select');
        const newStatus = select.value;
        await Tasks.update(taskId, { status: newStatus });
        this.currentTask.status = newStatus;
        this.renderTaskModal(this.currentTask);
        refreshPage();
    },

    async analyzeTask(taskId) {
        const btn = event.target;
        btn.disabled = true;
        btn.textContent = 'Analyzing...';

        try {
            await Tasks.analyze([taskId]);
            // Wait a bit for analysis to complete
            await new Promise((resolve) => setTimeout(resolve, 2000));
            refreshPage();
        } catch (e) {
            alert('Analysis failed: ' + e.message);
            btn.disabled = false;
            btn.textContent = 'Analyze with AI';
        }
    },

    async deleteTask(taskId) {
        if (!confirm('Delete this task? This action cannot be undone.')) {
            return;
        }

        try {
            await Tasks.delete(taskId);
            this.closeTaskModal();
            refreshPage();
        } catch (e) {
            alert('Delete failed: ' + e.message);
        }
    },
};

// Helper functions
function escapeHtml(text) {
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;',
    };
    return text.replace(/[&<>"']/g, (m) => map[m]);
}

function refreshPage() {
    // Simple refresh for now (can be optimized with partial HTMX updates)
    setTimeout(() => {
        window.location.reload();
    }, 500);
}

// Event delegation for task cards
document.addEventListener('click', (e) => {
    const taskCard = e.target.closest('.task-card');
    if (taskCard && !e.target.closest('.btn-move')) {
        const taskId = taskCard.dataset.taskId;
        UI.openTaskModal(taskId);
    }

    // Close modal when clicking outside
    const modal = document.getElementById('task-modal');
    if (e.target === modal) {
        UI.closeTaskModal();
    }

    const addModal = document.getElementById('add-task-modal');
    if (e.target === addModal) {
        closeModal('add-task-modal');
    }
});

// Modal functions
window.openAddTask = function (location = 'radar') {
    const modal = document.getElementById('add-task-modal');
    const form = document.getElementById('add-task-form');
    form.dataset.location = location;
    form.reset();
    modal.classList.remove('hidden');
};

window.closeModal = function (modalId) {
    document.getElementById(modalId).classList.add('hidden');
};

// Add task form submission
if (document.getElementById('add-task-form')) {
    document.getElementById('add-task-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const form = e.target;
        const location = form.dataset.location || 'radar';
        const title = form.querySelector('input[name="title"]').value;
        const description = form.querySelector('textarea[name="description"]').value;
        const tagsStr = form.querySelector('input[name="tags"]').value;
        const tags = tagsStr
            .split(/\s+/)
            .filter((t) => t.length > 0)
            .map((t) => (t.startsWith('#') ? t : '#' + t));

        try {
            const task = await Tasks.create(title, description, tags, location);
            closeModal('add-task-modal');
            form.reset();
            refreshPage();
        } catch (e) {
            alert('Error creating task: ' + e.message);
        }
    });
}

// Analyze task button in task card
window.analyzeTask = async function (event, taskId) {
    event.stopPropagation();
    const card = document.querySelector(`[data-task-id="${taskId}"]`);
    const btn = event.target;

    card.classList.add('analyzing');
    btn.style.pointerEvents = 'none';
    btn.textContent = '⟳';

    try {
        await Tasks.analyze([taskId]);
        // Wait for analysis to complete
        await new Promise((resolve) => setTimeout(resolve, 2000));
        refreshPage();
    } catch (e) {
        alert('Analysis failed: ' + e.message);
        card.classList.remove('analyzing');
        btn.style.pointerEvents = 'auto';
        btn.textContent = '🧠';
    }
};

// Export function
window.exportObsidian = async function () {
    try {
        const response = await fetch('/export/obsidian');
        const text = await response.text();
        const blob = new Blob([text], { type: 'text/markdown' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'Radar-Runway.md';
        a.click();
        URL.revokeObjectURL(url);
    } catch (e) {
        alert('Export failed: ' + e.message);
    }
};

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    // Draw radar animation if canvas exists
    const canvas = document.getElementById('radar-canvas');
    if (canvas) {
        drawRadar();
    }

    // Set up HTMX event listeners for stats refresh
    htmx.on('htmx:afterSettle', (evt) => {
        if (evt.detail.xhr.responseURL && evt.detail.xhr.responseURL.includes('/logs')) {
            // Auto-scroll logs to bottom
            const container = document.querySelector('.logs-container');
            if (container) {
                container.scrollTop = container.scrollHeight;
            }
        }
    });
});

function drawRadar() {
    const canvas = document.getElementById('radar-canvas');
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    const centerX = canvas.width / 2;
    const centerY = canvas.height / 2;
    const maxRadius = Math.min(centerX, centerY) - 10;

    function animate() {
        // Clear canvas
        const bgColor = getComputedStyle(document.documentElement).getPropertyValue('--bg').trim();
        ctx.fillStyle = bgColor || '#05080d';
        ctx.fillRect(0, 0, canvas.width, canvas.height);

        // Draw rings
        const borderColor = getComputedStyle(document.documentElement)
            .getPropertyValue('--border')
            .trim();
        ctx.strokeStyle = borderColor || '#152035';
        ctx.lineWidth = 1;
        for (let i = 1; i <= 4; i++) {
            const r = (maxRadius / 4) * i;
            ctx.beginPath();
            ctx.arc(centerX, centerY, r, 0, Math.PI * 2);
            ctx.stroke();
        }

        // Draw sweep line (rotating)
        const time = Date.now() / 2000;
        const angle = (time % 1) * Math.PI * 2;
        const amberColor = getComputedStyle(document.documentElement)
            .getPropertyValue('--amber')
            .trim();
        ctx.strokeStyle = amberColor || '#e8a020';
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(centerX, centerY);
        ctx.lineTo(
            centerX + Math.cos(angle - Math.PI / 2) * maxRadius,
            centerY + Math.sin(angle - Math.PI / 2) * maxRadius
        );
        ctx.stroke();

        // Draw glow effect
        ctx.fillStyle = 'rgba(232, 160, 32, 0.1)';
        ctx.beginPath();
        ctx.arc(centerX, centerY, maxRadius, angle - Math.PI / 6, angle + Math.PI / 6);
        ctx.lineTo(centerX, centerY);
        ctx.fill();

        requestAnimationFrame(animate);
    }

    animate();
}
