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
    tag: 'kapa-meet', renotify: true, data: { link: link }
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
