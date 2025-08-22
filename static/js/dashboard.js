// Dashboard JavaScript
class Dashboard {
    constructor() {
        this.init();
    }

    init() {
        this.setupNavigation();
        this.autoHideFlashMessages();
        this.initializeTooltips();
        this.initializeCharts();
        
        // Initialize component managers
        this.modalManager = new ModalManager();
        this.fileManager = new FileManager(this);
        this.folderManager = new FolderManager(this);
        this.batchManager = new BatchManager(this);
        this.apiTester = new ApiTester(this);
        this.historyManager = new HistoryManager(this);
    }

    setupNavigation() {
        const sections = document.querySelectorAll('.content-section');
        const navLinks = document.querySelectorAll('#sidebar-nav a');

        const showSection = (hash) => {
            sections.forEach(section => section.classList.remove('active'));
            navLinks.forEach(link => link.classList.remove('active'));
            
            const targetSection = document.querySelector(hash);
            const targetLink = document.querySelector(`#sidebar-nav a[href="${hash}"]`);
            
            if (targetSection) targetSection.classList.add('active');
            if (targetLink) targetLink.classList.add('active');
        };

        navLinks.forEach(link => {
            link.addEventListener('click', (e) => { 
                e.preventDefault();
                window.location.hash = e.currentTarget.getAttribute('href'); 
            });
        });

        window.addEventListener('hashchange', () => showSection(window.location.hash || '#overview'));
        
        const initialHash = window.location.hash || '#overview';
        showSection(initialHash);
    }

    initializeCharts() {
        // Requests Timeline Chart
        const requestsCtx = document.getElementById('requestsChart');
        if (requestsCtx) {
            const chartData = window.dashboardData?.chart_data || [];
            const labels = chartData.map(d => d.date);
            const data = chartData.map(d => d.requests);
            
            new Chart(requestsCtx, {
                type: 'line',
                data: {
                    labels: labels.length ? labels : ['Sem dados'],
                    datasets: [{
                        label: 'Requisições',
                        data: data.length ? data : [0],
                        borderColor: '#06b6d4',
                        backgroundColor: 'rgba(6, 182, 212, 0.1)',
                        tension: 0.4,
                        fill: true
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            labels: { color: '#ffffff' }
                        }
                    },
                    scales: {
                        x: { 
                            ticks: { color: '#9ca3af' },
                            grid: { color: 'rgba(156, 163, 175, 0.1)' }
                        },
                        y: { 
                            ticks: { color: '#9ca3af' },
                            grid: { color: 'rgba(156, 163, 175, 0.1)' }
                        }
                    }
                }
            });
        }
        
        // Distribution Pie Chart
        const distributionCtx = document.getElementById('distributionChart');
        if (distributionCtx) {
            const stats = window.dashboardData?.stats || {};
            const audioCount = stats.audio_requests || 0;
            const videoCount = stats.video_requests || 0;
            
            new Chart(distributionCtx, {
                type: 'doughnut',
                data: {
                    labels: ['Áudio', 'Vídeo'],
                    datasets: [{
                        data: [audioCount, videoCount],
                        backgroundColor: ['#8b5cf6', '#3b82f6'],
                        borderWidth: 0
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'bottom',
                            labels: { 
                                color: '#ffffff',
                                padding: 20
                            }
                        }
                    }
                }
            });
        }
    }

    autoHideFlashMessages() {
        setTimeout(() => {
            const flashContainer = document.getElementById('flash-container');
            if (flashContainer) {
                flashContainer.style.transition = 'opacity 0.5s ease';
                flashContainer.style.opacity = '0';
                setTimeout(() => flashContainer.remove(), 500);
            }
        }, 5000);
    }

    initializeTooltips() {
        document.querySelectorAll('[data-tooltip]').forEach(element => {
            element.classList.add('tooltip');
        });
    }

    showNotification(message, type = 'info') {
        const notification = document.createElement('div');
        notification.className = `fixed top-5 right-5 z-50 p-4 rounded-lg glass-effect border text-white shadow-xl animate-pulse ${
            type === 'success' ? 'border-green-500' : 
            type === 'error' ? 'border-red-500' : 'border-blue-500'
        }`;
        notification.textContent = message;
        
        document.body.appendChild(notification);
        
        setTimeout(() => {
            notification.style.transition = 'opacity 0.5s ease';
            notification.style.opacity = '0';
            setTimeout(() => notification.remove(), 500);
        }, 3000);
    }
}

// Initialize dashboard when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new Dashboard();
});