(() => {
  const params = new URLSearchParams(location.search);
  if (window.top !== window.self || location.pathname !== '/kiosk' || params.get('wired') !== '1' ||
      ['demo', 'edit', 'receiver'].some(key => params.has(key))) return;

  const version = new URL(document.currentScript.src).searchParams.get('v');
  if (!version) return;
  let lastInteraction = 0;
  let checking = false;

  const noteInteraction = () => { lastInteraction = Date.now(); };
  addEventListener('pointerdown', noteInteraction, {passive: true});
  addEventListener('keydown', noteInteraction);

  async function checkForUpdate() {
    if (checking || Date.now() - lastInteraction < 60000) return;
    checking = true;
    try {
      const response = await fetch('/healthz', {cache: 'no-store'});
      if (!response.ok) return;
      const health = await response.json();
      if (health.version && health.version !== version) location.reload();
    } catch (_) {
      // Keep the current display during a temporary server outage.
    } finally {
      checking = false;
    }
  }

  setInterval(checkForUpdate, 300000);
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden) checkForUpdate();
  });
})();
