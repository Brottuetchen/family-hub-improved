(() => {
  const API = window.location.origin;
  const log = (msg) => {
    const el = document.getElementById('actionLog');
    el.textContent += (typeof msg === 'string' ? msg : JSON.stringify(msg, null, 2)) + "\n";
  };
  const setEnv = (obj) => {
    const el = document.getElementById('envInfo');
    el.textContent = JSON.stringify(obj, null, 2);
  };

  async function checkEnv() {
    const secure = window.isSecureContext;
    const hasSW = 'serviceWorker' in navigator;
    const hasPush = 'PushManager' in window;
    const hasNotif = 'Notification' in window;
    const perm = hasNotif ? Notification.permission : 'n/a';

    let vapid = null;
    let subsCount = null;
    try {
      const r1 = await fetch(`${API}/api/vapid-public-key`, { cache: 'no-cache' });
      vapid = `${r1.status} ${r1.statusText}`;
      if (r1.ok) {
        const j = await r1.json();
        vapid += ` (prefix=${String(j.publicKey||'').slice(0, 16)})`;
      } else {
        const t = await r1.text();
        vapid += ` -> ${t}`;
      }
    } catch (e) {
      vapid = `ERROR: ${e.message}`;
    }

    try {
      const r2 = await fetch(`${API}/api/push/subscriptions-count`, { cache: 'no-cache' });
      subsCount = await r2.json();
    } catch (e) {
      subsCount = { error: e.message };
    }

    setEnv({ secure, hasSW, hasPush, hasNotif, permission: perm, vapid, subsCount });
  }

  async function registerSW() {
    if (!('serviceWorker' in navigator)) {
      log('Service Worker not supported');
      return;
    }
    try {
      const reg = await navigator.serviceWorker.register('service-worker.js');
      await navigator.serviceWorker.ready;
      log('SW registered and ready: ' + (reg && reg.scope));
    } catch (e) {
      log('SW register failed: ' + e.message);
    }
  }

  async function subscribePush() {
    try {
      const pm = new window.PushManager(API);
      await pm.init();
      await pm.subscribe();
      log('Subscription created.');
      await checkEnv();
    } catch (e) {
      log('Subscribe failed: ' + e.message);
    }
  }

  async function sendTestPush() {
    try {
      const r = await fetch(`${API}/api/push/notify`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: 'Test', body: 'Push funktioniert?', url: '/index.html' })
      });
      const j = await r.json().catch(() => ({}));
      log({ status: r.status, body: j });
    } catch (e) {
      log('Test push failed: ' + e.message);
    }
  }

  async function fetchDebugApi() {
    try {
      const r = await window.AuthUtils.authenticatedFetch(`${API}/api/push/debug`);
      const j = await r.json();
      log(j);
    } catch (e) {
      log('Debug api failed (admin only?): ' + e.message);
    }
  }

  document.getElementById('btnRefresh').addEventListener('click', checkEnv);
  document.getElementById('btnRegisterSW').addEventListener('click', registerSW);
  document.getElementById('btnSubscribe').addEventListener('click', subscribePush);
  document.getElementById('btnTestPush').addEventListener('click', sendTestPush);
  document.getElementById('btnDebugApi').addEventListener('click', fetchDebugApi);

  checkEnv();
})();

