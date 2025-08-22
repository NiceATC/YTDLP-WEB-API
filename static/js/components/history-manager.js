// History Manager
class HistoryManager {
    constructor(dashboard) {
        this.dashboard = dashboard;
        this.init();
    }

    init() {
        this.setupHistoryActions();
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
                        this.dashboard.showNotification('Erro ao limpar histórico', 'error');
                    }
                } catch (error) {
                    this.dashboard.showNotification('Erro ao limpar histórico', 'error');
                }
            });
        }
    }

    updateHistoryStats() {
        const historyRows = document.querySelectorAll('#history tbody tr');
        const totalRequests = historyRows.length;
        
        const totalRequestsEl = document.querySelector('[data-stat="total-requests"]');
        if (totalRequestsEl) totalRequestsEl.textContent = totalRequests;
    }
}

// Export for use in main dashboard
window.HistoryManager = HistoryManager;