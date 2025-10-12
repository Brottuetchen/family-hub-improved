// Family Hub - Main Application Logic
// Enhanced with Quick Stats and Push Notifications

// API Configuration
const API_BASE_URL = window.location.origin;
const USE_MOCK_DATA = false; // Auf false setzen wenn Backend läuft

// Local Storage Keys
const PUSH_DISMISSED_KEY = 'pushDismissed';

function showPushModal() {
    if (!pushModal) return;
    pushModal.classList.remove('is-hidden');
}

function hidePushModal() {
    if (!pushModal) return;
    pushModal.classList.add('is-hidden');
}

// DOM Elements
const servicesGrid = document.getElementById('servicesGrid');
const newsletterList = document.getElementById('newsletterList');
const latestNewsletter = document.getElementById('latestNewsletter');
const installButton = document.getElementById('installButton');
const notificationToggle = document.getElementById('notificationToggle');
const notificationBadge = document.getElementById('notificationBadge');
const pushModal = document.getElementById('pushModal');
const enablePushBtn = document.getElementById('enablePush');
const cancelPushBtn = document.getElementById('cancelPush');

// Global State
let deferredPrompt = null;
let pushManager = null;
let statsRefreshInterval = null;

// === UTILITY FUNCTIONS ===

function formatDate(dateString) {
    try {
        const date = new Date(dateString);
        return new Intl.DateTimeFormat('de-DE', {
            day: '2-digit',
            month: 'long',
            year: 'numeric'
        }).format(date);
    } catch {
        return dateString;
    }
}

async function fetchJson(url) {
    const response = await fetch(url, { cache: 'no-cache' });
    if (!response.ok) {
        throw new Error(`HTTP ${response.status} for ${url}`);
    }
    return response.json();
}

async function fetchAPI(endpoint) {
    try {
        if (USE_MOCK_DATA) {
            return getMockData(endpoint);
        }
        return await fetchJson(`${API_BASE_URL}${endpoint}`);
    } catch (error) {
        console.error(`API Error [${endpoint}]:`, error);
        return getMockData(endpoint);
    }
}

// Mock Data für Entwicklung ohne Backend
function getMockData(endpoint) {
    const mockData = {
        '/api/plex/stats': {
            active_streams: 2,
            streams: [
                { title: 'The Last of Us S01E03', user: 'Papa' },
                { title: 'Avatar: The Way of Water', user: 'Mama' }
            ],
            recently_added: [
                { title: 'Dune: Part Two', type: 'movie', thumb_url: 'assets/icons/plex.png' },
                { title: 'Fallout S01E01', type: 'episode', thumb_url: 'assets/icons/plex.png' },
                { title: 'The Bear S02E01', type: 'episode', thumb_url: 'assets/icons/plex.png' },
                { title: 'Interstellar', type: 'movie', thumb_url: 'assets/icons/plex.png' }
            ],
            timestamp: new Date().toISOString()
        },
        '/api/overseerr/stats': {
            pending_requests: 3,
            recent_requests: [
                { title: 'Oppenheimer', type: 'movie' },
                { title: 'The Bear S02', type: 'tv' }
            ]
        },
        '/api/services/status': [
            { name: 'Plex', status: 'online' },
            { name: 'Overseerr', status: 'online' },
            { name: 'Trilium', status: 'online' },
            { name: 'Immich', status: 'online' },
            { name: 'SABnzbd', status: 'online' }
        ]
    };
    return Promise.resolve(mockData[endpoint] || {});
}

// === SERVICE CARDS ===

function createServiceCard(service) {
    const card = document.createElement('a');
    card.className = 'service-card';
    card.href = service.url;
    card.target = '_blank';
    card.rel = 'noopener noreferrer';
    card.role = 'listitem';

    card.innerHTML = `
        <div class="service-card__icon">
            <img src="${service.icon}" alt="" aria-hidden="true">
        </div>
        <h3 class="service-card__title">${service.name}</h3>
        <p class="service-card__description">${service.description}</p>
        <span class="service-card__link">Jetzt öffnen →</span>
    `;

    // Tracking für Analytics
    card.addEventListener('click', () => {
        console.log(`Service opened: ${service.name}`);
        localStorage.setItem('lastOpenedService', JSON.stringify({
            name: service.name,
            timestamp: Date.now()
        }));
    });

    return card;
}

async function loadServices() {
    try {
        const services = await fetchJson('data/services.json');
        servicesGrid.innerHTML = '';
        services.forEach(service => {
            servicesGrid.appendChild(createServiceCard(service));
        });
    } catch (error) {
        console.error('Services konnten nicht geladen werden:', error);
        servicesGrid.innerHTML = `
            <div class="placeholder">
                <p>⚠️ Services konnten nicht geladen werden. Bitte später erneut versuchen.</p>
            </div>
        `;
    }
}

// === NEWSLETTER ===

function truncateReason(reason) {
    if (!reason) return '';
    const maxLength = 160;
    return reason.length <= maxLength ? reason : `${reason.slice(0, maxLength).trim()}…`;
}

function renderNewsletterHighlight(entry) {
    const movieItems = entry.movies.slice(0, 5).map(movie => `
        <li>${movie.title}</li>
    `).join('');

    const showItems = entry.shows.slice(0, 5).map(show => `
        <li>${show.title}</li>
    `).join('');

    const absoluteUrl = `/newsletters/${entry.path}`;

    latestNewsletter.innerHTML = `
        <header>
            <span class="newsletter-highlight__date">📅 ${formatDate(entry.date)}</span>
            <h3 class="newsletter-highlight__title">${entry.title || 'Weekly Media Newsletter'}</h3>
        </header>
        <div class="newsletter-highlight__meta">
            <div class="highlight-card">
                <h4>Top Filme</h4>
                <ul>${movieItems || '<li>Noch keine Einträge</li>'}</ul>
            </div>
            <div class="highlight-card">
                <h4>Top Serien</h4>
                <ul>${showItems || '<li>Noch keine Einträge</li>'}</ul>
            </div>
        </div>
        <a class="newsletter-highlight__cta" href="${absoluteUrl}" target="_blank" rel="noopener">
            Ganze Ausgabe lesen
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M5 12h14"></path>
                <path d="m12 5 7 7-7 7"></path>
            </svg>
        </a>
    `;
}

function renderNewsletterArchive(entries) {
    if (!entries.length) {
        newsletterList.innerHTML = '<li class="placeholder">Noch keine Newsletter veröffentlicht.</li>';
        return;
    }

    const items = entries.map(entry => {
        const movieCount = entry.movies?.length ?? 0;
        const showCount = entry.shows?.length ?? 0;
        const absoluteUrl = `/newsletters/${entry.path}`;

        return `
            <li class="newsletter-list__item">
                <a href="${absoluteUrl}" target="_blank" rel="noopener" class="newsletter-list__title">
                    <span>${entry.title || 'Weekly Media Newsletter'}</span>
                    <span class="newsletter-list__badges">
                        <span class="badge">🎬 ${movieCount}</span>
                        <span class="badge">📺 ${showCount}</span>
                    </span>
                </a>
                <div class="newsletter-list__meta">
                    ${formatDate(entry.date)}
                </div>
            </li>
        `;
    }).join('');

    newsletterList.innerHTML = items;
}

async function loadNewsletters() {
    try {
        const entries = await fetchJson('/newsletters/index.json');
        const sorted = entries.sort((a, b) => b.date.localeCompare(a.date));

        if (sorted.length) {
            renderNewsletterHighlight(sorted[0]);
        } else {
            latestNewsletter.innerHTML = `
                <div class="placeholder">
                    <p>Noch keine Newsletter vorhanden.</p>
                </div>
            `;
        }

        renderNewsletterArchive(sorted.slice(0, 50));
    } catch (error) {
        console.error('Newsletter konnten nicht geladen werden:', error);
        latestNewsletter.innerHTML = `
            <div class="placeholder">
                <p>Newsletter konnten nicht geladen werden. Bitte Verbindung prüfen.</p>
            </div>
        `;
    }
}

// === QUICK STATS ===

async function updatePlexStats() {
    try {
        const stats = await fetchAPI('/api/plex/stats');
        const streamsEl = document.getElementById('plexStreams');
        const recentStreamEl = document.getElementById('plexRecent');
        const recentCountEl = document.getElementById('plexRecentCount');
        const recentGridEl = document.getElementById('plexRecentGrid');
        const recentDetailEl = document.getElementById('plexRecentDetail');
        const plexCardEl = document.getElementById('plexStats');

        const streamCount = stats?.active_streams ?? 0;

        if (streamsEl) {
            streamsEl.textContent = `${streamCount} aktive Stream${streamCount !== 1 ? 's' : ''}`;
        }

        if (recentStreamEl) {
            if (stats?.streams && stats.streams.length > 0) {
                const recentStream = stats.streams[0];
                recentStreamEl.textContent = `Zuletzt: ${recentStream.title}`;
            } else {
                recentStreamEl.textContent = 'Keine aktiven Streams';
            }
        }

        if (plexCardEl) {
            if (streamCount > 0) {
                plexCardEl.classList.add('stat-card--active');
            } else {
                plexCardEl.classList.remove('stat-card--active');
            }
        }

        const recentItems = Array.isArray(stats?.recently_added)
            ? stats.recently_added.slice(0, 4)
            : [];

        if (recentCountEl) {
            recentCountEl.textContent = recentItems.length
                ? `${recentItems.length} neue Titel`
                : 'Keine neuen Medien';
        }

        if (recentDetailEl) {
            if (recentItems.length && stats?.timestamp) {
                const updatedAt = new Date(stats.timestamp);
                recentDetailEl.textContent = `Stand: ${updatedAt.toLocaleTimeString('de-DE', {
                    hour: '2-digit',
                    minute: '2-digit'
                })} Uhr`;
            } else if (recentItems.length) {
                recentDetailEl.textContent = 'Letzte Aktualisierung erfolgreich';
            } else {
                recentDetailEl.textContent = 'Keine neuen Medien gefunden';
            }
        }

        if (recentGridEl) {
            recentGridEl.innerHTML = '';

            const renderPlaceholder = () => {
                const placeholder = document.createElement('div');
                placeholder.className = 'recent-cover recent-cover--placeholder';
                recentGridEl.appendChild(placeholder);
            };

            if (recentItems.length) {
                recentItems.forEach(item => {
                    const cover = document.createElement('div');
                    cover.className = 'recent-cover';
                    cover.dataset.title = item.title || 'Neuer Plex Inhalt';
                    cover.setAttribute('role', 'img');
                    cover.setAttribute('aria-label', item.title || 'Neuer Plex Inhalt');

                    if (item.thumb_url) {
                        cover.style.backgroundImage = `url('${item.thumb_url}')`;
                    } else {
                        cover.classList.add('recent-cover--placeholder');
                    }

                    recentGridEl.appendChild(cover);
                });

                for (let i = recentItems.length; i < 4; i += 1) {
                    renderPlaceholder();
                }
            } else {
                for (let i = 0; i < 4; i += 1) {
                    renderPlaceholder();
                }
            }
        }
    } catch (error) {
        console.error('Plex Stats Error:', error);

        const streamsEl = document.getElementById('plexStreams');
        const recentStreamEl = document.getElementById('plexRecent');
        const recentCountEl = document.getElementById('plexRecentCount');
        const recentGridEl = document.getElementById('plexRecentGrid');
        const recentDetailEl = document.getElementById('plexRecentDetail');

        if (streamsEl) streamsEl.textContent = 'Nicht verfügbar';
        if (recentStreamEl) recentStreamEl.textContent = 'Fehler beim Laden';
        if (recentCountEl) recentCountEl.textContent = 'Keine Daten';
        if (recentDetailEl) recentDetailEl.textContent = 'Aktualisierung fehlgeschlagen';

        if (recentGridEl) {
            recentGridEl.innerHTML = '';
            for (let i = 0; i < 4; i += 1) {
                const placeholder = document.createElement('div');
                placeholder.className = 'recent-cover recent-cover--placeholder';
                recentGridEl.appendChild(placeholder);
            }
        }
    }
}


async function updateOverseerrStats() {
    try {
        const stats = await fetchAPI('/api/overseerr/stats');
        const requestsEl = document.getElementById('overseerrRequests');

        const requestCount = stats?.pending_requests ?? 0;
        if (requestsEl) {
            requestsEl.textContent = `${requestCount} offene Request${requestCount !== 1 ? 's' : ''}`;
        }

        if (notificationBadge) {
            if (requestCount > 0) {
                notificationBadge.textContent = requestCount;
                notificationBadge.hidden = false;
            } else {
                notificationBadge.hidden = true;
            }
        }
    } catch (error) {
        console.error('Overseerr Stats Error:', error);
        const requestsEl = document.getElementById('overseerrRequests');
        if (requestsEl) {
            requestsEl.textContent = 'Nicht verfügbar';
        }
        if (notificationBadge) {
            notificationBadge.hidden = true;
        }
    }
}

async function updateAllStats() {
    await Promise.all([
        updatePlexStats(),
        updateOverseerrStats()
    ]);
}

// === PUSH NOTIFICATIONS ===

async function initPushNotifications() {
    if (!('serviceWorker' in navigator) || !('PushManager' in window)) {
        console.warn('Push notifications not supported');
        if (notificationToggle) {
        if (notificationToggle) {
            notificationToggle.style.display = 'none';
        }
    }
        return;
    }

    // Lade Push Manager
    const script = document.createElement('script');
    script.src = 'push-manager.js';
    script.onload = async () => {
        pushManager = new window.PushManager(API_BASE_URL);
        const hasSubscription = await pushManager.init();

        if (hasSubscription) {
            notificationToggle?.classList.add('active');
            localStorage.removeItem(PUSH_DISMISSED_KEY);
        }
    };
    document.head.appendChild(script);
}

// === SERVICE WORKER ===

function registerServiceWorker() {
    if (!('serviceWorker' in navigator)) {
        return;
    }

    window.addEventListener('load', async () => {
        try {
            const registration = await navigator.serviceWorker.register('service-worker.js');
            console.log('Service Worker registered:', registration);
        } catch (error) {
            console.error('Service Worker registration failed:', error);
        }
    });
}

// === PWA INSTALL ===

window.addEventListener('beforeinstallprompt', (event) => {
    event.preventDefault();
    deferredPrompt = event;

    if (installButton) {
        installButton.hidden = false;
    }
});

installButton?.addEventListener('click', async () => {
    if (!deferredPrompt) return;

    deferredPrompt.prompt();
    const { outcome } = await deferredPrompt.userChoice;

    if (outcome === 'accepted' && installButton) {
        installButton.hidden = true;
        console.log('PWA installed');
    }

    deferredPrompt = null;
});

// === NAVIGATION ===

function initNavigation() {
    const navLinks = document.querySelectorAll('.nav-link');

    navLinks.forEach(link => {
        link.addEventListener('click', (e) => {
            // Entferne active von allen
            navLinks.forEach(l => l.classList.remove('active'));
            // Füge active zu geklicktem hinzu
            link.classList.add('active');

            // Smooth scroll
            const target = link.getAttribute('href');
            if (target.startsWith('#')) {
                e.preventDefault();
                const element = document.querySelector(target);
                if (element) {
                    element.scrollIntoView({ behavior: 'smooth', block: 'start' });
                }
            }
        });
    });

    // Active Link beim Scrollen aktualisieren
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const id = entry.target.id;
                const link = document.querySelector(`.nav-link[href="#${id}"]`);
                if (link) {
                    navLinks.forEach(l => l.classList.remove('active'));
                    link.classList.add('active');
                }
            }
        });
    }, { threshold: 0.3 });

    document.querySelectorAll('section[id], main[id]').forEach(section => {
        observer.observe(section);
    });
}

// === NOTIFICATION MODAL ===

notificationToggle?.addEventListener('click', () => {
    if (!pushManager) {
        alert('Push Notifications werden noch geladen...');
        return;
    }

    showPushModal();
});

enablePushBtn?.addEventListener('click', async () => {
    try {
        await pushManager.subscribe();
        notificationToggle?.classList.add('active');
        hidePushModal();
        localStorage.removeItem(PUSH_DISMISSED_KEY);
        alert('Benachrichtigungen aktiviert!');
    } catch (error) {
        console.error('Push subscription failed:', error);
        alert('Fehler beim Aktivieren der Benachrichtigungen.');
    }
});

cancelPushBtn?.addEventListener('click', () => {
    hidePushModal();
    localStorage.setItem(PUSH_DISMISSED_KEY, '1');
});

// Schließe Modal bei Klick auf Overlay
pushModal?.querySelector('.modal__overlay')?.addEventListener('click', () => {
    hidePushModal();
});

// === STATS AUTO-REFRESH ===

function startStatsRefresh() {
    // Initial load
    updateAllStats();

    // Refresh alle 30 Sekunden
    statsRefreshInterval = setInterval(updateAllStats, 30000);
}

function stopStatsRefresh() {
    if (statsRefreshInterval) {
        clearInterval(statsRefreshInterval);
        statsRefreshInterval = null;
    }
}

// Stoppe Refresh wenn Tab nicht sichtbar
document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
        stopStatsRefresh();
    } else {
        startStatsRefresh();
    }
});

// === INITIALIZATION ===

document.addEventListener('DOMContentLoaded', () => {
    console.log('Family Hub initialized');

    if (localStorage.getItem(PUSH_DISMISSED_KEY) === '1') {
        hidePushModal();
    }

    // Core Functions
    registerServiceWorker();
    loadServices();
    loadNewsletters();
    initNavigation();

    // Enhanced Features
    startStatsRefresh();
    initPushNotifications();

    // Show welcome message on first visit
    if (!localStorage.getItem('hasVisited')) {
        localStorage.setItem('hasVisited', 'true');
        console.log('Welcome to Family Hub! 🏠');
    }
});

// Cleanup
window.addEventListener('beforeunload', () => {
    stopStatsRefresh();
});
