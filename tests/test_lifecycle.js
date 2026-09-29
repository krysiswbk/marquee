const assert = require('assert');
const fs = require('fs');
const vm = require('vm');

class Target {
  constructor() { this.listeners = new Map(); }
  addEventListener(type, fn) { if (!this.listeners.has(type)) this.listeners.set(type, new Set()); this.listeners.get(type).add(fn); }
  removeEventListener(type, fn) { this.listeners.get(type)?.delete(fn); }
  dispatch(type) { for (const fn of this.listeners.get(type) || []) fn(); }
}
const document = new Target();
document.hidden = false; document.visibilityState = 'visible';
document.getElementById = () => null;
document.createElement = () => ({setAttribute(){}, dataset:{}, style:{}});
document.body = {append(){}};
const window = new Target();
const context = {window, document, AbortController, setTimeout, clearTimeout, Promise, console};
vm.runInNewContext(fs.readFileSync('output/lifecycle.js', 'utf8'), context);
const lifecycle = window.MarqueeLifecycle;
let active = 0, maximum = 0, completed = 0;
const gate = [];
const handle = lifecycle.register('resource', {interval: 0, refresh: ({signal, isCurrent}) => new Promise(resolve => {
  active++; maximum = Math.max(maximum, active);
  gate.push(() => { if (isCurrent()) completed++; active--; resolve(); });
  signal.addEventListener('abort', () => { active--; resolve(); }, {once: true});
})});

setTimeout(() => {
  assert.strictEqual(active, 1, 'initial refresh starts');
  handle.request(); handle.request();
  assert.strictEqual(maximum, 1, 'repeated requests do not overlap');
  document.hidden = true; document.visibilityState = 'hidden'; document.dispatch('visibilitychange');
  assert.strictEqual(active, 0, 'hidden transition aborts active work');
  document.hidden = false; document.visibilityState = 'visible';
  document.dispatch('visibilitychange'); document.dispatch('pageshow'); document.dispatch('pageshow');
  setTimeout(() => {
    assert.strictEqual(maximum, 1, 'resume events coalesce');
    gate.splice(0).forEach(done => done());
    lifecycle.destroy();
    assert.strictEqual(lifecycle.inspect().length, 0, 'cleanup removes owned resources');
    console.log('lifecycle: overlap, suspension, resume, and cleanup assertions passed');
  }, 10);
}, 10);
