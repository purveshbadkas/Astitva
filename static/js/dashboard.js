// Initialize Particles Only for Dashboard
particlesJS("particles-js", {
  particles: {
    number: { value: 100 },
    color: { value: "#FFF" }, // Cyan-like color for dashboard
    shape: { type: "circle" },
    opacity: { value: 0.3 }, // Lower opacity only for dashboard
    size: { value: 3 },
    line_linked: {
      enable: true,
      distance: 150,
      color: "#00ffff",
      opacity: 0.2,
      width: 1,
    },
    move: { enable: true, speed: 2 },
  },
  interactivity: {
    events: {
      onhover: { enable: true, mode: "repulse" },
      onclick: { enable: true, mode: "push" },
    },
    modes: {
      repulse: { distance: 100 },
      push: { particles_nb: 4 },
    },
  },
  retina_detect: true,
});

// GSAP Animations
gsap.from(".logo", { duration: 1, y: -50, opacity: 0, ease: "bounce" });
gsap.from(".header-center", { duration: 1, x: -50, opacity: 0, delay: 0.5 });
gsap.from(".nav-links a", {
  duration: 1,
  y: -30,
  opacity: 0,
  stagger: 0.2,
  delay: 0.5,
});
gsap.from(".circle-container", { duration: 1, scale: 0, opacity: 0, delay: 1 });
gsap.from(".card", {
  duration: 1,
  y: 50,
  opacity: 0,
  stagger: 0.3,
  delay: 1.5,
});
gsap.from(".about-us", { duration: 1, x: -100, opacity: 0, delay: 2 });
gsap.from(".team-section", { duration: 1, x: 100, opacity: 0, delay: 2.5 });
gsap.from("footer", { duration: 1, y: 50, opacity: 0, delay: 3 });

/* Chatbot Integration JavaScript - Add this to your dashboard.js */

// Chatbot functionality
(function() {
    'use strict';

    // Wait for DOM to be fully loaded
    document.addEventListener('DOMContentLoaded', function() {
        initializeChatbot();
    });

    function initializeChatbot() {
        // Get DOM elements
        const elements = {
            toggleBtn: document.getElementById('chatbot-toggle'),
            modal: document.getElementById('chatbot-modal'),
            overlay: document.getElementById('chatbot-overlay'),
            closeBtn: document.getElementById('chatbot-close'),
            searchBtn: document.getElementById('search-criminal-btn'),
            firBtn: document.getElementById('file-fir-btn'),
            criminalNameInput: document.getElementById('criminal-name'),
            firDetailsTextarea: document.getElementById('fir-details'),
            searchResult: document.getElementById('search-result'),
            firResult: document.getElementById('fir-result'),
            loadingIndicator: document.getElementById('loading-indicator')
        };

        // Check if all required elements exist
        const missingElements = Object.entries(elements)
            .filter(([key, element]) => !element)
            .map(([key]) => key);

        if (missingElements.length > 0) {
            console.error('Chatbot: Missing DOM elements:', missingElements);
            return;
        }

        // Initialize event listeners
        setupEventListeners(elements);
        
        console.log('Chatbot initialized successfully');
    }

    function setupEventListeners(elements) {
        // Toggle modal visibility
        elements.toggleBtn.addEventListener('click', function() {
            openModal(elements);
        });

        // Close modal events
        elements.closeBtn.addEventListener('click', function() {
            closeModal(elements);
        });

        elements.overlay.addEventListener('click', function() {
            closeModal(elements);
        });

        // Keyboard events
        document.addEventListener('keydown', function(event) {
            if (event.key === 'Escape' && !elements.modal.classList.contains('hidden')) {
                closeModal(elements);
            }
        });

        // Search criminal functionality
        elements.searchBtn.addEventListener('click', function() {
            handleSearchCriminal(elements);
        });

        // Enter key support for criminal search
        elements.criminalNameInput.addEventListener('keypress', function(event) {
            if (event.key === 'Enter') {
                handleSearchCriminal(elements);
            }
        });

        // File FIR functionality
        elements.firBtn.addEventListener('click', function() {
            handleFileFIR(elements);
        });

        // Ctrl+Enter support for FIR submission
        elements.firDetailsTextarea.addEventListener('keydown', function(event) {
            if (event.ctrlKey && event.key === 'Enter') {
                handleFileFIR(elements);
            }
        });
    }

    function openModal(elements) {
        elements.overlay.classList.remove('hidden');
        elements.modal.classList.remove('hidden');
        
        // Add animation classes
        setTimeout(() => {
            elements.overlay.classList.add('show');
            elements.modal.classList.add('show');
        }, 10);

        // Focus management for accessibility
        elements.modal.focus();
        
        // Prevent body scroll
        document.body.style.overflow = 'hidden';
    }

    function closeModal(elements) {
        elements.overlay.classList.remove('show');
        elements.modal.classList.remove('show');
        
        setTimeout(() => {
            elements.overlay.classList.add('hidden');
            elements.modal.classList.add('hidden');
            document.body.style.overflow = '';
        }, 300);

        // Clear results when closing
        clearResults(elements);
    }

    function clearResults(elements) {
        elements.searchResult.classList.add('hidden');
        elements.firResult.classList.add('hidden');
        elements.searchResult.className = 'result-area hidden';
        elements.firResult.className = 'result-area hidden';
    }

    function showLoading(elements, show = true) {
        if (show) {
            elements.loadingIndicator.classList.remove('hidden');
        } else {
            elements.loadingIndicator.classList.add('hidden');
        }
    }

    function handleSearchCriminal(elements) {
        const criminalName = elements.criminalNameInput.value.trim();
        
        if (!criminalName) {
            showResult(elements.searchResult, 'Please enter a criminal name to search.', 'error');
            return;
        }

        // Disable button and show loading
        elements.searchBtn.disabled = true;
        elements.searchBtn.textContent = 'Searching...';
        showLoading(elements, true);

        // Prepare request data
        const requestData = {
            name: criminalName
        };

        // Make API call to Flask backend
        fetch('/search_criminal', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: JSON.stringify(requestData)
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            if (data.reply) {
                showResult(elements.searchResult, data.reply, 'success');
            } else {
                showResult(elements.searchResult, 'No response received from server.', 'error');
            }
        })
        .catch(error => {
            console.error('Search criminal error:', error);
            showResult(elements.searchResult, 
                `Error searching criminal database: ${error.message}. Please try again.`, 
                'error'
            );
        })
        .finally(() => {
            // Re-enable button and hide loading
            elements.searchBtn.disabled = false;
            elements.searchBtn.textContent = 'Search';
            showLoading(elements, false);
        });
    }

    function handleFileFIR(elements) {
        const firDetails = elements.firDetailsTextarea.value.trim();
        
        if (!firDetails) {
            showResult(elements.firResult, 'Please enter incident details to generate FIR.', 'error');
            return;
        }

        if (firDetails.length < 20) {
            showResult(elements.firResult, 'Please provide more detailed information (at least 20 characters).', 'error');
            return;
        }

        // Disable button and show loading
        elements.firBtn.disabled = true;
        elements.firBtn.textContent = 'Generating FIR...';
        showLoading(elements, true);

        // Prepare request data
        const requestData = {
            details: firDetails
        };

        // Make API call to Flask backend
        fetch('/write_fir', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: JSON.stringify(requestData)
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            if (data.reply) {
                showResult(elements.firResult, data.reply, 'success');
            } else {
                showResult(elements.firResult, 'No response received from server.', 'error');
            }
        })
        .catch(error => {
            console.error('File FIR error:', error);
            showResult(elements.firResult, 
                `Error generating FIR: ${error.message}. Please try again.`, 
                'error'
            );
        })
        .finally(() => {
            // Re-enable button and hide loading
            elements.firBtn.disabled = false;
            elements.firBtn.textContent = 'Generate FIR';
            showLoading(elements, false);
        });
    }

    function showResult(resultElement, message, type = 'success') {
        resultElement.textContent = message;
        resultElement.className = `result-area ${type}`;
        resultElement.classList.remove('hidden');
        
        // Scroll result into view
        resultElement.scrollIntoView({ 
            behavior: 'smooth', 
            block: 'nearest' 
        });
    }

    // Utility function to format criminal info (if needed)
    function formatCriminalInfo(info) {
        if (typeof info === 'string') {
            return info;
        }
        
        if (typeof info === 'object' && info !== null) {
            return Object.entries(info)
                .map(([key, value]) => `${key.charAt(0).toUpperCase() + key.slice(1)}: ${value}`)
                .join('\n');
        }
        
        return 'Invalid criminal information format.';
    }

    // Error handling for network issues
    window.addEventListener('online', function() {
        console.log('Chatbot: Network connection restored');
    });

    window.addEventListener('offline', function() {
        console.log('Chatbot: Network connection lost');
    });

    // Export functions for testing (optional)
    if (typeof module !== 'undefined' && module.exports) {
        module.exports = {
            initializeChatbot,
            formatCriminalInfo
        };
    }

})();

// Additional utility functions for dashboard integration
function getChatbotStatus() {
    const modal = document.getElementById('chatbot-modal');
    return modal && !modal.classList.contains('hidden');
}

function closeChatbotModal() {
    const closeBtn = document.getElementById('chatbot-close');
    if (closeBtn) {
        closeBtn.click();
    }
}

// Global error handler for chatbot-related errors
window.addEventListener('error', function(event) {
    if (event.filename && event.filename.includes('chatbot')) {
        console.error('Chatbot error:', event.error);
    }
});

// Performance monitoring (optional)
if ('performance' in window) {
    window.addEventListener('load', function() {
        setTimeout(function() {
            const perfData = performance.getEntriesByType('navigation')[0];
            if (perfData) {
                console.log('Chatbot: Page load time:', perfData.loadEventEnd - perfData.loadEventStart, 'ms');
            }
        }, 0);
    });
}
