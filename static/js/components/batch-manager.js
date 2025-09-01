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
                const urls = formData.get('urls');
                const mediaType = formData.get('type');
                
                if (!urls || !mediaType) {
                    this.dashboard.showNotification('Todos os campos obrigatórios devem ser preenchidos', 'error');
                    return;
                }
                
                const urlList = urls.split('\n').filter(url => url.trim());
                if (urlList.length === 0) {
                    this.dashboard.showNotification('Pelo menos uma URL deve ser fornecida', 'error');
                    return;
                }
                
                try {
                    const response = await fetch('/admin/batch-download', {
                        method: 'POST',
                        body: formData
                    });
                    
                    const result = await response.json();
                    
                    if (result.success) {
                        this.dashboard.showNotification(result.message, 'success');
                        this.dashboard.modalManager.closeAllModals();
                        batchDownloadForm.reset();
                        
                        // Start progress tracking
                        this.dashboard.progressTracker.startTracking(result.task_id, 'batch', {
                            total_urls: result.total_urls
                        });
                    } else {
                        this.dashboard.showNotification(result.error || 'Erro ao iniciar download em lote', 'error');
                    }
                } catch (error) {
                    console.error('Erro ao iniciar download em lote:', error);
                    this.dashboard.showNotification('Erro ao iniciar download em lote', 'error');
                }
            });
        }
    }
}

// Export for use in main dashboard
window.BatchManager = BatchManager;