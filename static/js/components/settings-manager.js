// Settings Manager
class SettingsManager {
    constructor(dashboard) {
        this.dashboard = dashboard;
        this.init();
    }

    init() {
        this.setupTabs();
        this.setupBrandingForm();
        this.setupApiKeyManagement();
        this.setupCookieManagement();
        this.setupAdvancedActions();
    }

    setupTabs() {
        const tabButtons = document.querySelectorAll('.settings-tab-btn');
        const tabContents = document.querySelectorAll('.settings-tab-content');
        
        tabButtons.forEach(button => {
            button.addEventListener('click', () => {
                const targetTab = button.dataset.tab;
                
                // Update button states
                tabButtons.forEach(btn => {
                    btn.classList.remove('text-cyan-300', 'border-b-2', 'border-cyan-500', 'bg-gray-700/30');
                    btn.classList.add('text-gray-400');
                });
                button.classList.remove('text-gray-400');
                button.classList.add('text-cyan-300', 'border-b-2', 'border-cyan-500', 'bg-gray-700/30');
                
                // Update content visibility
                tabContents.forEach(content => {
                    content.classList.add('hidden');
                });
                document.getElementById(`${targetTab}-tab`).classList.remove('hidden');
            });
        });
    }

    setupBrandingForm() {
        const brandingForm = document.querySelector('#branding-tab form');
        if (brandingForm) {
            brandingForm.addEventListener('submit', async (e) => {
                e.preventDefault();
                
                const formData = new FormData(brandingForm);
                
                try {
                    const response = await fetch('/admin/app-settings', {
                        method: 'POST',
                        body: formData
                    });
                    
                    const result = await response.json();
                    
                    if (result.success) {
                        this.dashboard.showNotification('Configurações salvas com sucesso!', 'success');
                        this.applyBrandingChanges(result.settings);
                    } else {
                        this.dashboard.showNotification(result.error || 'Erro ao salvar configurações', 'error');
                    }
                } catch (error) {
                    this.dashboard.showNotification('Erro ao salvar configurações', 'error');
                }
            });
        }

        // Live preview
        ['app_name', 'app_logo', 'primary_color'].forEach(id => {
            const element = document.getElementById(id);
            if (element) {
                element.addEventListener('input', () => this.updatePreview());
            }
        });
    }

    setupApiKeyManagement() {
        // Create new API key
        const newApiKeyForm = document.getElementById('new-api-key-form');
        if (newApiKeyForm) {
            newApiKeyForm.addEventListener('submit', async (e) => {
                e.preventDefault();
                
                const formData = new FormData(newApiKeyForm);
                
                try {
                    const response = await fetch('/admin/api-keys/new', {
                        method: 'POST',
                        body: formData
                    });
                    
                    const result = await response.json();
                    
                    if (result.success) {
                        this.dashboard.showNotification(`Nova chave criada: ${result.api_key.key}`, 'success');
                        this.addApiKeyToList(result.api_key);
                        newApiKeyForm.reset();
                    } else {
                        this.dashboard.showNotification(result.error || 'Erro ao criar chave', 'error');
                    }
                } catch (error) {
                    this.dashboard.showNotification('Erro ao criar chave', 'error');
                }
            });
        }

        // Delete API keys
        document.addEventListener('click', async (e) => {
            if (e.target.closest('.delete-api-key-btn')) {
                e.preventDefault();
                const button = e.target.closest('.delete-api-key-btn');
                const apiKey = button.dataset.key;
                
                if (!confirm('Tem certeza que deseja deletar esta chave de API?')) return;
                
                try {
                    const response = await fetch('/admin/api-keys/delete', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ api_key: apiKey })
                    });
                    
                    if (response.ok) {
                        button.closest('.api-key-item').remove();
                        this.dashboard.showNotification('Chave removida com sucesso!', 'success');
                    } else {
                        this.dashboard.showNotification('Erro ao remover chave', 'error');
                    }
                } catch (error) {
                    this.dashboard.showNotification('Erro ao remover chave', 'error');
                }
            }
        });

        // Copy API keys
        document.addEventListener('click', (e) => {
            if (e.target.closest('.copy-key-btn')) {
                e.preventDefault();
                const button = e.target.closest('.copy-key-btn');
                const key = button.dataset.key;
                
                navigator.clipboard.writeText(key).then(() => {
                    this.dashboard.showNotification('Chave copiada!', 'success');
                });
            }
        });
    }

    setupCookieManagement() {
        const deleteCookiesBtn = document.querySelector('.delete-cookies-btn');
        if (deleteCookiesBtn) {
            deleteCookiesBtn.addEventListener('click', async (e) => {
                e.preventDefault();
                
                if (!confirm('Tem certeza que deseja remover os cookies?')) return;
                
                try {
                    const response = await fetch('/admin/cookies/delete', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' }
                    });
                    
                    const result = await response.json();
                    
                    if (result.success) {
                        this.dashboard.showNotification(result.message, 'success');
                        // Update cookie status
                        this.updateCookieStatus('missing');
                    } else {
                        this.dashboard.showNotification(result.error, 'error');
                    }
                } catch (error) {
                    this.dashboard.showNotification('Erro ao remover cookies', 'error');
                }
            });
        }
    }

    setupAdvancedActions() {
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
                        this.dashboard.showNotification(`${result.removed_count} registros removidos!`, 'success');
                    }
                } catch (error) {
                    this.dashboard.showNotification('Erro ao limpar arquivos', 'error');
                }
            });
        }
    }

    updatePreview() {
        const appName = document.getElementById('app_name')?.value || 'YTDL Web API';
        const appLogo = document.getElementById('app_logo')?.value;
        const primaryColor = document.getElementById('primary_color')?.value || '#0891b2';
        
        const namePreview = document.getElementById('app-name-preview');
        const logoPreview = document.getElementById('logo-preview');
        
        if (namePreview) namePreview.textContent = appName;
        
        if (logoPreview) {
            if (appLogo) {
                logoPreview.innerHTML = `<img src="${appLogo}" alt="Logo" class="w-full h-full object-contain rounded-lg">`;
            } else {
                logoPreview.innerHTML = '<i class="fas fa-download text-white text-xl"></i>';
            }
            logoPreview.style.background = `linear-gradient(135deg, ${primaryColor}, ${primaryColor}dd)`;
        }
    }

    applyBrandingChanges(settings) {
        // Apply changes to current page
        document.title = `${settings.app_name} - Admin Dashboard`;
        
        // Update any visible branding elements
        const sidebarTitle = document.querySelector('aside h1 span');
        if (sidebarTitle) sidebarTitle.textContent = settings.app_name;
        
        // Update logo
        const logoContainer = document.querySelector('aside h1');
        if (logoContainer && settings.app_logo) {
            const existingLogo = logoContainer.querySelector('img');
            const existingIcon = logoContainer.querySelector('i');
            
            if (existingIcon) existingIcon.remove();
            
            if (existingLogo) {
                existingLogo.src = settings.app_logo;
            } else {
                const logoImg = document.createElement('img');
                logoImg.src = settings.app_logo;
                logoImg.alt = 'Logo';
                logoImg.className = 'w-8 h-8 mr-2 rounded';
                logoContainer.insertBefore(logoImg, logoContainer.querySelector('span'));
            }
        }
        
        // Update CSS custom properties if needed
        document.documentElement.style.setProperty('--primary-color', settings.primary_color);
        document.documentElement.style.setProperty('--secondary-color', settings.secondary_color);
        
        // Update favicon
        if (settings.favicon_url) {
            let favicon = document.querySelector('link[rel="icon"]');
            if (!favicon) {
                favicon = document.createElement('link');
                favicon.rel = 'icon';
                favicon.type = 'image/x-icon';
                document.head.appendChild(favicon);
            }
            favicon.href = settings.favicon_url;
        }
    }

    addApiKeyToList(apiKey) {
        const apiKeysList = document.getElementById('api-keys-list');
        if (apiKeysList) {
            const keyHtml = `
                <div class="flex items-center justify-between bg-gray-700/30 p-4 rounded-lg border border-gray-600 api-key-item" data-key-id="${apiKey.id}">
                    <div class="flex-1">
                        <div class="flex items-center space-x-3">
                            <span class="font-mono text-sm text-white">${apiKey.key}</span>
                            <button class="copy-key-btn text-gray-400 hover:text-cyan-300 transition-colors" data-key="${apiKey.key}">
                                <i class="fas fa-copy"></i>
                            </button>
                        </div>
                        <div class="flex items-center space-x-4 mt-2">
                            <span class="text-sm text-gray-400">${apiKey.name || 'Sem nome'}</span>
                            <span class="text-xs text-gray-500">Criada: ${apiKey.created_at}</span>
                        </div>
                    </div>
                    <button class="delete-api-key-btn text-red-400 hover:text-red-300 p-2 rounded-lg hover:bg-red-900/20 transition-all" data-key="${apiKey.key}">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
            `;
            
            // Remove "no keys" message if exists
            const noKeysMsg = apiKeysList.querySelector('p');
            if (noKeysMsg) noKeysMsg.remove();
            
            apiKeysList.insertAdjacentHTML('beforeend', keyHtml);
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
window.SettingsManager = SettingsManager;