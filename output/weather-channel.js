/* Weather presentation shared by Live and Cast. Forecast values remain source data. */
(() => {
  const card=document.getElementById('weather-card');if(!card)return;
  const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const rounded=v=>Number.isFinite(v)?Math.round(v):'—';
  function condition(code,night=false){if(code==null)return {label:'Conditions unavailable',kind:'unknown'};if(code===0)return {label:night?'Clear night':'Sunny',kind:night?'night':'sun'};if(code<=2)return {label:'Partly cloudy',kind:night?'night':'partly'};if(code===3)return {label:'Cloudy',kind:'cloud'};if(code<50)return {label:'Fog',kind:'fog'};if(code>=95)return {label:'Thunderstorms',kind:'storm'};if([71,73,75,77,85,86].includes(code))return {label:'Snow',kind:'snow'};return {label:'Rain',kind:'rain'}}
  const sun='<g class="wx-sun"><circle cx="32" cy="31" r="12" fill="#ffe270"/><path d="M32 4v7m0 40v7M5 31h7m40 0h7M13 12l5 5m28 28 5 5M13 50l5-5m28-28 5-5" stroke="#ffe270" stroke-width="3" stroke-linecap="round"/></g>';
  const cloud='<path class="wx-cloud" d="M15 45a11 11 0 1 1 3-22 16 16 0 0 1 30-2 12 12 0 1 1 3 24Z" fill="#e9f5ff"/>';
  function icon(kind){let art=kind==='sun'?sun:kind==='night'?'<path class="wx-moon" d="M43 6a25 25 0 1 0 15 40A26 26 0 0 1 43 6Z" fill="#dee9ff"/>':kind==='partly'?`<g transform="translate(12,-6) scale(.8)">${sun}</g>${cloud}`:cloud;if(['rain','storm'].includes(kind))art+='<path class="wx-rain" d="m21 51-4 8m18-8-4 8m18-8-4 8" stroke="#6dd9ff" stroke-width="3"/>';if(kind==='snow')art+='<g class="wx-snow" fill="#fff"><circle cx="20" cy="55" r="2"/><circle cx="34" cy="55" r="2"/><circle cx="48" cy="55" r="2"/></g>';if(kind==='storm')art+='<path class="wx-bolt" d="m35 34-9 16h8l-5 12 18-20h-9l5-8Z" fill="#ffe36e"/>';if(kind==='fog')art+='<g class="wx-fog" stroke="#b8c7df" stroke-width="3"><path d="M10 51h42M17 58h30"/></g>';if(kind==='unknown')art='<text x="32" y="45" font-size="40" text-anchor="middle" fill="#b8c7df">?</text>';return `<svg class="wx-icon" data-kind="${kind}" viewBox="0 0 64 64" aria-hidden="true">${art}</svg>`}

  card.classList.add('wx-broadcast');
  card.querySelector('.weather-source').innerHTML='<b>M/</b> MARQUEE <span>WEATHER</span>';
  const heading=document.createElement('header');heading.className='wx-heading';
  heading.innerHTML='<div><p>YOUR LOCAL WEATHER</p><h1 id="wx-segment-title" tabindex="-1">Current conditions</h1><small id="wx-retained-context"></small></div><span id="wx-data-status"></span>';
  const main=document.createElement('div');main.className='wx-main';
  main.innerHTML=`<section id="weather-conditions" class="wx-panel channel-current" aria-label="Current conditions"><div class="wx-observation"><div id="channel-icon" class="channel-icon"></div><div id="channel-temp" class="channel-temp"></div><div id="channel-condition" class="channel-condition"></div><span id="wx-observation-source"></span></div><div class="wx-readings"><div class="channel-metrics" id="channel-metrics"></div><p id="channel-outlook" class="channel-outlook"></p></div></section>
  <section id="weather-hours" class="wx-panel channel-hours" aria-label="Hourly outlook" hidden><div id="channel-hours"></div></section>
  <section id="weather-days" class="wx-panel channel-days" aria-label="Five-day forecast" hidden><div id="channel-days"></div></section>
  <section id="wx-radar-panel" class="wx-panel" aria-label="Local radar" hidden><div class="wx-radar-frame"><p id="wx-radar-status">Radar is loading…</p></div><aside class="wx-radar-copy"><p>PRECIPITATION RADAR</p><h2 id="wx-radar-title">Around home</h2><div id="wx-radar-detail"></div><small>Environment Canada<br>Original radar product</small></aside></section>`;
  const radar=document.getElementById('weather-radar');main.querySelector('.wx-radar-frame').append(radar);
  const warning=document.createElement('aside');warning.id='channel-warning';warning.className='channel-warning';warning.hidden=true;warning.setAttribute('role','status');
  const nav=document.createElement('nav');nav.className='wx-segments';nav.setAttribute('aria-label','Weather segments');
  const titles={conditions:'Current conditions',hours:'Hourly outlook',forecast:'Five-day forecast',radar:'Local radar'};
  nav.innerHTML=Object.entries(titles).map(([key,title])=>`<button type="button" data-segment="${key}" aria-pressed="false">${title}</button>`).join('')+'<button type="button" id="wx-pause" aria-pressed="false">Pause</button>';
  const footer=document.createElement('footer');footer.className='wx-footer';footer.innerHTML='<strong>LOCAL WEATHER</strong><div id="wx-ticker"></div><span id="channel-source">ENVIRONMENT CANADA · HOME ASSISTANT</span>';
  card.append(warning,heading,main,nav,footer);
  let observed=null,ctx=null,visibility={},segment='conditions',started=Date.now(),last='',lastActive=false;
  const params=new URLSearchParams(location.search),editing=params.has('edit');
  let paused=editing||matchMedia('(prefers-reduced-motion: reduce)').matches;
  const $=id=>document.getElementById(id);
  const panels={conditions:$('weather-conditions'),hours:$('weather-hours'),forecast:$('weather-days'),radar:$('wx-radar-panel')};
  function time(stamp,day=false){try{return new Date(stamp).toLocaleString([],{...(day?{weekday:'short'}:{hour:'numeric',minute:'2-digit'}),timeZone:ctx?.weather?.timezone||'America/Toronto'})}catch(_){return '—'}}
  function modelFresh(){const at=Date.parse(ctx?.weather?.observed_at||ctx?.weather?.generated_at);return Number.isFinite(at)&&Date.now()-at<90*60000;}
  function radarFresh(){if(ctx?.weather?.radar_enabled===false)return false;const stamp=ctx?.weather?.radar_updated_at;return stamp ? Date.now()/1000-stamp<1200 : Boolean(ctx?.weather?.radar_relevant||['rain','snow'].includes(ctx?.subtype));}
  function available(){return Object.keys(panels).filter(k=>visibility[k]!==false&&(k!=='radar'||ctx?.weather?.radar_enabled!==false));}
  function choose(key){if(!available().includes(key))return;segment=key;started=Date.now();paintSegment();}
  function paintSegment(){
    const options=available();if(!options.includes(segment))segment=options[0]||'';
    for(const [key,el]of Object.entries(panels))el.hidden=key!==segment;
    for(const button of nav.querySelectorAll('[data-segment]')){button.hidden=!options.includes(button.dataset.segment);button.setAttribute('aria-pressed',String(button.dataset.segment===segment));}
    $('wx-pause').textContent=paused?'Play':'Pause';$('wx-pause').setAttribute('aria-pressed',String(paused));
    $('wx-segment-title').textContent=titles[segment]||'Local weather';
    card.dataset.segment=segment;
    $('wx-radar-status').hidden=Boolean(radarFresh()&&radar.complete&&radar.naturalWidth&&!radar.classList.contains('loading'));
    radar.hidden=!radarFresh()||!$('wx-radar-status').hidden||visibility.radar===false;
    $('wx-radar-status').textContent=radarFresh()?'Radar image is unavailable. Waiting for the next update.':'Radar is temporarily unavailable. Waiting for a fresh image.';
  }
  nav.addEventListener('click',e=>{const b=e.target.closest('button');if(!b)return;if(b.dataset.segment)choose(b.dataset.segment);else{paused=!paused;started=Date.now();paintSegment();}});
  radar.addEventListener('load',paintSegment);radar.addEventListener('error',paintSegment);
  function draw(){
    if(!ctx)return;
    const raw=ctx.weather||{},data=modelFresh()?raw:{},model=data.current||{},now=Date.now();
    const freshObservation=Boolean(observed&&Number.isFinite(observed.temp)&&observed.updated&&now/1000-observed.updated>=0&&now/1000-observed.updated<1800);
    const temp=freshObservation?observed.temp:null;
    let kind=condition(model.weather_code??null,model.is_day===0);
    if(freshObservation&&observed.condition){const normalized=String(observed.condition).toLowerCase().replaceAll(' ','-');const names={sunny:'sun',clear:'sun','clear-night':'night',partlycloudy:'partly','partly-cloudy':'partly',cloudy:'cloud',fog:'fog',rainy:'rain',rain:'rain',pouring:'rain',snowy:'snow',snow:'snow','snowy-rainy':'snow',lightning:'storm','lightning-rainy':'storm'};kind={...kind,kind:names[normalized]||kind.kind};}
    card.dataset.sky=kind.kind;
    const alert=['alert','extreme'].includes(ctx.subtype);card.dataset.alert=String(alert);warning.hidden=!alert;
    if(alert)warning.innerHTML=`<strong>${esc(ctx.title)}</strong><div>${esc(ctx.detail||ctx.subtitle)}</div>`;
    const signature=JSON.stringify([data,ctx.title,ctx.detail,ctx.subtype,temp,freshObservation?observed:null,weatherFetchState,Math.floor(now/60000)]);
    if(signature!==last){last=signature;
      $('channel-icon').innerHTML=icon(kind.kind);$('channel-temp').innerHTML=rounded(temp)+'<small>°C</small>';
      const description=freshObservation&&observed.condition?String(observed.condition).replace(/partlycloudy/g,'Partly cloudy').replace(/-/g,' ').replace(/^./,c=>c.toUpperCase()):kind.label;
      $('channel-condition').textContent=description;
      $('wx-observation-source').textContent=freshObservation?'Observed '+time(observed.observed_at||observed.updated*1000)+' · Environment Canada':modelFresh()?'Home Assistant · Environment Canada':'Current conditions unavailable';
      const weatherState = window.MarqueeState?.resolve({stale: !modelFresh(), empty: !data.current, hasData: Boolean(data.current)}) || (modelFresh() ? 'ready' : 'stale');
      card.dataset.state = weatherState;
      $('wx-data-status').textContent=weatherState === 'stale' ? 'LAST KNOWN FORECAST · STALE' : weatherState === 'empty' ? 'FORECAST EMPTY' : 'LOCAL FORECAST · °C / KM/H';
      const wind=freshObservation?observed.wind:model.wind_speed_10m,humidity=freshObservation?observed.humidity:model.relative_humidity_2m;
      const metrics=[['Feels like',Number.isFinite(model.apparent_temperature)?rounded(model.apparent_temperature)+'°C':'—'],['Humidity',Number.isFinite(humidity)?rounded(humidity)+'%':'—'],['Wind',Number.isFinite(wind)?rounded(wind)+' km/h':'—'],['Pressure',freshObservation&&Number.isFinite(observed.pressure)?rounded(observed.pressure)+' hPa':'—']];
      const today=(data.days||[]).find(d=>d.date===new Intl.DateTimeFormat('en-CA',{timeZone:raw.timezone||'America/Toronto'}).format(new Date()));
      if(Number.isFinite(today?.uv))metrics.push(['UV high today',String(rounded(today.uv))]);
      if(today?.sunset)metrics.push(['Sunset',time(today.sunset)]);
      $('channel-metrics').innerHTML=metrics.map(([label,value])=>`<div><span>${esc(label)}</span><strong>${esc(value)}</strong></div>`).join('');
      $('channel-outlook').textContent=modelFresh()?ctx.detail||'':'';
      const upcoming=(data.hours||[]).filter(h=>Date.parse(h.at)>now-60000).slice(0,6);
      $('channel-hours').innerHTML=upcoming.length?upcoming.map(h=>`<article class="channel-hour"><time>${esc(time(h.at))}</time>${icon(condition(h.code,h.is_day===0).kind)}<strong>${rounded(h.temp)}°</strong><span>${esc(condition(h.code,h.is_day===0).label)}</span><small>${h.rain==null?'—':rounded(h.rain)+'%'} precip.</small></article>`).join(''):'<p class="channel-missing">Hourly forecast is temporarily unavailable.</p>';
      const localDate=new Intl.DateTimeFormat('en-CA',{timeZone:raw.timezone||'America/Toronto'}).format(new Date());
      const forecast=(data.days||[]).filter(d=>d.date>=localDate).slice(0,5);
      $('channel-days').innerHTML=forecast.length?forecast.map(d=>`<article class="channel-day"><h3>${d.date===localDate?'TODAY':esc(new Date(d.date+'T12:00:00Z').toLocaleDateString('en-US',{weekday:'short',timeZone:'UTC'}).toUpperCase())}</h3>${icon(condition(d.code).kind)}<p>${esc(condition(d.code).label)}</p><div class="channel-highlow"><div><small>HIGH</small><b>${rounded(d.high)}°</b></div><div><small>LOW</small><span>${rounded(d.low)}°</span></div></div><div class="channel-chance">${d.rain==null?'—':rounded(d.rain)+'%'} precip.</div></article>`).join(''):'<p class="channel-missing">The extended forecast is temporarily unavailable.</p>';
      $('wx-radar-title').textContent=['rain','snow'].includes(ctx.subtype)?ctx.title:'Around home';
      $('wx-radar-detail').textContent=['rain','snow'].includes(ctx.subtype)?ctx.subtitle||ctx.detail||'':raw.radar_updated_at?'Radar received '+time(raw.radar_updated_at*1000):'Precipitation around your configured location';
    }
    const ticker=[modelFresh()?ctx.detail:'Forecast feed is unavailable. Waiting for fresh data.',freshObservation?`${$('channel-condition').textContent} · ${rounded(temp)}°C · Wind ${rounded(observed.wind)} km/h`:null, 'Environment Canada · via Home Assistant'].filter(Boolean);
    $('wx-ticker').textContent=ticker[Math.floor(now/9000)%ticker.length]||'Your local weather';
    paintSegment();
  }
  window.MarqueeWeather={render(context,visible={}){
    const newContext=ctx?.id!==context.id||ctx?.subtype!==context.subtype;
    ctx=context;visibility=visible;
    $('wx-retained-context').textContent=context.title||'';
    if(newContext){segment=['rain','snow'].includes(ctx.subtype)?'radar':'conditions';started=Date.now();last='';}
    draw();return visibility.radar!==false&&radarFresh();
  },observation(value){observed=value;draw()}};
  setInterval(()=>{
    const active=card.closest('.stage')?.classList.contains('weather-context')&&!document.body.classList.contains('idle')&&!document.hidden;
    if(!active){lastActive=false;return;}
    if(!lastActive){started=Date.now();lastActive=true;}
    if(!paused&&!['alert','extreme'].includes(ctx?.subtype)&&Date.now()-started>=15000){const options=available();choose(options[(options.indexOf(segment)+1)%options.length]);}
    draw();
  },1000);
})();
