(() => {
  'use strict';
  const $ = selector => document.querySelector(selector);
  const state = { pending: false };
  const option = (value, label) => { const node = document.createElement('option'); node.value = value; node.textContent = label; return node; };
  function message(value, type = '') { const node = $('#message'); node.textContent = value; node.className = 'status ' + type; }
  async function request(path, method = 'GET', body) {
    const response = await fetch(path, body === undefined ? { method } : { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || `Request failed (${response.status})`);
    return data;
  }
  function updateDestination() { $('#cast-row').hidden = $('#destination').value === 'live'; }
  function setPending(pending) {
    state.pending = pending;
    ['show', 'clear', 'refresh'].forEach(id => { $('#' + id).disabled = pending; });
  }
  function renderScreens(data) {
    const screen = $('#screen'); screen.replaceChildren();
    (data.candidates || []).forEach(item => screen.append(option(`candidate:${item.id}`, `Live data · ${(item.source || item.provider || 'provider').toUpperCase()} · ${item.title}`)));
    (data.samples || []).forEach(item => screen.append(option(`sample:${item.id}`, `Sample · ${(item.provider || '').toUpperCase()} · ${item.title}`)));
    if (!screen.children.length) screen.append(option('', 'No test screens are available'));
    const active = data.active || []; $('#active-test').textContent = active.length ? `Active: ${active.map(item => item.title || item.id).join(', ')}.` : 'No temporary test is active.';
  }
  function renderDevices(data) {
    const cast = $('#cast'); cast.replaceChildren(); const displays = (data.devices || []).filter(item => !String(item.model || '').toLowerCase().includes('audio'));
    displays.forEach(item => { const node = option(item.ip, `${item.name || item.ip} · ${item.ip}`); node.selected = item.ip === data.current; cast.append(node); });
    if (!cast.children.length) cast.append(option('', 'No Cast displays discovered'));
  }
  async function load(announce = true) {
    if (announce) message('Loading available screens…');
    try { const [screens, devices] = await Promise.all([request('/api/screen-test'), request('/devices').catch(() => ({ devices: [] }))]); renderScreens(screens); renderDevices(devices); if (announce) message((screens.active || []).length ? 'A temporary test is active.' : 'Choose a screen to preview.'); }
    catch (error) { message(error.message, 'error'); throw error; } finally { updateDestination(); }
  }
  async function refresh() { setPending(true); try { await load(); } finally { setPending(false); } }
  $('#destination').addEventListener('change', updateDestination); $('#refresh').onclick = refresh;
  $('#show').onclick = async () => {
    const selected = $('#screen').value; const separator = selected.indexOf(':');
    if (separator <= 0) return message('Select an available screen first.', 'error');
    const kind = selected.slice(0, separator); const id = selected.slice(separator + 1);
    if (!id) return message('Select an available screen first.', 'error');
    const payload = { destination: $('#destination').value, durationSeconds: Number($('#duration').value), castTarget: $('#cast').value };
    payload[kind === 'candidate' ? 'candidateId' : 'sampleId'] = id;
    setPending(true); message('Starting temporary screen…');
    try { const result = await request('/api/screen-test', 'POST', payload); await load(false); message(`Showing ${result.context.title}.`, 'success'); }
    catch (error) { message(error.message, 'error'); } finally { setPending(false); }
  };
  $('#clear').onclick = async () => { setPending(true); try { const result = await request('/api/screen-test', 'DELETE'); await load(false); message(`Cleared ${result.removed} temporary screen${result.removed === 1 ? '' : 's'}.`, 'success'); } catch (error) { message(error.message, 'error'); } finally { setPending(false); } };
  refresh();
})();
