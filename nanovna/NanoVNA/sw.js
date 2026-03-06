// Service Worker for HamRadio Mobile App PWA Support

const CACHE_NAME = 'hamradio-mobile-v1.0';
const urlsToCache = [
  './',
  './index.html',
  './nanovna.js',
  './script.js',
  './lib/vue.min.js',
  './lib/vue-material.min.js',
  './lib/chart.js',
  './lib/chartjs-chart-smith.js',
  './lib/strftime-min.js',
  './lib/micro-strptime.js',
  './lib/material-design-icons-iconfont/material-design-icons.css',
  './lib/vue-material.min.css',
  './lib/theme/default.css',
  './images/icons/icon-512x512.png',
  './manifest.json'
];

// Install event - cache essential files
self.addEventListener('install', function(event) {
  console.log('Service Worker installing...');
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(function(cache) {
        console.log('Opened cache');
        return cache.addAll(urlsToCache);
      })
      .catch(function(error) {
        console.error('Failed to cache files during install:', error);
      })
  );
});

// Fetch event - serve cached content when offline
self.addEventListener('fetch', function(event) {
  event.respondWith(
    caches.match(event.request)
      .then(function(response) {
        // Return cached version if available
        if (response) {
          return response;
        }
        
        // Clone the request because it's a stream and can only be consumed once
        const fetchRequest = event.request.clone();
        
        // Try to fetch from network
        return fetch(fetchRequest)
          .then(function(response) {
            // Check if we received a valid response
            if (!response || response.status !== 200 || response.type !== 'basic') {
              return response;
            }
            
            // Clone the response because it's a stream and can only be consumed once
            const responseToCache = response.clone();
            
            // Cache the response for future use
            caches.open(CACHE_NAME)
              .then(function(cache) {
                cache.put(event.request, responseToCache);
              })
              .catch(function(error) {
                console.error('Failed to cache response:', error);
              });
              
            return response;
          })
          .catch(function(error) {
            console.error('Network fetch failed:', error);
            // Return a fallback response if available
            return new Response('Offline content', {
              status: 200,
              statusText: 'OK',
              headers: {
                'Content-Type': 'text/html'
              }
            });
          });
      })
      .catch(function(error) {
        console.error('Cache match failed:', error);
      })
  );
});

// Activate event - clean up old caches
self.addEventListener('activate', function(event) {
  console.log('Service Worker activating...');
  const cacheWhitelist = [CACHE_NAME];
  
  event.waitUntil(
    caches.keys()
      .then(function(cacheNames) {
        return Promise.all(
          cacheNames.map(function(cacheName) {
            if (cacheWhitelist.indexOf(cacheName) === -1) {
              return caches.delete(cacheName);
            }
          })
        );
      })
      .catch(function(error) {
        console.error('Failed to clean up old caches:', error);
      })
  );
});

// Handle push notifications (if needed in future)
self.addEventListener('push', function(event) {
  console.log('Push notification received:', event);
  // Handle push notifications here if implemented
});

// Handle notification clicks (if needed in future)
self.addEventListener('notificationclick', function(event) {
  console.log('Notification clicked:', event);
  // Handle notification clicks here if implemented
});

console.log('HamRadio Service Worker loaded');

