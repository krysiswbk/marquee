/* Shared lifecycle coordinator for long-running Live/Kiosk browser work. */
(() => {
  if (window.MarqueeLifecycle) return;
  const records = new Map();
  let suspended = document.visibilityState === 'hidden';
  let destroyed = false;
  let listeners = [];

  const active = () => !destroyed && !suspended && !document.hidden;
  const listen = (target, type, handler, options) => {
    target.addEventListener(type, handler, options);
    listeners.push(() => target.removeEventListener(type, handler, options));
  };
  const stop = record => {
    if (record.timer !== null) { clearTimeout(record.timer); record.timer = null; }
    record.epoch++;
    record.controller?.abort();
    record.controller = null;
    record.running = false;
    record.pending = false;
  };
  const schedule = (record, delay = 0) => {
    if (!active() || record.timer !== null || record.running) return;
    record.timer = setTimeout(() => {
      record.timer = null;
      run(record);
    }, Math.max(0, delay));
  };
  const run = record => {
    if (!active() || record.running) { if (active()) record.pending = true; return; }
    record.running = true;
    record.pending = false;
    const epoch = ++record.epoch;
    const controller = new AbortController();
    record.controller = controller;
    const guard = {
      signal: controller.signal,
      epoch,
      isCurrent: () => active() && records.get(record.name) === record && record.epoch === epoch && !controller.signal.aborted,
    };
    Promise.resolve().then(() => record.refresh(guard)).catch(error => {
      if (error?.name !== 'AbortError' && guard.isCurrent()) record.onError?.(error);
    }).finally(() => {
      if (records.get(record.name) !== record || record.epoch !== epoch) return;
      record.running = false;
      record.controller = null;
      if (record.pending && active()) {
        record.pending = false;
        schedule(record);
      } else if (active() && record.interval > 0) schedule(record, record.interval);
    });
  };
  const resume = () => {
    if (destroyed || document.hidden) return;
    if (!suspended) return;
    suspended = false;
    for (const record of records.values()) {
      record.controller?.abort();
      record.epoch++;
      record.pending = false;
      schedule(record);
    }
  };
  const suspend = () => {
    if (destroyed || suspended) return;
    suspended = true;
    for (const record of records.values()) stop(record);
  };
  listen(document, 'visibilitychange', () => document.hidden ? suspend() : resume());
  listen(window, 'pagehide', suspend);
  listen(window, 'pageshow', resume);
  listen(window, 'beforeunload', () => api.destroy());
  listen(window, 'unload', () => api.destroy());

  const api = {
    register(name, options = {}) {
      if (records.has(name)) records.get(name).dispose();
      const record = {name, refresh: options.refresh || (() => {}), onError: options.onError,
        interval: Number(options.interval) || 0, timer: null, controller: null,
        epoch: 0, running: false, pending: false};
      records.set(name, record);
      schedule(record);
      return {
        request() { if (!active()) return; if (record.running) record.pending = true; else schedule(record); },
        dispose() { if (records.get(name) !== record) return; stop(record); records.delete(name); },
      };
    },
    request(name) {
      const record = records.get(name);
      if (!record) return;
      if (record.running) record.pending = true;
      else schedule(record);
    },
    status(message, kind = 'error') {
      let node = document.getElementById('marquee-lifecycle-status');
      if (!node) { node = document.createElement('div'); node.id = 'marquee-lifecycle-status'; node.setAttribute('role', 'status'); node.setAttribute('aria-live', 'polite'); document.body.append(node); }
      node.dataset.kind = kind; node.textContent = message; node.hidden = !message;
    },
    isActive: active,
    inspect() { return [...records.values()].map(r => ({name: r.name, timer: r.timer !== null, running: r.running, listeners: listeners.length})); },
    destroy() {
      if (destroyed) return;
      destroyed = true;
      for (const record of records.values()) stop(record);
      records.clear(); listeners.splice(0).forEach(remove => remove());
    },
  };
  window.MarqueeLifecycle = api;
})();
