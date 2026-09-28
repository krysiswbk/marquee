(() => {
  'use strict';
  const $ = selector => document.querySelector(selector);
  const clone = value => structuredClone(value);
  const state = { base: null, draft: null, diagnostics: null, schema: {}, dirty: false, saving: false, conflict: false, invalidEditors: new Set(), lockState: null };
  const sceneOptions = ['attention', 'source', 'image', 'radar'];
  const urgencyOptions = ['AMBIENT', 'CONTEXTUAL', 'ACTIONABLE', 'IMPORTANT', 'CRITICAL'];
  const text = (tag, value, className = '') => {
    const node = document.createElement(tag); node.textContent = value ?? '';
    if (className) node.className = className; return node;
  };
  const element = (tag, className = '') => {
    const node = document.createElement(tag); if (className) node.className = className; return node;
  };
  const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
  function setStatus(message, type = '') { const node = $('#status'); node.textContent = message; node.className = 'status ' + type; }
  function changed() {
    const invalid = !!state.invalidEditors.size;
    state.dirty = !same(state.base, state.draft) || invalid;
    $('#save').disabled = !state.dirty || invalid || state.saving || state.conflict;
    $('#discard').disabled = !state.dirty || state.saving;
    document.querySelectorAll('[data-rebuild]').forEach(control => control.disabled = invalid || state.saving);
  }
  function lockEditing(locked) {
    state.saving = locked;
    if (locked) {
      state.lockState = new Map();
      document.querySelectorAll('.settings-admin input, .settings-admin select, .settings-admin textarea, .settings-admin button').forEach(control => {
        state.lockState.set(control, control.disabled);
        control.disabled = true;
      });
      return;
    }
    state.lockState?.forEach((disabled, control) => { if (control.isConnected) control.disabled = disabled; });
    state.lockState = null;
    changed();
  }
  async function request(path, method = 'GET', body) {
    const response = await fetch(path, body === undefined ? { method } : { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || `Request failed (${response.status})`);
    return data;
  }
  function input(label, value, write, type = 'text', options = null, help = '', attrs = {}) {
    const wrap = element('label'); wrap.textContent = label;
    let control;
    if (options) {
      control = element('select'); options.forEach(([key, name]) => { const option = text('option', name); option.value = key; option.selected = String(value) === String(key); control.append(option); });
    } else { control = document.createElement('input'); control.type = type; control.value = value ?? ''; }
    Object.entries(attrs).forEach(([key, attrValue]) => { if (key !== 'error' && attrValue !== undefined) control.setAttribute(key, String(attrValue)); });
    const error = attrs.error ? text('small', '', 'mq-field-error') : null;
    if (error) { error.id = `${control.id || 'attention-field'}-error`; control.setAttribute('aria-describedby', error.id); }
    control.addEventListener(type === 'checkbox' || options ? 'change' : 'input', () => {
      const invalid = type === 'number' && (!control.value || !control.validity.valid);
      if (invalid) { state.invalidEditors.add(control); control.setAttribute('aria-invalid', 'true'); if (error) error.textContent = `${label}: enter a value from ${control.min} to ${control.max}.`; }
      else { state.invalidEditors.delete(control); control.removeAttribute('aria-invalid'); if (error) error.textContent = ''; write(options ? control.value : type === 'number' ? Number(control.value) : control.value); }
      changed();
    });
    wrap.append(control); if (help) wrap.append(text('small', help)); if (error) wrap.append(error); return wrap;
  }
  const slug = value => String(value || 'field').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
  function numeric(label, value, write, schemaKey, id, help = '') {
    const rule = state.schema[schemaKey] || {};
    const attrs = { id: `attention-${id}`, name: `attention.${id}`, min: rule.min, max: rule.max,
      step: rule.step ?? 'any', required: rule.required !== false, error: true };
    const unit = rule.unit ? ` (${rule.unit})` : '';
    return input(label, value, write, 'number', null, help || `Allowed: ${rule.min}–${rule.max}${unit}.`, attrs);
  }
  function check(label, value, write) {
    const wrap = element('label', 'check'); const control = document.createElement('input'); control.type = 'checkbox'; control.checked = !!value;
    control.addEventListener('change', () => { write(control.checked); changed(); }); wrap.append(control, text('span', label)); return wrap;
  }
  function fieldGrid(...children) { const grid = element('div', 'field-grid'); grid.append(...children); return grid; }
  function details(title, open = false) { const node = element('details', 'editor-row'); node.open = open; node.append(text('summary', title)); const body = element('div', 'editor-body'); node.append(body); return [node, body]; }
  function removeButton(label, callback) { const button = text('button', label, 'secondary delete'); button.type = 'button'; button.dataset.rebuild = ''; button.addEventListener('click', callback); return button; }
  function number(value, fallback = 0) { return Number.isFinite(Number(value)) ? Number(value) : fallback; }
  function jsonEditor(label, value, write, description) {
    const wrap = element('label'); wrap.textContent = label; const control = document.createElement('textarea'); control.value = JSON.stringify(value ?? {}, null, 2);
    const error = text('small', description || 'Structured condition. Changes are validated before save.');
    control.addEventListener('input', () => { try { write(JSON.parse(control.value)); state.invalidEditors.delete(control); control.removeAttribute('aria-invalid'); error.textContent = description || 'Condition is valid JSON.'; error.className = ''; changed(); } catch (_) { state.invalidEditors.add(control); control.closest('.grouping')?.setAttribute('open', ''); control.setAttribute('aria-invalid', 'true'); error.textContent = 'Enter valid JSON before saving.'; error.className = 'mq-field-error'; changed(); } });
    wrap.append(control, error); return wrap;
  }
  function renderPolicy() {
    const editor = $('#policy-editor'); editor.replaceChildren(); const c = state.draft;
    $('#policy-summary').textContent = `${c.enabled ? 'Enabled' : 'Disabled'} · ${c.signal_bindings.length} signal bindings · ${c.rules.length} rules · quiet ${String(c.quiet_hours.start).padStart(2, '0')}:00–${String(c.quiet_hours.end).padStart(2, '0')}:00`;
    const globals = element('div'); globals.append(text('h3', 'Policy limits'));
    globals.append(fieldGrid(
      check('Attention enabled', c.enabled, value => c.enabled = value),
      numeric('Signal TTL', c.signal_ttl, value => c.signal_ttl = number(value), 'signal_ttl', 'signal-ttl'),
      numeric('Switch margin', c.switch_margin, value => c.switch_margin = number(value), 'switch_margin', 'switch-margin'),
      numeric('Maximum signals', c.max_signals, value => c.max_signals = number(value), 'max_signals', 'max-signals'),
      numeric('History entries', c.history_limit, value => c.history_limit = number(value), 'history_limit', 'history-limit'),
      numeric('History retention', c.history_seconds, value => c.history_seconds = number(value), 'history_seconds', 'history-retention'),
      numeric('Quiet hours start', c.quiet_hours.start, value => c.quiet_hours.start = number(value), 'quiet_hours', 'quiet-hours-start', 'Local clock hour (0–23).'),
      numeric('Quiet hours end', c.quiet_hours.end, value => c.quiet_hours.end = number(value), 'quiet_hours', 'quiet-hours-end', 'Local clock hour (0–23).')
    )); editor.append(globals);
    const delivery = element('div', 'subsection'); delivery.append(text('h3', 'Delivery displays'));
    const list = element('div', 'editable-list');
    c.displays.forEach((display, index) => {
      const [row, body] = details(`${display.id} · ${display.family || 'kiosk'} · ${display.location || 'no location'}`);
      body.append(fieldGrid(
        input('Display ID', display.id, value => display.id = value),
        input('Family', display.family, value => display.family = value, 'text', [['kiosk', 'Kiosk'], ['hubs', 'Cast hubs']]),
        input('Location', display.location, value => display.location = value),
        input('Screen size', display.screen_size, value => display.screen_size = value),
        input('Orientation', display.orientation, value => display.orientation = value, 'text', [['landscape', 'Landscape'], ['portrait', 'Portrait']]),
        check('Image capable', display.supports_image, value => display.supports_image = value),
        check('Video capable', display.supports_video, value => display.supports_video = value),
        check('Animation capable', display.supports_animation, value => display.supports_animation = value),
        check('Touch capable', display.supports_touch, value => display.supports_touch = value),
        check('Audio capable', display.supports_audio, value => display.supports_audio = value),
        check('Idle', display.idle_state, value => display.idle_state = value),
        check('Visible', display.user_visible, value => display.user_visible = value),
        check('Critical capable', display.critical_capable, value => display.critical_capable = value),
        check('Available', display.available, value => display.available = value)
      )); body.append(removeButton('Remove display', () => { c.displays.splice(index, 1); renderPolicy(); changed(); })); list.append(row);
    });
    const add = text('button', 'Add delivery display', 'secondary'); add.type = 'button'; add.dataset.rebuild = ''; add.onclick = () => { c.displays.push({ id: 'display-' + (c.displays.length + 1), family: 'kiosk', location: '', supports_image: true, supports_video: false, supports_animation: true, supports_touch: false, supports_audio: false, screen_size: 'medium', orientation: 'landscape', idle_state: true, user_visible: true, critical_capable: true, available: true }); renderPolicy(); changed(); };
    delivery.append(list, add); editor.append(delivery);
  }
  function renderSignals() {
    const root = $('#signal-bindings'); root.replaceChildren(); const query = $('#signal-search').value.trim().toLowerCase();
    $('#signal-binding-count').textContent = `${state.draft.signal_bindings.length} binding${state.draft.signal_bindings.length === 1 ? '' : 's'}`;
    state.draft.signal_bindings.forEach((binding, index) => {
      if (query && !Object.values(binding).join(' ').toLowerCase().includes(query)) return;
      const [row, body] = details(`${binding.entity_id} · ${binding.category || 'household'}${binding.location ? ' · ' + binding.location : ''}`);
      body.append(fieldGrid(
        input('Entity ID', binding.entity_id, value => binding.entity_id = value),
        input('Type', binding.type || '', value => value ? binding.type = value : delete binding.type),
        input('Category', binding.category || '', value => value ? binding.category = value : delete binding.category),
        input('Location', binding.location || '', value => value ? binding.location = value : delete binding.location),
        numeric('TTL', binding.ttl ?? '', value => value ? binding.ttl = number(value) : delete binding.ttl, 'binding_ttl', `signal-binding-${index}-ttl`)
      )); body.append(removeButton('Remove binding', () => { state.draft.signal_bindings.splice(index, 1); renderSignals(); changed(); })); root.append(row);
    });
    if (!root.children.length) root.append(text('p', 'No matching bindings.', 'empty'));
  }
  function renderContexts() {
    const root = $('#context-bindings'); root.replaceChildren();
    const count = Object.keys(state.draft.context_bindings).length;
    $('#context-binding-count').textContent = `${count} binding${count === 1 ? '' : 's'}`;
    Object.entries(state.draft.context_bindings).forEach(([name, binding]) => {
      const [row, body] = details(`${name} · ${binding.entity_id}`);
      body.append(fieldGrid(
        input('Context name', name, value => { if (!value || value === name) return; state.draft.context_bindings[value] = binding; delete state.draft.context_bindings[name]; renderContexts(); }),
        input('Entity ID', binding.entity_id, value => binding.entity_id = value),
        input('Attribute', binding.attribute || '', value => value ? binding.attribute = value : delete binding.attribute),
        numeric('TTL', binding.ttl ?? '', value => value ? binding.ttl = number(value) : delete binding.ttl, 'binding_ttl', `context-binding-${slug(name)}-ttl`)
      ));
      const maps = element('div', 'subsection'); maps.append(text('h3', 'Value map'));
      maps.append(jsonEditor('Raw state → semantic value map', binding.values || {}, value => { if (Object.keys(value).length) binding.values = value; else delete binding.values; }, 'Map raw Home Assistant states to string, boolean, or numeric meanings.'));
      body.append(maps, removeButton('Remove context binding', () => { delete state.draft.context_bindings[name]; renderContexts(); changed(); })); root.append(row);
    });
    if (!root.children.length) root.append(text('p', 'No context bindings.', 'empty'));
  }
  function renderRules() {
    const root = $('#rules'); root.replaceChildren(); const query = $('#rule-search').value.trim().toLowerCase(); const displays = state.draft.displays.map(display => display.id);
    state.draft.rules.forEach((rule, index) => {
      if (query && ![rule.id, rule.title, ...Object.values(rule.match || {})].join(' ').toLowerCase().includes(query)) return;
      const [row, body] = details(`${rule.id} · ${rule.title || rule.match?.category || 'Untitled rule'}`);
      const base = fieldGrid(
        input('Rule ID', rule.id, value => rule.id = value), input('Title', rule.title, value => rule.title = value), input('Summary', rule.summary, value => rule.summary = value),
        input('Active state', rule.active_state, value => rule.active_state = value), input('Resolution state', rule.resolution_state || '', value => value ? rule.resolution_state = value : delete rule.resolution_state),
        input('Persistence', rule.persistence, value => rule.persistence = value, 'text', [['while_active', 'While active'], ['timed', 'Timed']]),
        input('Strategy', rule.strategy, value => rule.strategy = value, 'text', [['global', 'Global'], ['local', 'Local'], ['targeted', 'Targeted'], ['ambient', 'Ambient'], ['critical', 'Critical']]),
        input('Preferred scene', rule.preferred_scene, value => rule.preferred_scene = value, 'text', sceneOptions.map(value => [value, value])), input('Fallback scene', rule.fallback_scene, value => rule.fallback_scene = value, 'text', sceneOptions.map(value => [value, value])),
        input('Eligible displays', (rule.eligible_displays || []).join(', '), value => rule.eligible_displays = value.split(',').map(x => x.trim()).filter(Boolean), 'text', null, `Available: ${displays.join(', ') || 'none'}`),
        input('Grouping key', rule.grouping_key, value => rule.grouping_key = value), input('Dedupe key', rule.dedupe_key, value => rule.dedupe_key = value),
        check('Interruptible', rule.interruptibility, value => rule.interruptibility = value), check('Acknowledgement required', rule.acknowledgement_required, value => rule.acknowledgement_required = value),
        input('Acknowledgement', rule.acknowledgement, value => rule.acknowledgement = value, 'text', [['reduce', 'Reduce score'], ['suppress', 'Suppress']])
      ); body.append(base);
      const timing = element('div', 'subsection'); timing.append(text('h3', 'Scoring and timing'), fieldGrid(
        numeric('Debounce', rule.debounce, value => rule.debounce = number(value), 'debounce', `rule-${slug(rule.id)}-debounce`), numeric('Cooldown', rule.cooldown, value => rule.cooldown = number(value), 'cooldown', `rule-${slug(rule.id)}-cooldown`), numeric('Minimum display', rule.minimum_display_time, value => rule.minimum_display_time = number(value), 'minimum_display_time', `rule-${slug(rule.id)}-minimum-display`), numeric('Maximum display', rule.maximum_display_time, value => rule.maximum_display_time = number(value), 'maximum_display_time', `rule-${slug(rule.id)}-maximum-display`), numeric('Acknowledgement delta', rule.ack_delta, value => rule.ack_delta = number(value), 'ack_delta', `rule-${slug(rule.id)}-ack-delta`), numeric('Recent display delta', rule.recent_delta, value => rule.recent_delta = number(value), 'recent_delta', `rule-${slug(rule.id)}-recent-delta`), numeric('Confidence weight', rule.confidence_weight, value => rule.confidence_weight = number(value), 'confidence_weight', `rule-${slug(rule.id)}-confidence-weight`), numeric('Worsening window', rule.worsening_seconds, value => rule.worsening_seconds = number(value), 'worsening_seconds', `rule-${slug(rule.id)}-worsening-window`)
      )); body.append(timing);
      const match = element('div', 'subsection'); match.append(text('h3', 'Signal match'), fieldGrid(
        input('Type', rule.match?.type || '', value => value ? rule.match.type = value : delete rule.match.type), input('Source', rule.match?.source || '', value => value ? rule.match.source = value : delete rule.match.source), input('Category', rule.match?.category || '', value => value ? rule.match.category = value : delete rule.match.category), input('Entities', (rule.match?.entities || []).join(', '), value => { const values = value.split(',').map(x => x.trim()).filter(Boolean); values.length ? rule.match.entities = values : delete rule.match.entities; })
      )); body.append(match, renderStages(rule), renderModifiers(rule), removeButton('Remove rule', () => { state.draft.rules.splice(index, 1); renderRules(); changed(); })); root.append(row);
    });
    if (!root.children.length) root.append(text('p', 'No matching rules.', 'empty'));
  }
  function renderStages(rule) {
    const section = element('div', 'subsection'); section.append(text('h3', 'Escalation stages'));
    rule.escalation.forEach((stage, index) => { const [row, body] = details(`${stage.id} · ${stage.urgency} · priority ${stage.priority}`); body.append(fieldGrid(
      input('Stage ID', stage.id, value => stage.id = value), numeric('After', stage.after, value => stage.after = number(value), 'stage_after', `stage-${slug(stage.id)}-after`), numeric('Priority', stage.priority, value => stage.priority = number(value), 'stage_priority', `stage-${slug(stage.id)}-priority`), input('Urgency', stage.urgency, value => stage.urgency = value, 'text', urgencyOptions.map(value => [value, value])), input('Persistence override', stage.persistence || '', value => value ? stage.persistence = value : delete stage.persistence, 'text', [['', 'Use rule'], ['while_active', 'While active'], ['timed', 'Timed']])
    )); body.append(jsonEditor('Conditional escalation', stage.when || {}, value => { if (Object.keys(value).length) stage.when = value; else delete stage.when; }), removeButton('Remove stage', () => { rule.escalation.splice(index, 1); renderRules(); changed(); })); section.append(row); });
    const add = text('button', 'Add escalation stage', 'secondary'); add.type = 'button'; add.dataset.rebuild = ''; add.onclick = () => { rule.escalation.push({ id: 'stage-' + (rule.escalation.length + 1), after: 0, priority: 20, urgency: 'ACTIONABLE' }); renderRules(); changed(); }; section.append(add); return section;
  }
  function renderModifiers(rule) {
    const section = element('div', 'subsection'); section.append(text('h3', 'Score modifiers'));
    rule.modifiers.forEach((modifier, index) => { const [row, body] = details(`${modifier.id} · ${modifier.delta >= 0 ? '+' : ''}${modifier.delta}`); body.append(fieldGrid(input('Modifier ID', modifier.id, value => modifier.id = value), numeric('Score delta', modifier.delta, value => modifier.delta = number(value), 'modifier_delta', `modifier-${slug(modifier.id)}-delta`))); body.append(jsonEditor('When', modifier.when, value => modifier.when = value), removeButton('Remove modifier', () => { rule.modifiers.splice(index, 1); renderRules(); changed(); })); section.append(row); });
    const add = text('button', 'Add score modifier', 'secondary'); add.type = 'button'; add.dataset.rebuild = ''; add.onclick = () => { rule.modifiers.push({ id: 'modifier-' + (rule.modifiers.length + 1), delta: 0, when: { field: 'context.home', op: 'eq', value: true } }); renderRules(); changed(); }; section.append(add); return section;
  }
  const HISTORY_PAGE_SIZE = 40;
  let historyVisible = HISTORY_PAGE_SIZE;
  function table(root, heads, rows) { root.replaceChildren(); if (!rows.length) { root.append(text('p', 'Nothing to show.', 'empty')); return; } const table = element('table'); const head = element('tr'); heads.forEach(value => head.append(text('th', value))); table.append(head); rows.forEach(row => { const tr = element('tr'); row.forEach(value => { const cell = element('td'); cell.append(value instanceof Node ? value : text('span', String(value ?? ''))); tr.append(cell); }); table.append(tr); }); root.append(table); }
  function humanize(value) { return String(value ?? '').replace(/[_-]+/g, ' ').replace(/\b\w/g, letter => letter.toUpperCase()); }
  function historyAge(timestamp) { const seconds = Math.max(0, Math.floor(Date.now() / 1000 - Number(timestamp || 0))); if (seconds < 60) return `${seconds}s ago`; if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`; if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`; return `${Math.floor(seconds / 86400)}d ago`; }
  function historyFields(item) { const source = item.source || item.provider || item.entity_id || item.id || item.rule_id || item.display; const outcome = item.state || item.stage || item.action || item.status || item.urgency || 'Recorded'; const reserved = new Set(['at', 'kind', 'source', 'provider', 'entity_id', 'id', 'rule_id', 'display', 'state', 'stage', 'action', 'status', 'urgency']); const summary = Object.entries(item).filter(([key, value]) => !reserved.has(key) && value !== undefined && value !== null).map(([key, value]) => `${humanize(key)}: ${typeof value === 'object' ? JSON.stringify(value) : String(value)}`).join(' · '); return { source: source ? String(source) : 'System', outcome: humanize(outcome), summary: summary || 'No additional summary supplied' }; }
  function historyDisclosureLabel(item, stampText) {
    const descriptors = [];
    const add = (label, value) => {
      if (value === undefined || value === null || value === '') return;
      const text = String(value);
      if (!descriptors.some(entry => entry.toLowerCase() === text.toLowerCase())) descriptors.push(`${label} ${text}`);
    };
    add('source', item.source || item.provider || item.entity_id);
    add('id', item.id || item.rule_id);
    add('context', item.context || item.context_id || item.category || item.location);
    add('display', item.display || item.display_id || item.target_display || item.target);
    const identity = descriptors.length ? ` — ${descriptors.join(' · ')}` : '';
    return `View full payload for ${humanize(item.kind || 'event')}${identity} at ${stampText}`;
  }
  function renderHistory(root, history, status = '') {
    root.replaceChildren(); if (status) { root.append(text('p', status, 'diagnostic-state error')); return; }
    if (!Array.isArray(history)) { root.append(text('p', 'History is unavailable: the response did not contain a valid event list.', 'diagnostic-state error')); return; }
    if (!history.length) { root.append(text('p', 'No recent attention history.', 'empty')); return; }
    const list = element('div', 'history-list'); history.slice(0, historyVisible).forEach(item => { const fields = historyFields(item); const row = element('article', 'history-row'); const identity = element('div', 'history-identity'); const stamp = text('time', `${new Date(Number(item.at || 0) * 1000).toLocaleString()} · ${historyAge(item.at)}`, 'history-time'); stamp.dateTime = new Date(Number(item.at || 0) * 1000).toISOString(); identity.append(stamp, text('strong', humanize(item.kind || 'event'), 'history-kind')); row.append(identity, text('span', fields.source, 'history-source'), text('span', fields.outcome, 'history-outcome'), text('span', fields.summary, 'history-summary')); const disclosure = element('details', 'history-details'); const summary = text('summary', 'View full event payload'); summary.setAttribute('aria-label', historyDisclosureLabel(item, stamp.textContent)); disclosure.append(summary, text('pre', JSON.stringify(item, null, 2), 'history-payload')); row.append(disclosure); list.append(row); }); root.append(list);
    if (historyVisible < history.length) { const controls = element('div', 'history-controls'); controls.append(text('span', `Showing ${Math.min(historyVisible, history.length)} of ${history.length} events. Older events remain available.`)); const more = text('button', 'Show older events', 'secondary'); more.type = 'button'; more.setAttribute('aria-label', `Show older attention history events after ${Math.min(historyVisible, history.length)} shown`); more.onclick = () => { historyVisible += HISTORY_PAGE_SIZE; renderHistory(root, history); }; controls.append(more); root.append(controls); } else if (history.length > HISTORY_PAGE_SIZE) root.append(text('p', `Showing all ${history.length} retained events.`, 'history-count'));
  }
  function renderDiagnosticsUnavailable(message) { ['active-items', 'signals', 'display-decisions', 'context'].forEach(id => { const root = $('#' + id); root.replaceChildren(text('p', `Diagnostics unavailable: ${message}`, 'diagnostic-state error')); }); renderHistory($('#history'), null, `History unavailable: ${message}`); }
  function renderDiagnostics(data) {
    $('#active-count').textContent = data.items.length; $('#signal-count').textContent = data.signals.filter(item => item.fresh).length; $('#display-count').textContent = (data.config?.displays || []).length; $('#policy-state').textContent = data.enabled ? 'Enabled' : 'Off';
    const active = $('#active-items'); active.replaceChildren(); if (!data.items.length) active.append(text('p', 'No active household attention.', 'empty'));
    data.items.forEach(item => { const row = element('article', 'item-row'); const top = element('div', 'item-top'); top.append(text('strong', item.title || item.id, 'item-title'), text('span', `${item.urgency} · ${item.score}`, 'pill ' + (item.urgency === 'CRITICAL' ? 'critical' : ''))); const identity = item.identity ? [item.identity.label, item.identity.location].filter(Boolean).join(' · ') : ''; row.append(top, text('p', `${identity ? identity + ' · ' : ''}${item.lifecycle}${item.suppression ? ' · ' + item.suppression : ''}${item.summary ? ' · ' + item.summary : ''}`, 'item-detail')); const actions = element('div', 'inline-actions'); ['acknowledge', 'suppress'].forEach(action => { const button = text('button', action === 'acknowledge' ? 'Acknowledge' : 'Suppress', 'secondary'); button.disabled = action === 'suppress' && item.urgency === 'CRITICAL'; button.onclick = async () => { try { await request('/api/attention/action', 'POST', { id: item.id, action }); await refresh(); } catch (error) { setStatus(error.message, 'error'); } }; actions.append(button); }); row.append(actions); active.append(row); });
    table($('#signals'), ['Signal', 'State', 'Age', 'Freshness'], data.signals.map(item => [item.id, item.state, `${Math.floor(item.duration || 0)}s`, item.fresh ? `Fresh until ${new Date(item.expires_at * 1000).toLocaleTimeString()}` : 'Expired']));
    historyVisible = Math.min(Math.max(historyVisible, HISTORY_PAGE_SIZE), Array.isArray(data.history) ? data.history.length : HISTORY_PAGE_SIZE);
    renderHistory($('#history'), data.history, data.history_status === 'error' ? (data.history_error || 'The history source reported an error.') : '');
    const decisions = $('#display-decisions'); decisions.replaceChildren(); Object.entries(data.displays).forEach(([id, display]) => { const row = document.createElement('details'); row.append(text('summary', `${id} — ${display.winner?.title || display.winner?.id || 'Ambient fallback'}`), text('p', display.reason || 'No decision reason supplied', 'item-detail'), text('pre', JSON.stringify(display, null, 2))); decisions.append(row); });
    $('#context').textContent = JSON.stringify(data.context, null, 2);
  }
  async function refresh() {
    try {
      const data = await request('/api/attention');
      state.schema = data.input_schema || state.schema;
      const replaceDraft = !state.dirty || state.conflict;
      state.diagnostics = data;
      if (replaceDraft) {
        const wasConflict = state.conflict;
        state.base = clone(data.config); state.draft = clone(data.config); state.conflict = false; state.invalidEditors.clear();
        renderPolicy(); renderSignals(); renderContexts(); renderRules(); $('#discard').textContent = 'Discard changes';
        changed();
        if (wasConflict) $('#save-status').textContent = 'Loaded the newer policy; your stale draft was discarded.';
      }
      renderDiagnostics(data);
      setStatus(data.enabled ? `Updated ${new Date().toLocaleTimeString()}` : 'Attention policy disabled');
    } catch (error) { renderDiagnosticsUnavailable(error.message); setStatus(error.message, 'error'); }
  }
  function addRule() { state.draft.rules.push({ id: 'rule-' + (state.draft.rules.length + 1), title: 'New household attention', summary: '', match: { category: 'household' }, active_state: 'on', debounce: 0, cooldown: 300, persistence: 'while_active', interruptibility: true, minimum_display_time: 15, maximum_display_time: 0, acknowledgement_required: false, acknowledgement: 'reduce', ack_delta: -30, recent_delta: -15, confidence_weight: 20, worsening_seconds: 300, strategy: 'global', eligible_displays: [], preferred_scene: 'attention', fallback_scene: 'attention', grouping_key: '', dedupe_key: '', modifiers: [], escalation: [{ id: 'active', after: 0, priority: 20, urgency: 'ACTIONABLE' }] }); renderRules(); changed(); }
  $('#refresh').onclick = refresh; $('#signal-search').oninput = renderSignals; $('#rule-search').oninput = renderRules;
  $('#add-signal').onclick = () => { state.draft.signal_bindings.push({ entity_id: 'binary_sensor.new_binding', category: 'household', location: '' }); renderSignals(); changed(); };
  $('#add-context').onclick = () => { state.draft.context_bindings['new_context'] = { entity_id: 'sensor.new_context' }; renderContexts(); changed(); };
  $('#add-rule').onclick = addRule;
  $('[data-expand="policy-editor"]').onclick = () => { const editor = $('#policy-editor'); editor.hidden = !editor.hidden; };
  $('#discard').onclick = async () => {
    if (state.conflict) {
      lockEditing(true); $('#save-status').textContent = 'Loading the newer attention policy…';
      try {
        const latest = await request('/api/attention');
        state.base = clone(latest.config); state.draft = clone(latest.config); state.conflict = false; state.invalidEditors.clear();
        renderDiagnostics(latest); $('#save-status').textContent = 'Loaded the newer policy; your stale draft was discarded.';
      } catch (error) { $('#save-status').textContent = error.message; $('#save-status').className = 'mq-field-error'; }
      finally { lockEditing(false); }
      if (!state.conflict) { renderPolicy(); renderSignals(); renderContexts(); renderRules(); $('#discard').textContent = 'Discard changes'; }
      return;
    }
    state.invalidEditors.clear(); state.draft = clone(state.base); renderPolicy(); renderSignals(); renderContexts(); renderRules(); $('#discard').textContent = 'Discard changes'; changed(); $('#save-status').textContent = 'Draft discarded.';
  };
  $('#save').onclick = async () => {
    if (state.invalidEditors.size) { $('#save-status').textContent = 'Fix each invalid field or JSON condition before saving.'; $('#save-status').className = 'mq-field-error'; document.querySelector('[aria-invalid="true"]')?.focus(); return; }
    lockEditing(true); $('#save-status').textContent = 'Checking for newer policy changes…'; $('#save-status').className = '';
    try {
      const latest = await request('/api/attention');
      if (!same(latest.config, state.base)) { state.conflict = true; $('#discard').textContent = 'Reload latest policy'; throw new Error('Attention policy changed elsewhere. Reload the latest policy before saving.'); }
      const submitted = clone(state.draft);
      $('#save-status').textContent = 'Validating and saving…';
      await request('/api/attention/config', 'PUT', submitted);
      state.base = clone(submitted); state.draft = clone(submitted); changed();
      $('#save-status').textContent = 'Attention policy saved. Live observations refreshed.';
      await refresh();
    } catch (error) { $('#save-status').textContent = error.message; $('#save-status').className = 'mq-field-error'; }
    finally { lockEditing(false); }
  };
  window.addEventListener('beforeunload', event => { if (state.dirty) { event.preventDefault(); event.returnValue = ''; } });
  refresh();
})();
