// Family Hub - Main Application Logic
// Enhanced with Quick Stats and Push Notifications

// API Configuration
const API_BASE_URL = window.location.origin;
const DEFAULT_PLEX_WEB_URL = 'http://192.168.188.7:32400/web';
const USE_MOCK_DATA = false; // Auf false setzen wenn Backend läuft

// Local Storage Keys
const PUSH_DISMISSED_KEY = 'pushDismissed';
const NEWSLETTER_LAST_READ_KEY = 'newsletterLastRead';

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
const pushModal = document.getElementById('pushModal');
const enablePushBtn = document.getElementById('enablePush');
const cancelPushBtn = document.getElementById('cancelPush');
const notificationHistoryContainer = document.getElementById('notificationHistory');
const notificationHistoryList = document.getElementById('notificationHistoryList');

// Global State
let deferredPrompt = null;
let pushManager = null;
let statsRefreshInterval = null;
let swRegistration = null;
let notificationHistory = [];
const NOTIFICATION_HISTORY_LIMIT = 20;

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

function formatDateTime(value) {
    try {
        const date = new Date(value);
        return new Intl.DateTimeFormat('de-DE', {
            day: '2-digit',
            month: 'long',
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        }).format(date);
    } catch {
        return typeof value === 'string' ? value : '';
    }
}

function resolvePlexItemUrl(item) {
    if (!item || typeof item !== 'object') {
        return null;
    }

    const candidateKeys = ['plex_url', 'web_url', 'url', 'link', 'href'];
    for (const key of candidateKeys) {
        const value = item[key];
        if (typeof value === 'string' && value.startsWith('http')) {
            return value;
        }
    }

    let metadataKey = item.key || item.rating_key || item.ratingKey || item.metadata?.key;
    if (typeof metadataKey === 'number') {
        metadataKey = `/library/metadata/${metadataKey}`;
    } else if (typeof metadataKey === 'string' && metadataKey && !metadataKey.startsWith('/')) {
        metadataKey = `/library/metadata/${metadataKey}`;
    }

    const serverId = item.server_id
        || item.serverId
        || item.machine_identifier
        || item.machineIdentifier
        || item.server?.machineIdentifier;

    const baseUrl = (DEFAULT_PLEX_WEB_URL || '').replace(/\/$/, '');

    if (metadataKey && serverId) {
        return `${baseUrl}/index.html#!/server/${encodeURIComponent(serverId)}/details?key=${encodeURIComponent(metadataKey)}`;
    }

    if (metadataKey) {
        return `${baseUrl}/index.html#!/details?key=${encodeURIComponent(metadataKey)}`;
    }

    if (item.title) {
        return `${baseUrl}/index.html#!/search?query=${encodeURIComponent(item.title)}`;
    }

    return null;
}

function sanitizeNewsletterTitle(title) {
    if (typeof title !== 'string' || !title.trim()) {
        return '';
    }

    const cleaned = title.replace(/\s*[-–—]?\s*kw\s*\d+.*$/i, '').trim();
    return cleaned || title.trim();
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
            active_streams: 0,
            streams: [],
            recently_added: [],
            timestamp: new Date().toISOString()
        }
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
        const services = await fetchJson('/data/services.json');
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
    const displayTitle = sanitizeNewsletterTitle(entry.title) || 'Weekly Media Newsletter';

    latestNewsletter.innerHTML = `
        <header>
            <span class="newsletter-highlight__date">📅 ${formatDate(entry.date)}</span>
            <h3 class="newsletter-highlight__title">${displayTitle}</h3>
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
                    <span>${sanitizeNewsletterTitle(entry.title) || 'Weekly Media Newsletter'}</span>
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

function updateNewsletterQuickCard(entry) {
    const card = document.getElementById('newsletterQuickCard');
    if (!card) {
        return;
    }

    const titleEl = document.getElementById('newsletterQuickTitle');
    const imageGridEl = document.getElementById('newsletterImageGrid');

    if (!entry || !entry.path) {
        card.classList.remove('stat-card--active');
        if (titleEl) titleEl.textContent = 'Kein Newsletter verfügbar';
        if (imageGridEl) imageGridEl.innerHTML = '';
        card.href = '#newsletter';
        card.removeAttribute('target');
        localStorage.removeItem(NEWSLETTER_LAST_READ_KEY);
        return;
    }

    const lastReadPath = localStorage.getItem(NEWSLETTER_LAST_READ_KEY);
    const isLatestRead = lastReadPath === entry.path;

    card.classList.toggle('stat-card--active', !isLatestRead);
    if (titleEl) {
        titleEl.textContent = sanitizeNewsletterTitle(entry.title) || 'Weekly Newsletter';
    }

    // Set card link properties
    card.href = `/newsletters/${entry.path}`;
    card.target = '_blank';
    card.rel = 'noopener noreferrer';
    card.onclick = () => {
        localStorage.setItem(NEWSLETTER_LAST_READ_KEY, entry.path);
        card.classList.remove('stat-card--active');
    };

    // Fill the 2x2 image grid
    if (imageGridEl) {
        fetch(`/newsletters/${entry.path}`)
            .then(response => response.text())
            .then(html => {
                const parser = new DOMParser();
                const doc = parser.parseFromString(html, 'text/html');

                const images = Array.from(doc.querySelectorAll('img'))
                    .filter(img => img.src.toLowerCase().includes('tmdb'))
                    .slice(0, 4);

                imageGridEl.innerHTML = ''; // Clear previous content
                for (let i = 0; i < 4; i++) {
                    const cover = document.createElement('div');
                    cover.className = 'recent-cover';
                    if (images[i]) {
                        cover.style.backgroundImage = `url('${images[i].src}')`;
                    } else {
                        cover.classList.add('recent-cover--placeholder');
                    }
                    imageGridEl.appendChild(cover);
                }
            })
            .catch(error => {
                console.error('Error fetching newsletter for image grid:', error);
                imageGridEl.innerHTML = ''; // Clear on error
            });
    }
}

async function loadNewsletters() {
    try {
        const entries = await fetchJson('/newsletters/index.json');
        const sorted = entries.sort((a, b) => b.date.localeCompare(a.date));

        if (sorted.length) {
            const latest = sorted[0];
            
            // Debug-Ausgabe des neuesten Newsletters
            console.log('Latest newsletter:', latest);
            
            // Stelle sicher, dass die Film-Metadaten geladen sind
            if (latest.movies && latest.movies.length > 0) {
                latest.movies = await Promise.all(latest.movies.map(async movie => {
                    if (!movie.thumb && movie.rating_key) {
                        try {
                            // Versuche, die Metadaten vom Plex-Server zu laden
                            const metadata = await fetchAPI(`/api/plex/metadata/${movie.rating_key}`);
                            return { ...movie, ...metadata };
                        } catch (error) {
                            console.error('Error loading movie metadata:', error);
                            return movie;
                        }
                    }
                    return movie;
                }));
            }
            
            renderNewsletterHighlight(latest);
            updateNewsletterQuickCard(latest);
        } else {
            latestNewsletter.innerHTML = `
                <div class="placeholder">
                    <p>Noch keine Newsletter vorhanden.</p>
                </div>
            `;
            updateNewsletterQuickCard(null);
        }

        renderNewsletterArchive(sorted.slice(1, 4));
    } catch (error) {
        console.error('Newsletter konnten nicht geladen werden:', error);
        latestNewsletter.innerHTML = `
            <div class="placeholder">
                <p>Newsletter konnten nicht geladen werden. Bitte Verbindung prüfen.</p>
            </div>
        `;
        updateNewsletterQuickCard(null);
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
            // Create a container for stream information
            recentStreamEl.innerHTML = '';
            
            if (stats?.streams && stats.streams.length > 0) {
                // Create grid for stream covers
                const streamGrid = document.createElement('div');
                // Use the same grid class as other stat cards for consistency
                streamGrid.className = 'stat-card__recent-grid';

                stats.streams.forEach(stream => {
                    const streamCover = document.createElement('a'); // Use 'a' tag for links
                    streamCover.className = 'stream-cover';
                    const plexUrl = resolvePlexItemUrl(stream);
                    if (plexUrl) {
                        streamCover.href = plexUrl;
                        streamCover.target = '_blank';
                        streamCover.rel = 'noopener noreferrer';
                    }
                    
                    // Verwende den Backend-Proxy für Plex-Bilder
                    // Bevorzuge das Serien-Cover (grandparentThumb) für Episoden
                    const thumb = (stream.type === 'episode' && stream.grandparentThumb) ? stream.grandparentThumb : (stream.thumb || stream.art);
                    if (thumb) {
                        streamCover.style.backgroundImage = `url('/api/plex/image${thumb}')`;
                    }

                    streamCover.title = stream.title || 'Aktiver Stream';
                    streamCover.dataset.title = stream.title || 'Aktiver Stream';

                    streamGrid.appendChild(streamCover);
                });

                recentStreamEl.appendChild(streamGrid);
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
                let addedCount = 0;

                recentItems.forEach((item) => {
                    if (item.thumb_url && item.thumb_url.trim()) {
                        const plexItemUrl = resolvePlexItemUrl(item);
                        const cover = document.createElement(plexItemUrl ? 'a' : 'div');
                        cover.className = plexItemUrl
                            ? 'recent-cover recent-cover--link'
                            : 'recent-cover';
                        cover.dataset.title = item.title || 'Neuer Plex Inhalt';
                        cover.title = item.title || 'Neuer Plex Inhalt';

                        if (plexItemUrl) {
                            cover.href = plexItemUrl;
                            cover.target = '_blank';
                            cover.rel = 'noopener noreferrer';
                            const ariaLabel = item.title
                                ? `Plex Titel ${item.title} oeffnen`
                                : 'Plex Details oeffnen';
                            cover.setAttribute('aria-label', ariaLabel);
                        } else {
                            cover.setAttribute('role', 'img');
                            cover.setAttribute('aria-label', item.title || 'Neuer Plex Inhalt');
                        }

                        cover.style.backgroundImage = `url('${item.thumb_url}')`;
                        cover.style.backgroundSize = 'cover';
                        cover.style.backgroundPosition = 'center';
                        recentGridEl.appendChild(cover);
                        addedCount += 1;
                    }
                });

                // Fill remaining slots with placeholders
                for (let i = addedCount; i < 4; i += 1) {
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


async function updateAllStats() {
    await updatePlexStats();
}

// === PUSH NOTIFICATIONS ===

async function initPushNotifications() {
    const supported = ('serviceWorker' in navigator) && ('PushManager' in window);
    if (!supported) {
        console.warn('Push notifications not supported (no SW or PushManager)');
        // Button sichtbar lassen, aber Aktivieren-Button deaktivieren
        const enablePushInMenuBtn = document.getElementById('enablePushInMenu');
        const pushEnableText = document.querySelector('#pushEnableSection .push-enable-text');
        // Bestmögliche HTTPS-URL ableiten: bevorzugt global konfiguriert, sonst gleicher Host mit https
        const secureUrl = window.SECURE_APP_URL || `https://${window.location.host}`;
        if (enablePushInMenuBtn) {
            enablePushInMenuBtn.disabled = true;
            enablePushInMenuBtn.title = 'Push-Benachrichtigungen benötigen HTTPS & Service Worker';
        }
        if (pushEnableText) {
            pushEnableText.innerHTML = `Push-Benachrichtigungen benötigen eine sichere Verbindung (HTTPS). ` +
                `Öffne die App über <a href="${secureUrl}" target="_blank" rel="noopener">${secureUrl}</a>, ` +
                `um Benachrichtigungen zu aktivieren und den Verlauf zu sehen.`;
        }
        return;
    }

    // Initialize Push Manager (loaded from push-manager.js in HTML head)
    try {
        if (!window.PushManager) {
            console.error('PushManager class not loaded from push-manager.js');
            return;
        }
        
        pushManager = new window.PushManager(API_BASE_URL);
        console.log('Push Manager created');
        
        const hasSubscription = await pushManager.init();
        console.log('Push Manager initialized, has subscription:', hasSubscription);

        if (hasSubscription) {
            notificationToggle?.classList.add('active');
            localStorage.removeItem(PUSH_DISMISSED_KEY);
            console.log('Bell icon turned green (active class added)');
        } else {
            console.log('No existing push subscription found');
        }
    } catch (error) {
        console.error('Push Manager initialization error:', error);
    }
}

// === NOTIFICATION HISTORY ===

function normalizeHistoryEntry(entry) {
    if (!entry || typeof entry !== 'object') {
        return null;
    }

    const parsedTimestamp = typeof entry.timestamp === 'number'
        ? entry.timestamp
        : Date.parse(entry.timestamp);
    const timestamp = Number.isFinite(parsedTimestamp) ? parsedTimestamp : Date.now();

    return {
        id: entry.id ?? `${timestamp}-${entry.tag || 'notification'}`,
        title: entry.title || 'Family Hub',
        body: entry.body || '',
        url: entry.url || '',
        icon: entry.icon || '',
        tag: entry.tag || '',
        timestamp
    };
}

function renderNotificationHistory() {
    if (!notificationHistoryList) {
        return;
    }

    notificationHistoryList.innerHTML = '';

    if (!notificationHistory.length) {
        const emptyItem = document.createElement('li');
        emptyItem.className = 'notification-history__empty';
        emptyItem.textContent = 'Noch keine Nachrichten vorhanden.';
        notificationHistoryList.appendChild(emptyItem);

        if (notificationHistoryContainer) {
            notificationHistoryContainer.classList.add('is-empty');
        }
        return;
    }

    if (notificationHistoryContainer) {
        notificationHistoryContainer.classList.remove('is-empty');
    }

    notificationHistory.forEach((item) => {
        if (!item) {
            return;
        }

        const listItem = document.createElement('li');
        listItem.className = 'notification-history__item';
        let hintElement = null;

        if (item.url) {
            listItem.classList.add('notification-history__item--link');
            listItem.setAttribute('role', 'button');
            listItem.tabIndex = 0;

            const openEntry = () => {
                window.open(item.url, '_blank', 'noopener');
            };

            listItem.addEventListener('click', openEntry);
            listItem.addEventListener('keypress', (evt) => {
                if (evt.key === 'Enter' || evt.key === ' ') {
                    evt.preventDefault();
                    openEntry();
                }
            });

            hintElement = document.createElement('span');
            hintElement.className = 'notification-history__hint';
            hintElement.textContent = 'Zum Ansehen klicken';
        }

        const header = document.createElement('div');
        header.className = 'notification-history__meta';

        const titleElement = document.createElement('span');
        titleElement.className = 'notification-history__title';
        titleElement.textContent = item.title || 'Family Hub';

        const timeElement = document.createElement('time');
        timeElement.className = 'notification-history__time';
        timeElement.dateTime = new Date(item.timestamp).toISOString();
        timeElement.textContent = formatDateTime(item.timestamp);

        header.appendChild(titleElement);
        header.appendChild(timeElement);
        listItem.appendChild(header);

        if (item.body) {
            const bodyElement = document.createElement('p');
            bodyElement.className = 'notification-history__body';
            bodyElement.textContent = item.body;
            listItem.appendChild(bodyElement);
        }

        if (hintElement) {
            listItem.appendChild(hintElement);
        }

        notificationHistoryList.appendChild(listItem);
    });
}

function addHistoryEntry(entry) {
    const normalized = normalizeHistoryEntry(entry);
    if (!normalized) {
        return;
    }

    notificationHistory = [
        normalized,
        ...notificationHistory.filter((item) => item && item.id !== normalized.id)
    ];

    if (notificationHistory.length > NOTIFICATION_HISTORY_LIMIT) {
        notificationHistory.length = NOTIFICATION_HISTORY_LIMIT;
    }

    renderNotificationHistory();
}

function handleServiceWorkerMessage(event) {
    if (!event || !event.data || typeof event.data !== 'object') {
        return;
    }

    if (event.data.type === 'PUSH_HISTORY_UPDATED') {
        addHistoryEntry(event.data.payload);
    }
}

function sendMessageToServiceWorker(registration, message) {
    return new Promise((resolve, reject) => {
        if (!registration || !registration.active) {
            reject(new Error('Service Worker nicht aktiv'));
            return;
        }

        const channel = new MessageChannel();
        const timeoutId = setTimeout(() => {
            reject(new Error('Service Worker Antwortzeit ueberschritten'));
        }, 5000);

        channel.port1.onmessage = (event) => {
            clearTimeout(timeoutId);
            resolve(event.data);
        };

        try {
            registration.active.postMessage(message, [channel.port2]);
        } catch (error) {
            clearTimeout(timeoutId);
            reject(error);
        }
    });
}

async function loadNotificationHistory() {
    if (!notificationHistoryList || !swRegistration || !swRegistration.active) {
        return;
    }

    try {
        const response = await sendMessageToServiceWorker(swRegistration, {
            type: 'GET_NOTIFICATION_HISTORY',
            limit: NOTIFICATION_HISTORY_LIMIT
        });

        if (response?.ok && Array.isArray(response.list)) {
            notificationHistory = response.list
                .map(normalizeHistoryEntry)
                .filter(Boolean);
            renderNotificationHistory();
            return;
        }

        if (Array.isArray(response?.list)) {
            notificationHistory = response.list
                .map(normalizeHistoryEntry)
                .filter(Boolean);
            renderNotificationHistory();
            return;
        }

        if (response?.error) {
            console.error('Notification history request failed:', response.error);
        }
    } catch (error) {
        console.error('Failed to load notification history:', error);
    }
}

// === SERVICE WORKER ===

function registerServiceWorker() {
    if (!('serviceWorker' in navigator)) {
        return;
    }

    navigator.serviceWorker.addEventListener('message', handleServiceWorkerMessage);

    window.addEventListener('load', async () => {
        try {
            const registration = await navigator.serviceWorker.register('service-worker.js');
            swRegistration = registration;
            console.log('Service Worker registered:', registration);
        } catch (error) {
            console.error('Service Worker registration failed:', error);
        }

        try {
            const readyRegistration = await navigator.serviceWorker.ready;
            swRegistration = readyRegistration;
            await loadNotificationHistory();
        } catch (error) {
            console.error('Service Worker readiness failed:', error);
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
    const menuToggle = document.getElementById('menuToggle');
    const menuDropdown = document.getElementById('menuDropdown');
    const menuItems = document.querySelectorAll('.menu-item');

    // Toggle Menu Dropdown
    menuToggle?.addEventListener('click', (e) => {
        e.stopPropagation();
        menuDropdown.classList.toggle('is-hidden');

        // Close notification dropdown if open
        const notificationDropdown = document.getElementById('notificationDropdown');
        if (notificationDropdown && !notificationDropdown.classList.contains('is-hidden')) {
            notificationDropdown.classList.add('is-hidden');
        }
    });

    // Menu Items Click Handler
    menuItems.forEach(item => {
        item.addEventListener('click', (e) => {
            // Remove active from all
            menuItems.forEach(i => i.classList.remove('active'));
            // Add active to clicked
            item.classList.add('active');

            // Smooth scroll
            const target = item.getAttribute('href');
            if (target.startsWith('#')) {
                e.preventDefault();
                const element = document.querySelector(target);
                if (element) {
                    element.scrollIntoView({ behavior: 'smooth', block: 'start' });
                }
                // Close menu after navigation
                menuDropdown.classList.add('is-hidden');
            }
        });
    });

    // Active Menu Item beim Scrollen aktualisieren
    const observer = new IntersectionObserver((entries) => {
        // Sort entries by intersectionRatio (highest = most visible)
        const sortedEntries = entries
            .filter(e => e.isIntersecting)
            .sort((a, b) => b.intersectionRatio - a.intersectionRatio);

        if (sortedEntries.length > 0) {
            const mostVisible = sortedEntries[0];
            const id = mostVisible.target.id;
            const menuItem = document.querySelector(`.menu-item[href="#${id}"]`);

            if (menuItem) {
                // Only update if different from current
                const currentActive = document.querySelector('.menu-item.active');
                if (currentActive !== menuItem) {
                    menuItems.forEach(i => i.classList.remove('active'));
                    menuItem.classList.add('active');
                    console.log(`[NAV] Active section: ${id}`);
                }
            }
        }
    }, {
        threshold: [0, 0.1, 0.3, 0.5, 0.7, 1.0],
        rootMargin: '-10% 0px -70% 0px'  // Top 10%, Bottom 70%
    });

    document.querySelectorAll('section[id], main[id]').forEach(section => {
        observer.observe(section);
    });

    // Close dropdowns when clicking outside
    document.addEventListener('click', (e) => {
        if (!menuToggle?.contains(e.target) && !menuDropdown?.contains(e.target)) {
            menuDropdown?.classList.add('is-hidden');
        }
    });
}

// === NOTIFICATION SYSTEM ===

// === NOTIFICATION DROPDOWN ===

notificationToggle?.addEventListener('click', (e) => {
    e.stopPropagation();

    const notificationDropdown = document.getElementById('notificationDropdown');
    const menuDropdown = document.getElementById('menuDropdown');
    const pushEnableSection = document.getElementById('pushEnableSection');

    if (!notificationDropdown) return;

    // Toggle notification dropdown
    notificationDropdown.classList.toggle('is-hidden');

    // Close menu dropdown if open
    if (menuDropdown && !menuDropdown.classList.contains('is-hidden')) {
        menuDropdown.classList.add('is-hidden');
    }

    const isOpen = !notificationDropdown.classList.contains('is-hidden');

    // Show or hide push enable section based on push status
    if (isOpen) {
        const isPushEnabled = notificationToggle.classList.contains('active');

        if (pushEnableSection) {
            if (!isPushEnabled) {
                pushEnableSection.classList.remove('is-hidden');
            } else {
                pushEnableSection.classList.add('is-hidden');
            }
        }

        loadNotificationHistory();
    }
});

// Push enable button - needs to be initialized after DOM is ready
function initNotificationButtons() {
    const enablePushInMenuBtn = document.getElementById('enablePushInMenu');
    if (enablePushInMenuBtn) {
        enablePushInMenuBtn.addEventListener('click', async (e) => {
            e.preventDefault();
            e.stopPropagation();
            try {
                if (!pushManager) {
                    console.error('Push manager not initialized');
                    alert('Push-Benachrichtigungen sind noch nicht bereit. Bitte versuche es in wenigen Sekunden erneut.');
                    return;
                }
                await pushManager.subscribe();
                notificationToggle?.classList.add('active');
                localStorage.removeItem(PUSH_DISMISSED_KEY);

                // Hide push enable section and close dropdown
                const pushEnableSection = document.getElementById('pushEnableSection');
                const notificationDropdown = document.getElementById('notificationDropdown');
                if (pushEnableSection) {
                    pushEnableSection.classList.add('is-hidden');
                }
                if (notificationDropdown) {
                    notificationDropdown.classList.add('is-hidden');
                }

                alert('Push-Benachrichtigungen aktiviert!');
            } catch (error) {
                console.error('Push subscription failed:', error);
                alert('Fehler beim Aktivieren der Push-Benachrichtigungen.');
            }
        });
    }
}

// Close notification dropdown when clicking outside
document.addEventListener('click', (e) => {
    const notificationDropdown = document.getElementById('notificationDropdown');
    if (notificationDropdown &&
        !notificationToggle?.contains(e.target) &&
        !notificationDropdown.contains(e.target)) {
        notificationDropdown.classList.add('is-hidden');
    }
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



// === AUTHENTICATION CHECK ===

async function checkAuthentication() {
    console.log('[AUTH] Checking authentication...');

    // Check if user is authenticated
    const isAuth = await window.AuthUtils.isAuthenticated();
    console.log('[AUTH] isAuthenticated:', isAuth);

    if (!isAuth) {
        console.log('[AUTH] Not authenticated, redirecting to login');
        // Save current page for redirect after login
        localStorage.setItem('redirectAfterLogin', window.location.pathname);
        window.location.href = '/login.html';
        return false;
    }

    // Get user info and display
    const user = await window.AuthUtils.getCurrentUser();
    if (user) {
        console.log(`[AUTH] Logged in as: ${user.username} (Admin: ${user.is_admin})`);
        // Cache user info
        localStorage.setItem('user', JSON.stringify(user));
    } else {
        console.warn('[AUTH] Authentication passed but could not get user info');
    }

    return true;
}

// Setup logout button
function setupLogout() {
    const logoutButton = document.getElementById('logoutButton');
    if (logoutButton) {
        logoutButton.addEventListener('click', async (e) => {
            e.preventDefault();
            e.stopPropagation();

            if (confirm('Möchtest du dich wirklich abmelden?')) {
                await window.AuthUtils.logout();
            }
        });
    }
}

// === INITIALIZATION ===

document.addEventListener('DOMContentLoaded', async () => {
    console.log('Family Hub initialized');

    // Check authentication first
    const isAuthenticated = await checkAuthentication();
    if (!isAuthenticated) {
        return; // Stop initialization if not authenticated
    }

    if (localStorage.getItem(PUSH_DISMISSED_KEY) === '1') {
        hidePushModal();
    }

    // Setup logout button
    setupLogout();

    // Core Functions
    renderNotificationHistory();
    registerServiceWorker();
    loadServices();
    loadNewsletters();
    initNavigation();

    // Enhanced Features
    startStatsRefresh();
    initPushNotifications();
    initNotificationButtons(); // Initialize push button


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
