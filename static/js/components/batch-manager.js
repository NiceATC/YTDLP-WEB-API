// Batch Download Manager
class BatchManager {
    constructor(dashboard) {
        this.dashboard = dashboard;
        this.init();
    }

    init() {
        this.setupBatchDownloadModal();
        this.setupBatchDownloadForm();
    }

    setupBatchDownloadModal() {
        const batchDownloadBtn = document.querySelector('.batch-download-btn');
        if (batchDownloadBtn) {
            batchDownloadBtn.addEventListener('click', (e) => {
                e.preventDefault();
                this.dashboard.modalManager.showModal('batchDownload');
            });
        }
    }

    setupBatchDownloadForm() {
        const batchDownloadForm = document.getElementById('batch-download-form');
        if (batchDownloadForm) {
            batchDownloadForm.addEventListener('submit', async (e) => {
                e.preventDefault();
                
                const formData = new FormData(batchDownloadForm);
                const batchName = formData.get('batch_name');
                const urls = formData.get('urls');
                const mediaType = formData.get('type');
                
                // Validação detalhada
                if (!batchName || !batchName.trim()) {
                    this.dashboard.showNotification('Nome do lote é obrigatório', 'error');
                    return;
                }
                
                if (!urls || !urls.trim()) {
                    this.dashboard.showNotification('URLs são obrigatórias', 'error');
                    return;
                }
                
                if (!mediaType) {
                    this.dashboard.showNotification('Tipo de mídia é obrigatório', 'error');
                    return;
                }
                
                const urlList = urls.split('\n').filter(url => url.trim());
                if (urlList.length === 0) {
                    this.dashboard.showNotification('Pelo menos uma URL válida deve ser fornecida', 'error');
                    return;
                }
                
                try {
                    // Desabilita botão durante envio
                    const submitBtn = batchDownloadForm.querySelector('button[type="submit"]');
                    const originalText = submitBtn.innerHTML;
                    submitBtn.disabled = true;
                    submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i>Iniciando...';
                    
                    const response = await fetch('/admin/batch-download', {
                        method: 'POST',
                        body: formData
                    });
                    
                    const result = await response.json();
                    
                    if (result.success) {
                        this.dashboard.showNotification(`Download em lote iniciado: ${urlList.length} URLs`, 'success');
                        this.dashboard.modalManager.closeAllModals();
                        batchDownloadForm.reset();
                        
                        // Inicia acompanhamento em tempo real
                        this.dashboard.progressTracker.startTracking(result.task_id, 'batch', {
                            total_urls: urlList.length,
                            batch_name: batchName
                        });
                    } else {
                        this.dashboard.showNotification(result.error || 'Erro ao iniciar download em lote', 'error');
                    }
                } catch (error) {
                    console.error('Erro ao iniciar download em lote:', error);
                    this.dashboard.showNotification('Erro de rede ao iniciar download', 'error');
                } finally {
                    // Reabilita botão
                    const submitBtn = batchDownloadForm.querySelector('button[type="submit"]');
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = originalText;
                }
            });
        }
    }
}

// Export for use in main dashboard
window.BatchManager = BatchManager;