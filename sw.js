// KAPA 웹앱 서비스 워커: 폰 알림(푸시)을 받아서 보여 주고, 누르면 체크인 화면을 열어 줌
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', e => e.waitUntil(self.clients.claim()));
self.addEventListener('push', e => {
  let p = {};
  try { p = e.data ? e.data.json() : {}; } catch (_) { p = { data: { body: e.data ? e.data.text() : '' } }; }
  const d = p.data || {}, n = p.notification || {};
  const title = d.title || n.title || 'KAPA';
  const link = d.link || '/';
  e.waitUntil(self.registration.showNotification(title, {
    body: d.body || n.body || '', icon: 'icon-192.png', badge: 'icon-192.png',
    tag: d.tag || 'kapa-meet', renotify: true, data: { link: link }   // 서버가 알림마다 다른 tag를 보내면 알림이 쌓임 (안 보내면 예전처럼 마지막 것만)
  }));
});
self.addEventListener('notificationclick', e => {
  e.notification.close();
  const link = new URL((e.notification.data && e.notification.data.link) || '/', self.location.origin).href;
  e.waitUntil(self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then(ws => {
    for (const w of ws) {
      if (new URL(w.url).origin === self.location.origin && 'focus' in w) {
        return w.focus().then(f => (f && 'navigate' in f ? f.navigate(link) : f)).catch(() => self.clients.openWindow(link));
      }
    }
    return self.clients.openWindow(link);
  }));
});
// 안드로이드 "공유 → KAPA": 공유한 스크린샷을 잠깐 보관해 두고 글쓰기 화면(?shared=1)으로 넘김
self.addEventListener('fetch', e => {
  const u = new URL(e.request.url);
  if (e.request.method !== 'POST' || u.origin !== self.location.origin || u.pathname !== '/share-target') return;
  e.respondWith((async () => {
    const page = u.searchParams.get('p') === 'test' ? '/test.html' : '/';
    try {
      const fd = await e.request.formData();
      const files = fd.getAll('images').filter(f => f && typeof f !== 'string' && f.size);
      const c = await caches.open('kapa-share');
      for (const k of await c.keys()) await c.delete(k);
      await Promise.all(files.slice(0, 3).map((f, i) => c.put('/__share/' + i, new Response(f, { headers: {
        'Content-Type': f.type || 'image/png', 'X-Name': encodeURIComponent(f.name || ('screenshot-' + (i + 1) + '.png')) } }))));
    } catch (_) {}
    return Response.redirect(page + '?shared=1', 303);
  })());
});
