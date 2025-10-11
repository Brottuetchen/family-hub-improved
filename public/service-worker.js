/**
 * Family Hub Service Worker
 * Enhanced with Push Notifications, Offline Support, and Caching
 */

const CACHE_VERSION = 'family-hub-v2.1';
const STATIC_CACHE = `${CACHE_VERSION}-static`;
const DYNAMIC_CACHE = `${CACHE_VERSION}-dynamic`;
const IMAGE_CACHE = `${CACHE_VERSION}-images`;

// Static Assets zum Cachen
const STATIC_ASSETS = [
    '/',
    '/index.html',
    '/styles.css',
    '/app.js',
    '/push-manager.js',
    '/service-viewer.html',
    '/service-viewer.js',
    '/manifest.webmanifest',
    '/assets/icons/app-icon.svg',
    '/data/services.json'
];

// URLs die NICHT gecacht werden sollen
const EXCLUDE_CACHE = [
    '/api/',
    'chrome-extension://',
    'analytics',
    'gtag'
];

// === INSTALL EVENT ===

self.addEventListener('install', (event) => {
    console.log('[SW] Installing Service Worker v2.0...');

    event.waitUntil(
        caches.open(STATIC_CACHE).then((cache) => {
            console.log('[SW] Caching static assets');
            return cache.addAll(STATIC_ASSETS).catch((error) => {
                console.error('[SW] Failed to cache static assets:', error);
                // Nicht komplett fehlschlagen wenn einzelne Dateien fehlen
            });
        })
    );

    // Force activate neuer Service Worker
    self.skipWaiting();
});

// === ACTIVATE EVENT ===

self.addEventListener('activate', (event) => {
    console.log('[SW] Activating Service Worker v2.0...');

    event.waitUntil(
        caches.keys().then((cacheNames) => {
            return Promise.all(
                cacheNames
                    .filter((name) => name.startsWith('family-hub-') && name !== CACHE_VERSION)
                    .map((name) => {
                        console.log('[SW] Deleting old cache:', name);
                        return caches.delete(name);
                    })
            );
        })
    );

    // Übernehme sofort die Kontrolle
    return self.clients.claim();
});

// === FETCH EVENT ===

self.addEventListener('fetch', (event) => {
    const { request } = event;
    const url = new URL(request.url);

    // Ignoriere non-GET requests
    if (request.method !== 'GET') {
        return;
    }

    // Ignoriere ausgeschlossene URLs
    if (EXCLUDE_CACHE.some((exclude) => url.href.includes(exclude))) {
        return;
    }

    // Strategie: Cache-First für static assets, Network-First für dynamic content
    if (STATIC_ASSETS.some((asset) => url.pathname === asset)) {
        event.respondWith(cacheFirst(request));
    } else if (url.pathname.match(/\.(png|jpg|jpeg|svg|gif|webp|ico)$/)) {
        event.respondWith(cacheFirst(request, IMAGE_CACHE));
    } else {
        event.respondWith(networkFirst(request));
    }
});

/**
 * Cache-First Strategy: Versuche Cache, fallback zu Network
 */
async function cacheFirst(request, cacheName = STATIC_CACHE) {
    const cachedResponse = await caches.match(request);

    if (cachedResponse) {
        return cachedResponse;
    }

    try {
        const networkResponse = await fetch(request);

        if (networkResponse && networkResponse.status === 200) {
            const cache = await caches.open(cacheName);
            cache.put(request, networkResponse.clone());
        }

        return networkResponse;
    } catch (error) {
        console.error('[SW] Fetch failed:', error);

        // Fallback für offline HTML pages
        if (request.mode === 'navigate') {
            return caches.match('/index.html');
        }

        return new Response('Offline', {
            status: 503,
            statusText: 'Service Unavailable'
        });
    }
}

/**
 * Network-First Strategy: Versuche Network, fallback zu Cache
 */
async function networkFirst(request) {
    try {
        const networkResponse = await fetch(request);

        if (networkResponse && networkResponse.status === 200) {
            const cache = await caches.open(DYNAMIC_CACHE);
            cache.put(request, networkResponse.clone());
        }

        return networkResponse;
    } catch (error) {
        console.log('[SW] Network failed, trying cache:', request.url);

        const cachedResponse = await caches.match(request);

        if (cachedResponse) {
            return cachedResponse;
        }

        // Fallback für navigate requests
        if (request.mode === 'navigate') {
            return caches.match('/index.html');
        }

        return new Response('Offline', {
            status: 503,
            statusText: 'Service Unavailable'
        });
    }
}

// === PUSH NOTIFICATIONS ===

/**
 * Push Event: Empfange Push Notification vom Server
 */
self.addEventListener('push', (event) => {
    console.log('[SW] Push notification received');

    let data = {
        title: 'Family Hub',
        body: 'Neue Updates verfügbar',
        url: '/',
        icon: '/assets/icons/app-icon-192.png'
    };

    // Parse payload falls vorhanden
    if (event.data) {
        try {
            data = { ...data, ...event.data.json() };
        } catch (e) {
            data.body = event.data.text();
        }
    }

    const options = {
        body: data.body,
        icon: data.icon || '/assets/icons/app-icon-192.png',
        badge: '/assets/icons/badge-icon.png',
        vibrate: [200, 100, 200, 100, 200],
        tag: data.tag || 'family-hub-notification',
        requireInteraction: false,
        data: {
            url: data.url || '/',
            timestamp: Date.now()
        },
        actions: [
            {
                action: 'open',
                title: 'Öffnen',
                icon: '/assets/icons/app-icon.svg'
            },
            {
                action: 'close',
                title: 'Schließen'
            }
        ]
    };

    event.waitUntil(
        self.registration.showNotification(data.title, options)
    );
});

/**
 * Notification Click Event: Reagiere auf Notification-Klicks
 */
self.addEventListener('notificationclick', (event) => {
    console.log('[SW] Notification clicked:', event.action);

    event.notification.close();

    if (event.action === 'close') {
        return;
    }

    // Öffne URL (default action oder 'open' button)
    const urlToOpen = event.notification.data?.url || '/';

    event.waitUntil(
        clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clientList) => {
            // Prüfe ob bereits ein Tab offen ist
            for (const client of clientList) {
                if (client.url === urlToOpen && 'focus' in client) {
                    return client.focus();
                }
            }

            // Öffne neuen Tab
            if (clients.openWindow) {
                return clients.openWindow(urlToOpen);
            }
        })
    );
});

/**
 * Notification Close Event: Tracking wenn Notification geschlossen wird
 */
self.addEventListener('notificationclose', (event) => {
    console.log('[SW] Notification closed:', event.notification.tag);

    // Optional: Analytics senden
    // event.waitUntil(
    //     fetch('/api/analytics/notification-closed', {
    //         method: 'POST',
    //         body: JSON.stringify({ tag: event.notification.tag })
    //     })
    // );
});

// === BACKGROUND SYNC (optional) ===

self.addEventListener('sync', (event) => {
    console.log('[SW] Background sync:', event.tag);

    if (event.tag === 'sync-stats') {
        event.waitUntil(syncStats());
    }
});

async function syncStats() {
    try {
        // Sync stats with backend when online
        const response = await fetch('/api/services/status');
        const stats = await response.json();
        console.log('[SW] Stats synced:', stats);
    } catch (error) {
        console.error('[SW] Sync failed:', error);
    }
}

// === PERIODIC BACKGROUND SYNC (optional, requires permission) ===

self.addEventListener('periodicsync', (event) => {
    if (event.tag === 'check-new-content') {
        event.waitUntil(checkNewContent());
    }
});

async function checkNewContent() {
    try {
        // Prüfe auf neue Plex Inhalte
        const response = await fetch('/api/plex/stats');
        const data = await response.json();

        if (data.recently_added && data.recently_added.length > 0) {
            const latest = data.recently_added[0];

            await self.registration.showNotification('Neue Inhalte auf Plex!', {
                body: `${latest.title} wurde hinzugefügt`,
                icon: '/assets/icons/plex.svg',
                data: { url: 'http://192.168.188.7:32400/web' }
            });
        }
    } catch (error) {
        console.error('[SW] Check new content failed:', error);
    }
}

// === MESSAGE HANDLER ===

self.addEventListener('message', (event) => {
    console.log('[SW] Message received:', event.data);

    if (event.data.type === 'SKIP_WAITING') {
        self.skipWaiting();
    }

    if (event.data.type === 'CLEAR_CACHE') {
        event.waitUntil(
            caches.keys().then((cacheNames) => {
                return Promise.all(
                    cacheNames.map((name) => caches.delete(name))
                );
            }).then(() => {
                event.ports[0].postMessage({ success: true });
            })
        );
    }

    if (event.data.type === 'GET_CACHE_SIZE') {
        event.waitUntil(
            getCacheSize().then((size) => {
                event.ports[0].postMessage({ size });
            })
        );
    }
});

async function getCacheSize() {
    const cacheNames = await caches.keys();
    let totalSize = 0;

    for (const name of cacheNames) {
        const cache = await caches.open(name);
        const keys = await cache.keys();
        totalSize += keys.length;
    }

    return totalSize;
}

// === ERROR HANDLING ===

self.addEventListener('error', (event) => {
    console.error('[SW] Error:', event.error);
});

self.addEventListener('unhandledrejection', (event) => {
    console.error('[SW] Unhandled rejection:', event.reason);
});

console.log('[SW] Service Worker v2.0 loaded');
