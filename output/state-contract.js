/* Small cross-surface contract for provider-backed browser resources. */
(() => {
  const states = Object.freeze(['loading', 'empty', 'stale', 'partial', 'disconnected', 'error', 'ready']);
  const labels = Object.freeze({
    loading: 'Loading', empty: 'Nothing here yet', stale: 'Last known data · stale',
    partial: 'Some data unavailable', disconnected: 'Connection unavailable',
    error: 'Source error', ready: ''
  });
  function resolve({loading = false, error = false, disconnected = false, stale = false,
    partial = false, empty = false, hasData = false} = {}) {
    if (disconnected) return 'disconnected';
    if (error && !hasData) return 'error';
    if (loading && !hasData) return 'loading';
    if (stale && hasData) return 'stale';
    if (partial && hasData) return 'partial';
    if (error) return hasData ? 'partial' : 'error';
    if (empty || (!hasData && !loading)) return 'empty';
    return 'ready';
  }
  function resource(resource) {
    const hasData = resource?.snapshot !== null && resource?.snapshot !== undefined;
    return resolve({loading: resource?.phase === 'loading' || resource?.phase === 'fetching',
      error: Boolean(resource?.error), stale: resource?.phase === 'stale' || resource?.stale,
      partial: resource?.phase === 'partial' || resource?.state === 'degraded',
      disconnected: resource?.phase === 'disconnected', empty: resource?.empty, hasData});
  }
  window.MarqueeState = Object.freeze({states, labels, resolve, resource});
})();
