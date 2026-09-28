/* Shared direct navigation for every Live/Kiosk content screen. */
(() => {
  const params = new URLSearchParams(location.search);
  if (!['/live', '/kiosk'].includes(location.pathname) || params.has('demo') || params.has('edit') || params.has('receiver')) return;
  const destinations = { plex:['Now playing','▶'], nhl:['NHL','⚑'], ufc:['UFC','⚑'], pfl:['PFL','⚑'], weather:['Weather','☼'], tv:['TV','▣'], astronomy:['Sky','✦'], movies:['Movies','▶'], trailers:['Trailers','▶'], major_events:['Events','◆'], gaming:['Gaming','⌘'], music:['Music','♫'], calendar:['Calendar','□'] };
  // Weather is a first-class ambient destination. Keep urgent weather visible
  // ahead of lower-priority sports when the rail has to compact or overflow.
  const destinationPriority = { plex:100, weather:95, nhl:85, ufc:75, pfl:65,
    calendar:55, tv:50, astronomy:45, gaming:40, music:35, movies:30,
    trailers:25, major_events:20 };
  let sections = [], contexts = [], health = {}, selected = '', loaded = false, offline = false;
  // The server payload is the only media truth. Navigation may choose which
  // surface is visible, but it must never manufacture a replacement Plex
  // state from browse contexts or from the previous render.
  let nowPlaying = null;
  let view = params.get('view') || '', interrupted = false;
  const label = key => destinations[key]?.[0] || key.replaceAll('_', ' ').replace(/^./, c => c.toUpperCase());
  const icon = key => destinations[key]?.[1] || '•';
  const esc = text => String(text ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const fresh = c => (!c.expires || Date.parse(c.expires) > Date.now()) && c.eventState !== 'EXPIRED';
  const items = key => contexts.filter(c => (c.provider || c.source) === key && fresh(c));
  document.body.classList.add('browser-controls');
  const rail = document.createElement('div'); rail.className = 'screen-controls kiosk-rail';
  rail.innerHTML = '<span class="kiosk-brand" role="status" aria-live="polite">Marquee</span><nav class="kiosk-primary" aria-label="Marquee destinations"></nav><button class="kiosk-more" type="button" aria-haspopup="dialog" aria-expanded="false"><span aria-hidden="true">•••</span><span class="kiosk-label">More</span></button>';
  document.body.append(rail);
  const primary = rail.querySelector('.kiosk-primary'), more = rail.querySelector('.kiosk-more'), status = rail.querySelector('[role=status]');
  const menu = document.createElement('dialog'); menu.className = 'kiosk-menu'; menu.setAttribute('aria-labelledby', 'kiosk-menu-title');
  menu.innerHTML = '<header><h2 id="kiosk-menu-title">More destinations</h2><button type="button" aria-label="Close menu">✕</button></header><nav aria-label="Additional Marquee destinations"></nav><details><summary>Settings</summary><nav aria-label="Marquee control pages"><a href="/live" aria-current="page">Live display</a><a href="/settings">Settings</a><a href="/settings/layout?profile=live">Edit screen layout</a><a href="/settings/attention">Alert rules</a><a href="/settings/tests">Test screens</a></nav></details>';
  document.body.append(menu);
  const overflow = menu.querySelector('nav');
  const panel = document.createElement('section'); panel.className = 'kiosk-section'; panel.hidden = true; panel.setAttribute('aria-label', 'Selected kiosk section'); document.body.append(panel);
  function href(key) { const u = new URL(location.href); key ? u.searchParams.set('view', key) : u.searchParams.delete('view'); return u.pathname + u.search; }
  function allDestinations() {
    return [['', 'Home', '⌂'], ...sections.map((key, index) => [key, label(key), icon(key), index])]
      .sort((a, b) => a[0] === '' ? -1 : b[0] === '' ? 1
        : (destinationPriority[b[0]] ?? 0) - (destinationPriority[a[0]] ?? 0) || a[3] - b[3])
      .map(([key, title, glyph]) => [key, title, glyph]);
  }
  function link([key, title, glyph], detail = '') { return `<a href="${esc(href(key))}" data-view="${esc(key)}" aria-label="${esc(title)}" title="${esc(title)}" ${key===view?'aria-current="page"':''}><span class="kiosk-icon" aria-hidden="true">${esc(glyph)}</span><span class="kiosk-label">${esc(title)}</span>${detail ? `<small>${esc(detail)}</small>` : ''}</a>`; }
  function drawNavigation() {
    const all = allDestinations(); primary.innerHTML = all.map(d => link(d)).join(''); primary.querySelectorAll('a').forEach(a => a.hidden = false); more.hidden = false;
    const available = () => Math.max(0, rail.clientWidth - rail.querySelector('.kiosk-brand').offsetWidth - more.offsetWidth - 44);
    let used = [...primary.children].reduce((sum, a) => sum + a.offsetWidth, 0), cutoff = all.length;
    while (used > available() && cutoff > 1) { const a = primary.children[--cutoff]; used -= a.offsetWidth; a.hidden = true; }
    const hidden = all.slice(cutoff); overflow.innerHTML = hidden.map(d => link(d, offline ? 'Connection unavailable' : `${items(d[0]).length} current item${items(d[0]).length === 1 ? '' : 's'}`)).join(''); more.hidden = hidden.length === 0; more.setAttribute('aria-expanded', 'false');
  }
  function drawMenu() { const hiddenKeys = new Set([...overflow.querySelectorAll('[data-view]')].map(a => a.dataset.view)); overflow.innerHTML = allDestinations().filter(([key]) => hiddenKeys.has(key)).map(d => link(d, offline ? 'Connection unavailable' : `${items(d[0]).length} current item${items(d[0]).length === 1 ? '' : 's'}`)).join(''); }
  function drawPanel() {
    panel.dataset.section = view; status.textContent = interrupted ? 'Household attention' : view === 'household' ? 'Household' : view ? label(view) : 'Marquee · Auto';
    const valid = sections.includes(view), list = valid && !offline ? items(view) : [];
    if (selected && !list.some(c => c.id === selected)) selected = '';
    if (view === 'weather' && !selected && list.length) selected = (list.find(c => ['alert','extreme'].includes(c.subtype)) || list.find(c => c.subtype === 'current') || list[0]).id;
    const plexActive = view === 'plex' && nowPlaying?.playing === true;
    panel.classList.toggle('now-playing-surface', view === 'plex');
    panel.hidden = interrupted || !view || view === 'household' || plexActive || Boolean(selected); if (panel.hidden) return;
    if (view === 'plex') {
      const unavailable = nowPlaying?.state === 'unavailable' || nowPlaying?.availability === 'unavailable';
      const loading = !nowPlaying;
      const title = loading ? 'Checking the media room' : unavailable ? 'Media service unavailable' : 'Nothing is playing';
      const detail = loading ? 'Reading the current playback state.' : unavailable
        ? 'Marquee is ready when the media service reconnects. No previous title or artwork is retained here.'
        : 'The room is quiet. Choose Home to return to the household view.';
      const ambient = document.querySelector('#idle-weather')?.textContent?.trim() || 'Home display ready';
      panel.innerHTML = `<header class="kiosk-now-playing-head"><p>NOW PLAYING</p><h1>${esc(title)}</h1><p class="kiosk-now-playing-detail">${esc(detail)}</p></header><div class="kiosk-now-playing-body"><div class="kiosk-state-mark ${unavailable ? 'is-unavailable' : ''}" aria-hidden="true"><span>${unavailable ? '↻' : '·'}</span></div><div class="kiosk-now-playing-copy"><p class="kiosk-ambient">${esc(ambient)}</p><p class="kiosk-now-playing-note">${unavailable ? 'Try again when the service is reachable.' : 'Nothing needs your attention right now.'}</p><div class="kiosk-now-playing-actions"><a class="kiosk-home-action" href="${esc(href(''))}" data-view="">Return to Home</a>${unavailable ? '<button type="button" class="kiosk-retry" data-kiosk-retry>Check again</button>' : ''}</div></div></div>`;
      return;
    }
    const message = !loaded ? 'Loading your sections…' : offline ? 'This section is temporarily unavailable. Trying again…' : !valid ? 'This section is not enabled. Choose another section.' : health[view]?.state === 'error' || health[view]?.stale || health[view]?.state === 'disabled' ? 'This source is unavailable. Check its configuration in Sources / Admin.' : 'Nothing to show here right now. New items will appear automatically.';
    const html = `<header><p>EXPLORE</p><h1>${esc(label(view))}</h1></header>` + (list.length ? `<div class="kiosk-items">${list.map(c => `<button type="button" data-item="${esc(c.id)}"><small>${esc(c.status || c.source || '')}</small><strong>${esc(c.title)}</strong><span>${esc(c.subtitle || c.detail || '')}</span>${(c.rows || []).slice(0,3).map(row=>`<span>${esc(row)}</span>`).join('')}</button>`).join('')}</div>` : `<p class="kiosk-empty" role="status">${esc(message)}</p>`);
    if (panel.innerHTML !== html) panel.innerHTML = html;
  }
  function change(key) { view = key; selected = ''; history.replaceState(null, '', href(key)); closeMenu(false); drawNavigation(); drawMenu(); drawPanel(); window.dispatchEvent(new Event('marquee-navigation')); }
  more.onclick = () => { drawMenu(); menu.showModal(); more.setAttribute('aria-expanded', 'true'); };
  function closeMenu(focus = true) {
    if (menu.open) menu.close();
    more.setAttribute('aria-expanded', 'false');
    if (focus) more.focus();
  }
  menu.addEventListener('close', () => { more.setAttribute('aria-expanded', 'false'); more.focus(); });
  menu.addEventListener('cancel', () => { more.setAttribute('aria-expanded', 'false'); });
  menu.querySelector('header button').onclick = () => closeMenu();
  function handleLink(e) { const a = e.target.closest('a[data-view]'); if (a) { e.preventDefault(); change(a.dataset.view); } }
  primary.addEventListener('click', handleLink); overflow.addEventListener('click', handleLink);
  menu.addEventListener('click', e => { if (e.target === menu) { const r = menu.getBoundingClientRect(); if (e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom) closeMenu(); } });
  panel.addEventListener('click', e => { const retry = e.target.closest('button[data-kiosk-retry]'); if (retry) { retry.disabled = true; retry.textContent = 'Checking…'; refresh().finally(() => { retry.disabled = false; }); return; } const b = e.target.closest('button[data-item]'); if (b) { selected = b.dataset.item; drawPanel(); primary.querySelector(`[data-view="${CSS.escape(view)}"]`)?.focus(); window.dispatchEvent(new Event('marquee-navigation')); } });
  document.addEventListener('keydown', e => { if (e.key === 'Escape' && view === 'plex' && !menu.open) { e.preventDefault(); change(''); } });
  window.addEventListener('popstate', () => { view = new URLSearchParams(location.search).get('view') || ''; selected = ''; drawNavigation(); drawMenu(); drawPanel(); window.dispatchEvent(new Event('marquee-navigation')); });
  window.MarqueeNavigation = { resolve(payload) { nowPlaying = payload || {playing:false, state:'idle', availability:'idle'}; const wasInterrupted = interrupted; interrupted = Boolean(payload?.attention || payload?.householdFocus); if (interrupted && !wasInterrupted && menu.open) closeMenu(false); drawPanel(); if (interrupted || !view || view === 'plex') return payload; const c = !offline && sections.includes(view) && items(view).find(item => item.id === selected); return c ? c.payload || {playing:true,type:'media_context',key:'browse:'+c.id,context:c} : {playing:false}; } };
  async function refresh() {
    try { const data = await Promise.all(['/api/config','/contexts','/providers'].map(async url => { const r = await fetch(url); if (!r.ok) throw Error(); return r.json(); })); sections = Object.entries(data[0].providers || {}).filter(([,cfg]) => cfg.enabled && (!cfg.targets || cfg.targets.includes('kiosk'))).map(([key]) => key); health = data[2].providers || {}; const seen = new Set(); contexts = (data[1].contexts || []).filter(c => { if (!c.id || c.id.startsWith('screen-test:') || (c.targets && !c.targets.includes('kiosk')) || !fresh(c)) return false; const key=(c.provider||c.source)+'|'+c.title+'|'+(c.starts||''); if (seen.has(key)) return false; seen.add(key); return true; }); for (const p of health.plex?.contexts || []) if (p.playing) contexts.push({id:'plex:now',source:'plex',title:p.title,subtitle:p.subtitle,payload:p}); loaded = true; offline = false; } catch (_) { offline = true; contexts = []; }
    if (!menu.open) { drawNavigation(); drawMenu(); } drawPanel(); window.dispatchEvent(new Event('marquee-navigation'));
  }
  const resize = new ResizeObserver(() => { if (!menu.open) { drawNavigation(); drawMenu(); } }); resize.observe(rail);
  drawNavigation(); drawMenu(); drawPanel(); refresh(); setInterval(refresh, 15000);
})();
