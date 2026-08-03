/* Hermes Family OS — Service Worker (offline shell + Web Push) */

const CACHE = "hermes-v1";
const SHELL = [
  "/",
  "/index.html",
  "/styles.css",
  "/app.js",
  "/login.html",
  "/login.js",
  "/manifest.webmanifest",
  "/assets/icons/app-icon-192.png",
  "/assets/icons/app-icon-512.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).catch(() => {}));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return;
  const url = new URL(request.url);

  // API: always network (never cache dynamic data)
  if (url.pathname.startsWith("/api/")) return;

  // Static: cache-first with network fallback
  event.respondWith(
    caches.match(request).then((cached) => {
      const network = fetch(request)
        .then((res) => {
          if (res && res.status === 200 && url.origin === self.location.origin) {
            const copy = res.clone();
            caches.open(CACHE).then((c) => c.put(request, copy));
          }
          return res;
        })
        .catch(() => cached);
      return cached || network;
    })
  );
});

/* --- Web Push --- */
self.addEventListener("push", (event) => {
  let data = { title: "Hermes", body: "Neue Benachrichtigung", url: "/", icon: "/assets/icons/app-icon-192.png" };
  try { if (event.data) data = { ...data, ...event.data.json() }; } catch (_) {}

  const options = {
    body: data.body,
    icon: data.icon || "/assets/icons/app-icon-192.png",
    badge: "/assets/icons/app-icon-192.png",
    data: { url: data.url || "/" },
    tag: data.priority === "critical" ? "hermes-critical" : "hermes",
    requireInteraction: data.priority === "critical",
  };
  event.waitUntil(self.registration.showNotification(data.title || "Hermes", options));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const target = (event.notification.data && event.notification.data.url) || "/";
  event.waitUntil(
    clients.matchAll({ type: "window", includeUncontrolled: true }).then((list) => {
      for (const client of list) {
        if (client.url.includes(target) && "focus" in client) return client.focus();
      }
      return clients.openWindow(target);
    })
  );
});
