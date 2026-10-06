/* Compact dashboard weather copy derived from the authoritative HA forecast. */
(function (root) {
  function amount(row, kind) {
    const names = kind === 'snow'
      ? ['snowfall', 'snowfall_amount', 'snowfall_cm', 'snow_accumulation']
      : ['precipitation', 'precipitation_amount', 'precipitation_mm', 'rain'];
    const value = names.map(name => row?.[name]).find(value => Number.isFinite(Number(value)));
    const numeric = Number(value);
    if (!Number.isFinite(numeric) || numeric <= 0) return '';
    const unit = kind === 'snow' ? 'cm' : 'mm';
    return `${numeric < 10 ? numeric.toFixed(1).replace(/\.0$/, '') : Math.round(numeric)} ${unit} expected`;
  }

  function nearTermPrecipSummary(hourly, now) {
    const row = Array.isArray(hourly)
      ? hourly.find(item => Number.isFinite(item?.precipitation_probability)
        && item.precipitation_probability >= 30)
      : null;
    if (!row) return '';

    const chance = Math.round(row.precipitation_probability);
    const snow = [71, 73, 75, 77, 85, 86].includes(Number(row.weather_code))
      || /snow/i.test(String(row.condition || ''));
    const label = snow ? 'Snow' : 'Rain';
    const expected = amount(row, snow ? 'snow' : 'rain');
    const at = Date.parse(row.datetime);
    const suffix = expected ? ` · ${expected}` : '';
    if (!Number.isFinite(at)) return `${label} ${chance}%${suffix}`;

    const minutes = Math.round((at - (now ?? Date.now())) / 60000);
    if (minutes >= 0 && minutes < 60) return `${label} ${chance}% within the hour${suffix}`;
    if (minutes >= 60 && minutes <= 24 * 60) {
      const hours = Math.round(minutes / 60);
      return `${label} ${chance}% in about ${hours} hour${hours === 1 ? '' : 's'}${suffix}`;
    }
    return `${label} ${chance}%${suffix}`;
  }

  const api = {nearTermRainSummary: nearTermPrecipSummary, nearTermPrecipSummary};
  root.MarqueeWeatherSummary = api;
  if (typeof module !== 'undefined') module.exports = api;
})(typeof window !== 'undefined' ? window : globalThis);
