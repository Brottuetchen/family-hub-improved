/**
 * Inline Push Subscribe - Same code as working debug page
 */

// Helper function from debug page
function urlBase64ToUint8Array(base64String) {
    const padding = '='.repeat((4 - (base64String.length % 4)) % 4);
    const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
    const rawData = window.atob(base64);
    const outputArray = new Uint8Array(rawData.length);
    for (let i = 0; i < rawData.length; ++i) {
        outputArray[i] = rawData.charCodeAt(i);
    }
    return outputArray;
}

// Wait for DOM to be ready
document.addEventListener('DOMContentLoaded', () => {
    console.log('[Push-Inline] Script loaded');
    
    setTimeout(() => {
        const enablePushInMenuBtn = document.getElementById('enablePushInMenu');
        const enablePushBtn = document.getElementById('enablePush');
        
        if (enablePushInMenuBtn) {
            const newBtn = enablePushInMenuBtn.cloneNode(true);
            enablePushInMenuBtn.parentNode.replaceChild(newBtn, enablePushInMenuBtn);
            newBtn.addEventListener('click', async (e) => {
                e.preventDefault();
                e.stopPropagation();
                await handlePushSubscribe();
            });
            console.log('[Push-Inline] Overrode menu button');
        }
        
        if (enablePushBtn) {
            const newBtn = enablePushBtn.cloneNode(true);
            enablePushBtn.parentNode.replaceChild(newBtn, enablePushBtn);
            newBtn.addEventListener('click', async (e) => {
                e.preventDefault();
                await handlePushSubscribe();
            });
            console.log('[Push-Inline] Overrode modal button');
        }
    }, 1000);
});

async function handlePushSubscribe() {
    const API_BASE_URL = window.location.origin;
    const notificationToggle = document.getElementById('notificationToggle');
    const PUSH_DISMISSED_KEY = 'pushDismissed';
    
    try {
        console.log('[Push-Inline] === PUSH SUBSCRIPTION START ===');
        const permission = await Notification.requestPermission();
        console.log('[Push-Inline] Permission:', permission);
        
        if (permission !== 'granted') {
            alert('Benachrichtigungen wurden abgelehnt!');
            return;
        }

        const vapidResp = await fetch(API_BASE_URL + '/api/vapid-public-key');
        const data = await vapidResp.json();
        const publicKey = data.publicKey;
        console.log('[Push-Inline] VAPID key received');

        const registration = await navigator.serviceWorker.ready;
        console.log('[Push-Inline] Service Worker ready');
        
        const subscription = await registration.pushManager.subscribe({
            userVisibleOnly: true,
            applicationServerKey: urlBase64ToUint8Array(publicKey)
        });
        console.log('[Push-Inline] Subscription created');

        const saveResp = await fetch(API_BASE_URL + '/api/push/subscribe', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(subscription.toJSON())
        });

        const result = await saveResp.json();
        console.log('[Push-Inline] Saved to backend');

        if (notificationToggle) notificationToggle.classList.add('active');
        localStorage.removeItem(PUSH_DISMISSED_KEY);

        const pushEnableSection = document.getElementById('pushEnableSection');
        const notificationDropdown = document.getElementById('notificationDropdown');
        const pushModal = document.getElementById('pushModal');
        
        if (pushEnableSection) pushEnableSection.classList.add('is-hidden');
        if (notificationDropdown) notificationDropdown.classList.add('is-hidden');
        if (pushModal) pushModal.classList.add('is-hidden');

        alert('Push-Benachrichtigungen aktiviert!');
        console.log('[Push-Inline] === SUCCESS ===');
        
    } catch (error) {
        console.error('[Push-Inline] Error:', error);
        alert('Fehler: ' + error.message);
    }
}

console.log('[Push-Inline] Loaded');
