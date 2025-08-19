// Dashboard JavaScript
class Dashboard {
    constructor() {
        this.init();
    }

    init() {
        this.setupNavigation();
        this.setupModals();
        this.setupApiTester();
        this.setupFileManagement();
        this.setupHistoryManagement();
        this.setupCookieManagement();
        this.autoHideFlashMessages();
        this.initializeTooltips();
        this.initializeCharts();
        this.setupFileManagement();
    }

    setupNavigation() {
        const sections = document.querySelectorAll('.content-section');
        const navLinks = document.querySelectorAll('#sidebar-nav a');

        const showSection = (hash) => {
            sections.forEach(section => section.classList.remove('active'));
            navLinks.forEach(link => link.classList.remove('active'));
            
            const targetSection = document.querySelector(hash);
            const targetLink = document.querySelector(`#sidebar-nav a[href="${hash}"]`);
            
            if (targetSection) targetSection.classList.add('active');
            if (targetLink) targetLink.classList.add('active');
        };

        navLinks.forEach(link => {
            link.addEventListener('click', (e) => { 
                e.preventDefault();
                window.location.hash = e.currentTarget.getAttribute('href'); 
            });
        });

        window.addEventListener('hashchange', () => showSection(window.location.hash || '#overview'));
        
        const initialHash = window.location.hash || '#overview';
        showSection(initialHash);
    }

    setupModals() {
        const modals = {
            response: document.getElementById('response-modal'),
            metadata: document.getElementById('metadata-modal'),
            player: document.getElementById('player-modal')
        };

        // Response modal handlers
        document.querySelectorAll('.view-response-btn').forEach(button => {
            button.addEventListener('click', () => {
                const responseData = JSON.parse(button.dataset.response);
                document.getElementById('modal-json-content').textContent = JSON.stringify(responseData, null, 2);
                modals.response.classList.add('active');
            });
        });
        
        // Metadata modal handlers
        document.querySelectorAll('.view-metadata-btn').forEach(button => {
            button.addEventListener('click', () => {
                const metadata = JSON.parse(button.dataset.metadata);
                this.renderMetadataModal(metadata);
                modals.metadata.classList.add('active');
            });
        });

        // Player modal handlers
        document.querySelectorAll('.play-media-btn').forEach(button => {
            button.addEventListener('click', () => {
                const { filename, type, title } = button.dataset;
                this.renderPlayerModal(filename, type, title);
                modals.player.classList.add('active');
            });
        });

        // Close modal handlers
        document.querySelectorAll('.close-modal-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                Object.values(modals).forEach(modal => modal.classList.remove('active'));
                this.stopAllMedia();
            });
        });

        // Close on outside click
        Object.values(modals).forEach(modal => {
            modal.addEventListener('click', (e) => {
                if (e.target === modal) {
                    modal.classList.remove('active');
                    this.stopAllMedia();
                }
            });
        });
    }

    renderMetadataModal(metadata) {
        const contentEl = document.getElementById('metadata-modal-content');
        contentEl.innerHTML = `
            <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                    <img src="${metadata.thumbnail_url || 'https://placehold.co/400x225/1f2937/374151?text=Sem+Thumb'}" 
                         alt="Thumbnail" class="w-full rounded-lg shadow-lg">
                </div>
                <div class="space-y-4">
                    <div>
                        <h4 class="font-semibold text-cyan-300 mb-2">Informações Básicas</h4>
                        <p><strong>Título:</strong> ${metadata.title}</p>
                        <p><strong>Autor:</strong> ${metadata.uploader}</p>
                        <p><strong>Duração:</strong> ${metadata.duration_string}</p>
                        <p><strong>Data de Upload:</strong> ${metadata.upload_date}</p>
                    </div>
                    <div>
                        <h4 class="font-semibold text-cyan-300 mb-2">Estatísticas</h4>
                        <p><strong>Visualizações:</strong> ${new Intl.NumberFormat().format(metadata.view_count || 0)}</p>
                        <p><strong>Gostos:</strong> ${new Intl.NumberFormat().format(metadata.like_count || 0)}</p>
                    </div>
                    <div>
                        <h4 class="font-semibold text-cyan-300 mb-2">Links</h4>
                        <p><strong>URL Original:</strong> <a href="${metadata.webpage_url}" target="_blank" class="text-cyan-400 hover:underline">Abrir no YouTube</a></p>
                    </div>
                </div>
            </div>
            <div class="mt-6">
                <h4 class="font-semibold text-cyan-300 mb-2">Descrição</h4>
                <div class="bg-gray-800 p-4 rounded-lg max-h-40 overflow-y-auto">
                    <p class="text-sm text-gray-300 whitespace-pre-wrap">${metadata.description || 'Sem descrição disponível.'}</p>
                </div>
            </div>
        `;
    }

    renderPlayerModal(filename, type, title) {
        const playerContent = document.getElementById('player-content');
        const downloadUrl = `/api/download/${filename}`;
        
        if (type === 'audio') {
            playerContent.innerHTML = `
                <div class="text-center">
                    <h3 class="text-xl font-semibold text-white mb-4">${title}</h3>
                    <audio controls class="w-full max-w-md mx-auto" autoplay>
                        <source src="${downloadUrl}" type="audio/mpeg">
                        Seu navegador não suporta o elemento de áudio.
                    </audio>
                </div>
            `;
        } else {
            playerContent.innerHTML = `
                <div class="text-center">
                    <h3 class="text-xl font-semibold text-white mb-4">${title}</h3>
                    <video controls class="w-full max-w-4xl mx-auto rounded-lg" autoplay>
                        <source src="${downloadUrl}" type="video/mp4">
                        Seu navegador não suporta o elemento de vídeo.
                    </video>
                </div>
            `;
        }
    }

    stopAllMedia() {
        const playerContent = document.getElementById('player-content');
        const audio = playerContent.querySelector('audio');
        const video = playerContent.querySelector('video');
        if (audio) audio.pause();
        if (video) video.pause();
    }

    setupApiTester() {
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
                    addLog(`URL para Download: <a href="${result.result.download_url}" class="text-cyan-400 hover:underline" target="_blank">${result.result.download_url}</a>`);
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
                    addLog(`URL para Download: <a href="${result.result.download_url}" class="text-cyan-400 hover:underline" target="_blank">${result.result.download_url}</a>`);
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

    setupFileManagement() {
        // Delete file handlers
        document.querySelectorAll('.delete-file-btn').forEach(button => {
            button.addEventListener('click', async () => {
                if (!confirm('Tem certeza que deseja deletar este arquivo?')) return;
                
                const filename = button.dataset.filename;
                const card = button.closest('.file-card');
                
                try {
                    card.classList.add('delete-animation');
                    
                    const response = await fetch('/admin/files/delete', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ filename })
                    });
                    
                    if (response.ok) {
                        setTimeout(() => card.remove(), 300);
                        this.showNotification('Arquivo deletado com sucesso!', 'success');
                        this.updateFileStats();
                    } else {
                        card.classList.remove('delete-animation');
                        this.showNotification('Erro ao deletar arquivo', 'error');
                    }
                } catch (error) {
                    card.classList.remove('delete-animation');
                    this.showNotification('Erro de rede', 'error');
                }
            });
        });

        // Cleanup missing files handler
        const cleanupBtn = document.querySelector('.cleanup-files-btn');
        if (cleanupBtn) {
            cleanupBtn.addEventListener('click', async (e) => {
                e.preventDefault();
                if (!confirm('Tem certeza que deseja limpar arquivos ausentes?')) return;
                
                try {
                    const response = await fetch('/admin/files/cleanup', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' }
                    });
                    
                    const result = await response.json();
                    if (result.success) {
                        this.showNotification(`${result.removed_count} registros removidos!`, 'success');
                        setTimeout(() => location.reload(), 1000);
                    }
                } catch (error) {
                    this.showNotification('Erro ao limpar arquivos', 'error');
                }
            });
        }
    }

    setupHistoryManagement() {
        // Delete history item handlers
        document.querySelectorAll('.delete-history-btn').forEach(button => {
            button.addEventListener('click', async () => {
                if (!confirm('Tem certeza que deseja deletar este item do histórico?')) return;
                
                const historyId = button.dataset.historyId;
                const row = button.closest('tr');
                
                try {
                    row.classList.add('delete-animation');
                    
                    const response = await fetch('/admin/history/delete', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ id: parseInt(historyId) })
                    });
                    
                    if (response.ok) {
                        setTimeout(() => row.remove(), 300);
                        this.showNotification('Item removido do histórico!', 'success');
                        this.updateHistoryStats();
                    } else {
                        row.classList.remove('delete-animation');
                        this.showNotification('Erro ao remover item', 'error');
                    }
                } catch (error) {
                    row.classList.remove('delete-animation');
                    this.showNotification('Erro de rede', 'error');
                }
            });
        });

        // Clear all history handler
        const clearBtn = document.querySelector('.clear-history-btn');
        if (clearBtn) {
            clearBtn.addEventListener('click', async () => {
                if (!confirm('Tem certeza que deseja limpar todo o histórico?')) return;
                
                try {
                    const response = await fetch('/admin/history/clear', {
                        method: 'POST',
                        headers: { 
                            'Content-Type': 'application/json',
                            'X-Requested-With': 'XMLHttpRequest'
                        }
                    });
                    
                    const result = await response.json();
                    if (result.success) {
                        this.showNotification('Histórico limpo com sucesso!', 'success');
                        // Remove all history rows
                        const tbody = document.querySelector('#history tbody');
                        if (tbody) {
                            tbody.innerHTML = `
                                <tr>
                                    <td colspan="4" class="text-center py-8 text-gray-500">
                                        <i class="fas fa-inbox text-4xl mb-4 block"></i>
                                        Nenhum histórico encontrado.
                                    </td>
                                </tr>
                            `;
                        }
                        this.updateHistoryStats();
                    } else {
                        this.showNotification('Erro ao limpar histórico', 'error');
                    }
                } catch (error) {
                    this.showNotification('Erro ao limpar histórico', 'error');
                }
            });
        }
    }

    setupCookieManagement() {
        // Sync cookies handler
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
                        this.showNotification(result.message, 'success');
                        this.updateCookieStatus(result.status);
                    } else {
                        this.showNotification('Erro ao sincronizar cookies', 'error');
                    }
                } catch (error) {
                    this.showNotification('Erro de rede', 'error');
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

    updateFileStats() {
        // Atualiza contadores de arquivos
        const fileCards = document.querySelectorAll('.file-card');
        const totalFiles = fileCards.length;
        const missingFiles = document.querySelectorAll('.file-card .bg-red-900').length;
        
        // Atualiza elementos de estatística se existirem
        const totalFilesEl = document.querySelector('[data-stat="total-files"]');
        const missingFilesEl = document.querySelector('[data-stat="missing-files"]');
        
        if (totalFilesEl) totalFilesEl.textContent = totalFiles;
        if (missingFilesEl) missingFilesEl.textContent = missingFiles;
    }

    updateHistoryStats() {
        // Atualiza contadores do histórico
        const historyRows = document.querySelectorAll('tbody tr');
        const totalRequests = historyRows.length;
        
        const totalRequestsEl = document.querySelector('[data-stat="total-requests"]');
        if (totalRequestsEl) totalRequestsEl.textContent = totalRequests;
    }

    autoHideFlashMessages() {
        setTimeout(() => {
            const flashContainer = document.getElementById('flash-container');
            if (flashContainer) {
                flashContainer.style.transition = 'opacity 0.5s ease';
                flashContainer.style.opacity = '0';
                setTimeout(() => flashContainer.remove(), 500);
            }
        }, 5000);
    }

    initializeTooltips() {
        // Add tooltip functionality for elements with data-tooltip attribute
        document.querySelectorAll('[data-tooltip]').forEach(element => {
            element.classList.add('tooltip');
        });
    }

    showNotification(message, type = 'info') {
        const notification = document.createElement('div');
        notification.className = `fixed top-5 right-5 z-50 p-4 rounded-lg glass-effect border text-white shadow-xl animate-pulse ${
            type === 'success' ? 'border-green-500' : 
            type === 'error' ? 'border-red-500' : 'border-blue-500'
        }`;
        notification.textContent = message;
        
        document.body.appendChild(notification);
        
        setTimeout(() => {
            notification.style.transition = 'opacity 0.5s ease';
            notification.style.opacity = '0';
            setTimeout(() => notification.remove(), 500);
        }, 3000);
    }
}

// Initialize dashboard when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new Dashboard();
});