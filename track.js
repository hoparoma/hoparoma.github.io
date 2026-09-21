// Counts clicks that leave the reference site for the web calculator or the App Store (GA4 events).
// placement comes from an optional data-placement attribute on the link.
// The web calculator opens in the same tab, so the hit is sent as a beacon to survive the navigation.
document.addEventListener('click', function (event) {
  var link = event.target.closest && event.target.closest('a[href]');
  if (!link || typeof window.gtag !== 'function') return;
  var name = link.hostname === 'app.hoparoma.com' ? 'web_app_click'
    : link.hostname === 'apps.apple.com' ? 'app_store_click'
    : null;
  if (!name) return;
  window.gtag('event', name, {
    link_url: link.href,
    placement: link.getAttribute('data-placement') || 'unspecified',
    transport_type: 'beacon'
  });
});
