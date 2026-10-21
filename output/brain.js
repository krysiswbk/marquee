/* The desk presents server facts. It never infers safety or operates devices. */
(() => {
  const live = ['/live','/kiosk'].includes(location.pathname);
  if (!live) return;
  const q = new URLSearchParams(location.search), demo = q.has('demo'), edit = q.has('edit');
  const castReceiver = ['hubs', 'garage'].includes(q.get('display'));
  document.body.classList.add('brain-live');
  const shell = document.createElement('section'); shell.className='brain-shell';shell.setAttribute('aria-label','Household desk');
  shell.innerHTML=`<header class="brain-mast"><div class="brain-brand"><em>M/</em> MARQUEE <a class="brain-customize" href="/settings/layout?profile=live" aria-label="Customize the household desk"><span class="brain-customize-icon" aria-hidden="true">↗</span><span class="brain-customize-label">Customize</span></a></div><div class="brain-edition">THE HOUSEHOLD EDITION</div><div class="brain-connection" id="brain-connection">CONNECTING</div></header>
  <section class="brain-panel" id="brain-house"><div class="brain-eyebrow"><span>Right now</span><b id="brain-house-label">THE HOUSE</b></div><div class="brain-lead"><div><h1 class="brain-headline" id="brain-headline" data-history-focus-owner tabindex="-1">Listening to the house.</h1><div class="brain-summary" id="brain-summary">Waiting for a fresh household snapshot.</div></div><div class="brain-orbit" id="brain-symbol" aria-hidden="true">⌂</div></div><ul class="brain-household-state" id="brain-household-state" aria-label="Current household state" hidden></ul><div class="brain-openings" id="brain-openings"></div><div id="brain-device-health" class="brain-summary" role="status" hidden></div><button class="brain-ack" id="brain-ack" hidden>Got it · keep monitoring</button><button type="button" class="brain-retry" id="brain-retry" hidden>Try again</button></section>
  <section class="brain-panel" id="brain-activity"><div class="brain-eyebrow"><span>Just happened</span><b>LAST 15 MIN</b></div><div id="brain-events"></div></section>
  <section class="brain-panel" id="brain-agenda" data-agenda-state="loading"><div class="brain-eyebrow"><span>Coming up</span><b>↗</b></div><div class="brain-agenda-list" id="brain-agenda-list"><p class="brain-empty">Calendar is loading.</p></div><a class="brain-agenda-more" id="brain-agenda-link" href="/kiosk?view=calendar&mode=all" hidden>View full Calendar</a></section>
  <section class="brain-activity-view" id="brain-activity-view" role="dialog" aria-modal="true" aria-labelledby="brain-activity-title" hidden><div class="brain-activity-dialog"><header><div><p class="brain-eyebrow">Household record</p><h2 id="brain-activity-title" tabindex="-1">Recent activity</h2><p id="brain-activity-count"></p></div><button type="button" id="brain-activity-close" aria-label="Close recent activity">Close</button></header><div id="brain-activity-list" role="region" aria-label="Recent activity records; use arrow keys or scroll to review" tabindex="0"></div></div></section>`;
  document.body.append(shell);
  if (q.get('wired') === '1') shell.querySelector('#brain-agenda-link').href = '/kiosk?wired=1&view=calendar&mode=all';
  const weatherLink=document.createElement('a');weatherLink.className='brain-weather-link';weatherLink.href=q.get('view')==='weather'?'/live':'/live?view=weather';weatherLink.textContent=q.get('view')==='weather'?'← HOUSEHOLD DESK':'LOCAL WEATHER ↗';document.body.append(weatherLink);
  const dock=document.createElement('aside');dock.className='brain-dock';dock.setAttribute('aria-label','Household updates');dock.innerHTML='<span class="brain-dock-brand">M/ HOUSE FEED</span><span class="brain-dock-copy" id="brain-dock-copy">Connecting to the house…</span><div class="brain-dock-people" id="brain-people"></div>';document.body.append(dock);
  // When Home Assistant embeds the kiosk in a fullscreen popup, its own
  // dismiss control can sit behind the iframe. Provide an exit in the feed.
  const parentUrl=document.referrer || window.location.ancestorOrigins?.[0] || '';
  let dashboardUrl;
  try { const candidate=new URL(parentUrl); if(window.top!==window&&/^https?:$/.test(candidate.protocol)&&candidate.origin!==location.origin)dashboardUrl=candidate.href; } catch (_) { /* Direct kiosk visit. */ }
  // HA may expose no referrer or only its origin. The dedicated popup marker
  // identifies the installed dashboard route regardless of those hints.
  const installedHaPopup=window.top!==window&&!castReceiver&&q.get('v')?.startsWith('household-desk-');
  if(installedHaPopup)
    dashboardUrl='http://10.10.9.5:8123/dashboard-homepage/0?BrowserID=a38e5c41-b99f0451';
  if(dashboardUrl&&!castReceiver){
    const actions=document.createElement('div');actions.className='brain-dock-actions';
    const close=document.createElement('button');close.type='button';close.className='brain-dock-close';close.textContent='Home controls';close.setAttribute('aria-label','Home controls in Home Assistant');
    close.onclick=()=>{ window.top.location.href=dashboardUrl; };
    actions.append(close);
    if(installedHaPopup){
      const doorbell=document.createElement('button');doorbell.type='button';doorbell.className='brain-dock-close brain-dock-doorbell';doorbell.textContent='Doorbell';doorbell.setAttribute('aria-label','Doorbell camera in Home Assistant');
      doorbell.onclick=()=>{ window.top.location.href='http://10.10.9.5:8123/dashboard-homepage/cameras?BrowserID=a38e5c41-b99f0451'; };
      actions.append(doorbell);
    }
    dock.append(actions);
  }
  const toast=document.createElement('div');toast.className='brain-toast';toast.setAttribute('role','status');document.body.append(toast);
  const $=id=>document.getElementById(id), esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const feedTier=()=>window.matchMedia('(max-width: 430px)').matches?'phone':window.matchMedia('(max-width: 700px)').matches?'tablet':'desktop';
  function compactNames(names, noun) {
    const values=(names||[]).filter(Boolean), count=values.length;
    if(!count)return '';
    if(count<=2)return values.join(', ');
    return `${values.slice(0,2).join(', ')} + ${count-2} more ${noun}`;
  }
  function narrowLabel(value, max=52) {
    const text=String(value||'').trim();
    if(text.length<=max)return text;
    const cut=text.slice(0,max-1).replace(/\s+\S*$/,'').trim();
    return `${cut||text.slice(0,max-1)}…`;
  }
  function feedEntry(fullText, narrowText=fullText) {
    return {fullText:String(fullText), narrowText:String(narrowText)};
  }
  function deviceHealthFeedEntry(fullText,names) {
    const count=names.length;
    const phone=`${count} device${count===1?'':'s'} offline · Check connection`;
    const tabletNames=names.map(name=>narrowLabel(name,24));
    const tablet=`Offline: ${compactNames(tabletNames,'devices')}. Check connection.`;
    return {fullText:String(fullText),narrowText:phone,tabletText:tablet};
  }
  function renderFeedEntry(entry) {
    const fullText=entry.fullText, tier=feedTier(), visible=tier==='desktop'?fullText:tier==='tablet'?(entry.tabletText||entry.narrowText):entry.narrowText;
    const copy=$('brain-dock-copy');
    copy.textContent=visible;
    copy.title=fullText;
    copy.setAttribute('aria-label',fullText);
    copy.dataset.fullText=fullText;
  }
  let state=null, wx=null, received=0, theme='afterhours', visibility={}, lastToast='', toastUntil=0, alertId='', hiddenByBlank=false, feedDisconnected=false;
  let fitFrame=0;
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
    const healthNames=deviceHealth.map(d=>d.name).filter(Boolean);
    const healthText=deviceHealth.length?`Offline: ${deviceHealth.map(d=>d.name).join(', ')}. Check batteries or connection.`:'';
    $('brain-device-health').hidden=!deviceHealth.length;
    $('brain-house').classList.toggle('device-alert',Boolean(deviceHealth.length));
    set('brain-device-health',healthText);
    $('brain-device-health').style.color='var(--brain-amber, #ffd28a)';
    const event=events[0];
    const householdState = window.MarqueeState?.resolve({loading: !state, disconnected: feedDisconnected, stale: !fresh, hasData: Boolean(state)}) || (feedDisconnected ? 'disconnected' : fresh ? 'ready' : 'stale');
    $('brain-house').dataset.state = householdState;
    $('brain-connection').classList.toggle('stale',householdState === 'stale');set('brain-connection',demo?'DESIGN PREVIEW':fresh?'HOUSE CONNECTED':householdState === 'disconnected'?'HOUSE FEED OFFLINE':'HOUSE FEED STALE');
    $('brain-retry').hidden = householdState !== 'disconnected';
    $('brain-house').dataset.tone=!fresh?'amber':primary||serious||deviceHealth.length?'amber':'mint';
    set('brain-house-label',!fresh?'SIGNAL LOST':serious||deviceHealth.length?'NEEDS ATTENTION':primary?'HOUSE IN MOTION':'LIVE AT HOME');
    set('brain-symbol',!fresh?'?':serious||deviceHealth.length?'!':primary?'↗':'⌂');
    const duration=primary?Math.max(primary.duration||0,now-primary.since):0;
    set('brain-headline',!fresh?'The house feed went quiet.':primary?`${primary.name} ${primary.state}.`:serious?serious.title:deviceHealth.length?'Nursery devices are offline.':event&&now-event.at<120?event.title:'Home');
    let summary=!fresh?'Live states are unavailable. The last report is not a current all-clear.':primary?`${duration<60?`Just observed ${primary.state}.`:`Observed ${primary.state} for ${elapsed(duration)}.`} ${serious?'Worth checking before you settle in.':state.weather_state&&/rain|snow/.test(state.weather_state)?'Wet weather outside — worth a look.':''}`:serious?serious.summary:state.lock==='locked'?'Front door locked.':state.lock==='unlocked'?'Front door unlocked.':'';
    if(deviceHealth.length)summary='Device status needs attention.';
    set('brain-summary',summary);
    // Show only facts in the current briefing. A stale snapshot must never
    // appear to certify a lock, person or mode as current.
    const facts=[];
    if(fresh){
      if(state.sleeping)facts.push('Someone sleeping');
      if(state.guests)facts.push('Guests expected');
      if(state.garage_occupied)facts.push('Garage occupied');
      (state.people||[]).filter(p=>p.name&&String(p.state||'').toLowerCase()==='home')
        .slice(0,1).forEach(p=>facts.push(`${p.name} home`));
    }
    const visibleFacts=facts.slice(0,3);
    $('brain-household-state').hidden=!visibleFacts.length;
    $('brain-household-state').innerHTML=visibleFacts.map(fact=>`<li>${esc(fact)}</li>`).join('');
    $('brain-openings').innerHTML=opening.filter(o=>o!==primary).map(o=>`<span class="brain-tag warm">${esc(o.name)} <small>${esc(o.state)} · ${elapsed(Math.max(o.duration||0,now-o.since))}</small></span>`).join('');
    const actionable=serious?.acknowledgement_required?serious:null;alertId=actionable?.id||'';$('brain-ack').hidden=!actionable||demo;
    const eventRows=events.slice(0,3).map(e=>`<div class="brain-event"><span>${esc(e.title)}</span><time>${elapsed(now-e.at)}${now-e.at>=60?' ago':''}</time></div>`);
    if(events.length>3)eventRows.push(`<div class="brain-event brain-event-more"><button type="button" id="brain-activity-open" data-history-focus-owner aria-label="View all ${events.length} recent events">View all ${events.length} recent events</button></div>`);
    const activityOpenerFocused=$('brain-activity-open')===document.activeElement;
    if(!activityOpenerFocused)$('brain-events').innerHTML=events.length?eventRows.join(''):`<p class="brain-empty">${fresh?'No new door or lock activity in the last 15 minutes.':'Activity feed reconnecting; recent activity is unavailable.'}</p>`;
    if(events.length>3) $('brain-activity-open').onclick=()=>openActivity(events,false,$('brain-activity-open'));
    shell.classList.toggle('brain-no-activity',fresh&&!events.length);
    shell.classList.toggle('brain-quiet',fresh&&!events.length&&!primary&&!serious&&!deviceHealth.length);
    shell.classList.toggle('brain-multiple-openings',opening.length>1);
    renderActivity(events, fresh);
    reconcileActivityHash(events, fresh);
    // Context cards share the household briefing freshness boundary. Do not
    // turn a disconnected snapshot into current agenda guidance.
    const cards=fresh?(state.cards||[]).filter(c=>!c.expires||Date.parse(c.expires)>Date.now()):[];
    const birthdays=cards.find(c=>c.subtype==='birthday_rollup');
    const upcomingAll=cards.filter(c=>c.type==='calendar_event'&&c.subtype!=='birthday_rollup')
      .sort((a,b)=>String(a.starts||'').localeCompare(String(b.starts||''))||(Number(b.priority)||0)-(Number(a.priority)||0));
    const birthdayRows=(birthdays?.rows||[]).filter(Boolean);
    const dayStart=new Date();dayStart.setHours(0,0,0,0);
    const relativeDay=text=>{const value=String(text||'');const match=value.match(/In (\d+) days?/i);return dayStart.getTime()+(match?Number(match[1]):/Tomorrow/i.test(value)?1:0)*86400000};
    const additionalBirthdays=birthdayRows.map(row=>{
      const value=String(row), separator=value.indexOf(' · ');
      const subtitle=separator<0?'Birthday':value.slice(separator+3);
      return {title:separator<0?value:value.slice(0,separator),subtitle,when:relativeDay(subtitle),priority:Number(birthdays?.priority)||0};
    });
    const agendaItems=[...(birthdays?[{title:birthdays.title,subtitle:birthdays.subtitle,when:Date.parse(birthdays.starts)||relativeDay(birthdays.subtitle),priority:Number(birthdays.priority)||0},...additionalBirthdays]:[]),
      ...upcomingAll.map(c=>({...c,when:Date.parse(c.starts)||Infinity}))]
      .sort((a,b)=>a.when-b.when||(Number(b.priority)||0)-(Number(a.priority)||0)).slice(0,10);
    $('brain-agenda-list').innerHTML=agendaItems.length?agendaItems.map(c=>`<div class="brain-agenda-item"><strong>${esc(c.title)}</strong><span>${esc(c.subtitle||c.detail||'')}</span></div>`).join(''):'<p class="brain-empty">No birthdays or events coming up.</p>';
    $('brain-agenda-link').hidden=!fresh;
    const agendaState=!fresh?'stale':(agendaItems.length?'ready':'empty');
    $('brain-agenda').dataset.agendaState=agendaState;
    if(!fresh){
      $('brain-agenda-list').innerHTML='<p class="brain-empty">Calendar context unavailable while the house feed is offline.</p>';
    }
    $('brain-people').innerHTML=(state.people||[]).map(p=>`<span class="brain-person" data-home="${fresh&&p.state.toLowerCase()==='home'}">${esc(p.name)} · ${esc(fresh?p.state:'Unknown')}</span>`).join('');
    let feed=[];
    if(!fresh)feed=[feedEntry('Household connection lost · Current door and lock states are unknown','Household connection lost · Current states unavailable')];
    else {
      if(healthText)feed.push(deviceHealthFeedEntry(healthText,healthNames));
      if(primary)feed.push(feedEntry(`${primary.name} ${primary.state} · observed for ${elapsed(duration)}`,`${primary.name} ${primary.state} · ${elapsed(duration)}`));
      if(event)feed.push(feedEntry(`${event.title} · ${elapsed(now-event.at)}${now-event.at>=60?' ago':''}`,`Recent event: ${narrowLabel(event.title)} · ${elapsed(now-event.at)}`));
      if(state.guests)feed.push(feedEntry('Guest mode is on · The house is expecting company','Guest mode is on'));
      if(state.sleeping)feed.push(feedEntry('Someone is sleeping · Keep it low-key','Someone is sleeping · Keep it low-key'));
      if(state.garage_occupied)feed.push(feedEntry('Garage occupied · Someone’s out in the workshop','Garage occupied · Someone’s out in the workshop'));
      if(state.network==='online')feed.push(feedEntry('House network online','House network online'));
      if(!feed.length)feed=[feedEntry('The house is listening for its next real update')];
    }
    renderFeedEntry(feed[castReceiver ? 0 : Math.floor(now/12)%feed.length]);
    if(event&&now-event.at<45&&event.id!==lastToast&&!demo){lastToast=event.id;toastUntil=now+12;toast.innerHTML=`<span aria-hidden="true">↗</span><div>${esc(event.title)}<small>Just happened at home</small></div>`}
    toast.classList.toggle('show',now<toastUntil);
    for(const [block,id]of [['house','brain-house'],['activity','brain-activity'],['agenda','brain-agenda']])$(id).hidden=visibility[block]===false;
    shell.hidden=hiddenByBlank;dock.hidden=hiddenByBlank;
    fitHousePanel();
    fitAgenda();
  }
  let agendaFitFrame=0;
  function fitAgenda(){
    if(agendaFitFrame)cancelAnimationFrame(agendaFitFrame);
    agendaFitFrame=requestAnimationFrame(()=>{
      agendaFitFrame=0;
      const list=$('brain-agenda-list');
      if(!list || !$('brain-agenda').getClientRects().length)return;
      const items=[...list.querySelectorAll('.brain-agenda-item')];
      items.forEach(item=>{item.hidden=false;item.style.gridColumn='';item.style.gridRow=''});
      const limit=list.getBoundingClientRect().bottom;
      // Keep complete rows in view; the Calendar link holds the full list.
      const columns=getComputedStyle(list).gridTemplateColumns.split(' ').length;
      const firstClipped=items.findIndex(item=>item.getBoundingClientRect().bottom>limit+1);
      const cutoff=firstClipped<0?items.length:Math.floor(firstClipped/columns)*columns;
      items.slice(cutoff).forEach(item=>{item.hidden=true});
      // On the wide Home, read the dates down each column. DOM order stays
      // chronological for keyboards and screen readers.
      if(columns>1&&shell.classList.contains('brain-quiet')&&cutoff){
        const rows=Math.ceil(cutoff/columns);
        items.slice(0,cutoff).forEach((item,index)=>{
          item.style.gridColumn=String(Math.floor(index/rows)+1);
          item.style.gridRow=String(index%rows+1);
        });
      }
    });
  }
  function fitHousePanel(){
    const panel=$('brain-house');
    if(!panel)return;
    panel.classList.remove('fit-compact');
    if(fitFrame)cancelAnimationFrame(fitFrame);
    fitFrame=requestAnimationFrame(()=>{
      fitFrame=0;
      panel.classList.toggle('fit-compact',panel.scrollHeight>panel.clientHeight);
    });
  }
  let activityOpenState=false, activityReturnFocus=null, activityHistoryState=false, activityHistoryTraversalPending=false;
  let activityHashConsumed=location.hash!=='#activity';
  const activityView=$('brain-activity-view'), activityDialog=activityView.querySelector('.brain-activity-dialog');
  const activityBackground=[...document.body.children].filter(node=>node!==shell);
  const activityShellBackground=[...shell.children].filter(node=>node!==activityView);
  const activityFallback=$('brain-headline');
  const activityBackgroundState=new Map();
  function setActivityBackground(inert){
    [...activityBackground,...activityShellBackground].forEach(node=>{
      if(inert){
        if(!activityBackgroundState.has(node))activityBackgroundState.set(node,{ariaHidden:node.getAttribute('aria-hidden'),inert:node.hasAttribute('inert')});
        node.setAttribute('aria-hidden','true');node.setAttribute('inert','');
      }else{
        const prior=activityBackgroundState.get(node);if(!prior)return;
        if(prior.ariaHidden===null)node.removeAttribute('aria-hidden');else node.setAttribute('aria-hidden',prior.ariaHidden);
        if(prior.inert)node.setAttribute('inert','');else node.removeAttribute('inert');activityBackgroundState.delete(node);
      }
    });
  }
  function activityFocusables(){return [...activityDialog.querySelectorAll('button:not([disabled]),[href],input:not([disabled]),select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex="-1"])')].filter(node=>node.getClientRects().length)}
  function reconcileActivityHash(events,fresh){
    if(fresh&&events.length&&location.hash==='#activity'&&!activityHashConsumed&&!activityOpenState)openActivity(events,true);
  }
  function activityCategoryLabel(category){
    const labels={garage_door:'Garage door',door_lock:'Door lock',exterior_door:'Exterior door',window:'Window',visitor:'Visitor',fire_alert:'Fire alert'};
    const key=String(category||'').trim().toLowerCase();
    return labels[key]||(/^[a-z][a-z0-9_-]*$/.test(key)?key.replace(/[_-]+/g,' ').replace(/\b[a-z]/g,letter=>letter.toUpperCase()):'Household activity');
  }
  function renderActivity(events, fresh){
    if(!activityOpenState)return;
    const list=$('brain-activity-list');
    $('brain-activity-count').textContent=!fresh?'Activity is unavailable while the household feed is offline.':`${events.length} event${events.length===1?'':'s'} in the current 15-minute activity window.`;
    list.innerHTML=fresh&&events.length?events.map(e=>`<article class="brain-activity-record"><time datetime="${esc(new Date(Number(e.at)*1000).toISOString())}">${esc(new Date(Number(e.at)*1000).toLocaleString())} · ${esc(elapsed(Date.now()/1000-e.at))}${Date.now()/1000-e.at>=60?' ago':''}</time><strong>${esc(e.title)}</strong><span>${esc(activityCategoryLabel(e.category))}</span></article>`).join(''):'<p class="brain-empty">'+(fresh?'No recent activity is recorded.':'Activity is unavailable while the household feed is offline.')+'</p>';
  }
  function openActivity(events, fromHistory=false, opener=null){
    if(!events.length)return;
    activityReturnFocus=fromHistory?activityFallback:(opener||(document.activeElement?.isConnected&&document.activeElement!==document.body?document.activeElement:null));activityOpenState=true;activityHashConsumed=true;
    if(!fromHistory){history.pushState({marqueeActivity:true},'',`${location.pathname}${location.search}#activity`);activityHistoryState=true;}
    setActivityBackground(true);shell.classList.add('activity-open');activityView.hidden=false;activityView.setAttribute('aria-hidden','false');renderActivity(events,true);$('brain-activity-close').focus();
  }
  function closeActivity(fromHistory=false){
    if(!activityOpenState)return;
    if(activityHistoryState&&!fromHistory){activityHistoryState=false;activityHistoryTraversalPending=true;window.dispatchEvent(new Event('marquee-history-focus-owned'));history.back();return;}
    activityOpenState=false;activityHistoryState=false;if(location.hash==='#activity'){history.replaceState(history.state,'',`${location.pathname}${location.search}`);activityHashConsumed=true;}
    activityView.hidden=true;activityView.setAttribute('aria-hidden','true');shell.classList.remove('activity-open');setActivityBackground(false);
    const activityReturnTarget=activityReturnFocus?.isConnected?activityReturnFocus:activityReturnFocus?.id==='brain-activity-open'?$('brain-activity-open'):null;
    const destination=activityReturnTarget&&!activityReturnTarget.matches('[inert]')?activityReturnTarget:activityFallback;
    // History navigation also lets kiosk-menu restore its destination focus;
    // hand back focus at the next render boundary after that lifecycle settles.
    const returnFocusId=activityReturnFocus?.id;
    requestAnimationFrame(()=>{const focusTarget=(returnFocusId==='brain-activity-open'&&$('brain-activity-open'))||(destination.isConnected?destination:activityFallback);if(focusTarget.isConnected&&!focusTarget.matches('[inert]'))focusTarget.focus()});activityReturnFocus=null;
  }
  $('brain-activity-close').onclick=()=>closeActivity();
  activityView.addEventListener('click',event=>{if(event.target===activityView)closeActivity()});
  document.addEventListener('keydown',event=>{
    if(!activityOpenState)return;
    if(event.key==='Escape'){event.preventDefault();closeActivity();return;}
    if(event.key!=='Tab')return;
    const focusables=activityFocusables(), first=focusables[0], last=focusables[focusables.length-1];
    if(!first)return;
    if(!activityView.contains(document.activeElement)||(event.shiftKey&&document.activeElement===first)||(!event.shiftKey&&document.activeElement===last)){event.preventDefault();(event.shiftKey?last:first).focus();}
  });
  window.addEventListener('popstate',()=>{
    if(activityOpenState){if(activityHistoryTraversalPending)activityHistoryTraversalPending=false;else window.dispatchEvent(new Event('marquee-history-focus-owned'));closeActivity(true);}
    else if(location.hash==='#activity'){activityHashConsumed=false;reconcileActivityHash((state?.events||[]).filter(e=>e.expires>Date.now()/1000),state?.fresh&&Date.now()/1000-received<45);}
  });
  $('brain-ack').onclick=async()=>{const b=$('brain-ack');b.disabled=true;try{const r=await fetch('/api/attention/action',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:alertId,action:'acknowledge'})});if(!r.ok)throw Error();await poll()}catch(_){b.textContent='Could not acknowledge · try again'}finally{b.disabled=false}};
  function weather(){window.MarqueeWeather?.observation(wx)}
  function connectionLost(){feedDisconnected=true;if(state)state.fresh=false;else state={fresh:false,openings:[],events:[],cards:[],alerts:[],people:[]};render()}
  async function poll(lifecycle={}){if(demo)return;try{const r=await fetch('/api/brain',{signal:lifecycle.signal});if(!r.ok)throw Error();const next=await r.json();if(lifecycle.isCurrent&&!lifecycle.isCurrent())return;state=next;feedDisconnected=false;received=Date.now()/1000;render();window.dispatchEvent(new Event('marquee-brain'))}catch(error){if(error?.name==='AbortError'||lifecycle.isCurrent&&!lifecycle.isCurrent())return;connectionLost()}}
  $('brain-retry').onclick=()=>{ $('brain-retry').disabled=true; window.MarqueeLifecycle.request('brain'); setTimeout(()=>{$('brain-retry').disabled=false},500); };
  async function pollWeather(lifecycle={}){try{const r=await fetch('/ha-weather.json',{signal:lifecycle.signal});if(r.ok){wx=await r.json();weather()}}catch(error){if(error?.name!=='AbortError'){} }}
  window.MarqueeBrain={weatherContext(){return state?.cards?.find(c=>c.type==='weather'&&(!c.expires||Date.parse(c.expires)>Date.now()))},configure(cfg,fallback){theme='afterhours';document.body.dataset.liveTheme=theme;visibility=cfg.liveVisibility?.home||{};hiddenByBlank=fallback?.screen==='blank';render()},weather};
  window.addEventListener('resize',()=>{fitHousePanel();fitAgenda()});
  if(document.fonts?.ready)document.fonts.ready.then(fitHousePanel);
  if(demo){const now=Date.now()/1000;received=now;state={fresh:true,source_at:now,openings:[{id:'preview:balcony',name:'Balcony door',category:'exterior_door',state:'open',since:now-420,duration:420}],unknown:[],people:[{name:'Alex',state:'Home'},{name:'Jamie',state:'Away'}],events:[{id:'preview:lock',title:'Front door lock unlocked',at:now-75,expires:now+825},{id:'preview:door',title:'Balcony door opened',at:now-420,expires:now+480}],cards:[{type:'calendar_event',subtype:'birthday_rollup',title:"Casey’s birthday",subtitle:'Tomorrow · September 12',rows:['Jordan · In 6 days','Sam · In 12 days']},{type:'calendar_event',title:'Recycling pickup',subtitle:'Tomorrow morning'},{type:'calendar_event',title:'Dinner with friends',subtitle:'Saturday · 6:30 PM'}],alerts:[],network:'online'};wx={temp:21,condition:'partly cloudy',wind:14,humidity:52,updated:now};render();weather()}
  else{
    window.MarqueeLifecycle.register('brain',{interval:3000,timeout:10000,refresh:poll,onError:connectionLost});
    window.MarqueeLifecycle.register('brain-weather',{interval:60000,refresh:pollWeather});
  }
  // Relative times only change by the minute. Fresh signals still render as
  // soon as the three-second brain poll returns.
  window.MarqueeLifecycle.register('brain-animation',{interval:60000,refresh:()=>{render();weather()}});
})();
