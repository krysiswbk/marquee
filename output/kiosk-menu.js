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
  // Mount the known product topology before remote configuration resolves.
  // Provider configuration may later remove destinations, but a cold direct
  // load must never collapse the rail to Home while that decision is pending.
  let sections = Object.keys(destinations), contexts = [], browseContexts = [], health = {}, selected = '', offline = false;
  // These are independent authoritative resources. A failed refresh retains
  // the last committed snapshot and reports degradation for that resource;
  // it never invalidates a sibling resource.
  const resources = {
    config: {phase: 'loading', snapshot: null, error: null},
    contexts: {phase: 'loading', snapshot: null, error: null},
    providers: {phase: 'loading', snapshot: null, error: null},
    sky: {phase: 'loading', snapshot: null, error: null},
  };
  let requestState = 'loading', requestSerial = 0;
  const resourceHasSnapshot = () => Object.values(resources).some(resource => resource.snapshot !== null);
  const sharedResourceState = resource => window.MarqueeState?.resource(resource) || resource.phase;
  const resourceFailure = resource => ['stale', 'partial', 'unavailable', 'disconnected', 'error'].includes(resource.phase);
  const refreshPhase = resource => resource.snapshot === null
    ? (resource.error ? 'disconnected' : 'loading')
    : (resource.error ? 'stale' : 'ready');
  let refreshInFlight = false;
  // The server payload is the only media truth. Navigation may choose which
  // surface is visible, but it must never manufacture a replacement Plex
  // state from browse contexts or from the previous render.
  let nowPlaying = null;
  const canonicalView = key => key === 'sky' ? 'astronomy' : key;
  let view = canonicalView(params.get('view') || ''), interrupted = false;
  let calendarMode = params.get('mode') === 'all' ? 'all' : '';
  let sportsMode = ['ufc', 'pfl'].includes(view) && params.get('mode') === 'all' ? 'all' : '';
  let sportsPage = Math.max(1, Number.parseInt(params.get('page') || '1', 10) || 1);
  let calendarDisclosure = null;
  let skyAircraftOpen = false;
  let calendarFocusHeadingPending = Boolean(calendarMode);
  let calendarFocusDisclosurePending = false;
  let sportsFocusHeadingPending = Boolean(sportsMode);
  let sportsFocusDisclosurePending = false;
  let sportsFocusControlPending = '';
  let scoreDetailsOpen = false;
  let historyFocusDestination = null;
  let historyFocusOwned = false;
  let initialDirectFocusPending = Boolean(view);
  const label = key => destinations[key]?.[0] || key.replaceAll('_', ' ').replace(/^./, c => c.toUpperCase());
  const icon = key => destinations[key]?.[1] || moreIcon;
  const esc = text => String(text ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  // Keep normal word boundaries intact while allowing platform suffixes such
  // as PS5/Xbox/Switch/PC to wrap at their deliberate slash opportunities.
  const titleMarkup = text => esc(text).replace(/\//g, '/<wbr>');
  const fresh = c => (!c.expires || Date.parse(c.expires) > Date.now()) && c.eventState !== 'EXPIRED';
  const items = key => {
    const sources = key === 'nhl' ? [browseContexts] :
      key === 'ufc' || key === 'pfl' ? [contexts, browseContexts] : [contexts];
    return [...new Map(sources.flat().filter(c => (c.provider || c.source) === key && fresh(c))
      .map(context => [context.id, context])).values()];
  };
  document.body.classList.add('browser-controls');
  const rail = document.createElement('div'); rail.className = 'screen-controls kiosk-rail';
  rail.setAttribute('data-kiosk-navigation', 'true');
  rail.innerHTML = '<span class="kiosk-brand" role="status" aria-live="polite">Marquee</span><nav class="kiosk-primary" aria-label="Marquee destinations"></nav><button class="kiosk-more" type="button" aria-haspopup="dialog" aria-expanded="false"><span class="kiosk-icon" aria-hidden="true">' + moreIcon + '</span><span class="kiosk-label">More</span></button>';
  document.body.append(rail);
  const primary = rail.querySelector('.kiosk-primary'), more = rail.querySelector('.kiosk-more'), status = rail.querySelector('[role=status]');
  const menu = document.createElement('dialog'); menu.className = 'kiosk-menu'; menu.setAttribute('aria-labelledby', 'kiosk-menu-title');
  menu.innerHTML = '<header><h2 id="kiosk-menu-title">More destinations</h2><button type="button" aria-label="Close menu">✕</button></header><nav aria-label="Additional Marquee destinations"></nav><details><summary>Settings</summary><nav aria-label="Marquee control pages"><a href="/live">Live display</a><a href="/settings">Settings</a><a href="/settings/layout?profile=live">Edit screen layout</a><a href="/settings/attention">Alert rules</a><a href="/settings/tests">Test screens</a></nav></details>';
  document.body.append(menu);
  const overflow = menu.querySelector('nav');
  // Keep control links ahead of the long destination list so opening Settings
  // on a phone reveals its links immediately instead of below the fold.
  menu.insertBefore(menu.querySelector('details'), overflow);
  const panel = document.createElement('section'); panel.id = 'kiosk-panel'; panel.className = 'kiosk-section'; panel.hidden = true; panel.inert = true; panel.setAttribute('aria-hidden', 'true'); panel.setAttribute('aria-label', 'Selected kiosk section'); panel.setAttribute('aria-labelledby', 'kiosk-section-title'); document.body.append(panel);
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
  const weatherLifecycle = document.querySelector('#weather-lifecycle');
  function drawWeatherLifecycle(lifecycle) {
    const visible = view === 'weather' && selected && lifecycle?.state === 'partial';
    if (!weatherLifecycle) return;
    weatherLifecycle.hidden = !visible;
    if (visible) weatherLifecycle.innerHTML = sharedState('Weather is partial', 'Return to Home', true, 'partial', view, lifecycle.reason);
    else weatherLifecycle.replaceChildren();
  }
  function setBackgroundActive(active, surface = active ? 'panel' : 'dashboard') {
    // The media shell may enter its real idle state independently of kiosk
    // navigation. A selected destination must therefore explicitly own the
    // surface; otherwise the idle rules can hide it after this render.
    document.body.classList.toggle('kiosk-destination-active', active);
    const weatherActive = active && surface === 'weather';
    backgroundState.forEach(({node, inert, ariaHidden, hidden}) => {
      const stageOwns = (weatherActive || surface === 'stage') && node === stage;
      const covered = active && !stageOwns;
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
    if (stage) stage.classList.toggle('kiosk-covered', active && !weatherActive && surface !== 'stage');
    const panelActive = active && !weatherActive && surface !== 'stage';
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
  function href(key, agenda = false, page = 1) {
    const u = new URL(location.href);
    key ? u.searchParams.set('view', key) : u.searchParams.delete('view');
    if (key === 'calendar' && agenda) { u.searchParams.set('mode', 'all'); u.searchParams.delete('page'); }
    else if (['ufc', 'pfl'].includes(key) && agenda) { u.searchParams.set('mode', 'all'); u.searchParams.set('page', String(page)); }
    else { u.searchParams.delete('mode'); u.searchParams.delete('page'); }
    return u.pathname + u.search;
  }
  if (view) {
    const initialAgenda = view === 'calendar' && calendarMode === 'all';
    const initialSports = ['ufc', 'pfl'].includes(view) && sportsMode === 'all';
    history.replaceState({marqueeHome: true}, '', href(''));
    history.pushState({marqueeDestination: true}, '', href(view));
    if (initialAgenda || initialSports) history.pushState({marqueeDetail: true}, '', href(view, true, sportsPage));
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
  function drawNavigation(preserveFocus = true) {
    const focusedView = document.activeElement?.closest?.('a[data-view]')?.dataset.view;
    const all = allDestinations();
    // Selection is state, not navigation topology. Replacing every anchor when
    // `view` changes races the native pointerup/click sequence: a touch can
    // finish against a detached anchor, and the focus repair can land on the
    // old destination after the new one has rendered. Keep the delegated
    // targets stable; update aria-current/visibility below instead.
    const primarySignature = all.map(([key]) => key).join('|');
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
    // Counts and health text are presentation details. They must not replace
    // overflow controls while a remote is activating one of them.
    const overflowSignature = hidden.map(([key]) => key).join('|');
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
    if (preserveFocus && focusedView !== undefined) {
      const replacement = primary.querySelector(`[data-view="${CSS.escape(focusedView)}"]`)
        || overflow.querySelector(`[data-view="${CSS.escape(focusedView)}"]`);
      if (replacement && !replacement.hidden) replacement.focus({preventScroll: true});
    }
  }
  function drawMenu() { const hiddenKeys = new Set([...overflow.querySelectorAll('[data-view]')].map(a => a.dataset.view)); overflow.innerHTML = allDestinations().filter(([key]) => hiddenKeys.has(key)).map(d => link(d, offline ? 'Connection unavailable' : `${items(d[0]).length} current item${items(d[0]).length === 1 ? '' : 's'}`)).join(''); updateCurrentDestination(); }
  const sportViews = new Set(['nhl', 'ufc', 'pfl']);
  const mediaViews = new Set(['tv', 'movies', 'trailers', 'gaming', 'music', 'major_events']);
  const categoryFor = key => sportViews.has(key) ? 'sports' : key === 'calendar' ? 'agenda' : key === 'astronomy' ? 'sky' : mediaViews.has(key) ? 'media' : 'generic';
  const dateOf = c => { const value = c.starts || c.start_time || c.start || ''; const date = value ? new Date(value) : null; return date && !Number.isNaN(date.valueOf()) ? date : null; };
  const stateCopy = c => c.status || ({LIVE:'Live now', STARTING_SOON:'Starting soon', UPCOMING:'Coming up', RESULT:'Result', POST_EVENT:'Recently finished'}[c.eventState] || '');
  const sourceLabel = c => {
    const value = String((c.rows || [])[0] || c.source || c.provider || '').trim();
    if (!value || /@/.test(value) || /(?:entity|calendar\.)[\w.-]+/i.test(value)) return 'Household calendar';
    return value.replace(/^(?:mdi:|provider:)/i, '').replace(/[_-]+/g, ' ').replace(/\b\w/g, ch => ch.toUpperCase());
  };
  const safeRows = (c, limit = 3) => (c.rows || []).filter(row => row && !/@/.test(String(row))).slice(0, limit);
  const ordered = list => [...list].sort((a, b) => (dateOf(a)?.valueOf() || Infinity) - (dateOf(b)?.valueOf() || Infinity));
  // CalendarProvider keeps the nearest birthday in title and publishes the
  // remaining authoritative birthdays in rows. Keep that rollup as one
  // agenda entry and render rows as its subordinate display-only list.
  const calendarEntries = list => [...list];
  const button = c => `<button type="button" data-item="${esc(c.id)}"><small>${esc(stateCopy(c))}</small><strong>${esc(c.title || 'Untitled')}</strong><span>${esc(c.subtitle || c.detail || '')}</span></button>`;
  const combatView = key => key === 'ufc' || key === 'pfl';
  const combatName = key => key === 'pfl' ? 'PFL' : 'UFC';
  function destinationLifecycle(key, list) {
    if (!sections.includes(key)) {
      return { state: resources.config.phase === 'disconnected' ? 'disconnected' : 'unavailable', reason: 'not-enabled' };
    }
    if (resources.contexts.phase === 'loading') return { state: 'loading', reason: 'context request pending' };
    if (resources.contexts.phase === 'disconnected') return { state: 'disconnected', reason: 'context source cannot be reached' };
    const provider = health[key] || {};
    if (resources.contexts.phase === 'stale') return { state: 'stale', reason: 'retained context snapshot' };
    if (provider.stale) return { state: 'stale', reason: provider.reason || 'provider data is delayed' };
    if (provider.state === 'degraded') return { state: 'partial', reason: provider.reason || 'some provider data is delayed' };
    if (provider.state === 'error') return { state: 'error', reason: provider.error || provider.reason || 'provider fetch failed' };
    if (provider.state === 'disabled') return { state: 'disconnected', reason: provider.reason || 'provider is disabled' };
    return { state: list.length ? 'populated' : 'empty', reason: provider.reason || '' };
  }
  function sharedState(message, action = 'Return to Home', retry = false, lifecycle = 'empty', destination = view, reason = '') {
    const combat = combatView(destination);
    const promotion = combatName(destination);
    const copy = lifecycle === 'loading'
      ? combat ? `Checking the published ${promotion} schedule.` : 'Fetching the latest information for this destination.'
      : lifecycle === 'error'
      ? combat ? `The ${promotion} source did not answer. No last-known events are being presented as current.` : 'The source did not answer. No last-known results are being presented as current.'
      : lifecycle === 'stale'
        ? combat ? `The ${promotion} source has not refreshed. Last-known events are not being presented as current.` : 'The source has not refreshed. Last-known results are not being presented as current.'
      : lifecycle === 'partial'
        ? reason || (combat ? `Only part of the ${promotion} schedule arrived. Showing the available events.` : 'Only part of this source arrived. Showing the available results.')
      : lifecycle === 'disconnected'
        ? reason || (combat ? `The ${promotion} source is disconnected. Try again or return Home.` : 'This source is disconnected. Try again or return Home.')
      : lifecycle === 'unavailable'
          ? combat ? `The ${promotion} schedule is unavailable because its source cannot be reached.` : 'This destination is unavailable. Try again when its source is reachable.'
          : combat ? 'Check back when the next event is published.' : 'New items will appear automatically when this destination has something relevant.';
    const kicker = combat
      ? ({loading: `${promotion} · LOADING`, error: `${promotion} · SOURCE ERROR`, stale: `${promotion} · STALE SOURCE`, partial: `${promotion} · PARTIAL`, unavailable: `${promotion} · UNAVAILABLE`, disconnected: `${promotion} · OFFLINE`, empty: `${promotion} · SCHEDULE`}[lifecycle] || promotion)
      : (lifecycle === 'loading' ? 'LOADING' : lifecycle === 'error' ? 'SOURCE ERROR' : lifecycle === 'stale' ? 'STALE SOURCE' : lifecycle === 'partial' ? 'PARTIAL SOURCE' : lifecycle === 'unavailable' ? 'UNAVAILABLE' : lifecycle === 'disconnected' ? 'OFFLINE' : 'MARQUEE');
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
  const renderSportStage = (feature, source, details = [], scoreDetails = []) => {
    const left = feature.left || {}, right = feature.right || {};
    const state = String(feature.eventState || '').toUpperCase();
    const final = ['RESULT', 'POST_EVENT'].includes(state);
    const live = state === 'LIVE';
    const matchupName = nhlMatchupName(left, right);
    const status = live ? (nhlStatus(feature) || 'Live now') : final ? 'Final' : '';
    const scoreLog = scoreDetails.length ? `<details class="kiosk-sport-score-details"${view === 'nhl' && scoreDetailsOpen ? ' open' : ''}><summary>Score details</summary><ul aria-label="Goal-by-goal scoring">${scoreDetails.map(goal => `<li>${esc(goal)}</li>`).join('')}</ul></details>` : '';
    const rows = details.length || scoreLog ? `<div class="kiosk-sport-context">${details.map(detail => `<span>${esc(detail)}</span>`).join('')}${scoreLog}</div>` : '';
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
    const ppLabel = feature.powerPlay === 'No active power play' ? 'NO POWER PLAY' :
      feature.powerPlay ? `POWER PLAY · ${feature.powerPlay}` : '';
    const liveDetail = [feature.lastGoal ? `LAST GOAL · ${feature.lastGoal}` : '', ppLabel].filter(Boolean).join('  ·  ');
    const liveDetails = liveDetail ? [liveDetail] : [];
    return renderSportStage(feature, 'NHL', [...liveDetails, ...sportDetails(feature)], feature.scoreDetails || []);
  }
  function renderSports(list) {
    // The shared sports contract retains kiosk-matchup and NEXT RELEVANT
    // semantics for callers that provide a queue, while the stage itself gives the selected event
    // the full broadcast surface. stateCopy(feature) remains the lifecycle
    // source for the eyebrow rather than a provider-specific status.
    const feature = ordered(list)[0];
    if (!feature) return sharedState(`No upcoming ${combatName(view)} events are scheduled.`, 'Return to Home', false, 'empty', view);
    const source = label(view).toUpperCase();
    if (sportsMode === 'all') {
      const page = Math.max(1, Math.min(sportsPage, list.length));
      sportsPage = page;
      const current = ordered(list)[page - 1];
      return `<div class="kiosk-sports-detail"><div class="kiosk-sports-content" tabindex="0" aria-label="Scrollable ${esc(source)} event details"><header class="kiosk-sports-detail-head"><p class="kiosk-kicker">FULL ${esc(source)} SCHEDULE</p><p class="kiosk-sports-count">Event ${page} of ${list.length}</p></header>${renderSportStage(current, source, [current.subtitle || '', current.detail || '', ...safeRows(current)].filter(Boolean))}</div><div class="kiosk-sports-controls"><button type="button" data-sports-control="previous" ${page <= 1 ? 'disabled' : ''}>Previous event</button><button type="button" data-sports-control="next" ${page >= list.length ? 'disabled' : ''}>Next event</button><button type="button" data-sports-summary>Back to schedule</button><a href="${esc(href(''))}" data-view="">Return to Home</a></div><p class="kiosk-sr-only" aria-live="polite">Event ${page} of ${list.length}</p></div>`;
    }
    const schedule = list.length > 1 ? `<div class="kiosk-sports-disclosure"><button type="button" data-sports-disclosure aria-label="View all ${list.length} ${esc(source)} events">View all ${list.length} events</button></div>` : '';
    return `${renderSportStage(feature, source, [feature.subtitle || '', feature.detail || '', ...safeRows(feature)].filter(Boolean))}${schedule}`;
  }
  function agendaGroup(date) {
    if (!date) return 'Later';
    const now = new Date(); const start = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const days = Math.round((new Date(date.getFullYear(), date.getMonth(), date.getDate()) - start) / 86400000);
    return days === 0 ? 'Today' : days === 1 ? 'Tomorrow' : days < 7 ? 'This week' : 'Later';
  }
  const agendaLimit = () => window.matchMedia?.('(max-width: 480px)').matches || window.matchMedia?.('(min-width: 1000px) and (max-height: 700px) and (min-aspect-ratio: 3/2)').matches ? 2 : 3;
  function calendarRow(c) {
    const birthday = c.subtype === 'birthday_rollup';
    const birthdayRows = birthday ? (c.rows || []).filter(Boolean) : [];
    const subordinate = birthdayRows.length
      ? `<ul class="kiosk-birthday-rows" aria-label="Additional birthdays">${birthdayRows.map(row => `<li>${esc(row)}</li>`).join('')}</ul>`
      : '';
    return `<div class="kiosk-agenda-row ${birthday ? 'is-birthday' : ''}"><time>${esc(c.subtitle || 'All day')}</time><strong>${esc(c.title || 'Untitled')}</strong><small>${esc(birthday ? 'Birthday' : sourceLabel(c))}</small>${subordinate}</div>`;
  }
  function calendarDetail(list) {
    const grouped = list.reduce((map, c) => { const key = agendaGroup(dateOf(c)); (map[key] ||= []).push(c); return map; }, {});
    const content = Object.entries(grouped).map(([group, values]) => `<section><h3>${esc(group)}</h3>${values.map(calendarRow).join('')}</section>`).join('') || '<p class="kiosk-empty">No events are available.</p>';
    return `<div class="kiosk-calendar-detail"><header class="kiosk-calendar-detail-head"><div><p class="kiosk-kicker">FULL AGENDA</p><h2 id="calendar-agenda-title" tabindex="-1">All calendar events</h2></div><p class="kiosk-calendar-count">${list.length} ${list.length === 1 ? 'event' : 'events'}</p></header><div class="kiosk-agenda-groups kiosk-calendar-page" tabindex="0" aria-label="All calendar events; scroll to browse the list">${content}</div><div class="kiosk-calendar-controls"><button type="button" data-calendar-summary>Back to summary</button><a href="${esc(href(''))}" data-view="">Return to Home</a></div></div>`;
  }
  function calendarFocusToken() {
    const active = document.activeElement;
    if (!panel.contains(active)) return '';
    if (active.hasAttribute('data-calendar-summary')) return 'summary';
    if (active.dataset.view === '') return 'home';
    if (active.id === 'calendar-agenda-title') return 'heading';
    return '';
  }
  function renderAgenda(list) {
    const values = ordered(list), feature = values[0];
    if (!feature) return sharedState('Your agenda is clear.', 'Return to Home', false, 'empty');
    const upcoming = values.slice(1, 1 + agendaLimit());
    const grouped = upcoming.reduce((map, c) => { const key = agendaGroup(dateOf(c)); (map[key] ||= []).push(c); return map; }, {});
    const fullValues = view === 'calendar' ? calendarEntries(values) : values;
    const remaining = Math.max(0, fullValues.length - 1 - upcoming.length);
    const remainder = remaining ? `<button type="button" class="kiosk-agenda-more" data-calendar-disclosure aria-label="View all ${fullValues.length} events">View all ${fullValues.length} events</button>` : '';
    return `<div class="kiosk-agenda"><article class="kiosk-agenda-feature"><p class="kiosk-kicker">UP NEXT</p><h2>${esc(feature.title)}</h2><p class="kiosk-lede">${esc(feature.subtitle || feature.detail || '')}</p><p class="kiosk-meta">${esc(feature.location || feature.detail || sourceLabel(feature))}</p></article><div class="kiosk-agenda-groups">${Object.entries(grouped).map(([group, entries]) => `<section><h3>${esc(group)}</h3>${entries.map(calendarRow).join('')}</section>`).join('') || '<p class="kiosk-empty">No later events in view.</p>'}${remainder}</div></div>`;
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
    const weather = resources.sky.snapshot || {};
    const sky = weather.sky || {};
    const sun = sky.sun || {}, moon = sky.moon || {};
    const hasNumber = value => value !== null && value !== undefined && value !== '' && Number.isFinite(Number(value));
    const condition = String(sky.condition || weather.condition || '').toLowerCase().replaceAll('_', '-');
    const known = {partlycloudy: 'Partly cloudy', 'partly-cloudy': 'Partly cloudy', clear: 'Clear',
      'clear-night': 'Clear night', cloudy: 'Cloudy', rainy: 'Rainy', pouring: 'Pouring', fog: 'Foggy'};
    const conditionLabel = known[condition] || condition.replaceAll('-', ' ').replace(/^./, letter => letter.toUpperCase());
    const aircraft = Array.isArray(sky.aircraft) ? sky.aircraft : [];
    const phase = String(moon.phase || '').toLowerCase().replace(/[\s-]+/g, '_');
    const phaseLabels = {new_moon: 'New moon', waxing_crescent: 'Waxing crescent', first_quarter: 'First quarter',
      waxing_gibbous: 'Waxing gibbous', full_moon: 'Full moon', waning_gibbous: 'Waning gibbous',
      last_quarter: 'Last quarter', third_quarter: 'Last quarter', waning_crescent: 'Waning crescent'};
    const phaseLabel = phaseLabels[phase] || (phase && !['unknown', 'unavailable'].includes(phase)
      ? phase.replaceAll('_', ' ').replace(/^./, letter => letter.toUpperCase()) : 'Moon phase unavailable');
    const illumination = hasNumber(moon.illumination) ? Math.round(Number(moon.illumination) * 100) : null;
    const phaseIndex = ['new_moon', 'waxing_crescent', 'first_quarter', 'waxing_gibbous', 'full_moon', 'waning_gibbous', 'last_quarter', 'waning_crescent'].indexOf(phase);
    const moonFacts = [phaseLabel, illumination === null ? '' : `${illumination}% illuminated`,
      hasNumber(moon.elevation) ? `${Number(moon.elevation).toFixed(0)}° above horizon` : '',
      hasNumber(moon.azimuth) ? `${Math.round(Number(moon.azimuth))}° azimuth` : ''].filter(Boolean);
    const visibility = hasNumber(sky.visibility) ? `${Number(sky.visibility).toLocaleString()} ${sky.visibility_unit || 'km'}` : '';
    const temperature = hasNumber(weather.temp) ? Math.round(Number(weather.temp)) : null;
    const apparentValue = window.MarqueeApparentTemperature
      ? window.MarqueeApparentTemperature(weather) : weather.apparent_temperature;
    const feelsLike = hasNumber(apparentValue) ? Math.round(Number(apparentValue)) : null;
    const temperatureUnit = weather.temperature_unit === '°F' ? '°F' : '°C';

    const sunAzimuth = hasNumber(sun.azimuth) ? Math.round(Number(sun.azimuth)) : null;
    const sunDirection = sunAzimuth === null ? '' : ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'][Math.round(sunAzimuth / 45) % 8];
    const moonElevation = hasNumber(moon.elevation) ? `${Number(moon.elevation).toFixed(0)}°` : '';
    const moonAzimuth = hasNumber(moon.azimuth) ? `${Math.round(Number(moon.azimuth))}°` : '';
    const moonPosition = [moonElevation, moonAzimuth ? `${moonAzimuth} azimuth` : ''].filter(Boolean).join(' · ');
    const moonStage = phaseIndex < 0 ? 'Cycle position unavailable' : `Lunar cycle · day ${Math.round(phaseIndex / 7 * 29.53) + 1} of 30`;
    const nextMoonPhase = phaseIndex < 0 ? '' : ['New moon', 'First quarter', 'Full moon', 'Last quarter'][Math.floor(((phaseIndex + 1) % 8) / 2)];
    const nextMoonTiming = phaseIndex < 0 ? '' : `${Math.max(1, Math.round((((phaseIndex + 1) % 2) || 2) * 3.69))} days into this phase`;
    const weatherDetails = [
      hasNumber(weather.humidity) ? {label: 'Humidity', value: `${Math.round(Number(weather.humidity))}%`, icon: '◌'} : null,
      hasNumber(weather.wind) ? {label: 'Wind', value: `${Number(weather.wind).toFixed(0)} ${weather.windUnit || 'km/h'}`, icon: '↗'} : null,
      hasNumber(weather.wind_gust) ? {label: 'Gusts', value: `${Number(weather.wind_gust).toFixed(0)} ${weather.windUnit || 'km/h'}`, icon: '⌁'} : null,
      hasNumber(weather.pressure) ? {label: 'Pressure', value: `${Math.round(Number(weather.pressure))} ${weather.pressure_unit || 'hPa'}`, icon: '⌖'} : null,
    ].filter(Boolean);
    const detailCards = weatherDetails.map(item => `<div class="sky-detail-card"><span aria-hidden="true">${item.icon}</span><small>${esc(item.label)}</small><b>${esc(item.value)}</b></div>`).join('');
    const aircraftRows = aircraft.map((track, index) => {
      const name = String(track.callsign || track.id || `Aircraft ${index + 1}`).trim();
      const facts = [hasNumber(track.altitude) ? `${Math.round(Number(track.altitude)).toLocaleString()} m` : '',
        hasNumber(track.bearing) ? `${Math.round(Number(track.bearing))}° bearing` : '',
        hasNumber(track.elevation) ? `${Number(track.elevation).toFixed(0)}° elevation` : ''].filter(Boolean);
      return `<li class="sky-aircraft-row"><span class="sky-aircraft-icon" aria-hidden="true">✈</span><span><strong>${esc(name)}</strong><small>${esc(facts.join(' · ') || 'Nearby aircraft')}</small></span></li>`;
    }).join('');
    const eventRows = feature ? safeRows(feature) : [];
    const dayLabel = sun.is_day === true ? 'Day sky' : sun.is_day === false ? 'Night sky' : 'The sky above home';
    const sceneTitle = conditionLabel || (feature?.title && !/^sky$/i.test(feature.title) ? feature.title : dayLabel);
    const ambient = '';
    const moonShadow = ({new_moon: '<circle class="sky-moon-shadow" cx="50" cy="50" r="48"/>',
      waxing_crescent: '<ellipse class="sky-moon-shadow" cx="24" cy="50" rx="40" ry="48"/>',
      first_quarter: '<path class="sky-moon-shadow" d="M2 2h48v96H2z"/>',
      waxing_gibbous: '<ellipse class="sky-moon-shadow" cx="-10" cy="50" rx="40" ry="48"/>',
      full_moon: '',
      waning_gibbous: '<ellipse class="sky-moon-shadow" cx="110" cy="50" rx="40" ry="48"/>',
      last_quarter: '<path class="sky-moon-shadow" d="M50 2h48v96H50z"/>',
      third_quarter: '<path class="sky-moon-shadow" d="M50 2h48v96H50z"/>',
      waning_crescent: '<ellipse class="sky-moon-shadow" cx="76" cy="50" rx="40" ry="48"/>'})[phase] ?? '<ellipse class="sky-moon-shadow" cx="50" cy="50" rx="28" ry="48"/>';
    const moonGlyph = `<svg class="sky-moon-glyph" aria-hidden="true" data-phase-index="${phaseIndex}" viewBox="0 0 100 100"><defs><radialGradient id="sky-moon-light" cx="35%" cy="30%"><stop stop-color="#fff9df"/><stop offset=".72" stop-color="#f1e5ba"/><stop offset="1" stop-color="#c5b88f"/></radialGradient><clipPath id="sky-moon-clip"><circle cx="50" cy="50" r="48"/></clipPath></defs><circle class="sky-moon-disc" cx="50" cy="50" r="48"/><g clip-path="url(#sky-moon-clip)">${moonShadow}<circle class="sky-moon-crater" cx="31" cy="35" r="7"/><circle class="sky-moon-crater" cx="67" cy="64" r="10"/><circle class="sky-moon-crater" cx="57" cy="25" r="4"/></g></svg>`;
    const clouds = hasNumber(sky.cloud_cover) ? `${Math.round(Number(sky.cloud_cover))}% cloud cover` : '';
    const planeDots = aircraft.map((track, index) => {
      if (!hasNumber(track.bearing)) return '';
      const bearing = Number(track.bearing) * Math.PI / 180;
      const x = 50 + Math.sin(bearing) * 39, y = 58 - Math.max(-20, Math.min(35, Number(track.elevation || 0))) * .42;
      const name = String(track.callsign || track.id || `Aircraft ${index + 1}`).trim();
      return `<g class="sky-map-plane" transform="translate(${x.toFixed(1)} ${Math.max(12, Math.min(56, y)).toFixed(1)})"><circle r="2.2"/><text x="0" y="-3.5">${esc(name)}</text></g>`;
    }).join('');
    const planeAction = aircraft.length
      ? `<button type="button" class="sky-aircraft-toggle" data-sky-aircraft aria-expanded="${skyAircraftOpen}">${skyAircraftOpen ? 'Hide' : 'View'} ${aircraft.length} nearby ${aircraft.length === 1 ? 'plane' : 'planes'} <span aria-hidden="true">${skyAircraftOpen ? '−' : '+'}</span></button>` : '';
    const cloudIntensity = hasNumber(sky.cloud_cover) ? Math.max(0, Math.min(100, Number(sky.cloud_cover))) : 0;
    return `<div class="kiosk-ambient-surface sky-destination"><div class="sky-celestial-backdrop" aria-hidden="true"><span class="sky-orbit sky-orbit-one"></span><span class="sky-orbit sky-orbit-two"></span><span class="sky-horizon-glow"></span></div><div class="sky-destination-main"><p class="kiosk-kicker">SKY · ${ambient}</p><h2>${esc(sceneTitle)}</h2><p class="kiosk-lede">${esc(feature?.subtitle || dayLabel)}${clouds ? ` <span class="sky-condition-dot">·</span> ${esc(clouds)}` : ''}</p>${eventRows.length ? `<p class="kiosk-meta">${eventRows.map(esc).join(' · ')}</p>` : ''}<div class="sky-weather-hero">${temperature !== null ? `<div class="sky-temperature" aria-label="Current temperature ${temperature} ${temperatureUnit}${feelsLike === null ? '' : `, feels like ${feelsLike} ${temperatureUnit}`} "><strong>${temperature}°</strong><span>${esc(conditionLabel || 'outside')}</span>${feelsLike === null ? '' : `<small>Feels like <b>${feelsLike}${esc(temperatureUnit)}</b></small>`}</div>` : ''}<div class="sky-weather-facts">${clouds ? `<span class="sky-fact-cloud"><b>${Math.round(cloudIntensity)}%</b><small>cloud cover</small></span>` : ''}${visibility ? `<span><b>${esc(visibility)}</b><small>visibility</small></span>` : ''}${hasNumber(sun.elevation) ? `<span><b>${Number(sun.elevation).toFixed(0)}°</b><small>sun elevation</small></span>` : ''}</div></div></div><div class="sky-vista" role="img" aria-label="${esc(dayLabel)} panorama with ${clouds || 'no cloud observation'} and ${aircraft.length} tracked aircraft"><svg viewBox="0 0 100 72" preserveAspectRatio="xMidYMid meet" aria-hidden="true"><defs><linearGradient id="sky-haze" x1="0" y1="0" x2="0" y2="1"><stop stop-color="#111c3b"/><stop offset="1" stop-color="#385c79"/></linearGradient><radialGradient id="sky-glow"><stop stop-color="#c2e5ff" stop-opacity=".35"/><stop offset="1" stop-color="#c2e5ff" stop-opacity="0"/></radialGradient></defs><rect width="100" height="72" rx="18" fill="url(#sky-haze)"/><ellipse cx="50" cy="56" rx="49" ry="18" fill="url(#sky-glow)"/><g class="sky-vista-stars">${Array.from({length: 22}, (_, i) => { const x=(i*37+11)%96+2,y=(i*19+7)%38+4,r=i%5===0?'.45':'.22'; return `<circle cx="${x}" cy="${y}" r="${r}"/>`; }).join('')}</g><g class="sky-vista-clouds" style="opacity:${(.1 + cloudIntensity / 100 * .75).toFixed(2)}"><path d="M-5 36c8-9 17-6 22 0 5-12 20-12 25 0 10-5 20 1 21 9H-5z"/><path d="M46 28c8-8 15-5 19 0 5-9 17-8 20 1 9-3 17 2 18 9H46z"/></g>${planeDots}<path class="sky-vista-horizon" d="M0 61 Q20 56 35 61T70 60T100 61V72H0Z"/></svg><div class="sky-vista-caption"><span>${sun.is_day === false ? 'AFTER DARK' : 'ABOVE HOME'}</span><span>${aircraft.length ? `${aircraft.length} TRACKED` : 'QUIET SKY'}</span></div></div><article class="sky-moon-card" aria-label="Current moon phase">${moonGlyph}<div class="sky-moon-copy"><p class="sky-card-label">TONIGHT'S MOON</p><h3>${esc(phaseLabel)}</h3><p>${illumination === null ? 'Moon phase' : `${illumination}% illuminated`}</p>${moonPosition ? `<p class="sky-moon-position">${esc(moonPosition)}</p>` : ''}<small class="sky-moon-cycle">${esc(moonStage)}</small>${nextMoonPhase ? `<small class="sky-next-phase">${esc(nextMoonPhase)} · approximately ${esc(nextMoonTiming)}</small>` : ''}<div class="sky-phase-track" aria-label="Moon phase progression"><span style="--phase-progress:${phaseIndex < 0 ? 0 : phaseIndex / 7 * 100}%"></span></div></div></article>${aircraft.length ? `<section class="sky-aircraft-panel"><div class="sky-aircraft-summary"><span class="sky-plane-count" aria-hidden="true">✈</span><span><strong>${aircraft.length} ${aircraft.length === 1 ? 'plane' : 'planes'} overhead</strong><small>Live nearby aircraft · ${esc(visibility || 'local sky')}</small></span>${planeAction}</div><ul class="sky-aircraft-list${skyAircraftOpen ? ' is-expanded' : ''}">${aircraftRows}</ul></section>` : `<p class="sky-aircraft-empty">No aircraft are currently being reported nearby.</p>`}${sunAzimuth !== null ? `<p class="sky-sun-bearing">SUN · ${sunDirection} ${sunAzimuth}°</p>` : ''}${detailCards ? `<section class="sky-detail-grid" aria-label="Current weather details">${detailCards}</section>` : ''}<div class="sky-sensor-ribbon">${conditionLabel ? `<span>${esc(conditionLabel)}</span>` : ''}${clouds ? `<span>${esc(clouds)}</span>` : ''}${visibility ? `<span>${esc(visibility)} visibility</span>` : ''}</div></div>`;
  }
  function renderDestination(key, list) { const category = categoryFor(key); return key === 'nhl' ? renderNhl(list) : category === 'sports' ? renderSports(list) : category === 'agenda' ? renderAgenda(list) : category === 'media' ? renderMedia(list) : category === 'sky' ? renderAmbient(list) : list.length ? `<div class="kiosk-items">${list.slice(0, 8).map(button).join('')}</div>` : sharedState('Nothing to show here right now.', 'Return to Home', false, 'empty'); }
  // Refreshes redraw panel markup, but an unchanged visible action must not be
  // disconnected between pointerdown and click. Keep the action node and
  // synchronize its rendered state after the new panel content is committed.
  function panelControlKey(node) {
    if (node.matches('a[data-view]')) return `view:${node.dataset.view}`;
    if (node.matches('[data-calendar-summary]')) return 'calendar:summary';
    if (node.matches('[data-sports-control]')) return `sports:${node.dataset.sportsControl}`;
    if (node.matches('[data-sports-summary]')) return 'sports:summary';
    if (node.matches('[data-calendar-disclosure]')) return 'calendar:disclosure';
    if (node.matches('[data-sports-disclosure]')) return 'sports:disclosure';
    if (node.matches('[data-kiosk-retry]')) return 'retry';
    if (node.matches('button[data-item]')) return `item:${node.dataset.item}`;
    return null;
  }
  function preservePanelControls() {
    const existing = new Map();
    panel.querySelectorAll('a[data-view],button').forEach(node => {
      const key = panelControlKey(node);
      if (key && !existing.has(key)) existing.set(key, node);
    });
    return existing;
  }
  function reconcilePanelControls(existing) {
    if (!existing.size) return;
    panel.querySelectorAll('a[data-view],button').forEach(next => {
      const key = panelControlKey(next), current = key && existing.get(key);
      if (!current || current === next) return;
      [...current.attributes].forEach(attribute => {
        if (!next.hasAttribute(attribute.name)) current.removeAttribute(attribute.name);
      });
      [...next.attributes].forEach(attribute => current.setAttribute(attribute.name, attribute.value));
      current.replaceChildren(...[...next.childNodes].map(child => child.cloneNode(true)));
      next.replaceWith(current);
    });
  }
  function drawPanel() {
    const preservedControls = preservePanelControls();
    const preserveHeadingFocus = Boolean(view && document.activeElement?.id === 'kiosk-section-title');
    const focusedSportsControl = sportsFocusControlPending || (sportsMode && panel.contains(document.activeElement)
      ? document.activeElement.dataset.sportsControl || (document.activeElement.hasAttribute('data-sports-summary') ? 'summary'
        : document.activeElement.dataset.view === '' ? 'home' : document.activeElement.matches?.('.kiosk-sports-content') ? 'content' : '')
      : '');
    sportsFocusControlPending = '';
    const preserveSportsDisclosureFocus = !sportsMode && ['ufc', 'pfl'].includes(view)
      && panel.contains(document.activeElement)
      && document.activeElement.matches?.('[data-sports-disclosure]');
    if (preserveSportsDisclosureFocus) sportsFocusDisclosurePending = true;
    panel.dataset.section = view;
    const failedResources = Object.values(resources).filter(resourceFailure).length;
    const resourceNotice = offline ? ' · Sources unavailable' : failedResources ? ` · ${failedResources} source${failedResources === 1 ? '' : 's'} delayed` : '';
    const valid = sections.includes(view), list = valid ? items(view) : [];
    const lifecyclePreview = valid ? destinationLifecycle(view, list) : null;
    if (selected && (!list.some(c => c.id === selected) || lifecyclePreview?.state === 'disconnected')) selected = '';
    if (view === 'weather' && !selected && list.length && lifecyclePreview?.state === 'populated') selected = (list.find(c => ['alert','extreme'].includes(c.subtype)) || list.find(c => c.subtype === 'current') || list[0]).id;
    // Plex has two legitimate owners. Active playback belongs to the real
    // media stage; every non-playing/manual lifecycle belongs to this panel.
    // Never let the stage and panel hide each other during the hand-off.
    const plexActive = view === 'plex' && nowPlaying?.playing === true;
    const kioskPlaybackActive = LIVE_SURFACE && ATTENTION_DISPLAY === 'kiosk' && nowPlaying?.playing === true;
    document.body.classList.toggle('kiosk-now-playing', plexActive);
    document.body.classList.toggle('kiosk-playback-active', kioskPlaybackActive);
    panel.classList.toggle('now-playing-surface', view === 'plex');
    const active = Boolean(view) && !interrupted && view !== 'household';
    const surface = active && view === 'weather' && selected ? 'weather'
      : active && plexActive ? 'stage' : active ? 'panel' : 'dashboard';
    setBackgroundActive(active, surface);
    panel.hidden = !active || surface !== 'panel' || Boolean(selected); panel.inert = !active || panel.hidden;
    if (panel.hidden && !selected) {
      if (panel.contains(document.activeElement)) {
        focusNavigation(view);
        if (panel.contains(document.activeElement)) document.activeElement.blur();
      }
      return;
    }
    if (view === 'plex') {
      const state = String(nowPlaying?.state || '').toLowerCase();
      const availability = String(nowPlaying?.availability || '').toLowerCase();
      const unavailable = state === 'unavailable' || availability === 'unavailable';
      const stale = state === 'stale' || availability === 'stale' || nowPlaying?.stale === true;
      const loading = !nowPlaying;
      const stopped = state === 'stopped' || state === 'idle' || !state;
      const title = loading ? 'Checking the media room' : unavailable ? 'Media service unavailable'
        : stale ? 'Media status is stale' : stopped ? 'Nothing is playing' : 'Nothing is playing';
      const detail = loading ? 'Reading the current playback state.' : unavailable
        ? 'The media service cannot confirm a current session.' : stale
          ? 'The last media response has expired. No previous title or artwork is retained here.'
          : state === 'stopped' ? 'Playback has stopped. Start something in the media room to see it here.'
          : 'There is no active session in the media room.';
      const weather = ['idle-weather-temp', 'idle-weather-condition', 'idle-weather-feels', 'idle-weather-range']
        .map(id => document.querySelector(`#${id}`)?.textContent?.trim() || '')
        .filter(Boolean);
      const weatherLabels = ['Temperature', 'Conditions', 'Feels like', 'High and low'];
      const weatherMarkup = weather.length
        ? `<div class="kiosk-weather-context" aria-label="Current weather">${weather.map((fact, index) => `${index ? '<span class="kiosk-weather-separator" aria-hidden="true">·</span>' : ''}<span class="kiosk-weather-fact" aria-label="${esc(`${weatherLabels[index]}: ${fact}`)}">${esc(fact)}</span>`).join('')}</div>`
        : '<div class="kiosk-weather-context" aria-label="Current weather">Home display ready</div>';
      const unavailableMark = unavailable || stale ? `<div class="kiosk-state-mark is-${unavailable ? 'unavailable' : 'stale'}" aria-hidden="true"><span>${unavailable ? '!' : '↻'}</span></div>` : '';
      const retry = unavailable || stale ? '<button type="button" class="kiosk-retry" data-kiosk-retry>Check again</button>' : '';
      panel.innerHTML = `<header class="kiosk-now-playing-head"><p>NOW PLAYING</p><h1 id="kiosk-section-title">${esc(title)}</h1>${detail ? `<p class="kiosk-now-playing-detail">${esc(detail)}</p>` : ''}</header><div class="kiosk-now-playing-body">${unavailableMark}<div class="kiosk-now-playing-copy">${weatherMarkup}<div class="kiosk-now-playing-actions"><a class="kiosk-home-action" href="${esc(href(''))}" data-view="">Return to Home</a>${retry}</div></div></div>`;
      reconcilePanelControls(preservedControls);
      focusInitialDestination();
      preserveDirectHeadingFocus(preserveHeadingFocus);
      return;
    }
    const lifecycle = requestState === 'loading'
      ? { state: 'loading', reason: 'provider request pending' }
      : destinationLifecycle(view, list);
    drawWeatherLifecycle(lifecycle);
    status.textContent = interrupted ? 'Household attention' : view === 'household' ? 'Household' : (view ? label(view) : 'Marquee · Auto') + (lifecycle.state === 'partial' ? ' · PARTIAL' : lifecycle.state === 'disconnected' ? ' · OFFLINE' : resourceNotice);
    const message = lifecycle.state === 'loading' ? `Loading ${label(view)}…` : lifecycle.state === 'error' ? `${label(view)} is unavailable` : lifecycle.state === 'stale' ? `${label(view)} is stale` : lifecycle.state === 'unavailable' ? `${label(view)} is unavailable` : lifecycle.state === 'disconnected' ? `${label(view)} is disconnected` : '';
    const feature = view === 'nhl' && list.length ? ordered(list)[0] : null;
    const headingName = feature ? nhlMatchupName(feature.left || {}, feature.right || {}) : label(view);
    const detail = view === 'calendar' && calendarMode === 'all' && lifecycle.state === 'populated';
    const sportsDetail = ['ufc', 'pfl'].includes(view) && sportsMode === 'all' && lifecycle.state === 'populated';
    panel.classList.toggle('calendar-detail-surface', detail);
    panel.classList.toggle('sports-detail-surface', sportsDetail);
    let html = detail
      ? `<header class="kiosk-section-head kiosk-section-head-detail"><p>CALENDAR</p><h1 id="kiosk-section-title">Calendar</h1></header>${calendarDetail(calendarEntries(ordered(list)))}`
      : `<header class="kiosk-section-head"><p>${esc(categoryFor(view).toUpperCase())}${lifecycle.state === 'partial' ? ' · PARTIAL' : lifecycle.state === 'disconnected' ? ' · OFFLINE' : ''}</p><h1 id="kiosk-section-title"${feature ? ` aria-label="${esc(headingName)}"` : ''}>${esc(label(view))}</h1></header>` + (message ? sharedState(message, 'Return to Home', ['error', 'stale', 'unavailable', 'disconnected', 'partial'].includes(lifecycle.state), lifecycle.state, view, lifecycle.reason) : lifecycle.state === 'partial' ? `<div class="kiosk-partial-surface" data-lifecycle="partial">${sharedState(`${label(view)} is partial`, 'Return to Home', true, 'partial', view, lifecycle.reason)}${renderDestination(view, list)}</div>` : renderDestination(view, list));
    const focusedCalendarControl = detail
      ? (calendarFocusHeadingPending ? '' : calendarFocusToken())
      : '';
    const preserveCalendarDisclosureFocus = !detail && view === 'calendar'
      && panel.contains(document.activeElement)
      && document.activeElement.matches?.('[data-calendar-disclosure]');
    if (preserveCalendarDisclosureFocus) calendarFocusDisclosurePending = true;
    if (panel.innerHTML !== html) {
      panel.innerHTML = html;
      reconcilePanelControls(preservedControls);
    }
    if (sportsDetail) {
      const canonical = new URL(location.href).searchParams.get('page');
      if (canonical !== String(sportsPage)) history.replaceState({marqueeDetail: true}, '', href(view, true, sportsPage));
    }
    calendarDisclosure = panel.querySelector('[data-calendar-disclosure]');
    if (!detail && calendarFocusDisclosurePending && calendarDisclosure) {
      calendarDisclosure.focus({preventScroll: true});
      calendarFocusDisclosurePending = false;
    }
    if (detail && calendarFocusHeadingPending) {
      panel.querySelector('#calendar-agenda-title')?.focus({preventScroll: true});
      calendarFocusHeadingPending = false;
      initialDirectFocusPending = false;
    } else if (detail && focusedCalendarControl) {
      const target = focusedCalendarControl === 'summary' ? '[data-calendar-summary]'
        : focusedCalendarControl === 'home' ? '[data-view=""]'
          : focusedCalendarControl === 'heading' ? '#calendar-agenda-title' : '';
      const control = panel.querySelector(target);
      if (control && !control.disabled) control.focus({preventScroll: true});
    }
    if (!sportsDetail && sportsFocusDisclosurePending) {
      panel.querySelector('[data-sports-disclosure]')?.focus({preventScroll: true});
      sportsFocusDisclosurePending = false;
    } else if (!sportsDetail && sportsFocusHeadingPending) {
      const heading = panel.querySelector('#kiosk-section-title');
      if (heading) { heading.tabIndex = -1; heading.focus({preventScroll: true}); }
      sportsFocusHeadingPending = false;
      initialDirectFocusPending = false;
    } else if (sportsDetail && sportsFocusHeadingPending) {
      const heading = panel.querySelector('#kiosk-section-title');
      if (heading) { heading.tabIndex = -1; heading.focus({preventScroll: true}); }
      sportsFocusHeadingPending = false;
      initialDirectFocusPending = false;
    } else if (sportsDetail && focusedSportsControl) {
      const target = focusedSportsControl === 'previous' ? '[data-sports-control="previous"]'
        : focusedSportsControl === 'next' ? '[data-sports-control="next"]'
          : focusedSportsControl === 'summary' ? '[data-sports-summary]'
            : focusedSportsControl === 'home' ? '[data-view=""]' : '.kiosk-sports-content';
      const control = panel.querySelector(target);
      if (control && !control.disabled) control.focus({preventScroll: true});
      else if (focusedSportsControl === 'next') panel.querySelector('[data-sports-control="previous"]')?.focus({preventScroll: true});
      else if (focusedSportsControl === 'previous') panel.querySelector('[data-sports-control="next"]')?.focus({preventScroll: true});
    }
    if (!detail) focusInitialDestination();
    preserveDirectHeadingFocus(preserveHeadingFocus);
  }
  function focusNavigation(key) {
    const target = primary.querySelector(`[data-view="${CSS.escape(key)}"]`);
    if (target && !target.hidden) target.focus();
    else if (key) more.focus();
    else primary.querySelector('[data-view=""]')?.focus();
  }
  function change(key, restoreFocus = true) { key = canonicalView(key); view = key; selected = ''; calendarMode = ''; sportsMode = ''; sportsPage = 1; sportsFocusHeadingPending = false; sportsFocusDisclosurePending = false; sportsFocusControlPending = ''; calendarFocusDisclosurePending = false; history.pushState({marqueeDestination: Boolean(key)}, '', href(key)); closeMenu(false); drawNavigation(); drawMenu(); drawPanel(); if (restoreFocus) { focusNavigation(key); setTimeout(() => focusNavigation(key), 0); } window.dispatchEvent(new Event('marquee-navigation')); }
  function openCalendarAgenda() { if (view !== 'calendar' || !items('calendar').length) return; calendarMode = 'all'; calendarFocusHeadingPending = true; calendarFocusDisclosurePending = false; history.pushState({marqueeCalendarAgenda: true}, '', href('calendar', true)); drawPanel(); }
  function closeCalendarAgenda() {
    if (!calendarMode) return;
    calendarFocusDisclosurePending = true;
    history.back();
  }
  function openSportsSchedule() { if (!['ufc', 'pfl'].includes(view) || items(view).length < 2) return; sportsMode = 'all'; sportsPage = 1; sportsFocusHeadingPending = true; sportsFocusDisclosurePending = false; history.pushState({marqueeDetail: true}, '', href(view, true, sportsPage)); drawPanel(); }
  function closeSportsSchedule() { if (!sportsMode) return; sportsFocusDisclosurePending = true; history.back(); }
  function setSportsPage(page) { const list = ordered(items(view)); sportsPage = Math.max(1, Math.min(list.length, page)); history.replaceState({marqueeDetail: true}, '', href(view, true, sportsPage)); drawPanel(); }
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
  let lastPointerNavigation = {anchor: null, at: 0};
  function navigateFromAnchor(anchor, eventType) {
    if (!anchor || anchor.matches('[aria-disabled="true"]')) return false;
    const now = performance.now();
    if (eventType === 'click' && lastPointerNavigation.anchor === anchor && now - lastPointerNavigation.at < 500) return true;
    if (eventType === 'pointerup') lastPointerNavigation = {anchor, at: now};
    change(anchor.dataset.view);
    return true;
  }
  // Links are replaced during refreshes; delegate from the stable rail and
  // handle pointer activation before a transient overlay can consume it.
  rail.addEventListener('pointerup', e => {
    const anchor = e.target.closest?.('a[data-view]');
    if (anchor && rail.contains(anchor)) { e.preventDefault(); navigateFromAnchor(anchor, 'pointerup'); }
  }, true);
  rail.addEventListener('click', e => {
    const anchor = e.target.closest?.('a[data-view]');
    if (anchor && rail.contains(anchor)) { e.preventDefault(); navigateFromAnchor(anchor, 'click'); }
  }, true);
  menu.addEventListener('click', e => { if (e.target === menu) { const r = menu.getBoundingClientRect(); if (e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom) closeMenu(); } });
  panel.addEventListener('click', e => { const scoreSummary = e.target.closest('.kiosk-sport-score-details summary'); if (scoreSummary) { scoreDetailsOpen = !scoreSummary.parentElement.open; return; } const a = e.target.closest('a[data-view]'); if (a) { e.preventDefault(); change(a.dataset.view); return; } if (e.target.closest('[data-sky-aircraft]')) { skyAircraftOpen = !skyAircraftOpen; drawPanel(); panel.querySelector('[data-sky-aircraft]')?.focus({preventScroll: true}); return; } if (e.target.closest('[data-calendar-disclosure]')) { openCalendarAgenda(); return; } if (e.target.closest('[data-calendar-summary]')) { closeCalendarAgenda(); return; } if (e.target.closest('[data-sports-disclosure]')) { openSportsSchedule(); return; } if (e.target.closest('[data-sports-summary]')) { closeSportsSchedule(); return; } const sportsControl = e.target.closest('[data-sports-control]'); if (sportsControl && !sportsControl.disabled) { sportsFocusControlPending = sportsControl.dataset.sportsControl; setSportsPage(sportsPage + (sportsControl.dataset.sportsControl === 'next' ? 1 : -1)); return; } const retry = e.target.closest('button[data-kiosk-retry]'); if (retry) { retry.disabled = true; retry.textContent = 'Checking…'; refresh().finally(() => { retry.disabled = false; }); return; } const b = e.target.closest('button[data-item]'); if (b) { selected = b.dataset.item; drawPanel(); primary.querySelector(`[data-view="${CSS.escape(view)}"]`)?.focus(); window.dispatchEvent(new Event('marquee-navigation')); } });
  stage?.addEventListener('click', e => { const a = e.target.closest('a[data-view]'); if (a) { e.preventDefault(); change(a.dataset.view); return; } const retry = e.target.closest('button[data-kiosk-retry]'); if (retry) { retry.disabled = true; retry.textContent = 'Checking…'; refresh().finally(() => { retry.disabled = false; }); } });
  document.addEventListener('keydown', e => { if (menu.open || !view) return; if (!calendarMode && !sportsMode && e.target.closest?.('[data-calendar-disclosure]') && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); openCalendarAgenda(); return; } if (!sportsMode && e.target.closest?.('[data-sports-disclosure]') && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); openSportsSchedule(); return; } if (calendarMode) { if (e.key === 'Escape' || e.key === 'BrowserBack') { e.preventDefault(); closeCalendarAgenda(); return; } } else if (sportsMode) { if (e.key === 'Escape' || e.key === 'BrowserBack') { e.preventDefault(); closeSportsSchedule(); return; } if (e.key === 'ArrowLeft' || e.key === 'PageUp') { e.preventDefault(); setSportsPage(sportsPage - 1); return; } if (e.key === 'ArrowRight' || e.key === 'PageDown') { e.preventDefault(); setSportsPage(sportsPage + 1); return; } } else if (e.key === 'Escape') { e.preventDefault(); change(''); } });
  function restoreHistoryDestinationFocus() { if (historyFocusDestination === null || calendarMode || view === 'calendar') return; const destination = historyFocusDestination; historyFocusDestination = null; focusNavigation(destination); }
  window.addEventListener('marquee-history-focus-owned', () => { historyFocusOwned = true; historyFocusDestination = null; });
  document.addEventListener('focusin', event => { if (historyFocusDestination === null || calendarMode || view === 'calendar') return; const destination = historyFocusDestination; historyFocusDestination = null; if (event.target?.dataset?.view !== destination) focusNavigation(destination); });
  window.addEventListener('popstate', () => { const overlayOwnsFocus = historyFocusOwned; historyFocusOwned = false; const wasCalendarDetail = view === 'calendar' && calendarMode === 'all'; const wasSportsDetail = ['ufc', 'pfl'].includes(view) && sportsMode === 'all'; const next = new URLSearchParams(location.search); const nextView = canonicalView(next.get('view') || ''); const activityHash = location.hash === '#activity'; view = nextView; calendarMode = view === 'calendar' && next.get('mode') === 'all' ? 'all' : ''; sportsMode = ['ufc', 'pfl'].includes(view) && next.get('mode') === 'all' ? 'all' : ''; if (wasCalendarDetail && view === 'calendar' && !calendarMode) calendarFocusDisclosurePending = true; if (!(view === 'calendar' && !calendarMode)) calendarFocusDisclosurePending = false; if (wasSportsDetail && !sportsMode && ['ufc', 'pfl'].includes(view)) sportsFocusDisclosurePending = true; sportsFocusHeadingPending = Boolean(sportsMode); sportsPage = Math.max(1, Number.parseInt(next.get('page') || '1', 10) || 1); calendarFocusHeadingPending = Boolean(calendarMode || sportsMode); selected = ''; drawNavigation(false); drawMenu(); drawPanel(); if (!overlayOwnsFocus && !calendarMode && !sportsMode && !activityHash) { if (view !== 'calendar' && !(['ufc', 'pfl'].includes(view))) focusNavigation(view); } window.dispatchEvent(new Event('marquee-navigation')); historyFocusDestination = overlayOwnsFocus || view === 'calendar' || sportsMode || activityHash || (['ufc', 'pfl'].includes(view) && !sportsMode) ? null : view; if (['ufc', 'pfl'].includes(view) && !sportsMode && wasSportsDetail) setTimeout(() => panel.querySelector('[data-sports-disclosure]')?.focus({preventScroll: true}), 0); });
  window.addEventListener('pageshow', restoreHistoryDestinationFocus);
  window.addEventListener('marquee-surface-rendered', drawPanel);
  window.MarqueeNavigation = { resolve(payload) { nowPlaying = payload || {playing:false, state:'idle', availability:'idle'}; const wasInterrupted = interrupted; interrupted = Boolean(payload?.attention || payload?.householdFocus); if (interrupted && !wasInterrupted && menu.open) closeMenu(false); drawPanel(); if (interrupted || !view || view === 'plex') return payload; const c = !offline && sections.includes(view) && items(view).find(item => item.id === selected); return c ? c.payload || {playing:true,type:'media_context',key:'browse:'+c.id,context:c} : {playing:false}; }, refresh };
  async function refresh(lifecycle = {}) {
    if (refreshInFlight) return;
    refreshInFlight = true;
    const serial = ++requestSerial;
    const clean = values => { const seen = new Set(); return (values || []).filter(c => { if (!c.id || c.id.startsWith('screen-test:') || (c.targets && !c.targets.includes('kiosk')) || !fresh(c)) return false; const key=(c.provider||c.source)+'|'+c.title+'|'+(c.starts||''); if (seen.has(key)) return false; seen.add(key); return true; }); };
    const requests = {
      config: fetch('/api/config', {signal: lifecycle.signal}),
      contexts: fetch('/contexts', {signal: lifecycle.signal}),
      providers: fetch('/providers', {signal: lifecycle.signal}),
      sky: fetch('/ha-weather.json', {signal: lifecycle.signal}),
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
      if (lifecycle.isCurrent && !lifecycle.isCurrent()) return;
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
        resource.state = sharedResourceState(resource);
        if (name === 'config') {
          if (resource.error) window.MarqueeLifecycle.status('Configuration refresh failed. Showing the last saved settings; retrying.', 'error');
          else window.MarqueeLifecycle.status('');
        }
      }
      if (resources.config.snapshot) {
        const config = resources.config.snapshot;
        sections = Object.entries(config.providers || {}).filter(([, cfg]) => cfg.enabled && (!cfg.targets || cfg.targets.includes('kiosk'))).map(([key]) => key);
      }
      if (resources.providers.snapshot) health = resources.providers.snapshot.providers || {};
      if (resources.contexts.snapshot) {
        const snapshot = resources.contexts.snapshot;
        contexts = clean(snapshot.contexts);
        browseContexts = clean(['nhl', 'ufc', 'pfl'].flatMap(name => snapshot.browse?.[name] || []));
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
  drawNavigation(); drawMenu(); drawPanel();
  window.MarqueeLifecycle.register('kiosk-resources', {interval: 15000, refresh});
})();
