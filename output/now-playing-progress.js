/* Deterministic client-side reconciliation for the authoritative media payload. */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  root.MarqueeNowPlayingProgress = api;
}(typeof globalThis === 'object' ? globalThis : this, function () {
  // The media poll interval is about one second. Two seconds absorbs a small
  // source-reporting wobble while still allowing an intentional larger seek.
  const SOURCE_JITTER_TOLERANCE_MS = 2000;

  function finite(value) {
    return Number.isFinite(Number(value)) ? Number(value) : null;
  }

  function clamp(value, duration) {
    const upper = duration > 0 ? duration : Number.POSITIVE_INFINITY;
    return Math.max(0, Math.min(value, upper));
  }

  function identity(payload) {
    return payload.key || ((payload.title || '') + '|' + (payload.subtitle || ''));
  }

  function estimate(previous, now, duration) {
    if (!previous || previous.progress == null) return null;
    const base = finite(previous.displayedOffsetMs);
    if (base == null) return null;
    const elapsed = previous.state === 'playing'
      ? Math.max(0, now - previous.fetchedAt) : 0;
    return clamp(base + elapsed, duration);
  }

  /**
   * Reconcile one payload at fetch time.
   *
   * The returned `displayedOffsetMs` is the offset actually shown at
   * `fetchedAt`, not merely the last source offset. Same-item playing payloads
   * compare their incoming offset with the prior displayed/estimated offset;
   * a backward delta <= 2000ms is source jitter and is suppressed. A larger
   * backward delta is a deliberate seek and is accepted. Paused payloads are
   * authoritative and never extrapolate. Idle/unavailable clears all state.
   */
  function reconcile(payload, previous, now) {
    now = finite(now) == null ? Date.now() : Number(now);
    if (!payload || payload.playing !== true ||
        payload.state === 'unavailable' || payload.availability === 'unavailable') {
      return {key: null, state: 'idle', progress: null, fetchedAt: now,
        displayedOffsetMs: 0};
    }
    const key = identity(payload);
    const state = payload.state || 'playing';
    const incoming = finite(payload.progress && payload.progress.offsetMs);
    const duration = finite(payload.progress && payload.progress.durationMs) || 0;
    const sameItem = previous && previous.key === key;
    const priorEstimate = sameItem ? estimate(previous, now, duration) : null;
    let displayed = incoming;
    if (sameItem && state === 'playing') {
      if (priorEstimate != null && (incoming == null ||
          (incoming < priorEstimate && priorEstimate - incoming <= SOURCE_JITTER_TOLERANCE_MS))) {
        displayed = priorEstimate;
      }
    } else if (sameItem && state === 'paused' && incoming == null) {
      displayed = finite(previous.displayedOffsetMs);
    }
    const progress = payload.progress && displayed != null
      ? Object.assign({}, payload.progress, {offsetMs: clamp(displayed, duration)}) : null;
    return {key, state, progress, fetchedAt: now,
      displayedOffsetMs: progress ? progress.offsetMs : 0};
  }

  return {SOURCE_JITTER_TOLERANCE_MS, reconcile};
}));
