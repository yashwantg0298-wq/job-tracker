// Job Vault — service worker for PWA offline support.
// Strategies:
//   - App shell (HTML/CSS/JS/icons): cache-first, fall through to network.
//   - Encrypted data file: network-first, fall back to last cached copy when offline.
//   - Cross-origin (logo CDNs etc): bypass — let the browser handle.

const VERSION = "v7";
const CACHE = `job-vault-${VERSION}`;

const APP_SHELL = [
  "./",
  "./index.html",
  "./admin.html",
  "./styles.css?v=7",
  "./app.js?v=7",
  "./manifest.json",
  "./icon-192.png",
  "./icon-512.png",
  "./icon-512-maskable.png",
  "./apple-touch-icon.png",
  "./favicon-32.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE).then((cache) =>
      // addAll fails the whole install on any 404; use individual put calls so
      // a single missing file doesn't kill SW activation.
      Promise.all(
        APP_SHELL.map((url) =>
          fetch(url, { cache: "reload" })
            .then((res) => res.ok ? cache.put(url, res) : null)
            .catch(() => null)
        )
      )
    )
  );
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
  if (url.origin !== self.location.origin) return; // pass-through for cross-origin (logos, etc.)

  // Network-first for the encrypted data file
  if (url.pathname.endsWith("/applications.enc.json")) {
    event.respondWith(
      fetch(req).then((res) => {
        const copy = res.clone();
        caches.open(CACHE).then((c) => c.put(req, copy));
        return res;
      }).catch(() => caches.match(req))
    );
    return;
  }

  // Cache-first for everything else (with background refresh)
  event.respondWith(
    caches.match(req).then((cached) => {
      const fetchPromise = fetch(req).then((res) => {
        if (res && res.ok) {
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put(req, copy));
        }
        return res;
      }).catch(() => cached);
      return cached || fetchPromise;
    })
  );
});

// Allow page to ask for an immediate skipWaiting (used by an "Update available" toast if we add one later).
self.addEventListener("message", (event) => {
  if (event.data && event.data.type === "SKIP_WAITING") self.skipWaiting();
});
