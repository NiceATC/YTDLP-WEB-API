// History Manager
class HistoryManager {
    constructor(dashboard) {
        this.dashboard = dashboard;
        this.init();
    }

    init() {
        this.setupHistoryActions();
        this.setupHistoryFilters();
        this.setupRefreshButton();
    }

    setupHistoryActions() {
        // Delete history item handlers
        document.addEventListener('click', async (e) => {
            if (e.target.closest('.delete-history-btn')) {
                e.preventDefault();
                const button = e.target.closest('.delete-history-btn');
                
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
                        setTimeout(() => {
                            row.remove();
                            this.updateHistoryStats();
                        }, 300);
                        this.dashboard.showNotification('Item removido do histórico!', 'success');
                    } else {
                        row.classList.remove('delete-animation');
                        this.dashboard.showNotification('Erro ao remover item', 'error');
                    }
                } catch (error) {
                    row.classList.remove('delete-animation');
                    this.dashboard.showNotification('Erro de rede', 'error');
                }
            }
        });

        // Clear all history handler
        const clearBtn = document.querySelector('.clear-history-btn');
        if (clearBtn) {
            clearBtn.addEventListener('click', async (e) => {
                e.preventDefault();
                
                if (!confirm('Tem certeza que deseja limpar todo o histórico?')) return;
                
                try {
                    const originalText = clearBtn.innerHTML;
                    clearBtn.disabled = true;
                    clearBtn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i>Limpando...';
                    
                    const response = await fetch('/admin/history/clear', {
                        method: 'POST',
                        headers: { 
                            'Content-Type': 'application/json',
                            'X-Requested-With': 'XMLHttpRequest'
                        }
                    });
                    
                    const result = await response.json();
                    if (result.success) {
                        this.dashboard.showNotification('Histórico limpo com sucesso!', 'success');
                        // Reload the page to refresh all data including charts
                        setTimeout(() => location.reload(), 1000);
                    } else {
                        this.dashboard.showNotification('Erro ao limpar histórico', 'error');
                    }
                } catch (error) {
                    this.dashboard.showNotification('Erro ao limpar histórico', 'error');
                } finally {
                    clearBtn.disabled = false;
                    clearBtn.innerHTML = originalText;
                }
            });
        }

        // Track task handlers
        document.addEventListener('click', (e) => {
            if (e.target.closest('.track-task-btn')) {
                e.preventDefault();
                const button = e.target.closest('.track-task-btn');
                const taskId = button.dataset.taskId;
                const taskType = button.dataset.taskType || 'single';
                
                // Start tracking this task
                this.dashboard.progressTracker.startTracking(taskId, taskType, {
                    source: 'history'
                });
                
                this.dashboard.showNotification(`Iniciando acompanhamento da tarefa ${taskId}`, 'info');
            }
        });

        // Copy response handler
        document.addEventListener('click', (e) => {
            if (e.target.closest('#copy-response-btn')) {
                e.preventDefault();
                const jsonContent = document.getElementById('modal-json-content').textContent;
                
                navigator.clipboard.writeText(jsonContent).then(() => {
                    this.dashboard.showNotification('JSON copiado para área de transferência!', 'success');
                }).catch(() => {
                    this.dashboard.showNotification('Erro ao copiar JSON', 'error');
                });
            }
        });

        // Click to copy JSON
        document.addEventListener('click', (e) => {
            if (e.target.closest('#modal-json-content')) {
                e.preventDefault();
                const jsonContent = e.target.closest('#modal-json-content').textContent;
                
                navigator.clipboard.writeText(jsonContent).then(() => {
                    this.dashboard.showNotification('JSON copiado!', 'success');
                });
            }
        });
    }

    setupHistoryFilters() {
        const statusFilter = document.getElementById('history-status-filter');
        const typeFilter = document.getElementById('history-type-filter');
        const categoryFilter = document.getElementById('history-category-filter');
        const periodFilter = document.getElementById('history-period-filter');
        
        [statusFilter, typeFilter, categoryFilter, periodFilter].forEach(filter => {
            if (filter) {
                filter.addEventListener('change', () => this.filterHistory());
            }
        });
    }

    setupRefreshButton() {
        const refreshBtn = document.querySelector('.refresh-history-btn');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', async (e) => {
                e.preventDefault();
                
                try {
                    const originalText = refreshBtn.innerHTML;
                    refreshBtn.disabled = true;
                    refreshBtn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i>Atualizando...';
                    
                    // Simula refresh (em uma implementação real, faria fetch dos dados)
                    await new Promise(resolve => setTimeout(resolve, 1000));
                    
                    location.reload();
                } catch (error) {
                    this.dashboard.showNotification('Erro ao atualizar histórico', 'error');
                } finally {
                    refreshBtn.disabled = false;
                    refreshBtn.innerHTML = originalText;
                }
            });
        }
    }

    filterHistory() {
        const statusFilter = document.getElementById('history-status-filter')?.value || '';
        const typeFilter = document.getElementById('history-type-filter')?.value || '';
        const categoryFilter = document.getElementById('history-category-filter')?.value || '';
        const periodFilter = document.getElementById('history-period-filter')?.value || '';
        
        const rows = document.querySelectorAll('.history-row');
        let visibleCount = 0;
        
        rows.forEach(row => {
            let show = true;
            
            // Filter by status
            if (statusFilter && row.dataset.status !== statusFilter) {
                show = false;
            }
            
            // Filter by type
            if (typeFilter && row.dataset.type !== typeFilter) {
                show = false;
            }
            
            // Filter by category
            if (categoryFilter && row.dataset.category !== categoryFilter) {
                show = false;
            }
            
            // Filter by period
            if (periodFilter) {
                const rowDate = new Date(row.dataset.date);
                const now = new Date();
                let cutoff;
                
                switch (periodFilter) {
                    case 'today':
                        cutoff = new Date(now.getFullYear(), now.getMonth(), now.getDate());
                        break;
                    case 'week':
                        cutoff = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
                        break;
                    case 'month':
                        cutoff = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);
                        break;
                }
                
                if (cutoff && rowDate < cutoff) {
                    show = false;
                }
            }
            
            if (show) {
                row.style.display = '';
                visibleCount++;
            } else {
                row.style.display = 'none';
            }
        });
        
        // Update stats
        this.updateFilteredStats(visibleCount);
    }

    updateFilteredStats(visibleCount) {
        const totalEl = document.getElementById('history-total');
        if (totalEl) {
            totalEl.textContent = visibleCount;
        }
        
        // Count visible items by status
        const visibleRows = document.querySelectorAll('.history-row[style=""], .history-row:not([style])');
        const completed = Array.from(visibleRows).filter(row => row.dataset.status === 'completed').length;
        const processing = Array.from(visibleRows).filter(row => row.dataset.status === 'processing').length;
        const failed = Array.from(visibleRows).filter(row => row.dataset.status === 'failed').length;
        
        const completedEl = document.getElementById('history-completed');
        const processingEl = document.getElementById('history-processing');
        const failedEl = document.getElementById('history-failed');
        
        if (completedEl) completedEl.textContent = completed;
        if (processingEl) processingEl.textContent = processing;
        if (failedEl) failedEl.textContent = failed;
    }

    updateHistoryStats() {
        const historyRows = document.querySelectorAll('.history-row');
        const totalRequests = historyRows.length;
        
        const totalRequestsEl = document.querySelector('[data-stat="total-requests"]');
        if (totalRequestsEl) totalRequestsEl.textContent = totalRequests;
    }
}

// Export for use in main dashboard
window.HistoryManager = HistoryManager;