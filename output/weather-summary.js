/* Compact dashboard weather copy derived from the authoritative HA forecast. */
(function (root) {
  function nearTermRainSummary(hourly, now) {
    const row = Array.isArray(hourly)
      ? hourly.find(item => Number.isFinite(item?.precipitation_probability)
        && item.precipitation_probability >= 30)
      : null;
    if (!row) return '';

    const chance = Math.round(row.precipitation_probability);
    const at = Date.parse(row.datetime);
    if (!Number.isFinite(at)) return `Rain ${chance}%`;

    const minutes = Math.round((at - (now ?? Date.now())) / 60000);
    if (minutes >= 0 && minutes < 60) return `Rain ${chance}% within the hour`;
    if (minutes >= 60 && minutes <= 24 * 60) {
      const hours = Math.round(minutes / 60);
      return `Rain ${chance}% in about ${hours} hour${hours === 1 ? '' : 's'}`;
    }
    return `Rain ${chance}%`;
  }

  const api = {nearTermRainSummary};
  root.MarqueeWeatherSummary = api;
  if (typeof module !== 'undefined') module.exports = api;
})(typeof window !== 'undefined' ? window : globalThis);
