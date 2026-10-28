/* Service worker mínimo: solo assets estáticos (requisito PWA). No cachea HTML ni rutas auth. */
const CACHE = "doctor-descheduler-static-v4";
const ASSETS = [
  "/static/css/style.css",
  "/static/js/app.js",
  "/static/js/theme.js",
  "/static/js/fleet-run.js",
  "/static/js/pwa.js",
  "/static/manifest.webmanifest",
  "/static/icons/icon-192.png",
  "/static/icons/icon-512.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(ASSETS)));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (!url.pathname.startsWith("/static/")) return;
  event.respondWith(caches.match(req).then((cached) => cached || fetch(req)));
});
