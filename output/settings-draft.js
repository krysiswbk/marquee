/* Shared persistence for the two layout editors. Previewing never writes. */
(() => {
  const metadata = new Set(['envBackend', 'customBackdropAvailable', 'customBackdropVersion']);
  const maps = new Set(['blockLayout', 'blockVisibility', 'liveLayout', 'liveVisibility']);
  const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
  const editable = key => !metadata.has(key) && !key.endsWith('Set');
  function changes(base, draft) {
    return Object.fromEntries(Object.entries(draft).filter(([key, value]) =>
      editable(key) && !same(value, base[key])));
  }
  async function json(url, options) {
    const response = await fetch(url, options);
    const result = await response.json();
    if (!response.ok || result.ok === false) throw new Error(result.error || `Request failed (${response.status})`);
    return result;
  }
  window.MarqueeDraft = {
    changes,
    async save(endpoint, base, draft, secrets = {}) {
      const patch = changes(base, draft);
      const latest = await json(endpoint === '/settings' ? '/settings.json' : '/live-settings.json');
      const conflicts = Object.keys(patch).filter(key => !same(latest[key], base[key]));
      if (conflicts.length) throw new Error('These settings changed in another page. Discard to reload before saving: ' + conflicts.join(', '));
      Object.assign(patch, secrets);
      if (!Object.keys(patch).length) return latest;
      const replace = Object.keys(patch).filter(key => maps.has(key));
      const result = await json(endpoint + (replace.length ? '?replace=' + replace.join(',') : ''), {
        method: 'PATCH', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(patch)
      });
      return result.settings;
    },
    freeze(busy) {
      document.querySelectorAll('button,input,select,textarea').forEach(control => {
        if (busy) { control.dataset.draftDisabled = String(control.disabled); control.disabled = true; }
        else { control.disabled = control.dataset.draftDisabled === 'true'; delete control.dataset.draftDisabled; }
      });
      document.querySelectorAll('iframe').forEach(frame => {
        frame.style.pointerEvents = busy ? 'none' : '';
        frame.inert = busy;
      });
    }
  };
})();
