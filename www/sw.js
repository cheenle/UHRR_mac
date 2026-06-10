// 只缓存静态资源 — JS/HTML 始终走网络，避免缓存旧代码
const CACHE_NAME = 'hamradio-static-v17.0';
const STATIC_ASSETS = [
  '/mobile_modern.css',
  '/favicon.png',
  '/manifest.json'
];

// Install
self.addEventListener('install', function(event) {
  console.log('SW v17.0 installing...');
  self.skipWaiting();
  event.waitUntil(
    caches.open(CACHE_NAME).then(function(cache) {
      return cache.addAll(STATIC_ASSETS);
    }).catch(function(e) {
      console.error('SW cache error:', e);
    })
  );
});

// Activate — 立即接管并清理旧缓存
self.addEventListener('activate', function(event) {
  console.log('SW v17.0 activating...');
  event.waitUntil(
    caches.keys().then(function(keys) {
      return Promise.all(
        keys.filter(function(k) { return k !== CACHE_NAME; })
            .map(function(k) { console.log('Deleting:', k); return caches.delete(k); })
      );
    }).then(function() {
      return self.clients.claim();
    })
  );
});

// Fetch — 只拦截静态资源，JS/HTML 直通网络
self.addEventListener('fetch', function(event) {
  const url = new URL(event.request.url);
  // JS/HTML: 完全不拦截，直接走网络
  if (url.pathname.endsWith('.js') || url.pathname.endsWith('.html') || url.pathname === '/') {
    return; // 不拦截 → 浏览器正常请求
  }
  // 静态资源: cache-first
  event.respondWith(
    caches.match(event.request).then(function(r) {
      return r || fetch(event.request);
    })
  );
});
