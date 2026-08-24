// web/sw.js — cache last-viewed data for offline
const CACHE = "cjr-v8";
const ASSETS = ["./", "index.html", "style.css", "app.js", "filters.js", "sections.js", "titles.js", "manifest.webmanifest",
  "data/jobs.json", "data/meta.json", "icons/logo.svg", "icons/logo-small.svg", "icons/logo-192.png"];

// Behind Cloudflare Access an expired session answers with the sign-in page —
// status 200, but redirected and HTML. Caching that would pin the login screen
// in place of the app's own data, and no amount of signing in would clear it.
function shouldCache(request, response) {
  if (!response || !response.ok || response.redirected) return false;
  if (response.type === "opaque" || response.type === "opaqueredirect") return false;
  const type = (response.headers && response.headers.get("content-type")) || "";
  if (request.url.endsWith(".json") && !type.includes("json")) return false;
  return true;
}
self.shouldCache = shouldCache;  // exposed so tests can exercise it directly

self.addEventListener("install", e =>
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(ASSETS)).then(() => self.skipWaiting())));
self.addEventListener("activate", e =>
  e.waitUntil(caches.keys().then(k => Promise.all(k.filter(x => x !== CACHE).map(x => caches.delete(x))))));
self.addEventListener("fetch", e => {
  e.respondWith(
    fetch(e.request).then(r => {
      if (shouldCache(e.request, r)) {
        const cp = r.clone();
        caches.open(CACHE).then(c => c.put(e.request, cp));
      }
      return r;
    }).catch(() => caches.match(e.request))
  );
});
