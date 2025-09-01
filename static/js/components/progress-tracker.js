// Progress Tracker for Real-time Task Monitoring
class ProgressTracker {
    constructor(dashboard) {
        this.dashboard = dashboard;
        this.activeTrackers = new Map();
        this.init();
    }

    init() {
        this.setupProgressContainer();
    }

    setupProgressContainer() {
        // Create progress container if it doesn't exist
        if (!document.getElementById('progress-container')) {
            const container = document.createElement('div');
            container.id = 'progress-container';
            container.className = 'fixed bottom-5 right-5 z-50 space-y-3 max-w-sm';
            document.body.appendChild(container);
        }
    }

    startTracking(taskId, taskType = 'download', initialData = {}) {
        if (this.activeTrackers.has(taskId)) {
            return; // Already tracking this task
        }

        const tracker = this.createProgressCard(taskId, taskType, initialData);
        this.activeTrackers.set(taskId, tracker);
        
        // Start polling for updates
        this.pollTaskStatus(taskId);
    }

    createProgressCard(taskId, taskType, initialData) {
        const container = document.getElementById('progress-container');
        
        const card = document.createElement('div');
        card.id = `progress-${taskId}`;
        card.className = 'glass-effect border border-blue-500 rounded-lg p-4 text-white shadow-xl';
        
        const title = taskType === 'batch' ? 'Download em Lote' : 
                     taskType === 'playlist' ? 'Download de Playlist' : 'Download';
        
        card.innerHTML = `
            <div class="flex items-center justify-between mb-3">
                <h4 class="font-semibold text-cyan-300">${title}</h4>
                <button class="close-progress text-gray-400 hover:text-white" data-task-id="${taskId}">
                    <i class="fas fa-times"></i>
                </button>
            </div>
            <div class="space-y-2">
                <div class="text-sm text-gray-300">
                    <span class="status-message">Iniciando...</span>
                </div>
                <div class="w-full bg-gray-700 rounded-full h-2">
                    <div class="progress-bar bg-blue-600 h-2 rounded-full transition-all duration-300" style="width: 0%"></div>
                </div>
                <div class="text-xs text-gray-400">
                    <span class="progress-text">0%</span>
                    <span class="details-text"></span>
                </div>
                <div class="task-logs max-h-32 overflow-y-auto text-xs text-gray-400 bg-gray-800/50 rounded p-2 hidden">
                    <!-- Logs will be added here -->
                </div>
                <button class="toggle-logs text-xs text-cyan-400 hover:text-cyan-300">
                    <i class="fas fa-chevron-down mr-1"></i>Mostrar Logs
                </button>
            </div>
        `;
        
        container.appendChild(card);
        
        // Setup close button
        card.querySelector('.close-progress').addEventListener('click', () => {
            this.stopTracking(taskId);
        });
        
        // Setup logs toggle
        card.querySelector('.toggle-logs').addEventListener('click', (e) => {
            const logsDiv = card.querySelector('.task-logs');
            const button = e.target;
            
            if (logsDiv.classList.contains('hidden')) {
                logsDiv.classList.remove('hidden');
                button.innerHTML = '<i class="fas fa-chevron-up mr-1"></i>Ocultar Logs';
            } else {
                logsDiv.classList.add('hidden');
                button.innerHTML = '<i class="fas fa-chevron-down mr-1"></i>Mostrar Logs';
            }
        });
        
        return card;
    }

    async pollTaskStatus(taskId) {
        const pollInterval = setInterval(async () => {
            if (!this.activeTrackers.has(taskId)) {
                clearInterval(pollInterval);
                return;
            }

            try {
                const response = await fetch(`/admin/tasks/${taskId}/status`);
                const data = await response.json();
                
                this.updateProgressCard(taskId, data);
                
                if (data.state === 'SUCCESS' || data.state === 'FAILURE') {
                    clearInterval(pollInterval);
                    
                    // Auto-remove after 10 seconds if successful
                    if (data.state === 'SUCCESS') {
                        setTimeout(() => {
                            this.stopTracking(taskId);
                            // Refresh files section if visible
                            if (window.location.hash === '#files') {
                                this.dashboard.fileManager.filterFiles();
                            }
                        }, 10000);
                    }
                }
            } catch (error) {
                console.error(`Erro ao obter status da tarefa ${taskId}:`, error);
                this.addLogToCard(taskId, `Erro de rede: ${error.message}`, 'error');
            }
        }, 2000); // Poll every 2 seconds
    }

    updateProgressCard(taskId, data) {
        const card = this.activeTrackers.get(taskId);
        if (!card) return;

        const progressBar = card.querySelector('.progress-bar');
        const progressText = card.querySelector('.progress-text');
        const statusMessage = card.querySelector('.status-message');
        const detailsText = card.querySelector('.details-text');
        
        // Update progress bar
        const progress = data.progress || 0;
        progressBar.style.width = `${progress}%`;
        progressText.textContent = `${progress}%`;
        
        // Update status message
        statusMessage.textContent = data.message || 'Processando...';
        
        // Update details based on task type
        if (data.stage === 'batch_processing') {
            detailsText.textContent = ` • ${data.completed || 0}/${data.total_urls || 0} URLs`;
            
            if (data.current_url) {
                this.addLogToCard(taskId, `Processando: ${data.current_url}`, 'info');
            }
        } else if (data.stage === 'downloading' && data.total_videos) {
            detailsText.textContent = ` • ${data.completed_videos || 0}/${data.total_videos} vídeos`;
            
            if (data.current_title) {
                this.addLogToCard(taskId, `Baixando: ${data.current_title}`, 'info');
            }
        }
        
        // Update card color based on state
        if (data.state === 'SUCCESS') {
            card.className = card.className.replace('border-blue-500', 'border-green-500');
            statusMessage.textContent = 'Concluído com sucesso!';
        } else if (data.state === 'FAILURE') {
            card.className = card.className.replace('border-blue-500', 'border-red-500');
            statusMessage.textContent = 'Falha no processamento';
            this.addLogToCard(taskId, data.error || 'Erro desconhecido', 'error');
        }
    }

    addLogToCard(taskId, message, type = 'info') {
        const card = this.activeTrackers.get(taskId);
        if (!card) return;

        const logsDiv = card.querySelector('.task-logs');
        const timestamp = new Date().toLocaleTimeString();
        
        const logColor = type === 'error' ? 'text-red-400' : 
                        type === 'success' ? 'text-green-400' : 'text-gray-300';
        
        const logEntry = document.createElement('div');
        logEntry.className = `${logColor} text-xs`;
        logEntry.innerHTML = `<span class="text-gray-500">[${timestamp}]</span> ${message}`;
        
        logsDiv.appendChild(logEntry);
        logsDiv.scrollTop = logsDiv.scrollHeight;
    }

    stopTracking(taskId) {
        const card = this.activeTrackers.get(taskId);
        if (card) {
            card.style.transition = 'opacity 0.3s ease';
            card.style.opacity = '0';
            setTimeout(() => {
                card.remove();
                this.activeTrackers.delete(taskId);
            }, 300);
        }
    }

    stopAllTracking() {
        this.activeTrackers.forEach((card, taskId) => {
            this.stopTracking(taskId);
        });
    }
}

// Export for use in main dashboard
window.ProgressTracker = ProgressTracker;