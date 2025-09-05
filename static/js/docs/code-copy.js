// Code Copy Functionality
class CodeCopy {
    constructor() {
        this.init();
    }

    init() {
        this.addCopyButtons();
        this.setupCopyHandlers();
    }

    addCopyButtons() {
        document.querySelectorAll('.code-block pre').forEach(block => {
            const button = document.createElement('button');
            button.className = 'copy-btn';
            button.textContent = 'Copiar';
            button.setAttribute('data-copy', 'true');
            
            const container = block.parentElement;
            container.style.position = 'relative';
            container.appendChild(button);
        });
    }

    setupCopyHandlers() {
        document.addEventListener('click', async (e) => {
            if (e.target.matches('[data-copy]')) {
                e.preventDefault();
                
                const button = e.target;
                const codeBlock = button.parentElement.querySelector('pre code');
                const text = codeBlock.textContent;
                
                try {
                    await navigator.clipboard.writeText(text);
                    
                    const originalText = button.textContent;
                    button.textContent = 'Copiado!';
                    button.style.background = 'rgba(34, 197, 94, 0.8)';
                    
                    setTimeout(() => {
                        button.textContent = originalText;
                        button.style.background = 'rgba(107, 114, 128, 0.8)';
                    }, 2000);
                    
                } catch (err) {
                    console.error('Erro ao copiar:', err);
                    button.textContent = 'Erro!';
                    button.style.background = 'rgba(239, 68, 68, 0.8)';
                    
                    setTimeout(() => {
                        button.textContent = 'Copiar';
                        button.style.background = 'rgba(107, 114, 128, 0.8)';
                    }, 2000);
                }
            }
        });

        // Also allow clicking on code blocks to copy
        document.addEventListener('click', async (e) => {
            if (e.target.matches('pre code') || e.target.closest('pre code')) {
                const codeElement = e.target.matches('pre code') ? e.target : e.target.closest('pre code');
                const text = codeElement.textContent;
                
                try {
                    await navigator.clipboard.writeText(text);
                    
                    // Show temporary feedback
                    const feedback = document.createElement('div');
                    feedback.className = 'fixed top-5 right-5 bg-green-600 text-white px-4 py-2 rounded-lg shadow-lg z-50';
                    feedback.textContent = 'Código copiado!';
                    document.body.appendChild(feedback);
                    
                    setTimeout(() => {
                        feedback.remove();
                    }, 2000);
                    
                } catch (err) {
                    console.error('Erro ao copiar código:', err);
                }
            }
        });
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new CodeCopy();
});