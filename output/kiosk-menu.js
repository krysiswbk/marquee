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
  // A destination is loading until its first provider snapshot commits. Keep
  // this separate from provider failure: an empty list during a request is not
  // evidence that the destination is unavailable.
  let requestState = 'loading', requestSerial = 0;
  // The server payload is the only media truth. Navigation may choose which
  // surface is visible, but it must never manufacture a replacement Plex
  // state from browse contexts or from the previous render.
  let nowPlaying = null;
  let view = params.get('view') || '', interrupted = false;
  let initialDirectFocusPending = Boolean(view);
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
  const panel = document.createElement('section'); panel.className = 'kiosk-section'; panel.hidden = true; panel.inert = true; panel.setAttribute('aria-hidden', 'true'); panel.setAttribute('aria-label', 'Selected kiosk section'); panel.setAttribute('aria-labelledby', 'kiosk-section-title'); document.body.append(panel);
  // The destination is a sibling overlay, so explicitly own the accessibility
  // state of the dashboard it covers. Keep the original values so Home and
  // browser history can restore the dashboard without stale inert/hidden state.
  const backgroundNodes = [...document.body.children].filter(node => ![rail, menu, panel].includes(node));
  const backgroundState = backgroundNodes.map(node => ({
    node,
    inert: node.inert,
    ariaHidden: node.getAttribute('aria-hidden'),
  }));
  function setBackgroundActive(active) {
    backgroundState.forEach(({node, inert, ariaHidden}) => {
      if (active) {
        node.inert = true;
        node.setAttribute('aria-hidden', 'true');
      } else {
        node.inert = inert;
        if (ariaHidden === null) node.removeAttribute('aria-hidden');
        else node.setAttribute('aria-hidden', ariaHidden);
      }
    });
    panel.hidden = !active;
    panel.inert = !active;
    if (active) panel.removeAttribute('aria-hidden');
    else panel.setAttribute('aria-hidden', 'true');
  }
  function focusInitialDestination() {
    if (!initialDirectFocusPending || requestState === 'loading' || !view || panel.hidden || panel.inert) return;
    const heading = panel.querySelector('#kiosk-section-title');
    if (!heading || !heading.getClientRects().length) return;
    heading.tabIndex = -1;
    heading.focus({preventScroll: true});
    initialDirectFocusPending = false;
  }
  function preserveDirectHeadingFocus(wasFocused) {
    if (!wasFocused) return;
    const heading = panel.querySelector('#kiosk-section-title');
    if (heading) {
      heading.tabIndex = -1;
      heading.focus({preventScroll: true});
    }
  }
  function href(key) { const u = new URL(location.href); key ? u.searchParams.set('view', key) : u.searchParams.delete('view'); return u.pathname + u.search; }
  if (view) {
    const initialDestination = href(view);
    history.replaceState({marqueeHome: true}, '', href(''));
    history.pushState({marqueeDestination: true}, '', initialDestination);
  }
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
    const hidden = all.slice(cutoff); overflow.innerHTML = hidden.map(d => link(d, offline ? 'Connection unavailable' : `${items(d[0]).length} current item${items(d[0]).length === 1 ? '' : 's'}`)).join(''); more.hidden = hidden.length === 0;
    const activeInOverflow = hidden.some(([key]) => key === view);
    more.classList.toggle('is-active', activeInOverflow);
    more.setAttribute('aria-label', activeInOverflow ? `More destinations; current destination is ${label(view)}` : 'More destinations');
    more.setAttribute('aria-current', activeInOverflow ? 'page' : 'false');
    more.setAttribute('aria-expanded', 'false');
  }
  function drawMenu() { const hiddenKeys = new Set([...overflow.querySelectorAll('[data-view]')].map(a => a.dataset.view)); overflow.innerHTML = allDestinations().filter(([key]) => hiddenKeys.has(key)).map(d => link(d, offline ? 'Connection unavailable' : `${items(d[0]).length} current item${items(d[0]).length === 1 ? '' : 's'}`)).join(''); }
  const sportViews = new Set(['nhl', 'ufc', 'pfl']);
  const mediaViews = new Set(['tv', 'movies', 'trailers', 'gaming', 'music', 'major_events']);
  const categoryFor = key => sportViews.has(key) ? 'sports' : key === 'calendar' ? 'agenda' : key === 'astronomy' ? 'ambient' : mediaViews.has(key) ? 'media' : 'generic';
  const dateOf = c => { const value = c.starts || c.start_time || c.start || ''; const date = value ? new Date(value) : null; return date && !Number.isNaN(date.valueOf()) ? date : null; };
  const stateCopy = c => c.status || ({LIVE:'Live now', STARTING_SOON:'Starting soon', UPCOMING:'Coming up', RESULT:'Result', POST_EVENT:'Recently finished'}[c.eventState] || '');
  const sourceLabel = c => {
    const value = String((c.rows || [])[0] || c.source || c.provider || '').trim();
    if (!value || /@/.test(value) || /(?:entity|calendar\.)[\w.-]+/i.test(value)) return 'Household calendar';
    return value.replace(/^(?:mdi:|provider:)/i, '').replace(/[_-]+/g, ' ').replace(/\b\w/g, ch => ch.toUpperCase());
  };
  const safeRows = (c, limit = 3) => (c.rows || []).filter(row => row && !/@/.test(String(row))).slice(0, limit);
  const ordered = list => [...list].sort((a, b) => (dateOf(a)?.valueOf() || Infinity) - (dateOf(b)?.valueOf() || Infinity));
  const button = c => `<button type="button" data-item="${esc(c.id)}"><small>${esc(stateCopy(c))}</small><strong>${esc(c.title || 'Untitled')}</strong><span>${esc(c.subtitle || c.detail || '')}</span></button>`;
  function destinationLifecycle(key, list) {
    if (offline) return { state: 'unavailable', reason: 'connection' };
    if (!sections.includes(key)) return { state: 'unavailable', reason: 'not-enabled' };
    const provider = health[key] || {};
    if (provider.stale) return { state: 'stale', reason: provider.reason || 'provider data is stale' };
    if (provider.state === 'error') return { state: 'error', reason: provider.error || provider.reason || 'provider fetch failed' };
    if (provider.state === 'disabled') return { state: 'unavailable', reason: provider.reason || 'provider is disabled' };
    return { state: list.length ? 'populated' : 'empty', reason: provider.reason || '' };
  }
  function sharedState(message, action = 'Return to Home', retry = false, lifecycle = 'empty') {
    const copy = lifecycle === 'loading'
      ? 'Fetching the latest information for this destination.'
      : lifecycle === 'error'
      ? 'The source did not answer. No last-known results are being presented as current.'
      : lifecycle === 'stale'
        ? 'The source has not refreshed. Last-known results are not being presented as current.'
        : lifecycle === 'unavailable'
          ? 'This destination is unavailable. Try again when its source is reachable.'
          : 'New items will appear automatically when this destination has something relevant.';
    const kicker = lifecycle === 'loading' ? 'LOADING' : lifecycle === 'error' ? 'SOURCE ERROR' : lifecycle === 'stale' ? 'STALE SOURCE' : lifecycle === 'unavailable' ? 'UNAVAILABLE' : 'MARQUEE';
    return `<div class="kiosk-state" data-lifecycle="${esc(lifecycle)}"><div class="kiosk-state-mark" aria-hidden="true">·</div><div><p class="kiosk-kicker">${kicker}</p><h2>${esc(message)}</h2><p class="kiosk-empty">${copy}</p><div class="kiosk-now-playing-actions"><a class="kiosk-home-action" href="${esc(href(''))}" data-view="">${esc(action)}</a>${retry ? '<button type="button" class="kiosk-retry" data-kiosk-retry>Try again</button>' : ''}</div></div></div>`;
  }
  function renderSports(list) {
    const [feature, ...queue] = ordered(list);
    if (!feature) return sharedState('No games or fights are on the board.', 'Return to Home', false, 'empty');
    const left = feature.left || {}, right = feature.right || {};
    const matchup = left.name && right.name ? `<div class="kiosk-matchup"><div><strong>${esc(left.name)}</strong><b>${esc(left.score || '')}</b></div><span>vs</span><div><strong>${esc(right.name)}</strong><b>${esc(right.score || '')}</b></div></div>` : '';
    return `<div class="kiosk-sports-layout"><article class="kiosk-sport-feature"><p class="kiosk-kicker">${esc(stateCopy(feature))} · ${esc(label(view))}</p><h2>${esc(feature.title)}</h2><p class="kiosk-lede">${esc(feature.subtitle || feature.detail || '')}</p>${matchup}<p class="kiosk-meta">${esc(feature.detail || '')}</p><div class="kiosk-sport-rows">${safeRows(feature).map(row => `<span>${esc(row)}</span>`).join('')}</div></article><aside class="kiosk-support"><p class="kiosk-kicker">NEXT RELEVANT</p>${queue.slice(0, 3).map(c => `<div class="kiosk-queue-row"><strong>${esc(c.title)}</strong><span>${esc(c.subtitle || stateCopy(c))}</span></div>`).join('') || '<p class="kiosk-empty">No other current event.</p>'}</aside></div>`;
  }
  function agendaGroup(date) {
    if (!date) return 'Later';
    const now = new Date(); const start = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const days = Math.round((new Date(date.getFullYear(), date.getMonth(), date.getDate()) - start) / 86400000);
    return days === 0 ? 'Today' : days === 1 ? 'Tomorrow' : days < 7 ? 'This week' : 'Later';
  }
  const shortWide = () => window.matchMedia?.('(min-width: 1000px) and (max-height: 700px) and (min-aspect-ratio: 3/2)').matches;
  const agendaLimit = () => window.matchMedia?.('(max-width: 480px)').matches || shortWide() ? 2 : 3;
  function renderAgenda(list) {
    const values = ordered(list), feature = values[0];
    if (!feature) return sharedState('Your agenda is clear.', 'Return to Home', false, 'empty');
    const upcoming = values.slice(1, 1 + agendaLimit()), remaining = Math.max(0, values.length - 1 - upcoming.length);
    const grouped = upcoming.reduce((map, c) => { const key = agendaGroup(dateOf(c)); (map[key] ||= []).push(c); return map; }, {});
    const remainder = remaining ? `<p class="kiosk-agenda-more">${remaining} more event${remaining === 1 ? '' : 's'} remain beyond this summary.</p>` : '';
    return `<div class="kiosk-agenda"><article class="kiosk-agenda-feature"><p class="kiosk-kicker">UP NEXT</p><h2>${esc(feature.title)}</h2><p class="kiosk-lede">${esc(feature.subtitle || feature.detail || '')}</p><p class="kiosk-meta">${esc(feature.location || feature.detail || sourceLabel(feature))}</p></article><div class="kiosk-agenda-groups">${Object.entries(grouped).map(([group, entries]) => `<section><h3>${esc(group)}</h3>${entries.map(c => `<div class="kiosk-agenda-row ${c.subtype === 'birthday_rollup' ? 'is-birthday' : ''}"><time>${esc(c.subtitle || 'All day')}</time><strong>${esc(c.title)}</strong><small>${esc(c.subtype === 'birthday_rollup' ? 'Birthday' : sourceLabel(c))}</small></div>`).join('')}</section>`).join('') || '<p class="kiosk-empty">No later events in view.</p>'}${remainder}</div></div>`;
  }
  function renderMedia(list) {
    const [feature, ...queue] = ordered(list);
    if (!feature) return sharedState(`${label(view)} is quiet right now.`, 'Return to Home', false, 'empty');
    const art = feature.artwork || feature.background || '';
    const featureDetail = feature.detail || safeRows(feature, 1)[0] || '';
    const queueRows = queue.map((c, index) => `<div class="kiosk-queue-row"><p class="kiosk-queue-label">${index === 0 ? 'Up next' : 'Later'}</p><strong>${esc(c.title || 'Untitled')}</strong><span>${esc(c.subtitle || c.detail || stateCopy(c) || '')}</span></div>`).join('');
    return `<div class="kiosk-editorial"><article class="kiosk-editorial-feature${art ? ' has-art' : ''}"${art ? ` style="--kiosk-art:url('${esc(art)}')"` : ''}><div><p class="kiosk-kicker">${esc(stateCopy(feature))} · ${esc(label(view))}</p><h2>${esc(feature.title || 'Untitled')}</h2><p class="kiosk-lede">${esc(feature.subtitle || featureDetail || '')}</p>${featureDetail ? `<p class="kiosk-meta">${esc(featureDetail)}</p>` : ''}</div></article><aside class="kiosk-support" aria-label="${esc(label(view))} queue"><p class="kiosk-kicker">${queue.length ? 'QUEUE' : 'UP NEXT'}</p>${queueRows || '<p class="kiosk-empty">No supporting items.</p>'}</aside></div>`;
  }
  function renderAmbient(list) {
    const feature = ordered(list)[0];
    if (!feature) return sharedState('The sky is quiet for now.', 'Return to Home', false, 'empty');
    return `<div class="kiosk-ambient-surface"><p class="kiosk-kicker">SKY · ${esc(stateCopy(feature))}</p><h2>${esc(feature.title)}</h2><p class="kiosk-lede">${esc(feature.subtitle || '')}</p><p class="kiosk-empty">${esc(feature.detail || '')}</p><div class="kiosk-ambient-rows">${safeRows(feature).map(row => `<span>${esc(row)}</span>`).join('')}</div></div>`;
  }
  function renderDestination(key, list) { const category = categoryFor(key); return category === 'sports' ? renderSports(list) : category === 'agenda' ? renderAgenda(list) : category === 'media' ? renderMedia(list) : category === 'ambient' ? renderAmbient(list) : list.length ? `<div class="kiosk-items">${list.slice(0, 8).map(button).join('')}</div>` : sharedState('Nothing to show here right now.', 'Return to Home', false, 'empty'); }
  function drawPanel() {
    const preserveHeadingFocus = Boolean(view && document.activeElement?.id === 'kiosk-section-title');
    panel.dataset.section = view; status.textContent = interrupted ? 'Household attention' : view === 'household' ? 'Household' : view ? label(view) : 'Marquee · Auto';
    const valid = sections.includes(view), list = valid && !offline ? items(view) : [];
    if (selected && !list.some(c => c.id === selected)) selected = '';
    if (view === 'weather' && !selected && list.length) selected = (list.find(c => ['alert','extreme'].includes(c.subtype)) || list.find(c => c.subtype === 'current') || list[0]).id;
    const plexActive = view === 'plex' && nowPlaying?.playing === true;
    panel.classList.toggle('now-playing-surface', view === 'plex');
    const active = Boolean(view) && !interrupted && view !== 'household';
    setBackgroundActive(active);
    panel.hidden = !active || plexActive || Boolean(selected); panel.inert = !active || panel.hidden;
    if (panel.hidden) {
      if (panel.contains(document.activeElement)) focusNavigation(view);
      return;
    }
    if (view === 'plex') {
      const unavailable = nowPlaying?.state === 'unavailable' || nowPlaying?.availability === 'unavailable';
      const loading = !nowPlaying;
      const title = loading ? 'Checking the media room' : unavailable ? 'Media service unavailable' : 'Nothing is playing';
      const detail = loading ? 'Reading the current playback state.' : unavailable
        ? 'Marquee is ready when the media service reconnects. No previous title or artwork is retained here.'
        : 'The room is quiet. Choose Home to return to the household view.';
      const ambient = document.querySelector('#idle-weather')?.textContent?.trim() || 'Home display ready';
      panel.innerHTML = `<header class="kiosk-now-playing-head"><p>NOW PLAYING</p><h1 id="kiosk-section-title">${esc(title)}</h1><p class="kiosk-now-playing-detail">${esc(detail)}</p></header><div class="kiosk-now-playing-body"><div class="kiosk-state-mark ${unavailable ? 'is-unavailable' : ''}" aria-hidden="true"><span>${unavailable ? '↻' : '·'}</span></div><div class="kiosk-now-playing-copy"><p class="kiosk-ambient">${esc(ambient)}</p><p class="kiosk-now-playing-note">${unavailable ? 'Try again when the service is reachable.' : 'Nothing needs your attention right now.'}</p><div class="kiosk-now-playing-actions"><a class="kiosk-home-action" href="${esc(href(''))}" data-view="">Return to Home</a>${unavailable ? '<button type="button" class="kiosk-retry" data-kiosk-retry>Check again</button>' : ''}</div></div></div>`;
      focusInitialDestination();
      preserveDirectHeadingFocus(preserveHeadingFocus);
      return;
    }
    const lifecycle = requestState === 'loading'
      ? { state: 'loading', reason: 'provider request pending' }
      : destinationLifecycle(view, list);
    const message = lifecycle.state === 'loading' ? `Loading ${label(view)}…` : lifecycle.state === 'error' ? `${label(view)} is unavailable` : lifecycle.state === 'stale' ? `${label(view)} is stale` : lifecycle.state === 'unavailable' ? `${label(view)} is unavailable` : '';
    const html = `<header class="kiosk-section-head"><p>${esc(categoryFor(view).toUpperCase())}</p><h1 id="kiosk-section-title">${esc(label(view))}</h1></header>` + (message ? sharedState(message, 'Return to Home', lifecycle.state === 'error' || lifecycle.state === 'stale' || lifecycle.state === 'unavailable', lifecycle.state) : renderDestination(view, list));
    if (panel.innerHTML !== html) panel.innerHTML = html;
    focusInitialDestination();
    preserveDirectHeadingFocus(preserveHeadingFocus);
  }
  function focusNavigation(key) {
    const target = primary.querySelector(`[data-view="${CSS.escape(key)}"]`);
    if (target && !target.hidden) target.focus();
    else if (key) more.focus();
    else primary.querySelector('[data-view=""]')?.focus();
  }
  function change(key, restoreFocus = true) { view = key; selected = ''; history.pushState({marqueeDestination: Boolean(key)}, '', href(key)); closeMenu(false); drawNavigation(); drawMenu(); drawPanel(); if (restoreFocus) focusNavigation(key); window.dispatchEvent(new Event('marquee-navigation')); }
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
  panel.addEventListener('click', e => { const a = e.target.closest('a[data-view]'); if (a) { e.preventDefault(); change(a.dataset.view); return; } const retry = e.target.closest('button[data-kiosk-retry]'); if (retry) { retry.disabled = true; retry.textContent = 'Checking…'; refresh().finally(() => { retry.disabled = false; }); return; } const b = e.target.closest('button[data-item]'); if (b) { selected = b.dataset.item; drawPanel(); primary.querySelector(`[data-view="${CSS.escape(view)}"]`)?.focus(); window.dispatchEvent(new Event('marquee-navigation')); } });
  document.addEventListener('keydown', e => { if (e.key === 'Escape' && view && !menu.open) { e.preventDefault(); change(''); } });
  window.addEventListener('popstate', () => { view = new URLSearchParams(location.search).get('view') || ''; selected = ''; drawNavigation(); drawMenu(); drawPanel(); focusNavigation(view); setTimeout(() => focusNavigation(view), 0); window.dispatchEvent(new Event('marquee-navigation')); });
  window.MarqueeNavigation = { resolve(payload) { nowPlaying = payload || {playing:false, state:'idle', availability:'idle'}; const wasInterrupted = interrupted; interrupted = Boolean(payload?.attention || payload?.householdFocus); if (interrupted && !wasInterrupted && menu.open) closeMenu(false); drawPanel(); if (interrupted || !view || view === 'plex') return payload; const c = !offline && sections.includes(view) && items(view).find(item => item.id === selected); return c ? c.payload || {playing:true,type:'media_context',key:'browse:'+c.id,context:c} : {playing:false}; } };
  async function refresh() {
    if (requestState === 'loading' && requestSerial > 0) return;
    const serial = ++requestSerial;
    requestState = 'loading';
    drawPanel();
    try { const data = await Promise.all(['/api/config','/contexts','/providers'].map(async url => { const r = await fetch(url); if (!r.ok) throw Error(); return r.json(); })); if (serial !== requestSerial) return; sections = Object.entries(data[0].providers || {}).filter(([,cfg]) => cfg.enabled && (!cfg.targets || cfg.targets.includes('kiosk'))).map(([key]) => key); health = data[2].providers || {}; const seen = new Set(); contexts = (data[1].contexts || []).filter(c => { if (!c.id || c.id.startsWith('screen-test:') || (c.targets && !c.targets.includes('kiosk')) || !fresh(c)) return false; const key=(c.provider||c.source)+'|'+c.title+'|'+(c.starts||''); if (seen.has(key)) return false; seen.add(key); return true; }); for (const p of health.plex?.contexts || []) if (p.playing) contexts.push({id:'plex:now',source:'plex',title:p.title,subtitle:p.subtitle,payload:p}); loaded = true; requestState = 'ready'; offline = false; } catch (_) { if (serial !== requestSerial) return; requestState = 'failed'; offline = true; contexts = []; }
    if (!menu.open) { drawNavigation(); drawMenu(); } drawPanel(); window.dispatchEvent(new Event('marquee-navigation'));
  }
  const resize = new ResizeObserver(() => { if (!menu.open) { drawNavigation(); drawMenu(); } }); resize.observe(rail);
  drawNavigation(); drawMenu(); drawPanel(); refresh(); setInterval(refresh, 15000);
})();
