/* A short, observed house readout for the idle Cast receiver. */
(() => {
  if (location.pathname !== '/image') return;
  const node = document.getElementById('cast-house-status');
  if (!node || !window.MarqueeLifecycle) return;
  let expiryTimer;
  const clear = () => {
    clearTimeout(expiryTimer);
    node.replaceChildren();
    node.hidden = true;
  };
  const show = snapshot => {
    clear();
    const observed = Number(snapshot?.source_at);
    const age = Date.now() / 1000 - observed;
    if (snapshot?.fresh !== true || !Number.isFinite(observed) || observed <= 0 || age < -5 || age >= 45) return;
    const facts = [];
    const important = Array.isArray(snapshot.alerts) && snapshot.alerts.find(
      alert => ['CRITICAL', 'IMPORTANT', 'ACTIONABLE'].includes(String(alert?.urgency).toUpperCase()) && alert.title
    );
    const opening = Array.isArray(snapshot.openings) && snapshot.openings.find(
      item => item?.name && ['open', 'unlocked'].includes(item.state)
    );
    if (important) facts.push(String(important.title).slice(0, 48));
    else if (opening) facts.push(`${String(opening.name).slice(0, 36)} ${opening.state}`);
    if (snapshot.lock === 'unlocked' && !facts.some(fact => fact.includes('Front door'))) facts.push('Front door unlocked');
    if (!facts.length) {
      if (snapshot.lock === 'locked') facts.push('Front door locked');
      if (snapshot.house_activity?.living_room_occupied === true) facts.push('Living room occupied');
      else if (snapshot.house_activity?.bedroom_occupied === true) facts.push('Bedroom occupied');
      if (snapshot.sleeping === true && facts.length < 2) facts.push('Someone sleeping');
    }
    if (!facts.length) return;
    for (const fact of facts.slice(0, 2)) {
      const item = document.createElement('span');
      item.textContent = fact;
      node.append(item);
    }
    node.hidden = false;
    expiryTimer = setTimeout(clear, Math.max(0, (45 - age) * 1000));
  };
  window.MarqueeLifecycle.register('cast-house-status', {
    interval: 15000,
    timeout: 10000,
    async refresh(lifecycle) {
      const response = await fetch('/api/brain', {signal: lifecycle.signal});
      if (!response.ok) throw Error('House status unavailable');
      const snapshot = await response.json();
      if (lifecycle.isCurrent()) show(snapshot);
    },
    onError: clear,
  });
})();
