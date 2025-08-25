// Folder Manager
class FolderManager {
    constructor(dashboard) {
        this.dashboard = dashboard;
        this.init();
    }

    init() {
        this.setupNewFolderModal();
        this.setupNewFolderForm();
    }

    setupNewFolderModal() {
        const newFolderBtn = document.querySelector('.new-folder-btn');
        if (newFolderBtn) {
            newFolderBtn.addEventListener('click', (e) => {
                e.preventDefault();
                this.dashboard.modalManager.showModal('newFolder');
            });
        }
    }

    setupNewFolderForm() {
        const newFolderForm = document.getElementById('new-folder-form');
        if (newFolderForm) {
            newFolderForm.addEventListener('submit', async (e) => {
                e.preventDefault();
                
                const formData = new FormData(newFolderForm);
                const folderName = formData.get('folder_name');
                
                if (!folderName || !folderName.trim()) {
                    this.dashboard.showNotification('Nome da pasta é obrigatório', 'error');
                    return;
                }
                
                try {
                    const response = await fetch('/admin/folders/create', {
                        method: 'POST',
                        body: formData
                    });
                    
                    const result = await response.json();
                    
                    if (result.success) {
                        this.dashboard.showNotification('Pasta criada com sucesso!', 'success');
                        this.dashboard.modalManager.closeAllModals();
                        newFolderForm.reset();
                        
                        // Add folder to interface
                        this.addFolderToInterface(result.folder);
                        
                        // Update folder filter dropdown
                        this.updateFolderFilter(result.folder);
                    } else {
                        this.dashboard.showNotification(result.error || 'Erro ao criar pasta', 'error');
                    }
                } catch (error) {
                    console.error('Erro ao criar pasta:', error);
                    this.dashboard.showNotification('Erro ao criar pasta', 'error');
                }
            });
        }
    }

    addFolderToInterface(folder) {
        const foldersGrid = document.getElementById('folders-grid');
        if (foldersGrid) {
            const folderHtml = `
                <div class="folder-item glass-effect p-4 rounded-lg cursor-pointer hover:bg-gray-700/30 transition-all group relative border border-gray-600" data-folder-id="${folder.id}">
                    <div class="text-center">
                        <i class="fas fa-folder text-3xl text-blue-400 mb-2"></i>
                        <p class="text-sm text-white">${folder.name}</p>
                        <p class="text-xs text-gray-400">0 arquivos</p>
                    </div>
                    <button class="delete-folder-btn absolute top-2 right-2 text-red-400 hover:text-red-300 opacity-0 group-hover:opacity-100 transition-opacity" data-folder-id="${folder.id}">
                        <i class="fas fa-times text-xs"></i>
                    </button>
                </div>
            `;
            foldersGrid.insertAdjacentHTML('beforeend', folderHtml);
        }
    }

    updateFolderFilter(folder) {
        const folderFilter = document.getElementById('folder-filter');
        const moveFolderSelect = document.querySelector('#move-file-modal select[name="folder_id"]');
        const batchFolderSelect = document.querySelector('#batch-download-modal select[name="folder_id"]');
        
        const optionHtml = `<option value="${folder.id}">${folder.name}</option>`;
        
        [folderFilter, moveFolderSelect, batchFolderSelect].forEach(select => {
            if (select) {
                select.insertAdjacentHTML('beforeend', optionHtml);
            }
        });
    }
}

// Export for use in main dashboard
window.FolderManager = FolderManager;