// 只缓存静态资源 — JS/HTML 始终走网络，避免缓存旧代码
const CACHE_NAME = 'hamradio-static-v17.0';
// 预缓存必须是绝对路径，但前缀随部署位置变化 —— 从注册 scope 推出，不硬编码站点根。
const SW_BASE = new URL(self.registration.scope).pathname.replace(/\/$/, '');
const STATIC_ASSETS = [
  SW_BASE + '/mobile_modern.css',
  SW_BASE + '/favicon.png',
  SW_BASE + '/manifest.json'
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
