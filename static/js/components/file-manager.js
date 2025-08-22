// File Manager
class FileManager {
    constructor(dashboard) {
        this.dashboard = dashboard;
        this.currentView = 'grid';
        this.init();
    }

    init() {
        this.setupFileActions();
        this.setupFilters();
        this.setupViewToggle();
        this.setupFolderActions();
    }

    setupFileActions() {
        // Delete file handlers
        this.setupDeleteHandlers();
        
        // Move file handlers
        this.setupMoveHandlers();
    }

    setupDeleteHandlers() {
        document.addEventListener('click', async (e) => {
            if (e.target.closest('.delete-file-btn')) {
                e.preventDefault();
                const button = e.target.closest('.delete-file-btn');
                
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
                        setTimeout(() => {
                            card.remove();
                            this.updateFileStats();
                        }, 300);
                        this.dashboard.showNotification('Arquivo deletado com sucesso!', 'success');
                    } else {
                        card.classList.remove('delete-animation');
                        this.dashboard.showNotification('Erro ao deletar arquivo', 'error');
                    }
                } catch (error) {
                    card.classList.remove('delete-animation');
                    this.dashboard.showNotification('Erro de rede', 'error');
                }
            }
        });
    }

    setupMoveHandlers() {
        document.addEventListener('click', (e) => {
            if (e.target.closest('.move-file-btn')) {
                e.preventDefault();
                const button = e.target.closest('.move-file-btn');
                const fileId = button.dataset.fileId;
                
                document.getElementById('move-file-id').value = fileId;
                this.dashboard.modalManager.showModal('moveFile');
            }
        });

        // Move file form submission
        const moveFileForm = document.getElementById('move-file-form');
        if (moveFileForm) {
            moveFileForm.addEventListener('submit', async (e) => {
                e.preventDefault();
                const formData = new FormData(moveFileForm);
                
                try {
                    const response = await fetch('/admin/files/move', {
                        method: 'POST',
                        body: formData
                    });
                    
                    const result = await response.json();
                    
                    if (result.success) {
                        this.dashboard.showNotification('Arquivo movido com sucesso!', 'success');
                        this.dashboard.modalManager.closeAllModals();
                        this.filterFiles(); // Refresh file list
                    } else {
                        this.dashboard.showNotification(result.error || 'Erro ao mover arquivo', 'error');
                    }
                } catch (error) {
                    this.dashboard.showNotification('Erro ao mover arquivo', 'error');
                }
            });
        }
    }

    setupFilters() {
        const searchInput = document.getElementById('file-search');
        const folderFilter = document.getElementById('folder-filter');
        const typeFilter = document.getElementById('type-filter');
        const sortFilter = document.getElementById('sort-filter');
        
        [searchInput, folderFilter, typeFilter, sortFilter].forEach(element => {
            if (element) {
                element.addEventListener('change', () => this.filterFiles());
                if (element === searchInput) {
                    element.addEventListener('input', this.debounce(() => this.filterFiles(), 300));
                }
            }
        });
    }

    setupViewToggle() {
        const gridViewBtn = document.getElementById('grid-view-btn');
        const listViewBtn = document.getElementById('list-view-btn');
        const filesGrid = document.getElementById('files-grid');

        if (gridViewBtn && listViewBtn && filesGrid) {
            gridViewBtn.addEventListener('click', () => {
                this.currentView = 'grid';
                filesGrid.className = 'grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4';
                gridViewBtn.classList.add('bg-cyan-600');
                gridViewBtn.classList.remove('bg-gray-600');
                listViewBtn.classList.add('bg-gray-600');
                listViewBtn.classList.remove('bg-cyan-600');
            });

            listViewBtn.addEventListener('click', () => {
                this.currentView = 'list';
                filesGrid.className = 'space-y-2';
                listViewBtn.classList.add('bg-cyan-600');
                listViewBtn.classList.remove('bg-gray-600');
                gridViewBtn.classList.add('bg-gray-600');
                gridViewBtn.classList.remove('bg-cyan-600');
            });
        }
    }

    setupFolderActions() {
        // Folder click handlers
        document.addEventListener('click', (e) => {
            if (e.target.closest('.folder-item')) {
                const folderItem = e.target.closest('.folder-item');
                const folderId = folderItem.dataset.folderId;
                
                // Update folder filter
                const folderFilter = document.getElementById('folder-filter');
                if (folderFilter) {
                    folderFilter.value = folderId === '0' ? '' : folderId;
                    this.filterFiles();
                }
                
                // Visual feedback
                document.querySelectorAll('.folder-item').forEach(item => {
                    item.classList.remove('bg-cyan-600/20', 'border-cyan-500');
                });
                folderItem.classList.add('bg-cyan-600/20', 'border-cyan-500');
            }
        });

        // Delete folder handlers
        document.addEventListener('click', async (e) => {
            if (e.target.closest('.delete-folder-btn')) {
                e.preventDefault();
                e.stopPropagation();
                
                const button = e.target.closest('.delete-folder-btn');
                const folderId = button.dataset.folderId;
                
                if (confirm('Tem certeza que deseja deletar esta pasta? Os arquivos serão movidos para a raiz.')) {
                    try {
                        const response = await fetch('/admin/folders/delete', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ folder_id: parseInt(folderId) })
                        });

                        const result = await response.json();
                        if (result.success) {
                            button.closest('.folder-item').remove();
                            this.dashboard.showNotification('Pasta deletada com sucesso!', 'success');
                            this.filterFiles(); // Refresh file list
                        } else {
                            this.dashboard.showNotification(result.error || 'Erro ao deletar pasta', 'error');
                        }
                    } catch (error) {
                        this.dashboard.showNotification('Erro ao deletar pasta', 'error');
                    }
                }
            }
        });
    }

    async filterFiles() {
        const search = document.getElementById('file-search')?.value || '';
        const folder = document.getElementById('folder-filter')?.value || '';
        const type = document.getElementById('type-filter')?.value || '';
        const sort = document.getElementById('sort-filter')?.value || 'created_at-desc';
        
        const params = new URLSearchParams({
            search,
            folder_id: folder,
            media_type: type,
            sort: sort
        });
        
        try {
            const response = await fetch(`/admin/files/filter?${params}`);
            const data = await response.json();
            
            if (data.success) {
                document.getElementById('files-grid').innerHTML = data.html;
                document.getElementById('files-count').textContent = data.count;
                
                // Re-setup event listeners for new elements
                this.dashboard.modalManager.setupMetadataModals();
                this.dashboard.modalManager.setupPlayerModals();
            }
        } catch (error) {
            this.dashboard.showNotification('Erro ao filtrar arquivos', 'error');
        }
    }

    updateFileStats() {
        const fileCards = document.querySelectorAll('.file-card');
        const totalFiles = fileCards.length;
        const missingFiles = document.querySelectorAll('.file-card .bg-red-900').length;
        
        const totalFilesEl = document.querySelector('[data-stat="total-files"]');
        const missingFilesEl = document.querySelector('[data-stat="missing-files"]');
        
        if (totalFilesEl) totalFilesEl.textContent = totalFiles;
        if (missingFilesEl) missingFilesEl.textContent = missingFiles;
    }

    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }

    async cleanupMissingFiles() {
        try {
            const response = await fetch('/admin/files/cleanup', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            
            const result = await response.json();
            if (result.success) {
                this.dashboard.showNotification(`${result.removed_count} registros removidos!`, 'success');
                setTimeout(() => location.reload(), 1000);
            }
        } catch (error) {
            this.dashboard.showNotification('Erro ao limpar arquivos', 'error');
        }
    }
}

// Export for use in main dashboard
window.FileManager = FileManager;