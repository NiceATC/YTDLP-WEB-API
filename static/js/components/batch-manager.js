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
                
                if (!batchName || !urls || !mediaType) {
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
                        this.dashboard.showNotification(`Download em lote iniciado! ${urlList.length} URLs processando...`, 'success');
                        this.dashboard.modalManager.closeAllModals();
                        batchDownloadForm.reset();
                        
                        // Show progress notification
                        this.showBatchProgress(result.batch_id, urlList.length);
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

    showBatchProgress(batchId, totalUrls) {
        // Create a progress notification that updates
        const progressNotification = document.createElement('div');
        progressNotification.className = 'fixed bottom-5 right-5 z-50 p-4 rounded-lg glass-effect border border-blue-500 text-white shadow-xl max-w-sm';
        progressNotification.innerHTML = `
            <div class="flex items-center justify-between mb-2">
                <h4 class="font-semibold">Download em Lote</h4>
                <button class="close-progress text-gray-400 hover:text-white">&times;</button>
            </div>
            <div class="text-sm text-gray-300 mb-2">
                Processando <span class="completed">0</span> de ${totalUrls} URLs
            </div>
            <div class="w-full bg-gray-700 rounded-full h-2">
                <div class="progress-bar bg-blue-600 h-2 rounded-full transition-all duration-300" style="width: 0%"></div>
            </div>
        `;
        
        document.body.appendChild(progressNotification);
        
        // Close button
        progressNotification.querySelector('.close-progress').addEventListener('click', () => {
            progressNotification.remove();
        });
        
        // Auto-remove after 30 seconds
        setTimeout(() => {
            if (progressNotification.parentNode) {
                progressNotification.remove();
            }
        }, 30000);
    }
}

// Export for use in main dashboard
window.BatchManager = BatchManager;