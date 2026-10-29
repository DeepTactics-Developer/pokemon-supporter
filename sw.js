// 앱 화면: 온라인이면 최신 버전, 오프라인이면 캐시. 포켓몬 이미지·글꼴: 한 번 받으면 캐시에서.
// 포켓몬 데이터(GraphQL POST)는 앱이 localStorage에 따로 캐시하므로 여기선 건드리지 않음.
const CACHE = 'pokemon-supporter-v2';
const CACHED_HOSTS = ['raw.githubusercontent.com', 'fonts.googleapis.com', 'fonts.gstatic.com'];
const SHELL = ['./', 'index.html', 'manifest.webmanifest', 'icon-192.png', 'icon-512.png'];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL)).then(() => self.skipWaiting()));
});
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener('fetch', e => {
  const req = e.request, url = new URL(req.url);
  if (req.method !== 'GET') return;
  const put = res => { const copy = res.clone(); caches.open(CACHE).then(c => c.put(req, copy)); return res; };
  if (req.mode === 'navigate') {
    e.respondWith(fetch(req).then(put).catch(() => caches.match(req).then(r => r || caches.match('index.html'))));
  } else if (url.origin === location.origin || CACHED_HOSTS.includes(url.hostname)) {
    e.respondWith(caches.match(req).then(r => r || fetch(req).then(res => res.ok || res.type === 'opaque' ? put(res) : res)));
  }
});
