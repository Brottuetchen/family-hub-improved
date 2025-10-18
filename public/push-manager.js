/**
 * Push Notification Manager für Family Hub
 * Handhabt Web Push Subscriptions und Benachrichtigungen
 */

class PushManager {
    constructor(apiUrl) {
        this.apiUrl = apiUrl;
        this.subscription = null;
        this.publicKey = null;
        this.isSupported = this.checkSupport();
    }

    /**
     * Prüft ob Push Notifications unterstützt werden
     */
    checkSupport() {
        // Secure context is required for Service Worker + Push (except localhost)
        if (!window.isSecureContext && location.hostname !== 'localhost' && location.hostname !== '127.0.0.1') {
            console.warn('Push requires a secure context (HTTPS)');
            return false;
        }

        if (!('serviceWorker' in navigator)) {
            console.warn('Service Worker not supported');
            return false;
        }

        if (!('PushManager' in window)) {
            console.warn('Push API not supported');
            return false;
        }

        if (!('Notification' in window)) {
            console.warn('Notifications not supported');
            return false;
        }

        // iOS-specific checks
        const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent) ||
                      (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);

        if (isIOS) {
            console.log('[iOS] Push notifications detected on iOS device');
            // iOS 16.4+ supports push, but requires PWA installation
            const isStandalone = window.navigator.standalone === true ||
                                window.matchMedia('(display-mode: standalone)').matches;

            if (!isStandalone) {
                console.warn('[iOS] Push notifications require PWA to be installed (Add to Home Screen)');
                // Still return true - we'll show a helpful message to the user
            }
        }

        return true;
    }

    /**
     * Initialisiert Push Manager
     * @returns {Promise<boolean>} True wenn Subscription existiert
     */
    async init() {
        if (!this.isSupported) {
            return false;
        }

        try {
            // Warte auf Service Worker
            const registration = await navigator.serviceWorker.ready;

            // Prüfe bestehende Subscription
            this.subscription = await registration.pushManager.getSubscription();

            if (this.subscription) {
                console.log('Existing push subscription found');
                return true;
            }

            return false;
        } catch (error) {
            console.error('Push Manager init error:', error);
            return false;
        }
    }

    /**
     * Fragt Benutzer nach Notification-Berechtigung
     * @returns {Promise<string>} Permission status
     */
    async requestPermission() {
        if (!this.isSupported) {
            throw new Error('Push notifications not supported');
        }

        if (Notification.permission === 'granted') {
            return 'granted';
        }

        if (Notification.permission === 'denied') {
            throw new Error('Notification permission denied');
        }

        const permission = await Notification.requestPermission();
        return permission;
    }

    /**
     * Hole VAPID Public Key vom Backend
     * @returns {Promise<string>}
     */
    async getPublicKey() {
        if (this.publicKey) {
            return this.publicKey;
        }

        try {
            const response = await fetch(`${this.apiUrl}/api/vapid-public-key`);

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const data = await response.json();
            this.publicKey = data.publicKey;

            return this.publicKey;
        } catch (error) {
            console.error('Failed to get VAPID public key:', error);
            throw new Error('Backend nicht erreichbar oder Push nicht konfiguriert');
        }
    }

    /**
     * Konvertiert VAPID Base64 Key zu Uint8Array
     * @param {string} base64String
     * @returns {Uint8Array}
     */
    urlBase64ToUint8Array(base64String) {
        const padding = '='.repeat((4 - (base64String.length % 4)) % 4);
        const base64 = (base64String + padding)
            .replace(/-/g, '+')
            .replace(/_/g, '/');

        const rawData = window.atob(base64);
        const outputArray = new Uint8Array(rawData.length);

        for (let i = 0; i < rawData.length; ++i) {
            outputArray[i] = rawData.charCodeAt(i);
        }

        return outputArray;
    }

    /**
     * Erstellt neue Push Subscription
     * @returns {Promise<PushSubscription>}
     */
    async subscribe() {
        if (!this.isSupported) {
            throw new Error('Push notifications not supported');
        }

        // iOS-specific check
        const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent) ||
                      (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);

        if (isIOS) {
            const isStandalone = window.navigator.standalone === true ||
                                window.matchMedia('(display-mode: standalone)').matches;

            if (!isStandalone) {
                const errorMsg = 'iOS benötigt die Installation als PWA (Add to Home Screen) für Push-Benachrichtigungen. ' +
                                'Tippe auf das Teilen-Symbol und wähle "Zum Home-Bildschirm".';
                console.error('[iOS]', errorMsg);
                throw new Error(errorMsg);
            }
        }

        try {
            // 1. Hole Permission
            const permission = await this.requestPermission();

            if (permission !== 'granted') {
                throw new Error('Notification permission not granted');
            }

            // 2. Hole VAPID Public Key
            const publicKey = await this.getPublicKey();
            const applicationServerKey = this.urlBase64ToUint8Array(publicKey);

            // 3. Warte auf Service Worker (mit iOS-Timeout)
            console.log('[Push] Waiting for service worker...');
            const registration = await Promise.race([
                navigator.serviceWorker.ready,
                new Promise((_, reject) =>
                    setTimeout(() => reject(new Error('Service Worker timeout')), 10000)
                )
            ]);

            console.log('[Push] Service worker ready, subscribing...');

            // 4. Erstelle Subscription (mit iOS retry logic)
            let subscribeAttempt = 0;
            const maxAttempts = 3;

            while (subscribeAttempt < maxAttempts) {
                try {
                    this.subscription = await registration.pushManager.subscribe({
                        userVisibleOnly: true,
                        applicationServerKey: applicationServerKey
                    });

                    console.log('[Push] Subscription created successfully:', this.subscription.endpoint);
                    break;
                } catch (subscribeError) {
                    subscribeAttempt++;
                    console.warn(`[Push] Subscribe attempt ${subscribeAttempt} failed:`, subscribeError);

                    if (subscribeAttempt >= maxAttempts) {
                        throw subscribeError;
                    }

                    // Wait before retry (iOS sometimes needs a moment)
                    await new Promise(resolve => setTimeout(resolve, 1000));
                }
            }

            // 5. Sende Subscription an Backend
            await this.sendSubscriptionToBackend(this.subscription);

            return this.subscription;

        } catch (error) {
            console.error('[Push] Subscription failed:', error);
            // Provide user-friendly error messages
            if (error.name === 'NotAllowedError') {
                throw new Error('Push-Benachrichtigungen wurden blockiert. Bitte erlaube Benachrichtigungen in den Einstellungen.');
            } else if (error.name === 'NotSupportedError') {
                throw new Error('Push-Benachrichtigungen werden auf diesem Gerät nicht unterstützt.');
            } else if (error.message.includes('timeout')) {
                throw new Error('Service Worker konnte nicht geladen werden. Bitte versuche es erneut.');
            }
            throw error;
        }
    }

    /**
     * Sendet Subscription an Backend
     * @param {PushSubscription} subscription
     */
    async sendSubscriptionToBackend(subscription) {
        try {
            const response = await fetch(`${this.apiUrl}/api/push/subscribe`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(subscription.toJSON())
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const data = await response.json();
            console.log('Subscription saved to backend:', data);

        } catch (error) {
            console.error('Failed to save subscription:', error);
            throw new Error('Subscription konnte nicht gespeichert werden');
        }
    }

    /**
     * Entfernt Push Subscription
     * @returns {Promise<boolean>}
     */
    async unsubscribe() {
        if (!this.subscription) {
            return false;
        }

        try {
            await this.subscription.unsubscribe();
            this.subscription = null;
            console.log('Push subscription removed');
            return true;

        } catch (error) {
            console.error('Unsubscribe failed:', error);
            return false;
        }
    }

    /**
     * Prüft ob Subscription noch gültig ist
     * @returns {Promise<boolean>}
     */
    async checkSubscription() {
        if (!this.isSupported) {
            return false;
        }

        try {
            const registration = await navigator.serviceWorker.ready;
            const subscription = await registration.pushManager.getSubscription();

            if (!subscription) {
                this.subscription = null;
                return false;
            }

            // Prüfe Expiration (wenn verfügbar)
            if (subscription.expirationTime && subscription.expirationTime < Date.now()) {
                console.warn('Push subscription expired');
                await this.unsubscribe();
                return false;
            }

            this.subscription = subscription;
            return true;

        } catch (error) {
            console.error('Check subscription error:', error);
            return false;
        }
    }

    /**
     * Sendet Test-Benachrichtigung (nur für Testing)
     * @param {string} title
     * @param {string} body
     */
    async sendTestNotification(title = 'Test Notification', body = 'Dies ist eine Test-Benachrichtigung') {
        if (Notification.permission !== 'granted') {
            throw new Error('Notification permission not granted');
        }

        // Lokale Test-Notification (ohne Server)
        const registration = await navigator.serviceWorker.ready;
        await registration.showNotification(title, {
            body: body,
            icon: '/assets/icons/app-icon-192.png',
            badge: '/assets/icons/app-icon-192.png',
            vibrate: [200, 100, 200],
            tag: 'test-notification',
            requireInteraction: false
        });
    }

    /**
     * Debug-Informationen ausgeben
     */
    getDebugInfo() {
        return {
            supported: this.isSupported,
            permission: Notification.permission,
            subscribed: !!this.subscription,
            subscription: this.subscription ? {
                endpoint: this.subscription.endpoint,
                expirationTime: this.subscription.expirationTime
            } : null
        };
    }
}

// Export für use in app.js
if (typeof window !== 'undefined') {
    window.PushManager = PushManager;
}

// Auto-init wenn als Modul geladen
if (typeof module !== 'undefined' && module.exports) {
    module.exports = PushManager;
}
