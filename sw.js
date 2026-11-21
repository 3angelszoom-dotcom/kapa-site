// KAPA 웹앱 서비스 워커: 폰 알림(푸시)을 받아서 보여 주고, 누르면 체크인 화면을 열어 줌
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', e => e.waitUntil(self.clients.claim()));
self.addEventListener('push', e => {
  let p = {};
  try { p = e.data ? e.data.json() : {}; } catch (_) { p = { data: { body: e.data ? e.data.text() : '' } }; }
  const d = p.data || {}, n = p.notification || {};
  const title = d.title || n.title || 'KAPA';
  const link = d.link || '/';
  e.waitUntil(Promise.all([self.registration.showNotification(title, {
    body: d.body || n.body || '', icon: 'icon-192.png', badge: 'icon-192.png',
    tag: d.tag || 'kapa-meet', renotify: true, data: { link: link }   // 서버가 알림마다 다른 tag를 보내면 알림이 쌓임 (안 보내면 예전처럼 마지막 것만)
  }), bumpBadge()]));
});
// 홈 화면 앱 아이콘 숫자(배지): 알림이 올 때마다 +1, 앱을 열면 페이지가 0으로 지움.
// 숫자를 지우는 페이지(지금은 테스트 페이지)가 'on' 표시를 남겨 둔 경우에만 켬 → 지우지 못하는 화면에서 숫자가 계속 쌓이지 않게
async function bumpBadge() {
  try {
    if (!self.navigator || !self.navigator.setAppBadge) return;
    const c = await caches.open('kapa-badge');
    if (!(await c.match('/__badge/on'))) return;
    const r = await c.match('/__badge/n');
    const n = (r ? Number(await r.text()) || 0 : 0) + 1;
    await c.put('/__badge/n', new Response(String(n)));
    await self.navigator.setAppBadge(n);
  } catch (_) {}
}
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
