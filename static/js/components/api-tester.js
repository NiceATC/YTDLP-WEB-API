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
            const timestamp = new Date().toLocaleTimeString();
            const color = type === 'error' ? 'text-red-400' : 
                         type === 'success' ? 'text-green-400' : 
                         type === 'warning' ? 'text-yellow-400' : 'text-gray-300';
            
            const logEntry = document.createElement('div');
            logEntry.className = `${color} text-sm mb-1`;
            logEntry.innerHTML = `<span class="text-gray-500">[${timestamp}]</span> ${message}`;
            
            logContainer.appendChild(logEntry);
            logContainer.scrollTop = logContainer.scrollHeight;
        };

        apiTestForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            logContainer.innerHTML = '';
            const formData = new FormData(apiTestForm);
            const data = Object.fromEntries(formData.entries());

            addLog('🚀 Enviando requisição para API...', 'info');
            addLog(`📋 Parâmetros: ${JSON.stringify(data)}`, 'info');
            
            try {
                const response = await fetch("/admin/test-api", {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(data)
                });
                
                const result = await response.json();
                
                if (!response.ok) {
                    throw new Error(result.error || 'Erro desconhecido');
                }
                
                addLog(`✅ Resposta recebida (${response.status})`, 'success');
                addLog(`📄 Dados: ${JSON.stringify(result, null, 2)}`, 'info');
                
                if (result.status === 'processing' && result.task_id) {
                    addLog(`⏳ Tarefa em processamento. ID: ${result.task_id}`, 'warning');
                    addLog(`🔗 URL de acompanhamento: ${result.check_status_url}`, 'info');
                    
                    // Inicia acompanhamento em tempo real
                    const taskType = result.type || 'single';
                    this.dashboard.progressTracker.startTracking(result.task_id, taskType, {
                        source: 'api-test'
                    });
                    
                    // Também monitora no log
                    this.pollTaskStatusForLog(result.task_id, addLog);
                    
                } else if (result.status === 'completed' || (result.status && result.status.task === 'completed')) {
                    addLog('🎉 Tarefa concluída com sucesso!', 'success');
                    
                    const downloadUrl = result.status?.download_url || result.result?.download_url;
                    if (downloadUrl) {
                        addLog(`📥 <a href="${downloadUrl}" class="text-cyan-400 hover:underline" target="_blank">Clique aqui para baixar</a>`, 'success');
                    }
                    
                    if (result.metadata) {
                        addLog(`🎵 Título: ${result.metadata.title}`, 'info');
                        addLog(`👤 Autor: ${result.metadata.uploader}`, 'info');
                        addLog(`⏱️ Duração: ${result.metadata.duration_string}`, 'info');
                    }
                }
                
            } catch (error) {
                addLog(`❌ Erro na requisição: ${error.message}`, 'error');
            }
        });
    }

    async pollTaskStatusForLog(taskId, addLog) {
        let pollCount = 0;
        const maxPolls = 60; // 3 minutos máximo
        
        const intervalId = setInterval(async () => {
            pollCount++;
            
            if (pollCount > maxPolls) {
                addLog('⏰ Timeout: Parando verificação automática', 'warning');
                clearInterval(intervalId);
                return;
            }
            
            try {
                // Usa endpoint interno sem necessidade de API key
                const response = await fetch(`/admin/tasks/${taskId}/status`);
                const result = await response.json();
                
                if (!response.ok) {
                    addLog(`❌ Erro ao verificar status: ${result.error || 'Erro desconhecido'}`, 'error');
                    clearInterval(intervalId);
                    return;
                }
                
                if (result.state === 'SUCCESS') {
                    addLog('🎉 Tarefa concluída com sucesso!', 'success');
                    
                    const taskResult = result.result || {};
                    
                    if (taskResult.playlist) {
                        addLog(`📋 Playlist processada: ${taskResult.videos?.length || 0} vídeos`, 'success');
                        if (taskResult.videos) {
                            taskResult.videos.forEach((video, index) => {
                                addLog(`${index + 1}. <a href="${video.download_url}" class="text-cyan-400 hover:underline" target="_blank">${video.title}</a>`, 'success');
                            });
                        }
                    } else if (taskResult.batch) {
                        addLog(`📦 Lote processado: ${taskResult.completed}/${taskResult.total_urls} sucessos`, 'success');
                        if (taskResult.results) {
                            taskResult.results.forEach((item, index) => {
                                if (item.status === 'success') {
                                    addLog(`${index + 1}. <a href="${item.download_url}" class="text-cyan-400 hover:underline" target="_blank">${item.title}</a>`, 'success');
                                } else {
                                    addLog(`${index + 1}. ❌ Falha: ${item.error}`, 'error');
                                }
                            });
                        }
                    } else {
                        const downloadUrl = taskResult.download_url;
                        if (downloadUrl) {
                            addLog(`📥 <a href="${downloadUrl}" class="text-cyan-400 hover:underline" target="_blank">Clique aqui para baixar</a>`, 'success');
                        }
                    }
                    
                    clearInterval(intervalId);
                    
                    // Refresh files section after 2 seconds
                    setTimeout(() => {
                        if (window.location.hash === '#files') {
                            this.dashboard.fileManager.filterFiles();
                        }
                    }, 2000);
                    
                } else if (result.state === 'FAILURE') {
                    addLog(`❌ Tarefa falhou: ${result.error || result.message || 'Erro desconhecido'}`, 'error');
                    clearInterval(intervalId);
                    
                } else if (result.state === 'PROGRESS') {
                    const progress = result.progress || 0;
                    const message = result.message || 'Processando...';
                    addLog(`⏳ ${message} (${progress}%)`, 'info');
                    
                    // Log específico para playlists
                    if (result.current_title) {
                        addLog(`🎵 Baixando: ${result.current_title}`, 'info');
                    }
                    
                    // Log específico para batch
                    if (result.current_url) {
                        addLog(`🔗 Processando: ${result.current_url}`, 'info');
                    }
                }
                
            } catch (error) {
                addLog(`🌐 Erro de rede ao verificar status: ${error.message}`, 'error');
                clearInterval(intervalId);
            }
        }, 3000); // Verifica a cada 3 segundos
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