/* Shared direct navigation for every Live/Kiosk content screen. */
(() => {
  const params = new URLSearchParams(location.search);
  if (!['/live', '/kiosk'].includes(location.pathname) || params.has('demo') || params.has('edit') || params.has('receiver')) return;
  // Product-owned, monochrome marks. Keep the paths inline so the rail is
  // deterministic across browsers and inherits the active/current color.
  const destinations = {
    plex: ['Now playing', '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 4.5v15l12-7.5z"/></svg>'],
    nhl: ['NHL', '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 6h16M4 18h16M6 6l3 6-3 6m12-12-3 6 3 6"/></svg>'],
    ufc: ['UFC', '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m5 7 4 4m10-4-4 4M9 11l-2 6m8-6 2 6M8 17h8M9 11h6"/></svg>'],
    pfl: ['PFL', '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 17 8 7l4 10 4-10 4 10M6 12h12"/></svg>'],
    weather: ['Weather', '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3v3m0 12v3M3 12h3m12 0h3M5.6 5.6l2.1 2.1m8.6 8.6 2.1 2.1m0-12.8-2.1 2.1m-8.6 8.6-2.1 2.1M16 16a5.7 5.7 0 1 1-8-8 5.7 5.7 0 0 1 8 8Z"/></svg>'],
    tv: ['TV', '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="5" width="18" height="14" rx="1.5"/><path d="m8 3 4 3 4-3M7 16h4m2 0h4"/></svg>'],
    astronomy: ['Sky', '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m12 3 1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8zM19 16l.8 2.2L22 19l-2.2.8L19 22l-.8-2.2L16 19l2.2-.8z"/></svg>'],
    movies: ['Movies', '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 6h16v12H4zM4 10h16M8 6v4m4-4v4m4-4v4"/></svg>'],
    trailers: ['Trailers', '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 5h16v14H4zM4 9h16M8 5v4m4-4v4m4-4v4M10 12l5 3-5 3z"/></svg>'],
    major_events: ['Events', '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m12 3 8 9-8 9-8-9zM12 8v8m-4-4h8"/></svg>'],
    gaming: ['Gaming', '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 8h10a4 4 0 0 1 3.8 5.2l-1 3.2a2.2 2.2 0 0 1-3.8.7L14 15H10l-2 2.1a2.2 2.2 0 0 1-3.8-.7l-1-3.2A4 4 0 0 1 7 8Z"/><path d="M7 11v4m-2-2h4m8-1h.01m2 2h.01"/></svg>'],
    music: ['Music', '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 18V5l10-2v13M9 9l10-2M9 18a3 3 0 1 1-3-3 3 3 0 0 1 3 3Zm10-2a3 3 0 1 1-3-3 3 3 0 0 1 3 3Z"/></svg>'],
    calendar: ['Calendar', '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="4" y="5" width="16" height="15" rx="1.5"/><path d="M8 3v4m8-4v4M4 10h16M8 14h.01m4 0h.01m4 0h.01m-8 3h.01m4 0h.01"/></svg>']
  };
  const homeIcon = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m3 11 9-7 9 7v9H5v-7h6v7"/></svg>';
  const moreIcon = '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="5" cy="12" r="1.4"/><circle cx="12" cy="12" r="1.4"/><circle cx="19" cy="12" r="1.4"/></svg>';
  // Weather is a first-class ambient destination. Keep urgent weather visible
  // ahead of lower-priority sports when the rail has to compact or overflow.
  const destinationPriority = { plex:100, weather:95, nhl:85, ufc:75, pfl:65,
    calendar:55, tv:50, astronomy:45, gaming:40, music:35, movies:30,
    trailers:25, major_events:20 };
  let sections = [], contexts = [], browseContexts = [], health = {}, selected = '', offline = false;
  // These are independent authoritative resources. A failed refresh retains
  // the last committed snapshot and reports degradation for that resource;
  // it never invalidates a sibling resource.
  const resources = {
    config: {phase: 'loading', snapshot: null, error: null},
    contexts: {phase: 'loading', snapshot: null, error: null},
    providers: {phase: 'loading', snapshot: null, error: null},
  };
  let requestState = 'loading', requestSerial = 0;
  const resourceHasSnapshot = () => Object.values(resources).some(resource => resource.snapshot !== null);
  const resourceFailure = resource => resource.phase === 'stale' || resource.phase === 'unavailable';
  const refreshPhase = resource => resource.snapshot === null
    ? (resource.error ? 'unavailable' : 'loading')
    : (resource.error ? 'stale' : 'ready');
  let refreshInFlight = false;
  // The server payload is the only media truth. Navigation may choose which
  // surface is visible, but it must never manufacture a replacement Plex
  // state from browse contexts or from the previous render.
  let nowPlaying = null;
  let view = params.get('view') || '', interrupted = false;
  let initialDirectFocusPending = Boolean(view);
  const label = key => destinations[key]?.[0] || key.replaceAll('_', ' ').replace(/^./, c => c.toUpperCase());
  const icon = key => destinations[key]?.[1] || moreIcon;
  const esc = text => String(text ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  // Keep normal word boundaries intact while allowing platform suffixes such
  // as PS5/Xbox/Switch/PC to wrap at their deliberate slash opportunities.
  const titleMarkup = text => esc(text).replace(/\//g, '/<wbr>');
  const fresh = c => (!c.expires || Date.parse(c.expires) > Date.now()) && c.eventState !== 'EXPIRED';
  const items = key => (key === 'nhl' ? browseContexts : contexts).filter(c => (c.provider || c.source) === key && fresh(c));
  document.body.classList.add('browser-controls');
  const rail = document.createElement('div'); rail.className = 'screen-controls kiosk-rail';
  rail.innerHTML = '<span class="kiosk-brand" role="status" aria-live="polite">Marquee</span><nav class="kiosk-primary" aria-label="Marquee destinations"></nav><button class="kiosk-more" type="button" aria-haspopup="dialog" aria-expanded="false"><span class="kiosk-icon" aria-hidden="true">' + moreIcon + '</span><span class="kiosk-label">More</span></button>';
  document.body.append(rail);
  const primary = rail.querySelector('.kiosk-primary'), more = rail.querySelector('.kiosk-more'), status = rail.querySelector('[role=status]');
  const menu = document.createElement('dialog'); menu.className = 'kiosk-menu'; menu.setAttribute('aria-labelledby', 'kiosk-menu-title');
  menu.innerHTML = '<header><h2 id="kiosk-menu-title">More destinations</h2><button type="button" aria-label="Close menu">✕</button></header><nav aria-label="Additional Marquee destinations"></nav><details><summary>Settings</summary><nav aria-label="Marquee control pages"><a href="/live">Live display</a><a href="/settings">Settings</a><a href="/settings/layout?profile=live">Edit screen layout</a><a href="/settings/attention">Alert rules</a><a href="/settings/tests">Test screens</a></nav></details>';
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
    hidden: node.hidden,
  }));
  const stage = document.querySelector('.stage');
  function setBackgroundActive(active, surface = active ? 'panel' : 'dashboard') {
    const weatherActive = active && surface === 'weather';
    backgroundState.forEach(({node, inert, ariaHidden, hidden}) => {
      const covered = active && !(weatherActive && node === stage);
      if (covered) {
        node.inert = true;
        node.setAttribute('aria-hidden', 'true');
      } else {
        node.inert = inert;
        node.hidden = hidden;
        if (ariaHidden === null) node.removeAttribute('aria-hidden');
        else node.setAttribute('aria-hidden', ariaHidden);
      }
    });
    if (stage) stage.classList.toggle('kiosk-covered', active && !weatherActive);
    const panelActive = active && !weatherActive;
    panel.hidden = !panelActive;
    panel.inert = !panelActive;
    if (panelActive) panel.removeAttribute('aria-hidden');
    else panel.setAttribute('aria-hidden', 'true');
  }
  function focusInitialDestination() {
    if (!initialDirectFocusPending || requestState === 'loading' || !view) return;
    const weatherSurface = view === 'weather' && selected && stage && !stage.classList.contains('kiosk-covered')
      && !stage.inert && stage.getAttribute('aria-hidden') !== 'true';
    const heading = weatherSurface
      ? stage.querySelector('#wx-segment-title')
      : panel.hidden || panel.inert ? null : panel.querySelector('#kiosk-section-title');
    if (!heading || !heading.getClientRects().length) return;
    heading.tabIndex = -1;
    heading.focus({preventScroll: true});
    initialDirectFocusPending = false;
  }
  function preserveDirectHeadingFocus(wasFocused) {
    if (!wasFocused) return;
    const heading = view === 'weather' && selected
      ? stage?.querySelector('#wx-segment-title')
      : panel.querySelector('#kiosk-section-title');
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
    return [['', 'Home', homeIcon], ...sections.map((key, index) => [key, label(key), icon(key), index])]
      .sort((a, b) => a[0] === '' ? -1 : b[0] === '' ? 1
        : (destinationPriority[b[0]] ?? 0) - (destinationPriority[a[0]] ?? 0) || a[3] - b[3])
      .map(([key, title, glyph]) => [key, title, glyph]);
  }
  function link([key, title, glyph], detail = '') { return `<a href="${esc(href(key))}" data-view="${esc(key)}" aria-label="${esc(title)}" title="${esc(title)}"><span class="kiosk-icon" aria-hidden="true">${glyph}</span><span class="kiosk-label">${esc(title)}</span>${detail ? `<small>${esc(detail)}</small>` : ''}</a>`; }
  function updateCurrentDestination() {
    document.querySelectorAll('.kiosk-rail a[data-view], .kiosk-menu a[data-view]').forEach(a => a.removeAttribute('aria-current'));
    const currentView = view || '';
    const direct = primary.querySelector(`[data-view="${CSS.escape(currentView)}"]`);
    const active = direct && !direct.hidden ? direct : overflow.querySelector(`[data-view="${CSS.escape(currentView)}"]`);
    if (active) active.setAttribute('aria-current', 'page');
  }
  function drawNavigation() {
    const focusedView = document.activeElement?.closest?.('a[data-view]')?.dataset.view;
    const all = allDestinations();
    const primarySignature = all.map(([key]) => `${key}:${key === view}`).join('|');
    if (primary.dataset.signature !== primarySignature) {
      primary.innerHTML = all.map(d => link(d)).join('');
      primary.dataset.signature = primarySignature;
    }
    primary.querySelectorAll('a').forEach(a => a.hidden = false); more.hidden = false;
    const brand = rail.querySelector('.kiosk-brand');
    const railGap = parseFloat(getComputedStyle(rail).columnGap) || 0;
    const primaryGap = parseFloat(getComputedStyle(primary).columnGap) || 0;
    const available = () => Math.max(0, rail.getBoundingClientRect().width - brand.getBoundingClientRect().width - more.getBoundingClientRect().width - (railGap * 2));
    const visibleWidth = () => [...primary.children].filter(a => !a.hidden).reduce((sum, a) => sum + a.offsetWidth, 0) + Math.max(0, primary.querySelectorAll(':scope > a:not([hidden])').length - 1) * primaryGap;
    // Home and the current destination must remain direct, even when the
    // current destination would otherwise be the next item sent to More.
    const required = new Set(['']);
    if (view && all.some(([key]) => key === view)) required.add(view);
    while (visibleWidth() > available()) {
      const candidate = [...primary.children].reverse().find(a => !a.hidden && !required.has(a.dataset.view));
      if (!candidate) break;
      candidate.hidden = true;
    }
    const hidden = all.filter(([key]) => primary.querySelector(`[data-view="${CSS.escape(key)}"]`)?.hidden);
    const overflowSignature = hidden.map(([key]) => `${key}:${offline ? 'offline' : items(key).length}`).join('|');
    if (overflow.dataset.signature !== overflowSignature) {
      overflow.innerHTML = hidden.map(d => link(d, offline ? 'Connection unavailable' : `${items(d[0]).length} current item${items(d[0]).length === 1 ? '' : 's'}`)).join('');
      overflow.dataset.signature = overflowSignature;
    }
    more.hidden = hidden.length === 0;
    const activeInOverflow = hidden.some(([key]) => key === view);
    more.classList.toggle('is-active', activeInOverflow);
    more.setAttribute('aria-label', activeInOverflow ? `More destinations; current destination is ${label(view)}` : 'More destinations');
    more.removeAttribute('aria-current');
    more.setAttribute('aria-expanded', 'false');
    updateCurrentDestination();
    if (focusedView !== undefined) {
      const replacement = primary.querySelector(`[data-view="${CSS.escape(focusedView)}"]`)
        || overflow.querySelector(`[data-view="${CSS.escape(focusedView)}"]`);
      if (replacement && !replacement.hidden) replacement.focus({preventScroll: true});
    }
  }
  function drawMenu() { const hiddenKeys = new Set([...overflow.querySelectorAll('[data-view]')].map(a => a.dataset.view)); overflow.innerHTML = allDestinations().filter(([key]) => hiddenKeys.has(key)).map(d => link(d, offline ? 'Connection unavailable' : `${items(d[0]).length} current item${items(d[0]).length === 1 ? '' : 's'}`)).join(''); updateCurrentDestination(); }
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
  const combatView = key => key === 'ufc' || key === 'pfl';
  const combatName = key => key === 'pfl' ? 'PFL' : 'UFC';
  function destinationLifecycle(key, list) {
    if (!sections.includes(key)) {
      return { state: resources.config.phase === 'unavailable' ? 'unavailable' : 'unavailable', reason: 'not-enabled' };
    }
    if (resources.contexts.phase === 'loading') return { state: 'loading', reason: 'context request pending' };
    if (resources.contexts.phase === 'unavailable') return { state: 'unavailable', reason: 'context source cannot be reached' };
    const provider = health[key] || {};
    if (resources.contexts.phase === 'stale') return { state: 'stale', reason: 'retained context snapshot' };
    if (provider.stale || provider.state === 'degraded') return { state: 'stale', reason: provider.reason || 'provider data is delayed' };
    if (provider.state === 'error') return { state: 'error', reason: provider.error || provider.reason || 'provider fetch failed' };
    if (provider.state === 'disabled') return { state: 'unavailable', reason: provider.reason || 'provider is disabled' };
    return { state: list.length ? 'populated' : 'empty', reason: provider.reason || '' };
  }
  function sharedState(message, action = 'Return to Home', retry = false, lifecycle = 'empty', destination = view) {
    const combat = combatView(destination);
    const promotion = combatName(destination);
    const copy = lifecycle === 'loading'
      ? combat ? `Checking the published ${promotion} schedule.` : 'Fetching the latest information for this destination.'
      : lifecycle === 'error'
      ? combat ? `The ${promotion} source did not answer. No last-known events are being presented as current.` : 'The source did not answer. No last-known results are being presented as current.'
      : lifecycle === 'stale'
        ? combat ? `The ${promotion} source has not refreshed. Last-known events are not being presented as current.` : 'The source has not refreshed. Last-known results are not being presented as current.'
        : lifecycle === 'unavailable'
          ? combat ? `The ${promotion} schedule is unavailable because its source cannot be reached.` : 'This destination is unavailable. Try again when its source is reachable.'
          : combat ? `No upcoming ${promotion} events are in the current source window.` : 'New items will appear automatically when this destination has something relevant.';
    const kicker = combat
      ? ({loading: `${promotion} · LOADING`, error: `${promotion} · SOURCE ERROR`, stale: `${promotion} · STALE SOURCE`, unavailable: `${promotion} · UNAVAILABLE`, empty: `${promotion} · SCHEDULE`}[lifecycle] || promotion)
      : (lifecycle === 'loading' ? 'LOADING' : lifecycle === 'error' ? 'SOURCE ERROR' : lifecycle === 'stale' ? 'STALE SOURCE' : lifecycle === 'unavailable' ? 'UNAVAILABLE' : 'MARQUEE');
    const mark = lifecycle === 'empty' ? '' : `<div class="kiosk-state-mark is-${esc(lifecycle)}" role="img" aria-label="${esc(kicker)}"><span aria-hidden="true">${lifecycle === 'loading' ? '…' : lifecycle === 'stale' ? '↻' : lifecycle === 'error' || lifecycle === 'unavailable' ? '!' : '·'}</span></div>`;
    return `<div class="kiosk-state${lifecycle === 'empty' ? ' is-resolved' : ''}" data-lifecycle="${esc(lifecycle)}">${mark}<div><p class="kiosk-kicker">${kicker}</p><h2>${esc(message)}</h2><p class="kiosk-empty">${copy}</p><div class="kiosk-now-playing-actions"><a class="kiosk-home-action" href="${esc(href(''))}" data-view="">${esc(action)}</a>${retry ? '<button type="button" class="kiosk-retry" data-kiosk-retry>Try again</button>' : ''}</div></div></div>`;
  }
  const nhlDate = c => { const date = dateOf(c); return date ? new Intl.DateTimeFormat(undefined, {weekday:'short', month:'short', day:'numeric', hour:'numeric', minute:'2-digit', hour12:true}).format(date) : ''; };
  const nhlSense = side => side.homeAway === 'home' ? 'Home' : side.homeAway === 'away' ? 'Away' : '';
  const nhlName = (side, fallback) => side.name || fallback;
  const nhlMatchupName = (left, right) => `${nhlName(left, 'Followed team')} vs ${nhlName(right, 'Opponent')}`;
  const normalizeSportTitle = value => String(value ?? '').normalize('NFKC').toLocaleLowerCase().replace(/[^\p{L}\p{N}]+/gu, ' ').trim().replace(/\s+/g, ' ');
  const sportDisplayTitle = feature => {
    const title = String(feature.title || '').trim();
    if (!title) return '';
    const left = feature.left || {}, right = feature.right || {};
    const leftName = nhlName(left, 'Followed team'), rightName = nhlName(right, 'Opponent');
    const normalized = normalizeSportTitle(title);
    const redundant = [
      leftName, rightName, left.abbr, right.abbr,
      `${leftName} vs ${rightName}`, `${rightName} vs ${leftName}`,
      `${leftName} v ${rightName}`, `${rightName} v ${leftName}`,
      `${leftName} at ${rightName}`, `${rightName} at ${leftName}`,
      `${leftName} ${rightName}`, `${rightName} ${leftName}`
    ].map(normalizeSportTitle);
    const generatedAlias = [leftName, rightName].some(name => {
      const side = normalizeSportTitle(name).replace(/^(?:the|les) /, '');
      return normalized.split(' ').length > 1 && side.startsWith(`${normalized} `);
    });
    return redundant.includes(normalized) || generatedAlias ? '' : title;
  };
  const nhlStatus = c => {
    const value = String(c.sourceStatus || '').trim();
    if (!value || /scheduled|upcoming/i.test(value) || /\d{1,2}\/\d{1,2}|\b\d{1,2}:\d{2}\b/.test(value)) return '';
    return value;
  };
  const nhlLogo = side => side.logo
    ? `<img class="kiosk-team-logo" src="${esc(side.logo)}" alt="${esc(nhlName(side, 'Team'))} logo" onerror="this.remove()">`
    : `<span class="kiosk-team-mark" aria-hidden="true">${esc((side.abbr || nhlName(side, 'Team')).slice(0, 3).toUpperCase())}</span>`;
  const sportPhase = feature => {
    const state = String(feature.eventState || '').toUpperCase();
    return state === 'LIVE' ? 'LIVE NOW' : ['RESULT', 'POST_EVENT'].includes(state) ? 'FINAL' : stateCopy(feature);
  };
  const sportScore = side => String(side.score || '').trim();
  const sportCenter = feature => {
    const state = String(feature.eventState || '').toUpperCase();
    const leftScore = sportScore(feature.left || {}), rightScore = sportScore(feature.right || {});
    if (state === 'LIVE') return leftScore || rightScore ? `${leftScore || '—'} <span aria-hidden="true">–</span> ${rightScore || '—'}` : (nhlStatus(feature) || 'LIVE');
    if (['RESULT', 'POST_EVENT'].includes(state)) return leftScore || rightScore ? `${leftScore || '—'} <span aria-hidden="true">–</span> ${rightScore || '—'}` : 'FINAL';
    return 'VS';
  };
  const sportSide = (side, fallback, align) => `<div class="kiosk-sport-side ${align}">${nhlLogo(side)}<strong>${esc(nhlName(side, fallback))}</strong><small>${esc(nhlSense(side))}</small></div>`;
  const sportDetails = feature => { const details = [nhlDate(feature), feature.detail || '', feature.broadcast || '', nhlStatus(feature)]; return details.filter(Boolean); };
  const renderSportStage = (feature, source, details = []) => {
    const left = feature.left || {}, right = feature.right || {};
    const state = String(feature.eventState || '').toUpperCase();
    const final = ['RESULT', 'POST_EVENT'].includes(state);
    const live = state === 'LIVE';
    const matchupName = nhlMatchupName(left, right);
    const status = live ? (nhlStatus(feature) || 'Live now') : final ? 'Final' : '';
    const rows = details.length ? `<div class="kiosk-sport-context">${details.map(detail => `<span>${esc(detail)}</span>`).join('')}</div>` : '';
    const displayTitle = sportDisplayTitle(feature);
    return `<div class="kiosk-sports-layout kiosk-broadcast-layout"><article class="kiosk-sport-feature" aria-label="${esc(matchupName)}">
      <div class="kiosk-sport-eyebrow"><span>${esc(sportPhase(feature))}</span><span>${esc(source)}</span></div>
      ${displayTitle ? `<h2>${titleMarkup(displayTitle)}</h2>` : ''}
      <div class="kiosk-broadcast-matchup">
        ${sportSide(left, 'Followed team', 'home')}<div class="kiosk-broadcast-center"><strong class="kiosk-broadcast-state${live ? ' is-live' : ''}${final ? ' is-final' : ''}">${sportCenter(feature)}</strong>${status ? `<span>${esc(status)}</span>` : ''}</div>${sportSide(right, 'Opponent', 'away')}
      </div>${rows}
    </article></div>`;
  };
  function renderNhl(list) {
    const feature = ordered(list)[0];
    if (!feature) return sharedState('No followed-team games are scheduled.', 'Return to Home', false, 'empty');
    return renderSportStage(feature, 'NHL', sportDetails(feature));
  }
  function renderSports(list) {
    // The shared sports contract retains kiosk-matchup and NEXT RELEVANT
    // semantics for callers that provide a queue, while the stage itself gives the selected event
    // the full broadcast surface. stateCopy(feature) remains the lifecycle
    // source for the eyebrow rather than a provider-specific status.
    const feature = ordered(list)[0];
    if (!feature) return sharedState(`No upcoming ${combatName(view)} events are scheduled.`, 'Return to Home', false, 'empty', view);
    const source = label(view).toUpperCase();
    return renderSportStage(feature, source, [feature.subtitle || '', feature.detail || '', ...safeRows(feature)].filter(Boolean));
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
    const queueRows = queue.map((c, index) => `<div class="kiosk-queue-row"><p class="kiosk-queue-label">${index === 0 ? 'Up next' : 'Later'}</p><strong>${titleMarkup(c.title || 'Untitled')}</strong><span>${esc(c.subtitle || c.detail || stateCopy(c) || '')}</span></div>`).join('');
    return `<div class="kiosk-editorial"><article class="kiosk-editorial-feature${art ? ' has-art' : ''}"${art ? ` style="--kiosk-art:url('${esc(art)}')"` : ''}><div><p class="kiosk-kicker">${esc(stateCopy(feature))} · ${esc(label(view))}</p><h2>${titleMarkup(feature.title || 'Untitled')}</h2><p class="kiosk-lede">${esc(feature.subtitle || featureDetail || '')}</p>${featureDetail ? `<p class="kiosk-meta">${esc(featureDetail)}</p>` : ''}</div></article><aside class="kiosk-support" aria-label="${esc(label(view))} queue"><p class="kiosk-kicker">${queue.length ? 'QUEUE' : 'UP NEXT'}</p>${queueRows || '<p class="kiosk-empty">No supporting items.</p>'}</aside></div>`;
  }
  function renderAmbient(list) {
    const feature = ordered(list)[0];
    if (!feature) return sharedState('The sky is quiet for now.', 'Return to Home', false, 'empty');
    return `<div class="kiosk-ambient-surface"><p class="kiosk-kicker">SKY · ${esc(stateCopy(feature))}</p><h2>${esc(feature.title)}</h2><p class="kiosk-lede">${esc(feature.subtitle || '')}</p><p class="kiosk-empty">${esc(feature.detail || '')}</p><div class="kiosk-ambient-rows">${safeRows(feature).map(row => `<span>${esc(row)}</span>`).join('')}</div></div>`;
  }
  function renderDestination(key, list) { const category = categoryFor(key); return key === 'nhl' ? renderNhl(list) : category === 'sports' ? renderSports(list) : category === 'agenda' ? renderAgenda(list) : category === 'media' ? renderMedia(list) : category === 'ambient' ? renderAmbient(list) : list.length ? `<div class="kiosk-items">${list.slice(0, 8).map(button).join('')}</div>` : sharedState('Nothing to show here right now.', 'Return to Home', false, 'empty'); }
  function drawPanel() {
    const preserveHeadingFocus = Boolean(view && document.activeElement?.id === 'kiosk-section-title');
    panel.dataset.section = view;
    const failedResources = Object.values(resources).filter(resourceFailure).length;
    const resourceNotice = offline ? ' · Sources unavailable' : failedResources ? ` · ${failedResources} source${failedResources === 1 ? '' : 's'} delayed` : '';
    status.textContent = interrupted ? 'Household attention' : view === 'household' ? 'Household' : (view ? label(view) : 'Marquee · Auto') + resourceNotice;
    const valid = sections.includes(view), list = valid ? items(view) : [];
    if (selected && !list.some(c => c.id === selected)) selected = '';
    if (view === 'weather' && !selected && list.length) selected = (list.find(c => ['alert','extreme'].includes(c.subtype)) || list.find(c => c.subtype === 'current') || list[0]).id;
    const plexActive = view === 'plex' && nowPlaying?.playing === true;
    panel.classList.toggle('now-playing-surface', view === 'plex');
    const active = Boolean(view) && !interrupted && view !== 'household';
    const surface = active && view === 'weather' && selected ? 'weather' : active ? 'panel' : 'dashboard';
    setBackgroundActive(active, surface);
    panel.hidden = !active || plexActive || Boolean(selected); panel.inert = !active || panel.hidden;
    if (panel.hidden) {
      if (panel.contains(document.activeElement)) {
        focusNavigation(view);
        if (panel.contains(document.activeElement)) document.activeElement.blur();
      }
      return;
    }
    if (view === 'plex') {
      const unavailable = nowPlaying?.state === 'unavailable' || nowPlaying?.availability === 'unavailable';
      const loading = !nowPlaying;
      const title = loading ? 'Checking the media room' : unavailable ? 'Media service unavailable' : 'Nothing is playing';
      const detail = loading ? 'Reading the current playback state.' : unavailable
        ? 'No previous title or artwork is retained here.' : '';
      const weather = ['idle-weather-temp', 'idle-weather-condition', 'idle-weather-range']
        .map(id => document.querySelector(`#${id}`)?.textContent?.trim() || '')
        .filter(Boolean);
      const weatherLabels = ['Temperature', 'Conditions', 'High and low'];
      const weatherMarkup = weather.length
        ? `<div class="kiosk-weather-context" aria-label="Current weather">${weather.map((fact, index) => `${index ? '<span class="kiosk-weather-separator" aria-hidden="true">·</span>' : ''}<span class="kiosk-weather-fact" aria-label="${esc(`${weatherLabels[index]}: ${fact}`)}">${esc(fact)}</span>`).join('')}</div>`
        : '<div class="kiosk-weather-context" aria-label="Current weather">Home display ready</div>';
      const unavailableMark = unavailable ? '<div class="kiosk-state-mark is-unavailable" aria-hidden="true"><span>↻</span></div>' : '';
      const retry = unavailable ? '<button type="button" class="kiosk-retry" data-kiosk-retry>Check again</button>' : '';
      panel.innerHTML = `<header class="kiosk-now-playing-head"><p>NOW PLAYING</p><h1 id="kiosk-section-title">${esc(title)}</h1>${detail ? `<p class="kiosk-now-playing-detail">${esc(detail)}</p>` : ''}</header><div class="kiosk-now-playing-body">${unavailableMark}<div class="kiosk-now-playing-copy">${weatherMarkup}<div class="kiosk-now-playing-actions"><a class="kiosk-home-action" href="${esc(href(''))}" data-view="">Return to Home</a>${retry}</div></div></div>`;
      focusInitialDestination();
      preserveDirectHeadingFocus(preserveHeadingFocus);
      return;
    }
    const lifecycle = requestState === 'loading'
      ? { state: 'loading', reason: 'provider request pending' }
      : destinationLifecycle(view, list);
    const message = lifecycle.state === 'loading' ? `Loading ${label(view)}…` : lifecycle.state === 'error' ? `${label(view)} is unavailable` : lifecycle.state === 'stale' ? `${label(view)} is stale` : lifecycle.state === 'unavailable' ? `${label(view)} is unavailable` : '';
    const feature = view === 'nhl' && list.length ? ordered(list)[0] : null;
    const headingName = feature ? nhlMatchupName(feature.left || {}, feature.right || {}) : label(view);
    const html = `<header class="kiosk-section-head"><p>${esc(categoryFor(view).toUpperCase())}</p><h1 id="kiosk-section-title"${feature ? ` aria-label="${esc(headingName)}"` : ''}>${esc(label(view))}</h1></header>` + (message ? sharedState(message, 'Return to Home', lifecycle.state === 'error' || lifecycle.state === 'stale' || lifecycle.state === 'unavailable', lifecycle.state, view) : renderDestination(view, list));
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
  function change(key, restoreFocus = true) { view = key; selected = ''; history.pushState({marqueeDestination: Boolean(key)}, '', href(key)); closeMenu(false); drawNavigation(); drawMenu(); drawPanel(); if (restoreFocus) { focusNavigation(key); setTimeout(() => focusNavigation(key), 0); } window.dispatchEvent(new Event('marquee-navigation')); }
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
  window.addEventListener('marquee-surface-rendered', drawPanel);
  window.MarqueeNavigation = { resolve(payload) { nowPlaying = payload || {playing:false, state:'idle', availability:'idle'}; const wasInterrupted = interrupted; interrupted = Boolean(payload?.attention || payload?.householdFocus); if (interrupted && !wasInterrupted && menu.open) closeMenu(false); drawPanel(); if (interrupted || !view || view === 'plex') return payload; const c = !offline && sections.includes(view) && items(view).find(item => item.id === selected); return c ? c.payload || {playing:true,type:'media_context',key:'browse:'+c.id,context:c} : {playing:false}; }, refresh };
  async function refresh() {
    if (refreshInFlight) return;
    refreshInFlight = true;
    const serial = ++requestSerial;
    const clean = values => { const seen = new Set(); return (values || []).filter(c => { if (!c.id || c.id.startsWith('screen-test:') || (c.targets && !c.targets.includes('kiosk')) || !fresh(c)) return false; const key=(c.provider||c.source)+'|'+c.title+'|'+(c.starts||''); if (seen.has(key)) return false; seen.add(key); return true; }); };
    const requests = {
      config: fetch('/api/config'),
      contexts: fetch('/contexts'),
      providers: fetch('/providers'),
    };
    try {
      const settled = await Promise.allSettled(Object.entries(requests).map(async ([name, request]) => {
        try {
          const response = await request;
          if (!response.ok) throw Error(`${name} request failed (${response.status})`);
          return [name, await response.json()];
        } catch (error) {
          throw {name, error};
        }
      }));
      if (serial !== requestSerial) return;
      for (const result of settled) {
        if (result.status === 'fulfilled') {
          const [name, value] = result.value;
          resources[name].snapshot = value;
          resources[name].error = null;
        } else {
          resources[result.reason.name].error = result.reason.error;
        }
        const name = result.status === 'fulfilled' ? result.value[0] : result.reason.name;
        const resource = resources[name];
        resource.phase = refreshPhase(resource);
      }
      if (resources.config.snapshot) {
        const config = resources.config.snapshot;
        sections = Object.entries(config.providers || {}).filter(([, cfg]) => cfg.enabled && (!cfg.targets || cfg.targets.includes('kiosk'))).map(([key]) => key);
      }
      if (resources.providers.snapshot) health = resources.providers.snapshot.providers || {};
      if (resources.contexts.snapshot) {
        const snapshot = resources.contexts.snapshot;
        contexts = clean(snapshot.contexts);
        browseContexts = clean(snapshot.browse?.nhl);
      }
      // Plex remains exclusively authoritative through now-playing.json. The
      // provider diagnostics payload must not manufacture a second Plex item.
      offline = !resourceHasSnapshot();
      requestState = resourceHasSnapshot() ? 'ready' : 'failed';
      if (!menu.open) { drawNavigation(); drawMenu(); } drawPanel(); window.dispatchEvent(new Event('marquee-navigation'));
    } finally {
      refreshInFlight = false;
    }
  }
  const resize = new ResizeObserver(() => { if (!menu.open) { drawNavigation(); drawMenu(); } }); resize.observe(rail);
  drawNavigation(); drawMenu(); drawPanel(); refresh(); setInterval(refresh, 15000);
})();
