const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const source = fs.readFileSync('output/state-contract.js', 'utf8');
const context = {window: {}, console};
vm.runInNewContext(source, context);
const state = context.window.MarqueeState;

test('shared state vocabulary covers every platform resilience state', () => {
  assert.deepEqual(Array.from(state.states), ['loading', 'empty', 'stale', 'partial', 'disconnected', 'error', 'ready']);
});

test('state precedence preserves useful stale data and distinguishes empty', () => {
  assert.equal(state.resolve({loading: true}), 'loading');
  assert.equal(state.resolve({empty: true}), 'empty');
  assert.equal(state.resolve({stale: true, hasData: true}), 'stale');
  assert.equal(state.resolve({partial: true, hasData: true}), 'partial');
  assert.equal(state.resolve({error: true}), 'error');
  assert.equal(state.resolve({disconnected: true, hasData: true}), 'disconnected');
});

test('resource snapshots become stale instead of disappearing after refresh failure', () => {
  assert.equal(state.resource({phase: 'stale', snapshot: {events: []}, error: Error('offline')}), 'stale');
  assert.equal(state.resource({phase: 'loading', snapshot: null}), 'loading');
  assert.equal(state.resource({phase: 'disconnected', snapshot: null, error: Error('offline')}), 'disconnected');
});
