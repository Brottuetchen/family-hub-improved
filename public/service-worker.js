/**
 * Family Hub Service Worker
 * Enhanced with Push Notifications, Offline Support, and Caching
 */

const CACHE_VERSION = 'family-hub-v3.2';
const STATIC_CACHE = `${CACHE_VERSION}-static`;
const DYNAMIC_CACHE = `${CACHE_VERSION}-dynamic`;
const IMAGE_CACHE = `${CACHE_VERSION}-images`;

// Static Assets zum Cachen
const STATIC_ASSETS = [
    '/',
    '/index.html',
    '/styles.css',
    '/app.js',
    '/admin.html',
    '/admin.js',
    '/push-manager.js',
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

// Push Notification History (IndexedDB)
const HISTORY_DB_NAME = 'family-hub-push-history';
const HISTORY_DB_VERSION = 1;
const HISTORY_STORE_NAME = 'notifications';
const MAX_HISTORY_ITEMS = 50;

async function openHistoryDB() {
    return new Promise((resolve, reject) => {
        if (!self.indexedDB) {
            reject(new Error('IndexedDB not supported in Service Worker'));
            return;
        }

        const request = indexedDB.open(HISTORY_DB_NAME, HISTORY_DB_VERSION);

        request.onupgradeneeded = () => {
            const db = request.result;
            if (!db.objectStoreNames.contains(HISTORY_STORE_NAME)) {
                const store = db.createObjectStore(HISTORY_STORE_NAME, { keyPath: 'id', autoIncrement: true });
                store.createIndex('timestamp', 'timestamp', { unique: false });
            }
        };

        request.onsuccess = () => resolve(request.result);
        request.onerror = () => reject(request.error || new Error('Failed to open history database'));
    });
}

async function saveNotificationToHistory(record) {
    let db;

    try {
        db = await openHistoryDB();
        const entry = { ...record };

        await new Promise((resolve, reject) => {
            const tx = db.transaction(HISTORY_STORE_NAME, 'readwrite');
            const store = tx.objectStore(HISTORY_STORE_NAME);
            const addRequest = store.add(entry);

            addRequest.onsuccess = (event) => {
                entry.id = event.target.result;
            };

            tx.oncomplete = () => resolve();
            tx.onerror = () => reject(tx.error);
        });

        await trimNotificationHistory(db);

        return entry;
    } catch (error) {
        console.error('[SW] Failed to save notification history:', error);
        return null;
    } finally {
        db?.close();
    }
}

async function trimNotificationHistory(db) {
    return new Promise((resolve, reject) => {
        try {
            const tx = db.transaction(HISTORY_STORE_NAME, 'readwrite');
            const store = tx.objectStore(HISTORY_STORE_NAME);
            const index = store.index('timestamp');
            let count = 0;

            index.openCursor().onsuccess = (event) => {
                const cursor = event.target.result;
                if (!cursor) {
                    return;
                }

                count += 1;
                if (count > MAX_HISTORY_ITEMS) {
                    cursor.delete();
                }
                cursor.continue();
            };

            tx.oncomplete = () => resolve();
            tx.onerror = () => reject(tx.error);
        } catch (error) {
            reject(error);
        }
    });
}

async function getNotificationHistory(limit = MAX_HISTORY_ITEMS) {
    try {
        const db = await openHistoryDB();
        try {
            const items = await new Promise((resolve, reject) => {
                const tx = db.transaction(HISTORY_STORE_NAME, 'readonly');
                const store = tx.objectStore(HISTORY_STORE_NAME);
                const index = store.index('timestamp');
                const results = [];

            index.openCursor(null, 'prev').onsuccess = (event) => {
                const cursor = event.target.result;
                if (!cursor || results.length >= limit) {
                    resolve(results);
                    return;
                }

                results.push(cursor.value);
                cursor.continue();
                };

                tx.onerror = () => reject(tx.error);
            });

            return items;
        } finally {
            db.close();
        }
    } catch (error) {
        console.error('[SW] Failed to read notification history:', error);
        return [];
    }
}

async function broadcastHistoryUpdate(record) {
    if (!record) {
        return;
    }

    try {
        const clientList = await clients.matchAll({ type: 'window', includeUncontrolled: true });
        clientList.forEach((client) => {
            client.postMessage({
                type: 'PUSH_HISTORY_UPDATED',
                payload: record
            });
        });
    } catch (error) {
        console.error('[SW] Failed to broadcast history update:', error);
    }
}

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
                    .filter((name) => name.startsWith('family-hub-') && ![STATIC_CACHE, DYNAMIC_CACHE, IMAGE_CACHE].includes(name))
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

    event.waitUntil((async () => {
        await self.registration.showNotification(data.title, options);

        const historyRecord = {
            title: data.title,
            body: data.body,
            url: options.data?.url || '/',
            icon: options.icon || '/assets/icons/app-icon-192.png',
            tag: options.tag || 'family-hub-notification',
            timestamp: options.data?.timestamp || Date.now()
        };

        try {
            const stored = await saveNotificationToHistory(historyRecord);
            if (stored) {
                await broadcastHistoryUpdate(stored);
            }
        } catch (error) {
            console.error('[SW] Failed to persist notification history:', error);
        }
    })());
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

    const message = event.data || {};
    const replyPort = event.ports && event.ports[0];

    if (message.type === 'SKIP_WAITING') {
        self.skipWaiting();
    }

    if (message.type === 'CLEAR_CACHE') {
        event.waitUntil(
            caches.keys().then((cacheNames) => {
                return Promise.all(
                    cacheNames.map((name) => caches.delete(name))
                );
            }).then(() => {
                replyPort?.postMessage({ success: true });
            })
        );
    }

    if (message.type === 'GET_CACHE_SIZE') {
        event.waitUntil(
            getCacheSize().then((size) => {
                replyPort?.postMessage({ size });
            })
        );
    }

    if (message.type === 'GET_NOTIFICATION_HISTORY') {
        event.waitUntil(
            getNotificationHistory(message.limit).then((history) => {
                replyPort?.postMessage({ ok: true, list: history });
            }).catch((error) => {
                console.error('[SW] Failed to send notification history:', error);
                replyPort?.postMessage({ ok: false, error: error.message });
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
