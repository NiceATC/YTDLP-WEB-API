// Modal Manager
class ModalManager {
    constructor() {
        this.modals = {
            response: document.getElementById('response-modal'),
            metadata: document.getElementById('metadata-modal'),
            player: document.getElementById('player-modal'),
            newFolder: document.getElementById('new-folder-modal'),
            batchDownload: document.getElementById('batch-download-modal'),
            moveFile: document.getElementById('move-file-modal')
        };
        this.init();
    }

    init() {
        this.setupModalHandlers();
        this.setupResponseModals();
        this.setupMetadataModals();
        this.setupPlayerModals();
    }

    setupModalHandlers() {
        // Close modal handlers
        document.querySelectorAll('.close-modal-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.preventDefault();
                this.closeAllModals();
            });
        });

        // Close on outside click
        Object.values(this.modals).forEach(modal => {
            if (modal) {
                modal.addEventListener('click', (e) => {
                    if (e.target === modal) {
                        this.closeAllModals();
                    }
                });
            }
        });

        // Close on ESC key
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                this.closeAllModals();
            }
        });
    }

    setupResponseModals() {
        document.querySelectorAll('.view-response-btn').forEach(button => {
            button.addEventListener('click', () => {
                const responseData = JSON.parse(button.dataset.response);
                document.getElementById('modal-json-content').textContent = JSON.stringify(responseData, null, 2);
                this.showModal('response');
            });
        });
    }

    setupMetadataModals() {
        document.querySelectorAll('.view-metadata-btn').forEach(button => {
            button.addEventListener('click', () => {
                const metadata = JSON.parse(button.dataset.metadata);
                this.renderMetadataModal(metadata);
                this.showModal('metadata');
            });
        });
    }

    setupPlayerModals() {
        document.querySelectorAll('.play-media-btn').forEach(button => {
            button.addEventListener('click', () => {
                const { filename, type, title } = button.dataset;
                this.renderPlayerModal(filename, type, title);
                this.showModal('player');
            });
        });
    }

    showModal(modalName) {
        this.closeAllModals();
        if (this.modals[modalName]) {
            this.modals[modalName].classList.add('active');
            document.body.style.overflow = 'hidden';
        }
    }

    closeAllModals() {
        Object.values(this.modals).forEach(modal => {
            if (modal) {
                modal.classList.remove('active');
            }
        });
        document.body.style.overflow = '';
        this.stopAllMedia();
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
        if (playerContent) {
            const audio = playerContent.querySelector('audio');
            const video = playerContent.querySelector('video');
            if (audio) audio.pause();
            if (video) video.pause();
        }
    }
}

// Export for use in main dashboard
window.ModalManager = ModalManager;