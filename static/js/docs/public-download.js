// Public Download Handler
class PublicDownload {
    constructor() {
        this.init();
    }

    init() {
        this.setupPublicDownloadForm();
    }

    setupPublicDownloadForm() {
        const form = document.getElementById('public-download-form');
        const logContainer = document.getElementById('public-download-log');

        if (!form || !logContainer) return;

        const addLog = (message, type = 'info') => {
            const timestamp = new Date().toLocaleTimeString();
            const color = type === 'error' ? 'text-red-400' : 
                         type === 'success' ? 'text-green-400' : 
                         type === 'warning' ? 'text-yellow-400' : 'text-gray-300';
            
            const logEntry = document.createElement('div');
            logEntry.className = `${color} text-sm mb-1`;
            logEntry.innerHTML = `<span class="text-gray-500">[${timestamp}]</span> ${message}`;
            
            logContainer.appendChild(logEntry);
            logContainer.scrollTop = logContainer.scrollHeight;
        };

        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const submitBtn = form.querySelector('button[type="submit"]');
            const originalText = submitBtn.innerHTML;
            
            // Clear log
            logContainer.innerHTML = '';
            
            // Get form data
            const url = document.getElementById('public-url').value;
            const type = document.getElementById('public-type').value;
            const quality = document.getElementById('public-quality').value;

            // Disable button
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i>Processando...';

            addLog('🚀 Iniciando download público...', 'info');
            addLog(`📋 URL: ${url}`, 'info');
            addLog(`🎵 Tipo: ${type}`, 'info');
            if (quality) addLog(`📺 Qualidade: ${quality}`, 'info');

            try {
                const params = new URLSearchParams({ type, url });
                if (quality) params.append('quality', quality);

                const response = await fetch(`/api/public/media?${params}`, {
                    method: 'GET',
                    headers: {
                        'Content-Type': 'application/json'
                    }
                });

                const result = await response.json();

                if (!response.ok) {
                    throw new Error(result.error || `Erro ${response.status}`);
                }

                addLog(`✅ Resposta recebida (${response.status})`, 'success');

                if (result.status === 'processing' && result.task_id) {
                    addLog(`⏳ Processamento iniciado. ID: ${result.task_id}`, 'warning');
                    addLog(`🔗 Acompanhando progresso...`, 'info');
                    
                    // Poll for status
                    this.pollTaskStatus(result.task_id, addLog);
                    
                } else if (result.status === 'completed' || (result.status && result.status.task === 'completed')) {
                    addLog('🎉 Download concluído com sucesso!', 'success');
                    
                    const downloadUrl = result.status?.download_url || result.result?.download_url;
                    if (downloadUrl) {
                        addLog(`📥 <a href="${downloadUrl}" class="text-cyan-400 hover:underline" target="_blank">Clique aqui para baixar</a>`, 'success');
                    }
                    
                    if (result.metadata) {
                        addLog(`🎵 Título: ${result.metadata.title}`, 'info');
                        addLog(`👤 Autor: ${result.metadata.uploader}`, 'info');
                        addLog(`⏱️ Duração: ${result.metadata.duration_string}`, 'info');
                    }
                } else if (result.status === 'failed') {
                    addLog(`❌ Download falhou: ${result.error || 'Erro desconhecido'}`, 'error');
                }

            } catch (error) {
                console.error('Erro no download público:', error);
                addLog(`❌ Erro: ${error.message}`, 'error');
                
                if (error.message.includes('429')) {
                    addLog('⏰ Limite de downloads atingido. Tente novamente mais tarde.', 'warning');
                } else if (error.message.includes('400')) {
                    addLog('📋 Verifique se a URL está correta e é suportada.', 'warning');
                }
            } finally {
                // Re-enable button
                submitBtn.disabled = false;
                submitBtn.innerHTML = originalText;
            }
        });
    }

    async pollTaskStatus(taskId, addLog) {
        let pollCount = 0;
        const maxPolls = 60; // 3 minutes maximum
        
        const intervalId = setInterval(async () => {
            pollCount++;
            
            if (pollCount > maxPolls) {
                addLog('⏰ Timeout: Parando verificação automática', 'warning');
                clearInterval(intervalId);
                return;
            }
            
            try {
                const response = await fetch(`/api/tasks/${taskId}`);
                const result = await response.json();
                
                if (!response.ok) {
                    addLog(`❌ Erro ao verificar status: ${result.error || 'Erro desconhecido'}`, 'error');
                    clearInterval(intervalId);
                    return;
                }
                
                if (result.status === 'completed') {
                    addLog('🎉 Download concluído com sucesso!', 'success');
                    
                    const taskResult = result.result || {};
                    
                    if (taskResult.playlist) {
                        addLog(`📋 Playlist processada: ${taskResult.videos?.length || 0} vídeos`, 'success');
                        if (taskResult.videos) {
                            taskResult.videos.forEach((video, index) => {
                                addLog(`${index + 1}. <a href="${video.download_url}" class="text-cyan-400 hover:underline" target="_blank">${video.title}</a>`, 'success');
                            });
                        }
                    } else {
                        const downloadUrl = taskResult.download_url;
                        if (downloadUrl) {
                            addLog(`📥 <a href="${downloadUrl}" class="text-cyan-400 hover:underline" target="_blank">Clique aqui para baixar</a>`, 'success');
                        }
                        
                        if (taskResult.title) {
                            addLog(`🎵 Título: ${taskResult.title}`, 'info');
                        }
                    }
                    
                    clearInterval(intervalId);
                    
                } else if (result.status === 'failed') {
                    addLog(`❌ Download falhou: ${result.error || result.message || 'Erro desconhecido'}`, 'error');
                    clearInterval(intervalId);
                    
                } else if (result.status === 'processing') {
                    const progress = result.progress || 0;
                    const message = result.message || 'Processando...';
                    addLog(`⏳ ${message} (${progress}%)`, 'info');
                    
                    if (result.current_title) {
                        addLog(`🎵 Processando: ${result.current_title}`, 'info');
                    }
                }
                
            } catch (error) {
                addLog(`🌐 Erro de rede: ${error.message}`, 'error');
                clearInterval(intervalId);
            }
        }, 3000); // Check every 3 seconds
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new PublicDownload();
});