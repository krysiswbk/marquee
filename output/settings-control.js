(() => {
  'use strict';
  document.querySelectorAll('input[type="number"], input[type="range"]').forEach(control => control.setAttribute('aria-describedby', 'admin-numeric-help'));

  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
  const clone = value => structuredClone(value);
  const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
  const get = (value, path) => path.split('.').reduce((item, key) => item?.[key], value);
  const set = (value, path, next) => {
    const parts = path.split('.');
    const leaf = parts.pop();
    const owner = parts.reduce((item, key) => item[key] ??= {}, value);
    owner[leaf] = next;
    return value;
  };

  const DISPLAY_PROFILE_KEYS = new Set([
    'castKioskActivity', 'garageKioskActivity', 'template', 'theme', 'liveTheme',
    'clockFormat', 'clockSeconds', 'showWeather', 'weatherUnits', 'displayWidth',
    'displayHeight'
  ]);
  const ADVANCED_PROFILE_KEYS = new Set([
    'mediaBackend', 'plexHost', 'plexToken', 'embyHost', 'embyKey',
    'jellyfinHost', 'jellyfinKey', 'plexUsers', 'plexDevices', 'blockTags'
  ]);
  const DISPLAY_CONFIG_PREFIXES = ['fallback.'];
  const CONTENT_CONFIG_PREFIXES = ['providers.', 'interests.'];
  const ADVANCED_CONFIG_PREFIXES = ['general.', 'display.', 'context_engine.'];
  const PROFILE_META = {
    cast: {
      endpoint: '/settings',
      scope: 'Main Cast + Garage',
      help: 'The media card used when a Cast display is in Cast design mode.'
    },
    live: {
      endpoint: '/live-settings',
      scope: 'Browser Live / Kiosk',
      help: 'The browser dashboard used by Live, Kiosk, and Cast displays set to kiosk mode.'
    }
  };
  const PROVIDERS = {
    plex: { label: 'Plex', desc: 'Playback and household media activity.', target: 'Cast + Live / Kiosk', fields: [] },
    nhl: { label: 'NHL', desc: 'Followed-team schedules and live games.', target: 'Live / Kiosk', fields: [
      ['Teams', 'teams', 'list', 'Comma-separated team abbreviations'],
      ['Show before game', 'pregame_minutes', 'number', 'minutes', 0, 1440],
      ['Keep results after game', 'postgame_minutes', 'number', 'minutes', 0, 1440]
    ] },
    ufc: { label: 'UFC', desc: 'Fight cards and live bouts.', target: 'Live / Kiosk', fields: [
      ['Show before event', 'preevent_minutes', 'number', 'minutes', 0, 1440],
      ['Keep results after event', 'result_minutes', 'number', 'minutes', 0, 1440],
      ['Include Contender Series', 'include_contender_series', 'toggle']
    ] },
    pfl: { label: 'PFL', desc: 'PFL fight cards and live bouts.', target: 'Live / Kiosk', fields: [
      ['Show before event', 'preevent_minutes', 'number', 'minutes', 0, 1440],
      ['Keep results after event', 'result_minutes', 'number', 'minutes', 0, 1440]
    ] },
    weather: { label: 'Weather & radar', desc: 'Approaching precipitation and meaningful weather.', target: 'Live / Kiosk', fields: [
      ['Radar', 'radar', 'toggle'], ['Rain probability', 'precip_probability', 'number', '%', 0, 100],
      ['Approach window', 'approach_minutes', 'number', 'minutes', 5, 360],
      ['Strong wind', 'wind_gust_kmh', 'number', 'km/h', 20, 250],
      ['Radar range', 'radar_span_degrees', 'decimal', 'degrees', .2, 12],
      ['Severe weather takeover', 'severe_takeover', 'toggle'], ['Snow events', 'snow_enabled', 'toggle']
    ] },
    tv: { label: 'TV / Sonarr', desc: 'Upcoming monitored episodes.', target: 'Live / Kiosk', fields: [
      ['Sonarr URL', 'url', 'url'], ['Sonarr API key', 'api_key', 'password', 'Blank keeps the saved key'],
      ['Tracked shows', 'tracked_shows', 'list'], ['Tracking', 'tracking_mode', 'select', '', [['show_all', 'All monitored shows'], ['tracked_only', 'Tracked list only']]],
      ['Look ahead', 'lookahead_hours', 'number', 'hours', 1, 168]
    ] },
    astronomy: { label: 'Astronomy', desc: 'Notable events worth looking outside for.', target: 'Live / Kiosk', fields: [
      ['Aurora alerts', 'aurora', 'toggle'], ['Aurora threshold', 'kp_threshold', 'decimal', 'Kp', 0, 9],
      ['ISS passes', 'iss', 'toggle'], ['Meteor showers', 'meteor_showers', 'toggle'],
      ['Eclipses and rare events', 'eclipses', 'toggle'], ['Minimum significance', 'minimum_significance', 'number', '%', 0, 100]
    ] },
    gaming: { label: 'Gaming', desc: 'Free game claims and upcoming releases.', target: 'Live / Kiosk', fields: [
      ['Claims feed URL', 'claims_url', 'url'], ['Maximum claims', 'max_claims', 'number', 'items', 1, 10],
      ['Release look-ahead', 'release_lookahead_days', 'number', 'days', 1, 180],
      ['Maximum releases', 'max_releases', 'number', 'items', 1, 10]
    ] },
    calendar: { label: 'Calendars', desc: 'Sanitized Home Assistant events.', target: 'Choose destinations', fields: [
      ['Look ahead', 'lookahead_days', 'number', 'days', 1, 90],
      ['Allow Cast takeovers', 'allow_cast', 'toggle'], ['Cast minimum weight', 'cast_min_priority', 'number', '', 80, 100]
    ] },
    movies: { label: 'Movies', desc: 'No provider adapter is configured.', unavailable: true },
    trailers: { label: 'Trailers', desc: 'No provider adapter is configured.', unavailable: true },
    major_events: { label: 'Major events', desc: 'Unavailable until a curated source is configured.', unavailable: true },
    music: { label: 'Music', desc: 'No provider adapter is configured.', unavailable: true }
  };

  const state = {
    profiles: { cast: { base: null, edits: new Map() }, live: { base: null, edits: new Map() } },
    profile: 'cast', configBase: null, configEdits: new Map(), attentionBase: null,
    attentionDraft: null, attentionDiagnostics: null, brain: null, providerHealth: null, systemHealth: null,
    bindingCatalog: [], activeTab: 'displays', attentionConflict: false, busyArea: ''
  };

  function profileValue(profile, key) {
    const item = state.profiles[profile];
    return item.edits.has(key) ? item.edits.get(key) : item.base?.[key];
  }
  function editProfile(profile, key, value) {
    const item = state.profiles[profile];
    if (same(value, item.base?.[key])) item.edits.delete(key);
    else item.edits.set(key, value);
    updateDirty();
  }
  function configValue(path) {
    return state.configEdits.has(path) ? state.configEdits.get(path) : get(state.configBase, path);
  }
  function editConfig(path, value) {
    if (same(value, get(state.configBase, path))) state.configEdits.delete(path);
    else state.configEdits.set(path, value);
    updateDirty();
  }
  const pathsFor = prefixes => [...state.configEdits.keys()].filter(path => prefixes.some(prefix => path.startsWith(prefix)));
  const profileKeysFor = (profile, keys) => [...state.profiles[profile].edits.keys()].filter(key => keys.has(key));
  const attentionDirty = () => state.attentionBase && !same(state.attentionBase, state.attentionDraft);
  function areaDirty(area) {
    if (area === 'displays') return profileKeysFor('cast', DISPLAY_PROFILE_KEYS).length || profileKeysFor('live', DISPLAY_PROFILE_KEYS).length || pathsFor(DISPLAY_CONFIG_PREFIXES).length;
    if (area === 'content') return pathsFor(CONTENT_CONFIG_PREFIXES).length;
    if (area === 'alerts') return attentionDirty();
    return profileKeysFor('cast', ADVANCED_PROFILE_KEYS).length || pathsFor(ADVANCED_CONFIG_PREFIXES).length;
  }
  function updateDirty() {
    for (const area of ['displays', 'content', 'alerts', 'advanced']) {
      const dirty = !!areaDirty(area);
      $(`[data-tab="${area}"] .dirty-dot`).hidden = !dirty;
      const bar = $(`.savebar[data-area="${area}"]`);
      $('.save-area', bar).disabled = !dirty || !!state.busyArea;
      $('.discard', bar).disabled = !dirty || !!state.busyArea;
    }
    const area = state.activeTab;
    const bar = $(`.savebar[data-area="${area}"]`);
    if (!bar || !$('#mobile-actionbar')) return;
    const dirty = !!areaDirty(area);
    $('#mobile-save').disabled = !dirty || !!state.busyArea;
    $('#mobile-discard').disabled = !dirty || !!state.busyArea;
    const status = $('.area-status', bar);
    $('#mobile-actionbar-status').textContent = status.textContent || (dirty ? 'Unsaved changes' : 'No unsaved changes');
    $('#mobile-actionbar-status').className = 'mobile-actionbar-status' + (status.classList.contains('error') ? ' error' : status.classList.contains('success') ? ' success' : '');
  }

  function controlValue(control) {
    if (control.type === 'checkbox') return control.checked;
    if (control.type === 'number') return control.value === '' ? null : Number(control.value);
    if (control.dataset.list === '1') return control.value.split(',').map(item => item.trim()).filter(Boolean);
    return control.value;
  }
  function fillControl(control, value) {
    if (control.type === 'checkbox') control.checked = !!value;
    else if (control.dataset.list === '1' && Array.isArray(value)) control.value = value.join(', ');
    else control.value = value ?? '';
  }
  function bindStaticControls() {
    $$('[data-config-path]').forEach(control => {
      const write = () => editConfig(control.dataset.configPath, controlValue(control));
      control.addEventListener(control.type === 'checkbox' || control.tagName === 'SELECT' ? 'change' : 'input', write);
    });
    $$('[data-cast-key]').forEach(control => {
      const write = () => editProfile('cast', control.dataset.castKey, controlValue(control));
      control.addEventListener(control.type === 'checkbox' || control.tagName === 'SELECT' ? 'change' : 'input', write);
    });
    $$('[data-profile-key]').forEach(control => {
      const write = () => editProfile(state.profile, control.dataset.profileKey, controlValue(control));
      control.addEventListener(control.type === 'checkbox' || control.tagName === 'SELECT' ? 'change' : 'input', write);
    });
    $$('[data-profile]').forEach(button => button.addEventListener('click', () => {
      state.profile = button.dataset.profile;
      renderProfile();
    }));
  }
  function renderConfigControls() {
    $$('[data-config-path]').forEach(control => fillControl(control, configValue(control.dataset.configPath)));
    $$('[data-cast-key]').forEach(control => fillControl(control, profileValue('cast', control.dataset.castKey)));
    renderModeStates();
  }
  function renderModeStates() {
    $('#cast-mode-state').textContent = profileValue('cast', 'castKioskActivity') ? 'Live / Kiosk mode' : 'Native Cast design';
    $('#garage-mode-state').textContent = profileValue('cast', 'garageKioskActivity') ? 'Live / Kiosk mode' : 'Native Cast design';
  }
  function renderProfile() {
    $$('[data-profile]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.profile === state.profile)));
    $$('.cast-only').forEach(item => item.hidden = state.profile !== 'cast');
    $$('.live-only').forEach(item => item.hidden = state.profile !== 'live');
    $$('[data-profile-key]').forEach(control => fillControl(control, profileValue(state.profile, control.dataset.profileKey)));
    const meta = PROFILE_META[state.profile];
    $('#profile-help').textContent = meta.help;
    $('#profile-scope').textContent = meta.scope;
  }

  function providerField(name, field) {
    const [label, key, type, help = '', min, max] = field;
    const path = `providers.${name}.${key}`;
    const id = `provider-${name}-${key}`;
    if (type === 'toggle') return `<label class="check-field"><input type="checkbox" data-config-path="${path}"> ${label}</label>`;
    if (type === 'select') return `<div class="field"><label for="${id}">${label}</label><select id="${id}" data-config-path="${path}">${min.map(([value, text]) => `<option value="${value}">${text}</option>`).join('')}</select></div>`;
    const inputType = type === 'list' ? 'text' : type === 'decimal' ? 'number' : type;
    const attrs = ['number', 'decimal'].includes(type) ? `min="${min}" max="${max}" step="${type === 'decimal' ? 'any' : '1'}" required` : '';
    const hint = type === 'list' ? (help || 'Comma-separated') : help;
    return `<div class="field"><label for="${id}">${label}</label><input id="${id}" type="${inputType}" ${attrs} data-config-path="${path}" data-list="${type === 'list' ? '1' : '0'}" autocomplete="${type === 'password' ? 'new-password' : 'off'}"><small>${hint}</small></div>`;
  }
  function buildProviders() {
    const root = $('#provider-list');
    root.replaceChildren();
    for (const [name, provider] of Object.entries(PROVIDERS)) {
      const card = document.createElement('article');
      card.className = 'provider-card' + (provider.unavailable ? ' unavailable' : '');
      card.dataset.provider = name;
      if (provider.unavailable) {
        card.innerHTML = `<div class="provider-main"><div class="provider-name"><h3>${provider.label}</h3><p>${provider.desc}</p></div><span class="provider-target">Unavailable</span></div>`;
      } else {
        const target = name === 'calendar'
          ? `<label class="provider-target"><input type="checkbox" data-calendar-target="kiosk"> Live / Kiosk</label><label class="provider-target"><input type="checkbox" data-calendar-target="hubs"> Cast</label>`
          : `<span class="provider-target">${provider.target}</span>`;
        card.innerHTML = `<div class="provider-main"><div class="provider-name"><h3>${provider.label}</h3><p>${provider.desc}</p></div><label class="provider-toggle"><input class="switch" type="checkbox" role="switch" data-config-path="providers.${name}.enabled"><span>Enabled</span></label><div class="provider-targets">${target}</div></div><details><summary>Timing and source details</summary><div class="field-grid"><div class="field"><label for="provider-${name}-priority">Source weight</label><input id="provider-${name}-priority" type="number" min="0" max="100" required data-config-path="providers.${name}.priority"><small>Compared with the eligibility threshold in Advanced.</small></div>${(provider.fields || []).map(field => providerField(name, field)).join('')}</div></details>`;
      }
      root.append(card);
    }
    $$('[data-config-path]', root).forEach(control => {
      const path = control.dataset.configPath;
      let value = configValue(path);
      if (control.dataset.list === '1' && Array.isArray(value)) value = value.join(', ');
      fillControl(control, value);
      const write = () => {
        let next = controlValue(control);
        if (control.dataset.list === '1') next = String(next).split(',').map(item => item.trim()).filter(Boolean);
        if (control.type === 'password' && !next) state.configEdits.delete(path);
        else editConfig(path, next);
        updateDirty();
      };
      control.addEventListener(control.type === 'checkbox' || control.tagName === 'SELECT' ? 'change' : 'input', write);
    });
    $$('[data-calendar-target]', root).forEach(control => {
      control.checked = (configValue('providers.calendar.targets') || []).includes(control.dataset.calendarTarget);
      control.addEventListener('change', () => {
        let targets = $$('[data-calendar-target]:checked', root).map(item => item.dataset.calendarTarget);
        if (!targets.length) {
          control.checked = true;
          targets = [control.dataset.calendarTarget];
          setAreaStatus('content', 'Calendars need at least one destination.', 'error');
        }
        editConfig('providers.calendar.targets', targets);
      });
    });
  }

  function mediaBackend() {
    const chosen = profileValue('cast', 'mediaBackend');
    return ['plex', 'emby', 'jellyfin'].includes(chosen) ? chosen : (profileValue('cast', 'envBackend') || 'plex');
  }
  function renderMediaConnection() {
    const backend = mediaBackend();
    const fields = { plex: ['plexHost', 'plexToken', 'plexTokenSet'], emby: ['embyHost', 'embyKey', 'embyKeySet'], jellyfin: ['jellyfinHost', 'jellyfinKey', 'jellyfinKeySet'] };
    const [host, secret, saved] = fields[backend];
    $('#media-host').dataset.castDynamicKey = host;
    $('#media-secret').dataset.castDynamicKey = secret;
    $('#media-host').value = profileValue('cast', host) || '';
    $('#media-secret').value = state.profiles.cast.edits.get(secret) || '';
    $('#media-secret-help').textContent = profileValue('cast', saved) ? 'A secret is saved. Blank keeps it.' : 'No saved secret. Blank leaves it unset.';
  }

  function bindingLabel(binding) {
    const signal = (state.attentionDiagnostics?.signals || []).find(item => item.entity_id === binding.entity_id && !String(item.id).startsWith('ha-health:'));
    return signal?.attributes?.friendly_name || binding.entity_id.split('.').pop().replaceAll('_', ' ').replace(/\b\w/g, char => char.toUpperCase());
  }
  function renderBindings() {
    const active = new Set((state.attentionDraft.signal_bindings || []).map(item => item.entity_id));
    const nursery = state.bindingCatalog.filter(item => item.location === 'nursery');
    const other = state.bindingCatalog.filter(item => item.location !== 'nursery');
    const root = $('#binding-groups');
    root.replaceChildren();
    const addGroup = (title, bindings) => {
      if (!bindings.length) return;
      const group = document.createElement('div');
      group.className = 'binding-group';
      const heading = document.createElement('h4'); heading.textContent = title; group.append(heading);
      bindings.forEach(binding => {
        const row = document.createElement('div'); row.className = 'binding-row';
        const label = document.createElement('label');
        const input = document.createElement('input'); input.type = 'checkbox'; input.checked = active.has(binding.entity_id); input.dataset.binding = binding.entity_id;
        const copy = document.createElement('span'); copy.textContent = bindingLabel(binding);
        const detail = document.createElement('small'); detail.textContent = [binding.category, binding.location].filter(Boolean).join(' · ') || 'Household device'; copy.append(detail);
        label.append(input, copy);
        const stateCopy = document.createElement('span'); stateCopy.className = 'binding-state'; stateCopy.textContent = input.checked ? 'Monitored' : 'Excluded in this draft';
        row.append(label, stateCopy); group.append(row);
        input.addEventListener('change', () => {
          const items = state.attentionDraft.signal_bindings;
          const index = items.findIndex(item => item.entity_id === binding.entity_id);
          if (input.checked && index < 0) items.push(clone(binding));
          if (!input.checked && index >= 0) items.splice(index, 1);
          renderBindings(); renderNurseryHealth(); updateDirty();
        });
      });
      root.append(group);
    };
    addGroup('Nursery', nursery);
    addGroup('Other household devices', other);
    if (!state.bindingCatalog.length) {
      const empty = document.createElement('p'); empty.className = 'intro'; empty.textContent = 'No Home Assistant alert devices are configured.'; root.append(empty);
    }
  }
  function renderNurseryHealth() {
    const nursery = state.bindingCatalog.filter(item => item.location === 'nursery');
    $('#nursery-health').hidden = !nursery.length;
    if (!nursery.length) return;
    const active = new Set(state.attentionDraft.signal_bindings.map(item => item.entity_id));
    const healthKnown = !!state.brain;
    const outages = new Map((state.brain?.device_health || []).map(item => [item.entity_id, item]));
    $('#nursery-health-list').replaceChildren(...nursery.map(binding => {
      const row = document.createElement('div'); row.className = 'nursery-device';
      const status = !active.has(binding.entity_id) ? 'Excluded in this draft' : !healthKnown ? 'Health unavailable' : outages.has(binding.entity_id) ? 'Unavailable' : 'No outage reported';
      const name = document.createElement('span'); name.textContent = bindingLabel(binding);
      const value = document.createElement('span'); value.textContent = status; row.append(name, value); return row;
    }));
    const badge = $('#nursery-health-badge');
    const hasOutage = nursery.some(binding => active.has(binding.entity_id) && outages.has(binding.entity_id));
    badge.textContent = !healthKnown ? 'Health unavailable' : hasOutage ? 'Needs attention' : 'No outage reported';
    badge.className = 'health-badge ' + (!healthKnown ? '' : hasOutage ? 'bad' : 'good');
  }
  function fillHours() {
    for (const id of ['quiet-start', 'quiet-end']) {
      const select = $('#' + id);
      select.replaceChildren(...Array.from({ length: 24 }, (_, hour) => {
        const option = document.createElement('option'); option.value = String(hour);
        option.textContent = new Intl.DateTimeFormat(undefined, { hour: 'numeric' }).format(new Date(2020, 0, 1, hour)); return option;
      }));
    }
  }
  function renderAlerts() {
    if (!state.attentionDraft) return;
    $('#attention-enabled').checked = !!state.attentionDraft.enabled;
    $('#quiet-start').value = String(state.attentionDraft.quiet_hours.start);
    $('#quiet-end').value = String(state.attentionDraft.quiet_hours.end);
    renderBindings(); renderNurseryHealth();
  }
  function showAttentionUnavailable() {
    $$('#panel-alerts .panel, #panel-alerts .savebar').forEach(item => item.hidden = true);
    let notice = $('#alerts-unavailable');
    if (!notice) {
      notice = document.createElement('div'); notice.id = 'alerts-unavailable'; notice.className = 'load-state error';
      $('#panel-alerts .section-head').insertAdjacentElement('afterend', notice);
    }
    notice.replaceChildren(document.createTextNode('Alerts are still starting. Displays and Content are ready to use. '));
    const retry = document.createElement('button'); retry.className = 'secondary retry'; retry.textContent = 'Retry alerts';
    retry.addEventListener('click', async () => {
      retry.disabled = true;
      try {
        const attention = await request('/api/attention');
        state.attentionBase = clone(attention.config); state.attentionDraft = clone(attention.config);
        state.attentionDiagnostics = attention; state.bindingCatalog = clone(attention.config.signal_bindings || []);
        notice.remove(); $$('#panel-alerts .panel, #panel-alerts .savebar').forEach(item => item.hidden = false);
        renderAlerts(); updateDirty();
      } catch (_) { retry.disabled = false; }
    });
    notice.append(retry);
  }

  function renderHealth() {
    const root = $('#provider-health'); root.replaceChildren();
    for (const [name, provider] of Object.entries(PROVIDERS)) {
      if (provider.unavailable) continue;
      const health = state.providerHealth?.providers?.[name];
      const item = document.createElement('div'); item.className = 'health-item';
      const title = document.createElement('b'); title.className = 'health-provider'; title.textContent = provider.label;
      const status = document.createElement('span');
      const labels = {ok: 'Working', error: 'Failed', stale: 'Stale', disabled: 'Unavailable', fetching: 'Checking', starting: 'Starting'};
      status.textContent = !health ? 'Status unavailable' : labels[health.state] || 'Status unavailable';
      status.className = `health-status ${health?.state === 'ok' ? 'ok' : health?.state === 'error' ? 'error' : health?.state === 'stale' ? 'stale' : ''}`;
      item.append(title, status);
      if (health) {
        const candidates = health.candidateContexts ?? 0;
        const eligible = health.eligibleContexts ?? 0;
        const counts = document.createElement('span'); counts.textContent = `${eligible} eligible of ${candidates} candidate${candidates === 1 ? '' : 's'}`; item.append(counts);
        const minimum = Number(configValue('context_engine.minimum_relevance') ?? 0);
        const weight = Number(configValue(`providers.${name}.priority`) ?? 0);
        if (weight < minimum) {
          const excluded = document.createElement('span'); excluded.textContent = `Excluded from normal rotation: source weight ${weight} is below ${minimum}.`; item.append(excluded);
        }
        if (health.error) {
          const error = document.createElement('span'); error.className = 'health-explanation error'; error.textContent = health.errorSummary || health.error; item.append(error);
        }
        if (health.stale) {
          const stale = document.createElement('span'); stale.className = 'health-explanation'; stale.textContent = `Using cached data${health.cacheAgeSeconds != null ? ` (${Math.round(health.cacheAgeSeconds)}s old)` : ''}.`; item.append(stale);
        }
        const last = document.createElement('span'); last.className = 'health-recency'; last.textContent = `Last checked: ${health.lastFetch ? new Date(health.lastFetch).toLocaleString() : 'not checked'}${health.lastSuccess ? ` · Last successful: ${new Date(health.lastSuccess).toLocaleString()}` : ''}`; item.append(last);
      }
      root.append(item);
    }
  }
  function renderProductInfo() {
    $('#running-version').textContent = state.systemHealth?.version ? `v${state.systemHealth.version}` : 'Unavailable';
  }

  function activateTab(name, focus = false) {
    state.activeTab = name;
    $$('[role="tab"]').forEach(tab => {
      const selected = tab.dataset.tab === name;
      tab.setAttribute('aria-selected', String(selected)); tab.tabIndex = selected ? 0 : -1;
      if (selected && focus) tab.focus();
    });
    $$('.tabpanel').forEach(panel => panel.hidden = panel.id !== `panel-${name}`);
    history.replaceState(null, '', `#${name}`);
    updateDirty();
  }
  function bindTabs() {
    const tabs = $$('[role="tab"]');
    tabs.forEach((tab, index) => {
      tab.addEventListener('click', () => activateTab(tab.dataset.tab));
      tab.addEventListener('keydown', event => {
        if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
        event.preventDefault();
        const next = event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1 : (index + (event.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length;
        activateTab(tabs[next].dataset.tab, true);
      });
    });
  }

  function setAreaStatus(area, message, type = '') {
    const node = $(`.savebar[data-area="${area}"] .area-status`);
    node.textContent = message; node.className = 'area-status' + (type ? ` ${type}` : '');
    updateDirty();
  }
  function setAreaBusy(area, busy) {
    state.busyArea = busy ? area : '';
    $$('#app input, #app select, #app button').forEach(control => {
      if (busy) {
        control.dataset.beforeBusyDisabled = control.disabled ? '1' : '0';
        control.disabled = true;
      } else {
        control.disabled = control.dataset.beforeBusyDisabled === '1';
        delete control.dataset.beforeBusyDisabled;
      }
    });
  }
  function validateArea(area) {
    const panel = $(`#panel-${area}`);
    $$('[aria-invalid="true"]', panel).forEach(input => input.removeAttribute('aria-invalid'));
    $$('.field-error', panel).forEach(item => item.remove());
    const invalid = $$('input,select', panel).find(input => !input.disabled && !input.checkValidity());
    let control = invalid, message = invalid?.validationMessage;
    if (!control && area === 'displays' && Number(configValue('fallback.single_item_seconds')) > Number(configValue('fallback.rotation_seconds'))) {
      control = $('#fallback-item'); message = 'Single-item time cannot exceed the idle rotation interval.';
    }
    if (!control && area === 'advanced' && Number(configValue('display.minimum_context_seconds')) > Number(configValue('display.rotation_seconds'))) {
      control = $('#minimum-seconds'); message = 'Minimum screen time cannot exceed relevant screen duration.';
    }
    if (!control) return true;
    control.setAttribute('aria-invalid', 'true');
    const note = document.createElement('small'); note.className = 'field-error'; note.textContent = message; note.setAttribute('role', 'alert'); control.insertAdjacentElement('afterend', note);
    control.focus(); setAreaStatus(area, message, 'error'); return false;
  }
  async function request(url, options = {}) {
    const response = await fetch(url, options);
    let result = {};
    try { result = await response.json(); } catch (_) { /* readable fallback below */ }
    if (!response.ok) throw new Error(result.error || `Request failed (${response.status})`);
    return result;
  }
  const jsonOptions = (method, body) => ({ method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  function partialConfig(paths) {
    const body = {};
    paths.forEach(path => set(body, path, clone(state.configEdits.get(path))));
    return body;
  }
  async function saveProfile(profile, keys) {
    if (!keys.length) return null;
    const payload = Object.fromEntries(keys.map(key => [key, state.profiles[profile].edits.get(key)]));
    const result = await request(PROFILE_META[profile].endpoint, jsonOptions('PATCH', payload));
    state.profiles[profile].base = result.settings || { ...state.profiles[profile].base, ...payload };
    keys.forEach(key => {
      if (same(state.profiles[profile].edits.get(key), payload[key])) state.profiles[profile].edits.delete(key);
    });
    return profile === 'cast' ? 'Cast settings' : 'Live / Kiosk settings';
  }
  async function saveConfig(paths) {
    if (!paths.length) return null;
    const payload = partialConfig(paths);
    const snapshots = new Map(paths.map(path => [path, clone(state.configEdits.get(path))]));
    const result = await request('/api/config', jsonOptions('PUT', payload));
    state.configBase = result.config || state.configBase;
    paths.forEach(path => {
      if (same(state.configEdits.get(path), snapshots.get(path))) state.configEdits.delete(path);
    });
    return 'screen content';
  }
  async function saveResources(area, jobs) {
    if (!validateArea(area)) return;
    setAreaBusy(area, true);
    setAreaStatus(area, 'Saving…');
    const saved = [], failed = [];
    for (const job of jobs) {
      try { const label = await job.run(); if (label) saved.push(label); }
      catch (error) { failed.push(`${job.label}: ${error.message}`); }
    }
    setAreaBusy(area, false);
    renderConfigControls(); renderProfile(); buildProviders(); renderMediaConnection(); updateDirty();
    if (failed.length) setAreaStatus(area, `${saved.length ? `Saved ${saved.join(', ')}. ` : ''}${failed.join(' · ')}`, 'error');
    else setAreaStatus(area, `Saved ${saved.join(', ')}.`, 'success');
  }
  async function saveArea(area) {
    if (state.busyArea) return;
    if (area === 'displays') {
      const cast = profileKeysFor('cast', DISPLAY_PROFILE_KEYS), live = profileKeysFor('live', DISPLAY_PROFILE_KEYS), config = pathsFor(DISPLAY_CONFIG_PREFIXES);
      return saveResources(area, [
        { label: 'Cast settings', run: () => saveProfile('cast', cast) },
        { label: 'Live / Kiosk settings', run: () => saveProfile('live', live) },
        { label: 'idle display settings', run: () => saveConfig(config) }
      ]);
    }
    if (area === 'content') return saveResources(area, [{ label: 'content', run: () => saveConfig(pathsFor(CONTENT_CONFIG_PREFIXES)) }]);
    if (area === 'advanced') return saveResources(area, [
      { label: 'media connection', run: () => saveProfile('cast', profileKeysFor('cast', ADVANCED_PROFILE_KEYS)) },
      { label: 'advanced settings', run: () => saveConfig(pathsFor(ADVANCED_CONFIG_PREFIXES)) }
    ]);
    return saveAlerts();
  }
  async function saveAlerts() {
    if (state.busyArea || !state.attentionDraft) return;
    if (!validateArea('alerts')) return;
    setAreaBusy('alerts', true);
    setAreaStatus('alerts', 'Checking for newer alert settings…');
    try {
      const latest = await request('/api/attention');
      if (!same(latest.config, state.attentionBase)) {
        state.attentionConflict = true;
        throw new Error('Alert settings changed elsewhere. Discard this draft to reload the current settings before saving.');
      }
      await request('/api/attention/config', jsonOptions('PUT', state.attentionDraft));
      state.attentionBase = clone(state.attentionDraft); state.attentionConflict = false;
      setAreaStatus('alerts', 'Saved alerts.', 'success');
    } catch (error) {
      setAreaStatus('alerts', `Alerts were not saved: ${error.message}`, 'error');
    } finally { setAreaBusy('alerts', false); updateDirty(); }
  }
  async function discardArea(area) {
    if (state.busyArea) return;
    if (area === 'alerts' && state.attentionConflict) {
      setAreaBusy('alerts', true); setAreaStatus('alerts', 'Reloading current alert settings…');
      try {
        const latest = await request('/api/attention');
        state.attentionBase = clone(latest.config); state.attentionDraft = clone(latest.config);
        state.attentionDiagnostics = latest; state.bindingCatalog = clone(latest.config.signal_bindings || []);
        state.attentionConflict = false;
      } catch (error) {
        setAreaStatus('alerts', `Could not reload alerts: ${error.message}`, 'error');
        setAreaBusy('alerts', false); updateDirty(); return;
      }
      setAreaBusy('alerts', false);
    } else if (area === 'alerts') state.attentionDraft = clone(state.attentionBase);
    if (area === 'content') pathsFor(CONTENT_CONFIG_PREFIXES).forEach(path => state.configEdits.delete(path));
    if (area === 'displays') {
      profileKeysFor('cast', DISPLAY_PROFILE_KEYS).forEach(key => state.profiles.cast.edits.delete(key));
      profileKeysFor('live', DISPLAY_PROFILE_KEYS).forEach(key => state.profiles.live.edits.delete(key));
      pathsFor(DISPLAY_CONFIG_PREFIXES).forEach(path => state.configEdits.delete(path));
    }
    if (area === 'advanced') {
      profileKeysFor('cast', ADVANCED_PROFILE_KEYS).forEach(key => state.profiles.cast.edits.delete(key));
      pathsFor(ADVANCED_CONFIG_PREFIXES).forEach(path => state.configEdits.delete(path));
    }
    renderConfigControls(); renderProfile(); buildProviders(); renderMediaConnection(); renderAlerts(); updateDirty(); setAreaStatus(area, 'Draft discarded.');
  }

  async function refreshHealth() {
    $('#refresh-health').disabled = true;
    try { state.providerHealth = await request('/providers?refresh=1'); renderHealth(); }
    catch (error) { $('#provider-health').textContent = `Could not refresh source health: ${error.message}`; }
    finally { $('#refresh-health').disabled = false; }
  }
  async function load() {
    const optional = promise => promise.catch(() => null);
    const [cast, live, config, attention, health, brain, systemHealth] = await Promise.all([
      request('/settings.json'), request('/live-settings.json'), request('/api/config'), optional(request('/api/attention')),
      optional(request('/providers')), optional(request('/api/brain')), optional(request('/healthz'))
    ]);
    state.profiles.cast.base = cast; state.profiles.live.base = live; state.configBase = config;
    state.providerHealth = health; state.brain = brain; state.systemHealth = systemHealth;
    if (attention) {
      state.attentionBase = clone(attention.config); state.attentionDraft = clone(attention.config);
      state.attentionDiagnostics = attention; state.bindingCatalog = clone(attention.config.signal_bindings || []);
    }
    renderConfigControls(); renderProfile(); buildProviders(); renderMediaConnection();
    if (attention) renderAlerts(); else showAttentionUnavailable();
    renderHealth(); renderProductInfo(); updateDirty();
    $('#load-state').hidden = true; $('#app').hidden = false;
    const source = new URLSearchParams(location.search).get('source');
    const sourceTarget = source === 'interests' || !!PROVIDERS[source];
    const requested = sourceTarget ? 'content' : location.hash.slice(1);
    activateTab(['displays', 'content', 'alerts', 'advanced'].includes(requested) ? requested : 'displays');
    if (source === 'interests') {
      const details = $('#interest-details'); details.open = true;
      details.scrollIntoView({ block: 'center' });
      $('input,summary', details)?.focus({ preventScroll: true });
    } else if (source && PROVIDERS[source]) {
      const card = $(`[data-provider="${CSS.escape(source)}"]`);
      const details = $('details', card); if (details) details.open = true;
      card.scrollIntoView({ block: 'center' });
      $('input,select,summary', card)?.focus({ preventScroll: true });
    }
  }

  bindTabs(); bindStaticControls(); fillHours();
  $$('input[type="number"]').filter(input => !['latitude', 'longitude'].includes(input.id)).forEach(input => input.required = true);
  $('#attention-enabled').addEventListener('change', event => { state.attentionDraft.enabled = event.target.checked; updateDirty(); });
  $('#quiet-start').addEventListener('change', event => { state.attentionDraft.quiet_hours.start = Number(event.target.value); updateDirty(); });
  $('#quiet-end').addEventListener('change', event => { state.attentionDraft.quiet_hours.end = Number(event.target.value); updateDirty(); });
  $('#media-backend').addEventListener('change', renderMediaConnection);
  $('#media-host').addEventListener('input', event => editProfile('cast', event.target.dataset.castDynamicKey, event.target.value));
  $('#media-secret').addEventListener('input', event => {
    const key = event.target.dataset.castDynamicKey;
    if (!event.target.value) state.profiles.cast.edits.delete(key); else editProfile('cast', key, event.target.value);
    updateDirty();
  });
  $$('.save-area').forEach(button => button.addEventListener('click', () => saveArea(button.closest('.savebar').dataset.area)));
  $$('.discard').forEach(button => button.addEventListener('click', () => discardArea(button.closest('.savebar').dataset.area)));
  $('#mobile-save').addEventListener('click', () => saveArea(state.activeTab));
  $('#mobile-discard').addEventListener('click', () => discardArea(state.activeTab));
  $('#refresh-health').addEventListener('click', refreshHealth);
  $('#release-notes-details').addEventListener('toggle', async event => {
    const details = event.currentTarget;
    if (!details.open || details.dataset.loaded === '1') return;
    $('#release-notes').textContent = 'Loading release notes…';
    try {
      const response = await fetch('/release-notes');
      if (!response.ok) throw new Error(`Request failed (${response.status})`);
      $('#release-notes').textContent = await response.text(); details.dataset.loaded = '1';
    } catch (error) { $('#release-notes').textContent = `Release notes unavailable: ${error.message}`; }
  });
  window.addEventListener('beforeunload', event => {
    if (['displays', 'content', 'alerts', 'advanced'].some(areaDirty)) { event.preventDefault(); event.returnValue = ''; }
  });
  load().catch(error => {
    const box = $('#load-state'); box.className = 'load-state error';
    box.textContent = `Could not load settings: ${error.message}. `;
    const retry = document.createElement('button'); retry.className = 'secondary retry'; retry.textContent = 'Retry'; retry.addEventListener('click', () => location.reload()); box.append(retry);
  });
})();
