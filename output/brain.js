/* The desk presents server facts. It never infers safety or operates devices. */
(() => {
  const live = ['/live','/kiosk'].includes(location.pathname);
  if (!live) return;
  const q = new URLSearchParams(location.search), demo = q.has('demo'), edit = q.has('edit');
  document.body.classList.add('brain-live');
  const shell = document.createElement('section'); shell.className='brain-shell';shell.setAttribute('aria-label','Household desk');
  shell.innerHTML=`<header class="brain-mast"><div class="brain-brand"><em>M/</em> MARQUEE <a class="brain-customize" href="/settings/layout?profile=live" aria-label="Customize the household desk">↗</a></div><div class="brain-edition">THE HOUSEHOLD EDITION</div><div class="brain-connection" id="brain-connection">CONNECTING</div></header>
  <section class="brain-panel" id="brain-house"><div class="brain-eyebrow"><span>Right now</span><b id="brain-house-label">THE HOUSE</b></div><div class="brain-lead"><div><h1 class="brain-headline" id="brain-headline">Listening to the house.</h1><div class="brain-summary" id="brain-summary">Waiting for a fresh household snapshot.</div></div><div class="brain-orbit" id="brain-symbol" aria-hidden="true">⌂</div></div><div class="brain-openings" id="brain-openings"></div><div id="brain-device-health" class="brain-summary" role="status" hidden></div><button class="brain-ack" id="brain-ack" hidden>Got it · keep monitoring</button></section>
  <section class="brain-panel" id="brain-activity"><div class="brain-eyebrow"><span>Just happened</span><b>LAST 15 MIN</b></div><div id="brain-events"></div></section>
  <section class="brain-panel" id="brain-agenda"><div class="brain-birthday"><div class="brain-eyebrow"><span>People first</span><b>✳</b></div><div id="brain-birthdays"></div></div><div class="brain-upnext"><div class="brain-eyebrow"><span>On the horizon</span><b>↗</b></div><div id="brain-upnext"></div></div></section>`;
  document.body.append(shell);
  const weatherLink=document.createElement('a');weatherLink.className='brain-weather-link';weatherLink.href=q.get('view')==='weather'?'/live':'/live?view=weather';weatherLink.textContent=q.get('view')==='weather'?'← HOUSEHOLD DESK':'LOCAL WEATHER ↗';document.body.append(weatherLink);
  const dock=document.createElement('aside');dock.className='brain-dock';dock.setAttribute('aria-label','Household updates');dock.innerHTML='<span class="brain-dock-brand">M/ HOUSE FEED</span><span class="brain-dock-copy" id="brain-dock-copy">Connecting to the house…</span><div class="brain-dock-people" id="brain-people"></div>';document.body.append(dock);
  const toast=document.createElement('div');toast.className='brain-toast';toast.setAttribute('role','status');document.body.append(toast);
  const $=id=>document.getElementById(id), esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  let state=null, wx=null, received=0, theme='studio', visibility={}, lastToast='', toastUntil=0, alertId='', hiddenByBlank=false;
  function elapsed(seconds){const n=Math.max(0,Math.floor(seconds));return n<60?'just now':n<3600?`${Math.floor(n/60)}m`: `${Math.floor(n/3600)}h ${Math.floor(n%3600/60)}m`}
  function set(id,text){$(id).textContent=text}
  function render(){
    if(!state)return;
    const now=Date.now()/1000, fresh=state.fresh&&now-received<45;
    const opening=fresh?(state.openings||[]):[], events=fresh?(state.events||[]).filter(e=>e.expires>now):[];
    const alerts=fresh?(state.alerts||[]):[];
    const serious=alerts.find(a=>['CRITICAL','IMPORTANT','ACTIONABLE'].includes(a.urgency));
    const primary=serious?opening.find(o=>o.id===serious.signal_id):(opening.find(o=>o.category!=='window')||opening[0]);
    const deviceHealth=fresh?(state.device_health||[]):[];
    const healthText=deviceHealth.length?`Offline: ${deviceHealth.map(d=>d.name).join(', ')}. Check batteries or connection.`:'';
    $('brain-device-health').hidden=!deviceHealth.length;
    $('brain-house').classList.toggle('device-alert',Boolean(deviceHealth.length));
    set('brain-device-health',healthText);
    $('brain-device-health').style.color='var(--brain-amber, #ffd28a)';
    const event=events[0];
    $('brain-connection').classList.toggle('stale',!fresh);set('brain-connection',demo?'DESIGN PREVIEW':fresh?'HOUSE CONNECTED':'HOUSE FEED OFFLINE');
    $('brain-house').dataset.tone=!fresh?'amber':primary||serious||deviceHealth.length?'amber':'mint';
    set('brain-house-label',!fresh?'SIGNAL LOST':serious||deviceHealth.length?'NEEDS ATTENTION':primary?'HOUSE IN MOTION':'LIVE AT HOME');
    set('brain-symbol',!fresh?'?':serious||deviceHealth.length?'!':primary?'↗':'⌂');
    const duration=primary?Math.max(primary.duration||0,now-primary.since):0;
    set('brain-headline',!fresh?'The house feed went quiet.':primary?`${primary.name} ${primary.state}.`:serious?serious.title:deviceHealth.length?'Nursery devices are offline.':event&&now-event.at<120?event.title:'Home, in the present.');
    let summary=!fresh?'Live states are unavailable. The last report is not a current all-clear.':primary?`${duration<60?`Just observed ${primary.state}.`:`Observed ${primary.state} for ${elapsed(duration)}.`} ${serious?'Worth checking before you settle in.':state.sleeping?'Someone is sleeping.':state.weather_state&&/rain|snow/.test(state.weather_state)?'Wet weather outside — worth a look.':state.lock==='locked'?'Front door lock is secured.':''}`:serious?serious.summary:state.lock==='locked'?'Front door locked. Reporting doors and windows are closed.':'No monitored door or window is reporting open.';
    if(deviceHealth.length)summary='Device status needs attention.';
    else if(fresh&&state.unknown?.length)summary+=` ${state.unknown.length} household sensor${state.unknown.length===1?' is':'s are'} unavailable.`;
    set('brain-summary',summary);
    $('brain-openings').innerHTML=opening.slice(0,5).map(o=>`<span class="brain-tag warm">${esc(o.name)} <small>${esc(o.state)} · ${elapsed(Math.max(o.duration||0,now-o.since))}</small></span>`).join('');
    const actionable=serious?.acknowledgement_required?serious:null;alertId=actionable?.id||'';$('brain-ack').hidden=!actionable||demo;
    $('brain-events').innerHTML=events.length?events.slice(0,4).map(e=>`<div class="brain-event"><span>${esc(e.title)}</span><time>${elapsed(now-e.at)}${now-e.at>=60?' ago':''}</time></div>`).join(''):`<p class="brain-empty">${fresh?'No new door or lock activity in the last 15 minutes.':'Activity feed reconnecting; recent activity is unavailable.'}</p>`;
    const cards=(state.cards||[]).filter(c=>!c.expires||Date.parse(c.expires)>Date.now());
    const birthdays=cards.find(c=>c.subtype==='birthday_rollup');
    $('brain-birthdays').innerHTML=birthdays?`<h2>${esc(birthdays.title)}</h2><div class="birthday-when">${esc(birthdays.subtitle)}</div><ul>${(birthdays.rows||[]).slice(0,3).map(r=>`<li>${esc(r)}</li>`).join('')}</ul>`:'<p class="brain-empty">No birthdays in the next three weeks.</p>';
    const near=c=>!c.starts||Date.parse(c.starts)<=Date.now()+3*86400000;
    const upcoming=cards.filter(c=>c.type==='calendar_event'&&c.subtype!=='birthday_rollup'&&near(c)).slice(0,3);
    $('brain-upnext').innerHTML=upcoming.length?upcoming.map(c=>`<div class="brain-agenda-item"><strong>${esc(c.title)}</strong><span>${esc(c.subtitle||c.detail)}</span></div>`).join(''):'<p class="brain-empty">A little room in the calendar.</p>';
    $('brain-people').innerHTML=(state.people||[]).map(p=>`<span class="brain-person" data-home="${fresh&&p.state.toLowerCase()==='home'}">${esc(p.name)} · ${esc(fresh?p.state:'Unknown')}</span>`).join('');
    let feed=[];
    if(!fresh)feed=['Household connection lost · Current door and lock states are unknown'];
    else {
      if(healthText)feed.push(healthText);
      if(primary)feed.push(`${primary.name} ${primary.state} · observed for ${elapsed(duration)}`);
      if(event)feed.push(`${event.title} · ${elapsed(now-event.at)}${now-event.at>=60?' ago':''}`);
      if(state.guests)feed.push('Guest mode is on · The house is expecting company');
      if(state.sleeping)feed.push('Someone is sleeping · Keep it low-key');
      if(state.garage_occupied)feed.push('Garage occupied · Someone’s out in the workshop');
      feed.push(...cards.filter(c=>c.type!=='weather'&&c.type!=='astronomy'&&(c.subtype==='birthday_rollup'||near(c))).map(c=>`${c.title} · ${c.subtitle||c.detail||''}`));
      if(state.network==='online')feed.push('House network online');
      if(state.unknown?.length)feed.push(`Not reporting: ${state.unknown.join(', ')}`);
      if(!feed.length)feed=['The house is listening for its next real update'];
    }
    set('brain-dock-copy',feed[Math.floor(now/12)%feed.length]);
    if(event&&now-event.at<45&&event.id!==lastToast&&!demo){lastToast=event.id;toastUntil=now+12;toast.innerHTML=`<span aria-hidden="true">↗</span><div>${esc(event.title)}<small>Just happened at home</small></div>`}
    toast.classList.toggle('show',now<toastUntil);
    for(const [block,id]of [['house','brain-house'],['activity','brain-activity'],['agenda','brain-agenda']])$(id).hidden=visibility[block]===false;
    shell.hidden=hiddenByBlank;dock.hidden=hiddenByBlank;
  }
  $('brain-ack').onclick=async()=>{const b=$('brain-ack');b.disabled=true;try{const r=await fetch('/api/attention/action',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:alertId,action:'acknowledge'})});if(!r.ok)throw Error();await poll()}catch(_){b.textContent='Could not acknowledge · try again'}finally{b.disabled=false}};
  function weather(){window.MarqueeWeather?.observation(wx)}
  async function poll(){if(demo)return;try{const r=await fetch('/api/brain');if(!r.ok)throw Error();state=await r.json();received=Date.now()/1000;render();window.dispatchEvent(new Event('marquee-brain'))}catch(_){if(state){state.fresh=false;render()}}}
  async function pollWeather(){try{const r=await fetch('/ha-weather.json');if(r.ok){wx=await r.json();weather()}}catch(_){}}
  window.MarqueeBrain={weatherContext(){return state?.cards?.find(c=>c.type==='weather'&&(!c.expires||Date.parse(c.expires)>Date.now()))},configure(cfg,fallback){theme=['studio','afterhours','dispatch'].includes(cfg.liveTheme)?cfg.liveTheme:'studio';document.body.dataset.liveTheme=theme;visibility=cfg.liveVisibility?.home||{};hiddenByBlank=fallback?.screen==='blank';render()},weather};
  if(demo){const now=Date.now()/1000;received=now;state={fresh:true,source_at:now,openings:[{id:'preview:balcony',name:'Balcony door',category:'exterior_door',state:'open',since:now-420,duration:420}],unknown:[],people:[{name:'Alex',state:'Home'},{name:'Jamie',state:'Away'}],events:[{id:'preview:lock',title:'Front door lock unlocked',at:now-75,expires:now+825},{id:'preview:door',title:'Balcony door opened',at:now-420,expires:now+480}],cards:[{type:'calendar_event',subtype:'birthday_rollup',title:"Casey’s birthday",subtitle:'Tomorrow · September 12',rows:['Jordan · In 6 days','Sam · In 12 days']},{type:'calendar_event',title:'Recycling pickup',subtitle:'Tomorrow morning'},{type:'calendar_event',title:'Dinner with friends',subtitle:'Saturday · 6:30 PM'}],alerts:[],network:'online'};wx={temp:21,condition:'partly cloudy',wind:14,humidity:52,updated:now};render();weather()}
  else{poll();pollWeather();setInterval(poll,3000);setInterval(pollWeather,60000)}
  setInterval(()=>{render();weather()},1000);
})();
