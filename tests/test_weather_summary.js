const test = require('node:test');
const assert = require('node:assert/strict');
const {nearTermRainSummary} = require('../output/weather-summary.js');

const NOW = Date.parse('2026-09-28T12:00:00Z');

test('renders a complete near-term horizon from the authoritative forecast time', () => {
  assert.equal(nearTermRainSummary([
    {datetime: '2026-09-28T13:30:00Z', precipitation_probability: 40},
  ], NOW), 'Rain 40% in about 2 hours');
});

test('uses complete language for a forecast within the hour', () => {
  assert.equal(nearTermRainSummary([
    {datetime: '2026-09-28T12:20:00Z', precipitation_probability: 40},
  ], NOW), 'Rain 40% within the hour');
});

test('omits timing when the authoritative row has no usable time', () => {
  assert.equal(nearTermRainSummary([
    {datetime: null, precipitation_probability: 40},
  ], NOW), 'Rain 40%');
});

test('omits the signal when precipitation probability is unavailable', () => {
  assert.equal(nearTermRainSummary([
    {datetime: '2026-09-28T13:30:00Z', precipitation_probability: null},
  ], NOW), '');
});
