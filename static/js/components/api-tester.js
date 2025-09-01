// API Tester
class ApiTester {
    constructor(dashboard) {
        this.dashboard = dashboard;
        this.init();
    }

    init() {
        this.setupApiTestForm();
        this.setupCookieSync();
    }

    setupApiTestForm() {
        const apiTestForm = document.getElementById('api-test-form');
        const logContainer = document.getElementById('api-test-log');

        if (!apiTestForm || !logContainer) return;

        const addLog = (message, type = 'info') => {
            const color = type === 'error' ? 'text-red-400' : (type === 'success' ? 'text-green-400' : 'text-gray-400');
            logContainer.innerHTML += `<p class="${color}"><span class="text-gray-500">[${new Date().toLocaleTimeString()}]</span> ${message}</p>`;
            logContainer.scrollTop = logContainer.scrollHeight;
        };

        apiTestForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            logContainer.innerHTML = '';
            const formData = new FormData(apiTestForm);
            const data = Object.fromEntries(formData.entries());

            addLog('Enviando requisição...');
            
            try {
                const response = await fetch("/admin/test-api", {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(data)
                });
                const result = await response.json();
                if (!response.ok) throw new Error(result.error || 'Erro desconhecido');
                
                addLog(`Resposta recebida: ${JSON.stringify(result)}`);
                
                if (result.status === 'processing' && result.task_id) {
                    addLog(`Tarefa em processamento. ID: ${result.task_id}. Verificando status...`);
                    this.pollTaskStatus(result.task_id, addLog);
                } else if (result.status === 'completed') {
                    addLog('Tarefa concluída com sucesso!', 'success');
                    
                    if (result.result.playlist) {
                        addLog(`Playlist processada: ${result.result.playlist.playlist_count} vídeos baixados`, 'success');
                        result.result.playlist.videos.forEach((video, index) => {
                            addLog(`${index + 1}. <a href="${video.download_url}" class="text-cyan-400 hover:underline" target="_blank">${video.title}</a>`);
                        });
                    } else {
                        addLog(`URL para Download: <a href="${result.result.download_url}" class="text-cyan-400 hover:underline" target="_blank">${result.result.download_url}</a>`);
                    }
                } else if (result.status === 'processing' && result.task_id) {
                    addLog(`Tarefa em processamento. ID: ${result.task_id}`, 'info');
                    
                    // Start progress tracking
                    this.dashboard.progressTracker.startTracking(result.task_id, 'download');
                    
                    // Also poll for completion in the log
                    this.pollTaskStatus(result.task_id, addLog);
                }
            } catch (error) {
                addLog(`Erro na requisição inicial: ${error.message}`, 'error');
            }
        });
    }

    async pollTaskStatus(taskId, addLog) {
        const taskStatusUrl = `/api/tasks/${taskId}`;
        const intervalId = setInterval(async () => {
            try {
                const response = await fetch(taskStatusUrl);
                const result = await response.json();
                if (!response.ok) {
                    addLog(`Erro ao verificar status: ${result.error || 'Erro desconhecido'}`, 'error');
                    clearInterval(intervalId);
                    return;
                }
                if (result.status === 'completed') {
                    addLog('Tarefa concluída com sucesso!', 'success');
                    
                    if (result.result.playlist) {
                        addLog(`Playlist processada: ${result.result.playlist.playlist_count} vídeos baixados`, 'success');
                        result.result.playlist.videos.forEach((video, index) => {
                            addLog(`${index + 1}. <a href="${video.download_url}" class="text-cyan-400 hover:underline" target="_blank">${video.title}</a>`);
                        });
                    } else {
                        addLog(`URL para Download: <a href="${result.result.download_url}" class="text-cyan-400 hover:underline" target="_blank">${result.result.download_url}</a>`);
                    }
                    clearInterval(intervalId);
                    
                    // Refresh page to show new file
                    setTimeout(() => location.reload(), 2000);
                } else if (result.status === 'failed') {
                    addLog(`A tarefa falhou: ${result.message}`, 'error');
                    clearInterval(intervalId);
                } else {
                    addLog(`Status da tarefa: ${result.status}...`);
                }
            } catch (error) {
                addLog(`Erro de rede ao verificar status: ${error.message}`, 'error');
                clearInterval(intervalId);
            }
        }, 3000);
    }

    setupCookieSync() {
        const syncBtn = document.querySelector('.sync-cookies-btn');
        if (syncBtn) {
            syncBtn.addEventListener('click', async (e) => {
                e.preventDefault();
                
                try {
                    syncBtn.disabled = true;
                    syncBtn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i>Sincronizando...';
                    
                    const response = await fetch('/admin/cookies/sync', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' }
                    });
                    
                    const result = await response.json();
                    if (result.success) {
                        this.dashboard.showNotification(result.message, 'success');
                        this.updateCookieStatus(result.status);
                    } else {
                        this.dashboard.showNotification('Erro ao sincronizar cookies', 'error');
                    }
                } catch (error) {
                    this.dashboard.showNotification('Erro de rede', 'error');
                } finally {
                    syncBtn.disabled = false;
                    syncBtn.innerHTML = '<i class="fas fa-sync mr-2"></i>Sincronizar';
                }
            });
        }
    }

    updateCookieStatus(status) {
        const statusEl = document.querySelector('.cookie-status');
        if (statusEl) {
            statusEl.className = `cookie-status ${status}`;
            const statusText = {
                'ok': 'Cookies Válidos',
                'expired': 'Cookies Expirados',
                'needs_sync': 'Precisa Sincronizar',
                'missing': 'Sem Cookies'
            };
            statusEl.innerHTML = `<i class="fas fa-cookie-bite mr-1"></i>${statusText[status] || 'Status Desconhecido'}`;
        }
    }
}

// Export for use in main dashboard
window.ApiTester = ApiTester;