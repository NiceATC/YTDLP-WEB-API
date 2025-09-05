// Documentation Navigation
class DocsNavigation {
    constructor() {
        this.init();
    }

    init() {
        this.setupNavigation();
        this.setupScrollSpy();
    }

    setupNavigation() {
        const sections = document.querySelectorAll('.section');
        const navLinks = document.querySelectorAll('.nav-link');

        const showSection = (hash) => {
            sections.forEach(section => section.classList.remove('active'));
            navLinks.forEach(link => link.classList.remove('active'));
            
            const targetSection = document.querySelector(hash);
            const targetLink = document.querySelector(`.nav-link[href="${hash}"]`);
            
            if (targetSection) targetSection.classList.add('active');
            if (targetLink) targetLink.classList.add('active');
        };

        navLinks.forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                const hash = e.currentTarget.getAttribute('href');
                window.location.hash = hash;
                showSection(hash);
                
                // Smooth scroll to top of section
                document.querySelector(hash).scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            });
        });

        // Show initial section
        const initialHash = window.location.hash || '#overview';
        showSection(initialHash);

        // Handle browser back/forward
        window.addEventListener('hashchange', () => {
            showSection(window.location.hash || '#overview');
        });
    }

    setupScrollSpy() {
        const sections = document.querySelectorAll('.section');
        const navLinks = document.querySelectorAll('.nav-link');
        
        const observerOptions = {
            root: null,
            rootMargin: '-20% 0px -80% 0px',
            threshold: 0
        };

        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const id = entry.target.id;
                    const activeLink = document.querySelector(`.nav-link[href="#${id}"]`);
                    
                    navLinks.forEach(link => link.classList.remove('active'));
                    if (activeLink) {
                        activeLink.classList.add('active');
                        window.history.replaceState(null, null, `#${id}`);
                    }
                }
            });
        }, observerOptions);

        sections.forEach(section => {
            if (section.classList.contains('active')) {
                observer.observe(section);
            }
        });
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new DocsNavigation();
});