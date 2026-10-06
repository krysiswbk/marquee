/* Optional, source-grounded ambient sky. Missing fields intentionally render nothing. */
(() => {
  const root = document.getElementById('sky-layer'), art = document.getElementById('sky-art');
  if (!root || !art) return;
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const n = (value, low, high) => Number.isFinite(Number(value)) && Number(value) >= low && Number(value) <= high ? Number(value) : null;
  const stars = [[84,64],[146,118],[218,44],[278,91],[347,55],[412,136],[486,68],[557,112],[638,44],[704,88],[781,55],[864,126],[938,72],[1000,153],[120,218],[244,182],[382,231],[530,196],[690,224],[835,188],[962,246]];
  const phaseName = value => String(value || '').toLowerCase().replace(/[\s-]+/g, '_');
  const phaseShape = phase => {
    const shadow = '#646b7b';
    if (phase === 'new_moon') return `<circle class="sky-moon-shadow" r="25" fill="${shadow}"/>`;
    if (phase === 'first_quarter' || phase === 'waxing_quarter') return `<path class="sky-moon-shadow" d="M-25-25H0V25H-25Z" fill="${shadow}"/>`;
    if (phase === 'last_quarter' || phase === 'third_quarter' || phase === 'waning_quarter') return `<path class="sky-moon-shadow" d="M0-25H25V25H0Z" fill="${shadow}"/>`;
    if (phase === 'waxing_crescent') return `<circle class="sky-moon-shadow" cx="-11" r="25" fill="${shadow}"/>`;
    if (phase === 'waning_crescent') return `<circle class="sky-moon-shadow" cx="11" r="25" fill="${shadow}"/>`;
    if (phase === 'waxing_gibbous') return `<circle class="sky-moon-shadow" cx="-9" r="25" fill="${shadow}"/>`;
    if (phase === 'waning_gibbous') return `<circle class="sky-moon-shadow" cx="9" r="25" fill="${shadow}"/>`;
    return '';
  };
  function position(bearing, elevation) { return {x: 512 + Math.sin(bearing * Math.PI / 180) * 430, y: 280 - elevation * 2.2}; }
  function render(weather) {
    const sky = weather?.sky || {}, sun = sky.sun || {}, day = typeof sun.is_day === 'boolean' ? sun.is_day : weather?.isDay;
    const isNight = day === false || (day == null && String(weather?.condition || '').toLowerCase() === 'clear-night');
    document.body.classList.toggle('sky-night', isNight);
    document.body.classList.toggle('sky-day', !isNight);
    const cloud = n(sky.cloud_cover, 0, 100), condition = String(sky.condition || weather?.condition || '').toLowerCase();
    const cloudy = cloud != null ? cloud : /cloud|overcast|fog/.test(condition) ? 70 : /rain|snow|storm/.test(condition) ? 85 : 0;
    root.dataset.mode = isNight ? 'night' : 'day'; root.style.setProperty('--sky-cloud', `${Math.min(1, cloudy / 100)}`);
    const starArt = isNight ? stars.map(([x,y], i) => `<circle class="sky-star" cx="${x}" cy="${y}" r="${i % 3 ? 1.2 : 1.8}"/>`).join('') : '';
    let moonArt = '';
    const moon = sky.moon || {}, phase = phaseName(moon.phase), bearing = n(moon.azimuth, 0, 360), elevation = n(moon.elevation, -90, 90), illumination = n(moon.illumination, 0, 1);
    if (isNight && bearing != null && elevation != null && illumination != null && elevation > -5) {
      const p = position(bearing, elevation), r = 25;
      moonArt = `<g class="sky-moon" data-phase="${esc(moon.phase || '')}" data-illumination="${illumination}" transform="translate(${p.x.toFixed(1)} ${p.y.toFixed(1)})"><circle r="${r}"/><path d="M ${-r*.1} ${-r} A ${r} ${r} 0 1 0 ${-r*.1} ${r} A ${r*illumination} ${r} 0 1 1 ${-r*.1} ${-r}"/></g>`;
    } else if (isNight && phase && phase !== 'unknown' && phase !== 'unavailable') {
      // A phase-only sensor is useful for a quiet visual cue, but supplies no
      // claim about where the moon is or how much of it is illuminated.
      moonArt = `<g class="sky-moon" data-phase="${esc(moon.phase || '')}" data-position="ambient" transform="translate(848 128)"><circle r="25"/>${phaseShape(phase)}</g>`;
    }
    const cloudArt = cloudy > 0 ? `<g class="sky-clouds" opacity="${(.12 + cloudy / 100 * .42).toFixed(2)}"><path d="M-40 170 C120 92 260 180 410 126 S710 118 1064 176 L1064 290 L-40 290Z"/><path d="M-40 346 C160 278 300 362 520 314 S820 306 1064 360 L1064 475 L-40 475Z"/></g>` : '';
    const aircraft = Array.isArray(sky.aircraft) ? sky.aircraft : [];
    const aircraftArt = aircraft.map(track => { const b=n(track.bearing,0,360), e=n(track.elevation,-90,90); if (b==null||e==null) return ''; const p=position(b,e); return `<g class="sky-aircraft" transform="translate(${p.x.toFixed(1)} ${p.y.toFixed(1)}) rotate(${n(track.heading,0,360) ?? 0})"><path d="M-14 0H14M0-3v6"/><title>${esc(track.id)}</title></g>`; }).join('');
    art.innerHTML = `<defs><linearGradient id="sky-gradient" x2="0" y2="1"><stop offset="0"/><stop offset="1"/></linearGradient></defs><rect class="sky-fill" width="1024" height="600" fill="url(#sky-gradient)"/>${starArt}${moonArt}${cloudArt}${aircraftArt}`;
  }
  window.MarqueeSky = { render };
})();
