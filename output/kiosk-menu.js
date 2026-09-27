/* Shared direct navigation for every Live/Kiosk content screen. */
(() => {
  const params = new URLSearchParams(location.search);
  if (!['/live', '/kiosk'].includes(location.pathname) || params.has('demo') || params.has('edit') || params.has('receiver')) return;
  const destinations = { plex:['Now playing','▶'], nhl:['NHL','⚑'], ufc:['UFC','⚑'], pfl:['PFL','⚑'], weather:['Weather','☼'], tv:['TV','▣'], astronomy:['Sky','✦'], movies:['Movies','▶'], trailers:['Trailers','▶'], major_events:['Events','◆'], gaming:['Gaming','⌘'], music:['Music','♫'], calendar:['Calendar','□'] };
  let sections = [], contexts = [], health = {}, selected = '', loaded = false, offline = false;
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
  function allDestinations() { return [['', 'Home', '⌂'], ...sections.map(key => [key, label(key), icon(key)])]; }
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
    panel.hidden = interrupted || !view || view === 'household' || Boolean(selected); if (panel.hidden) return;
    const message = !loaded ? 'Loading your sections…' : offline ? 'This section is temporarily unavailable. Trying again…' : !valid ? 'This section is not enabled. Choose another section.' : health[view]?.state === 'error' || health[view]?.stale || health[view]?.state === 'disabled' ? 'This source is unavailable. Check its configuration in Sources / Admin.' : 'Nothing to show here right now. New items will appear automatically.';
    const html = `<header><p>EXPLORE</p><h1>${esc(label(view))}</h1></header>` + (list.length ? `<div class="kiosk-items">${list.map(c => `<button type="button" data-item="${esc(c.id)}"><small>${esc(c.status || c.source || '')}</small><strong>${esc(c.title)}</strong><span>${esc(c.subtitle || c.detail || '')}</span>${(c.rows || []).slice(0,3).map(row=>`<span>${esc(row)}</span>`).join('')}</button>`).join('')}</div>` : `<p class="kiosk-empty" role="status">${esc(message)}</p>`);
    if (panel.innerHTML !== html) panel.innerHTML = html;
  }
  function change(key) { view = key; selected = ''; history.replaceState(null, '', href(key)); if (menu.open) menu.close(); more.setAttribute('aria-expanded', 'false'); drawNavigation(); drawMenu(); drawPanel(); window.dispatchEvent(new Event('marquee-navigation')); }
  more.onclick = () => { drawMenu(); menu.showModal(); more.setAttribute('aria-expanded', 'true'); };
  menu.querySelector('header button').onclick = () => { menu.close(); more.setAttribute('aria-expanded', 'false'); };
  function handleLink(e) { const a = e.target.closest('a[data-view]'); if (a) { e.preventDefault(); change(a.dataset.view); } }
  primary.addEventListener('click', handleLink); overflow.addEventListener('click', handleLink);
  menu.addEventListener('click', e => { if (e.target === menu) { const r = menu.getBoundingClientRect(); if (e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom) { menu.close(); more.setAttribute('aria-expanded', 'false'); } } });
  panel.addEventListener('click', e => { const b = e.target.closest('button[data-item]'); if (b) { selected = b.dataset.item; drawPanel(); primary.querySelector(`[data-view="${CSS.escape(view)}"]`)?.focus(); window.dispatchEvent(new Event('marquee-navigation')); } });
  window.addEventListener('popstate', () => { view = new URLSearchParams(location.search).get('view') || ''; selected = ''; drawNavigation(); drawMenu(); drawPanel(); window.dispatchEvent(new Event('marquee-navigation')); });
  window.MarqueeNavigation = { resolve(payload) { const wasInterrupted = interrupted; interrupted = Boolean(payload.attention || payload.householdFocus); if (interrupted && !wasInterrupted && menu.open) { menu.close(); more.setAttribute('aria-expanded', 'false'); } drawPanel(); if (interrupted || !view) return payload; const c = !offline && sections.includes(view) && items(view).find(item => item.id === selected); return c ? c.payload || {playing:true,type:'media_context',key:'browse:'+c.id,context:c} : {playing:false}; } };
  async function refresh() {
    try { const data = await Promise.all(['/api/config','/contexts','/providers'].map(async url => { const r = await fetch(url); if (!r.ok) throw Error(); return r.json(); })); sections = Object.entries(data[0].providers || {}).filter(([,cfg]) => cfg.enabled && (!cfg.targets || cfg.targets.includes('kiosk'))).map(([key]) => key); health = data[2].providers || {}; const seen = new Set(); contexts = (data[1].contexts || []).filter(c => { if (!c.id || c.id.startsWith('screen-test:') || (c.targets && !c.targets.includes('kiosk')) || !fresh(c)) return false; const key=(c.provider||c.source)+'|'+c.title+'|'+(c.starts||''); if (seen.has(key)) return false; seen.add(key); return true; }); for (const p of health.plex?.contexts || []) if (p.playing) contexts.push({id:'plex:now',source:'plex',title:p.title,subtitle:p.subtitle,payload:p}); loaded = true; offline = false; } catch (_) { offline = true; contexts = []; }
    if (!menu.open) { drawNavigation(); drawMenu(); } drawPanel(); window.dispatchEvent(new Event('marquee-navigation'));
  }
  const resize = new ResizeObserver(() => { if (!menu.open) { drawNavigation(); drawMenu(); } }); resize.observe(rail);
  drawNavigation(); drawMenu(); drawPanel(); refresh(); setInterval(refresh, 15000);
})();
