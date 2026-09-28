const assert = require('assert');
const {reconcile, SOURCE_JITTER_TOLERANCE_MS} =
  require('../output/now-playing-progress.js');

const item = (offsetMs, state = 'playing', key = 'episode-1') => ({
  playing: true, state, key, progress: {offsetMs, durationMs: 20000},
});
const at = (payload, previous, now) => reconcile(payload, previous, now);

assert.strictEqual(SOURCE_JITTER_TOLERANCE_MS, 2000);
let state = at(item(1000), null, 0);
state = at(item(4000), state, 3000);
assert.strictEqual(state.progress.offsetMs, 4000,
  'elapsed playback must use the prior displayed estimate before accepting the poll');
state = at(item(4500), state, 4000);
assert.strictEqual(state.progress.offsetMs, 5000,
  'a small backward source jitter must not rewind the displayed estimate');
state = at(item(2000), state, 5000);
assert.strictEqual(state.progress.offsetMs, 2000,
  'a backward seek larger than the tolerance must be accepted');

state = at(item(7000, 'paused'), state, 6000);
assert.strictEqual(state.progress.offsetMs, 7000, 'paused source offset is authoritative');
state = at(item(7000, 'paused'), state, 9000);
assert.strictEqual(state.progress.offsetMs, 7000, 'paused progress must not extrapolate');
state = at(item(3000, 'paused'), state, 10000);
assert.strictEqual(state.progress.offsetMs, 3000, 'paused seek updates the stationary position');

state = at(item(1000, 'playing', 'episode-2'), state, 11000);
assert.strictEqual(state.progress.offsetMs, 1000, 'a new media identity accepts its own offset');
state = at({playing: false, state: 'idle', availability: 'idle'}, state, 12000);
assert.deepStrictEqual(state, {key: null, state: 'idle', progress: null, fetchedAt: 12000,
  displayedOffsetMs: 0});
state = at(item(900, 'playing', 'episode-3'), state, 13000);
assert.strictEqual(state.progress.offsetMs, 900, 'recovery accepts the recovered item normally');

console.log('now-playing-progress: 9 transition assertions passed');
