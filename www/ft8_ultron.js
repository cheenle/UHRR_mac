/**
 * FT8 Remote Control — WebSocket frontend for JTDX/WSJT-X (JTDX-class experience)
 * Protocol matches ft8_integration.py backend.
 *
 * Server → browser:
 *   {type:"connected", listen_port, jtdx_port}
 *   {type:"status", data:{software,frequency,mode,band,transmitting,de_call,
 *                         rx_df,tx_df,tx_enabled,tx_first,jtdx_detected,...}}
 *   {type:"decode", data:{time,snr,freq,mode,message,callsign,grid,dxcc_name,
 *                         dxcc_flag,delta_time,worked,excluded,is_cq,to_me,
 *                         new_dxcc,new_grid,...}}
 *   {type:"decodes", data:[...]}                 // history burst on connect
 *   {type:"cycle",  data:{phase,is_tx,slot,seconds_left}}
 *   {type:"qso_state", data:{state,dx_call,dx_grid,enabled}}
 *   {type:"qso_logged", data:{dx_call,dx_grid}}
 *   {type:"command_ack", data:{status,command,message}}
 *
 * Browser → server: {type:"command", command, params}
 *   cq | reply | rr73 | free_text | halt_tx | exclude | settings
 *   answer_cq | call_cq | stop_qso | set_auto_seq
 *   set_tx_msg | send_tx_slot | get_tx_slots
 */

function getCookie(name){const m=document.cookie.match('(?:^|;)\\s*'+name+'=([^;]*)');return m?decodeURIComponent(m[1]):'';}
function setCookie(name,val,days){const d=new Date();d.setDate(d.getDate()+(days||365));document.cookie=name+'='+encodeURIComponent(val)+'; expires='+d.toUTCString()+'; path=/';}

const FT8 = {
  ws:null, reconnectTimer:null, connected:false,
  decodes:[],                // newest first
  decodeMap:{},              // id → decode
  selected:null,             // selected decode (for Reply)
  txSlots:{},                // slot# → template
  status:{},                 // latest status packet
  cycleSlot:-1, sepPending:false,
  activePane:'band',
  filters:{cq:false, worked:false},
  qso:{state:'IDLE', dx_call:'', enabled:false},
  stats:{today:0, worked:0, newDxcc:0, decodes:0},
  settings:{
    callsign:getCookie('ft8_call')||'',
    grid:getCookie('ft8_grid')||'',
    threshold:parseInt(getCookie('ft8_thr'))||-20,
    autoSeq:getCookie('ft8_seq')==='1',
    waterfall:getCookie('ft8_wf')!=='0',
    jtdx_host:getCookie('ft8_jtdx_host')||'',
    jtdx_port:parseInt(getCookie('ft8_jtdx_port'))||0,
  },
};

document.addEventListener('DOMContentLoaded', () => {
  applySettings();
  buildTxSlots(defaultSlots());
  checkSetup();
  updateStats();
  initWaterfall();
  connect();
  if (FT8.settings.waterfall) startAudioWaterfall();
});

// ── WebSocket ──────────────────────────────────────────────
function connect(){
  if (FT8.ws && FT8.ws.readyState===WebSocket.OPEN) return;
  const proto = location.protocol==='https:' ? 'wss:' : 'ws:';
  const url = `${proto}//${location.host}/WSFT8`;
  FT8.ws = new WebSocket(url);
  FT8.ws.onopen = () => { FT8.connected=true; setConnected(true); log('WebSocket connected','ok'); };
  FT8.ws.onmessage = e => handleMsg(e.data);
  FT8.ws.onclose = () => {
    FT8.connected=false; setConnected(false);
    log('Disconnected, retry in 3s','err');
    clearTimeout(FT8.reconnectTimer);
    FT8.reconnectTimer=setTimeout(connect,3000);
  };
  FT8.ws.onerror = () => log('Connection error','err');
}

function sendCmd(command, params={}){
  if (!FT8.ws || FT8.ws.readyState!==WebSocket.OPEN){ log('Not connected','err'); return; }
  FT8.ws.send(JSON.stringify({type:'command', command, params}));
}

function handleMsg(raw){
  let msg; try{ msg=JSON.parse(raw); }catch{ return; }
  switch(msg.type){
    case 'connected':
      log(`FT8 bridge — listen ${msg.listen_port}, JTDX ${msg.jtdx_port}`,'ok');
      pushSettings();
      sendCmd('get_tx_slots');
      break;
    case 'decodes':
      if (Array.isArray(msg.data)) msg.data.forEach(d=>addDecode(d,true));
      renderDecodes();
      break;
    case 'decode': addDecode(msg.data); break;
    case 'status': setStatus(msg.data); break;
    case 'cycle': renderCycle(msg.data); break;
    case 'qso_state': renderQSO(msg.data); break;
    case 'qso_logged': onQSOLogged(msg.data); break;
    case 'command_ack':
      if (msg.data && msg.data.command==='get_tx_slots' && msg.data.slots){
        buildTxSlots(msg.data.slots);
      } else if (msg.data && msg.data.status==='error'){
        log('TX ERROR: '+(msg.data.message||'unknown'),'err');
      } else if (msg.data && msg.data.command){
        log('ACK '+msg.data.command+' '+(msg.data.status||''),'ok');
      }
      break;
    case 'error': log('Server: '+msg.message,'err'); break;
  }
}

// ── Decodes ────────────────────────────────────────────────
function addDecode(d, silent){
  if (FT8.sepPending && !silent){ FT8.decodes.unshift({_sep:true}); FT8.sepPending=false; }
  FT8.stats.decodes++;
  d._id = 'd'+(Date.now())+(Math.random()*1e6|0);
  FT8.decodes.unshift(d);
  FT8.decodeMap[d._id]=d;
  if (FT8.decodes.length>300){ const old=FT8.decodes.pop(); if(old&&old._id) delete FT8.decodeMap[old._id]; }
  if (!silent){
    updateStats();
    renderDecodes();
    // CQ notification for unworked stations above threshold
    if (d.is_cq && !d.worked && !d.excluded && d.snr>=FT8.settings.threshold){
      notify(`CQ ${d.callsign}`, `${d.dxcc_name||''} ${d.snr>0?'+':''}${d.snr}dB`);
    }
  }
}

function passesFilter(d){
  if (FT8.filters.cq && !d.is_cq) return false;
  if (FT8.filters.worked && d.worked) return false;
  return true;
}

// A decode belongs to the Rx-frequency pane if it's addressed to me, is the
// current QSO partner, or sits within ±15 Hz of my Rx audio frequency.
function inRxPane(d){
  if (d.to_me) return true;
  const dx = FT8.qso.dx_call;
  if (dx && d.callsign && d.callsign.toUpperCase()===dx) return true;
  const rxdf = FT8.status.rx_df||0;
  if (rxdf && d.freq && Math.abs(d.freq-rxdf)<=15) return true;
  return false;
}

function rowHtml(d){
  if (d._sep) return '<div class="cycle-sep"></div>';
  let cls='row';
  if (d.excluded) cls+=' excluded';
  else {
    if (d.is_cq) cls+=' cq';
    if (d.to_me) cls+=' tome';
    if (d.new_dxcc) cls+=' newdxcc';
    if (d.new_grid) cls+=' newgrid';
    if (d.worked) cls+=' worked';
  }
  if (FT8.selected && FT8.selected._id===d._id) cls+=' sel';
  const snr=(d.snr>0?'+':'')+d.snr;
  const dt=(typeof d.delta_time==='number')?d.delta_time.toFixed(1):'';
  const fl=((d.dxcc_flag||'')+' '+(d.dxcc_name||'')).trim();
  return `<div class="${cls}" onclick="selectDecode('${d._id}')" ondblclick="dblDecode('${d._id}')">`
    +`<span class="t">${d.time||''}</span>`
    +`<span class="db">${snr}</span>`
    +`<span class="dt">${dt}</span>`
    +`<span class="df">${d.freq||0}</span>`
    +`<span class="m">${escHtml(d.message||'')}</span>`
    +`<span class="fl">${escHtml(fl)}</span>`
  +`</div>`;
}

function renderDecodes(){
  const band=document.getElementById('band-list');
  const rx=document.getElementById('rx-list');
  if (!band||!rx) return;
  const visible=FT8.decodes.filter(d=>d._sep||passesFilter(d));
  if (!visible.length){
    band.innerHTML='<div class="empty">Waiting for decodes&hellip;<br><small>Forward JTDX UDP to '+location.hostname+':2238</small></div>';
  } else {
    band.innerHTML=visible.map(rowHtml).join('');
  }
  const rxItems=FT8.decodes.filter(d=>!d._sep && inRxPane(d));
  rx.innerHTML = rxItems.length ? rxItems.map(rowHtml).join('')
    : '<div class="empty">Traffic on your Rx frequency<br><small>and messages addressed to you</small></div>';
  setText('band-count', visible.filter(d=>!d._sep).length);
  setText('rx-count', rxItems.length);
}

function selectDecode(id){
  const d=FT8.decodeMap[id]; if(!d) return;
  FT8.selected=d;
  renderDecodes();
}

// Double-click = JTDX-style: immediately answer (auto-seq) or single reply.
function dblDecode(id){
  const d=FT8.decodeMap[id]; if(!d) return;
  FT8.selected=d;
  if (FT8.settings.autoSeq) answerCQ(d);
  else replyTo(d);
}

// ── Status & cycle ─────────────────────────────────────────
function setStatus(d){
  FT8.status=d;
  setText('sw-name', d.software||'-');
  setText('sw-freq', d.frequency?(d.frequency/1e6).toFixed(3)+' MHz':'-');
  setText('sw-mode', d.mode||'-');
  setText('sw-band', d.band||'-');
  setText('sw-callsign', d.de_call||'-');
  setText('rx-df', d.rx_df||0);
  setText('tx-df', d.tx_df||0);
  const txi=document.getElementById('tx-enabled-ind');
  if (txi) txi.innerHTML='Tx: <b>'+(d.tx_enabled?'on':'off')+'</b>';
  if (typeof d.tx_first==='boolean'){
    const cb=document.getElementById('tx-first'); if(cb) cb.checked=d.tx_first;
  }
  if (d.de_call && !FT8.settings.callsign){
    FT8.settings.callsign=d.de_call; applySettings(); checkSetup();
  }
  const detEl=document.getElementById('set-jtdx-detected');
  if (detEl && (d.jtdx_detected||d.jtdx_host)){
    detEl.textContent='Detected: '+(d.jtdx_detected||(d.jtdx_host+':'+(d.jtdx_port||'2237')));
  }
  updateWaterfallCursors();
}

function renderCycle(c){
  const bar=document.getElementById('cycle-bar');
  const label=document.getElementById('cycle-label');
  if (bar) bar.style.width=(c.phase*100)+'%';
  if (label){
    const n=Math.round(c.seconds_left);
    const txing = FT8.status.transmitting;
    label.textContent=`${txing?'TX':'RX'}  ${n}s / 15s`;
    label.className=txing?'tx':'rx';
  }
  if (FT8.cycleSlot!==-1 && c.slot!==FT8.cycleSlot) FT8.sepPending=true;
  FT8.cycleSlot=c.slot;
}

// ── QSO state ──────────────────────────────────────────────
function renderQSO(d){
  FT8.qso=d;
  const panel=document.getElementById('qso-panel');
  const badge=document.getElementById('qso-badge');
  const dx=document.getElementById('qso-dx');
  const info=document.getElementById('qso-info');
  if (!panel) return;
  if (!d.enabled && (d.state==='IDLE'||d.state==='DONE')){
    panel.style.display = d.state==='DONE' ? 'flex' : 'none';
  } else {
    panel.style.display='flex';
  }
  badge.textContent=d.state;
  badge.className='badge'+(d.state==='DONE'?' done':(d.enabled?' active':''));
  dx.textContent=d.dx_call||'-';
  const map={CQ:'Calling CQ…',CALLING:'Answered, waiting report',
    REPORTED:'Sent report, waiting R-rpt',ROGERED:'Sent RR73, waiting 73',
    DONE:'QSO complete',IDLE:''};
  info.textContent=(map[d.state]||'')+(d.dx_grid?'  '+d.dx_grid:'');
  // reflect auto-seq button state
  const seqBtn=document.getElementById('seq-btn');
  if (seqBtn) seqBtn.classList.toggle('on', d.enabled || FT8.settings.autoSeq);
  renderDecodes();
}

function onQSOLogged(d){
  FT8.stats.today++; FT8.stats.worked++;
  updateStats();
  log('QSO logged: '+(d.dx_call||''),'ok');
  notify('QSO Logged', d.dx_call||'');
}

// ── TX actions ─────────────────────────────────────────────
function curDx(){
  if (FT8.qso.dx_call) return FT8.qso.dx_call;
  if (FT8.selected && FT8.selected.callsign) return FT8.selected.callsign.toUpperCase();
  return '';
}

function sendCQ(){
  if (!FT8.settings.callsign){ toggleSettings(); return; }
  if (FT8.settings.autoSeq){ sendCmd('call_cq'); log('Auto CQ','tx'); return; }
  const g=FT8.settings.grid||'';
  sendCmd('cq',{message:`CQ ${FT8.settings.callsign} ${g}`.trim()});
  log('CQ','tx');
}

function answerCQ(d){
  if (!FT8.settings.callsign){ toggleSettings(); return; }
  sendCmd('answer_cq',{
    callsign:d.callsign, snr:d.snr,
    time_ms:d.time_ms, delta_time:d.delta_time||0,
    delta_freq:d.delta_freq||d.freq||0, mode:d.mode||'FT8',
    message:d.message,            // ORIGINAL decoded msg — JTDX matches this
  });
  log('Answer CQ → '+d.callsign,'tx');
}

function replySelected(){
  const d=FT8.selected;
  if (!d || !d.callsign){ alert('Select a decode first'); return; }
  if (FT8.settings.autoSeq) answerCQ(d);
  else replyTo(d);
}

function replyTo(d){
  const c=FT8.settings.callsign;
  if (!c){ toggleSettings(); return; }
  // The Reply packet must carry the ORIGINAL decoded message so JTDX can match
  // it against its decode list, key the radio, and auto-sequence the QSO.
  sendCmd('reply',{
    callsign:d.callsign, orig_message:d.message,
    time_ms:d.time_ms, snr:d.snr,
    delta_time:d.delta_time||0, delta_freq:d.delta_freq||d.freq||0,
    mode:d.mode||'FT8',
  });
  log('Reply → '+d.callsign,'tx');
}

function sendRR73(){
  const call=curDx(); if(!call){ alert('No target'); return; }
  sendCmd('rr73',{callsign:call});
  log(`RR73 → ${call}`,'tx');
}

function send73(){
  const call=curDx(); if(!call){ alert('No target'); return; }
  sendCmd('free_text',{text:`${call} ${FT8.settings.callsign} 73`});
  log(`73 → ${call}`,'tx');
}

function sendCustom(){
  const el=document.getElementById('custom-text');
  const text=(el.value||'').trim().toUpperCase();
  if (!text) return;
  if (text.length>13){ alert('Max 13 chars'); return; }
  sendCmd('free_text',{text});
  log('Free text: '+text,'tx');
  el.value='';
}

function haltTX(){ sendCmd('halt_tx'); sendCmd('stop_qso'); log('TX halted','tx'); }
function stopQSO(){ sendCmd('stop_qso'); log('QSO stopped','tx'); }

function toggleAutoSeq(){
  FT8.settings.autoSeq=!FT8.settings.autoSeq;
  setCookie('ft8_seq', FT8.settings.autoSeq?'1':'0');
  sendCmd('set_auto_seq',{enabled:FT8.settings.autoSeq});
  const cb=document.getElementById('set-autoseq'); if(cb) cb.checked=FT8.settings.autoSeq;
  document.getElementById('seq-btn').classList.toggle('on', FT8.settings.autoSeq);
  log('Auto Seq '+(FT8.settings.autoSeq?'ON':'OFF'), FT8.settings.autoSeq?'ok':'');
}

function onTxFirst(){
  // Tx 1st is a JTDX-side toggle; we only reflect it. Inform the user.
  log('Tx 1st is controlled in JTDX (read-only here)');
}

// ── Tx message slots ───────────────────────────────────────
function defaultSlots(){
  return {1:'{DxCall} {MyCall} {MyGrid}',2:'{DxCall} {MyCall} {Report}',
    3:'{DxCall} {MyCall} R{Report}',4:'{DxCall} {MyCall} RR73',
    5:'{DxCall} {MyCall} 73',6:'CQ {MyCall} {MyGrid}'};
}
function buildTxSlots(slots){
  FT8.txSlots=slots||{};
  const wrap=document.getElementById('tx-slots'); if(!wrap) return;
  let html='';
  for (let i=1;i<=6;i++){
    const tpl=FT8.txSlots[i]||FT8.txSlots[String(i)]||'';
    const preview=expandLocal(tpl);
    html+=`<button title="${escHtml(tpl)}" onclick="sendSlot(${i})">`
      +`<span class="n">Tx${i}</span>${escHtml(preview||tpl||'—')}</button>`;
  }
  wrap.innerHTML=html;
}
function expandLocal(tpl){
  if (!tpl) return '';
  const dx=curDx()||'DX';
  return tpl.replace(/\{MyCall\}/g,FT8.settings.callsign||'MYCALL')
    .replace(/\{DxCall\}/g,dx)
    .replace(/\{MyGrid\}/g,FT8.settings.grid||'')
    .replace(/\{Report\}/g,'-15');
}
function sendSlot(n){
  sendCmd('send_tx_slot',{slot:n, dx_call:curDx()});
  log(`Tx${n}`,'tx');
}

// ── Panes / filters ────────────────────────────────────────
function switchPane(p){
  FT8.activePane=p;
  document.querySelectorAll('.pane-tabs button').forEach(b=>{
    b.classList.toggle('on', b.dataset.pane===p);
  });
  document.getElementById('pane-band').classList.toggle('hidden-mobile', p!=='band');
  document.getElementById('pane-rx').classList.toggle('hidden-mobile', p!=='rx');
}
function toggleFilter(f){
  FT8.filters[f]=!FT8.filters[f];
  const id=f==='cq'?'flt-cq':'flt-worked';
  document.getElementById(id).classList.toggle('on', FT8.filters[f]);
  renderDecodes();
}

// ── Waterfall (client-side from /WSaudioRX Opus stream) ────
const WF = {
  canvas:null, ctx:null, w:1024, h:130,
  audioCtx:null, ws:null, decoder:null, opusDecode:false,
  analyser:null, scriptNode:null, srcRate:16000,
  fftBins:512, sampleBuf:[], running:false,
  minDb:-95, maxDb:-30, maxHz:3000,
};

function initWaterfall(){
  WF.canvas=document.getElementById('waterfall');
  if (!WF.canvas) return;
  WF.ctx=WF.canvas.getContext('2d');
  WF.ctx.fillStyle='#000'; WF.ctx.fillRect(0,0,WF.w,WF.h);
  drawScale();
  const wrap=document.getElementById('wf-wrap');
  if (wrap) wrap.classList.toggle('collapsed', !FT8.settings.waterfall);
}

function drawScale(){
  const scale=document.getElementById('wf-scale'); if(!scale) return;
  let html='';
  for (let hz=0; hz<=WF.maxHz; hz+=500){
    const x=(hz/WF.maxHz)*100;
    html+=`<span style="left:${x}%">${hz}</span>`;
  }
  scale.innerHTML=html;
}

function updateWaterfallCursors(){
  const setCur=(id,df)=>{
    const el=document.getElementById(id); if(!el) return;
    if (!df){ el.style.display='none'; return; }
    const x=Math.min(1,Math.max(0,df/WF.maxHz));
    el.style.left=(x*100)+'%';
    el.style.display='block';
  };
  setCur('wf-rx', FT8.status.rx_df||0);
  setCur('wf-tx', FT8.status.tx_df||0);
}

function startAudioWaterfall(){
  if (WF.running) return;
  if (typeof OpusDecoder==='undefined'){ log('Opus decoder unavailable — waterfall off','err'); return; }
  try{
    WF.audioCtx=new (window.AudioContext||window.webkitAudioContext)({sampleRate:WF.srcRate});
  }catch(e){ /* sampleRate hint may be ignored */ WF.audioCtx=new (window.AudioContext||window.webkitAudioContext)(); }
  WF.analyser=WF.audioCtx.createAnalyser();
  WF.analyser.fftSize=2048;
  WF.analyser.smoothingTimeConstant=0.4;
  WF.analyser.minDecibels=WF.minDb;
  WF.analyser.maxDecibels=WF.maxDb;
  const proto=location.protocol==='https:'?'wss:':'ws:';
  WF.ws=new WebSocket(`${proto}//${location.host}/WSaudioRX`);
  WF.ws.binaryType='arraybuffer';
  WF.ws.onopen=()=>{ WF.running=true; log('Waterfall audio connected','ok'); };
  WF.ws.onmessage=onWFAudio;
  WF.ws.onclose=()=>{ WF.running=false; if(FT8.settings.waterfall) setTimeout(startAudioWaterfall,4000); };
  WF.ws.onerror=()=>{};
  requestAnimationFrame(wfRender);
}

function stopAudioWaterfall(){
  WF.running=false;
  if (WF.ws){ try{WF.ws.close();}catch{} WF.ws=null; }
  if (WF.audioCtx){ try{WF.audioCtx.close();}catch{} WF.audioCtx=null; }
  WF.analyser=null;
}

function onWFAudio(msg){
  const data=msg.data;
  if (!data||!data.byteLength) return;
  let f32=null;
  // Opus frames are small (<500B); larger payloads are raw Int16.
  if (data.byteLength<500){
    if (!WF.decoder){ WF.decoder=new OpusDecoder(WF.srcRate,1); }
    try{
      const i16=WF.decoder.decode(data);
      f32=new Float32Array(i16.length);
      for (let i=0;i<i16.length;i++) f32[i]=i16[i]/32768;
    }catch(e){ return; }
  } else {
    const i16=new Int16Array(data);
    f32=new Float32Array(i16.length);
    for (let i=0;i<i16.length;i++) f32[i]=i16[i]/32768;
  }
  if (f32) pushAudio(f32);
}

// Feed PCM into the analyser via a buffer source chain (kept primed).
function pushAudio(f32){
  if (!WF.audioCtx||!WF.analyser) return;
  const buf=WF.audioCtx.createBuffer(1, f32.length, WF.srcRate);
  buf.copyToChannel(f32,0);
  const src=WF.audioCtx.createBufferSource();
  src.buffer=buf;
  src.connect(WF.analyser);
  // analyser is NOT connected to destination → silent (we only want FFT)
  try{ src.start(); }catch(e){}
}

function wfRender(){
  if (!WF.running){ return; }
  if (WF.analyser){
    const bins=WF.analyser.frequencyBinCount;          // 1024 for fftSize 2048
    const arr=new Uint8Array(bins);
    WF.analyser.getByteFrequencyData(arr);
    // Map 0..maxHz to the canvas width; bin freq = i * (srcRate/2)/bins
    const nyq=WF.srcRate/2;
    const maxBin=Math.min(bins, Math.floor(WF.maxHz/nyq*bins));
    const ctx=WF.ctx;
    // scroll up by 1px
    const img=ctx.getImageData(0,0,WF.w,WF.h-1);
    ctx.putImageData(img,0,1);
    // draw newest row at top
    for (let x=0;x<WF.w;x++){
      const bin=Math.floor(x/WF.w*maxBin);
      const v=arr[bin]||0;
      ctx.fillStyle=wfColor(v);
      ctx.fillRect(x,0,1,1);
    }
  }
  requestAnimationFrame(wfRender);
}

// Blue→cyan→green→yellow→red colormap
function wfColor(v){
  const t=v/255;
  let r,g,b;
  if (t<0.25){ r=0; g=Math.floor(t*4*255); b=255; }
  else if (t<0.5){ r=0; g=255; b=Math.floor((0.5-t)*4*255); }
  else if (t<0.75){ r=Math.floor((t-0.5)*4*255); g=255; b=0; }
  else { r=255; g=Math.floor((1-t)*4*255); b=0; }
  return `rgb(${r},${g},${b})`;
}

function toggleWaterfall(){
  FT8.settings.waterfall=!FT8.settings.waterfall;
  setCookie('ft8_wf', FT8.settings.waterfall?'1':'0');
  const wrap=document.getElementById('wf-wrap');
  if (wrap) wrap.classList.toggle('collapsed', !FT8.settings.waterfall);
  const cb=document.getElementById('set-waterfall'); if(cb) cb.checked=FT8.settings.waterfall;
  if (FT8.settings.waterfall) startAudioWaterfall(); else stopAudioWaterfall();
}

// ── Settings ───────────────────────────────────────────────
function toggleSettings(){ document.getElementById('settings-panel').classList.toggle('active'); }

function applySettings(){
  const s=FT8.settings, byId=id=>document.getElementById(id);
  if (byId('set-call')) byId('set-call').value=s.callsign;
  if (byId('set-grid')) byId('set-grid').value=s.grid;
  if (byId('set-threshold')) byId('set-threshold').value=s.threshold;
  if (byId('set-autoseq')) byId('set-autoseq').checked=s.autoSeq;
  if (byId('set-waterfall')) byId('set-waterfall').checked=s.waterfall;
  if (byId('set-jtdx-host')) byId('set-jtdx-host').value=s.jtdx_host;
  if (byId('set-jtdx-port')) byId('set-jtdx-port').value=s.jtdx_port||'';
  const seqBtn=document.getElementById('seq-btn'); if(seqBtn) seqBtn.classList.toggle('on', s.autoSeq);
}

function pushSettings(){
  const s=FT8.settings;
  sendCmd('settings',{
    callsign:s.callsign, grid:s.grid, threshold:s.threshold,
    auto_seq:s.autoSeq, jtdx_host:s.jtdx_host, jtdx_port:s.jtdx_port,
  });
}

function saveSettings(){
  const s=FT8.settings;
  s.callsign=(document.getElementById('set-call').value||'').toUpperCase();
  s.grid=(document.getElementById('set-grid').value||'').toUpperCase();
  s.threshold=parseInt(document.getElementById('set-threshold').value)||-20;
  s.autoSeq=document.getElementById('set-autoseq').checked;
  const wantWf=document.getElementById('set-waterfall').checked;
  s.jtdx_host=(document.getElementById('set-jtdx-host').value||'').trim();
  s.jtdx_port=parseInt(document.getElementById('set-jtdx-port').value)||0;
  setCookie('ft8_call',s.callsign); setCookie('ft8_grid',s.grid);
  setCookie('ft8_thr',s.threshold); setCookie('ft8_seq',s.autoSeq?'1':'0');
  setCookie('ft8_jtdx_host',s.jtdx_host); setCookie('ft8_jtdx_port',s.jtdx_port||'');
  setCookie('ft8_wf', wantWf?'1':'0');
  pushSettings();
  buildTxSlots(FT8.txSlots);   // refresh previews with new call/grid
  toggleSettings();
  checkSetup();
  if (wantWf!==s.waterfall){ s.waterfall=wantWf; if(wantWf) startAudioWaterfall(); else stopAudioWaterfall();
    const wrap=document.getElementById('wf-wrap'); if(wrap) wrap.classList.toggle('collapsed', !wantWf); }
  log('Settings saved');
}

function checkSetup(){
  const c=FT8.settings.callsign;
  const notice=document.getElementById('setup-notice');
  if (notice) notice.style.display=c?'none':'flex';
}

// ── UI helpers ─────────────────────────────────────────────
function setConnected(on){
  const dot=document.getElementById('conn-dot'), txt=document.getElementById('conn-text');
  if(!dot||!txt) return;
  dot.className='dot '+(on?'online':'offline');
  txt.textContent=on?'Online':'Offline';
}
function setText(id,val){ const el=document.getElementById(id); if(el) el.textContent=val; }
function log(msg,cls=''){
  const el=document.getElementById('log-panel'); if(!el) return;
  const d=document.createElement('div');
  d.className='log-line'+(cls?' '+cls:'');
  d.textContent=`[${new Date().toLocaleTimeString()}] ${msg}`;
  el.appendChild(d); el.scrollTop=el.scrollHeight;
  while(el.children.length>80) el.removeChild(el.firstChild);
}
function notify(title,body){
  if ('Notification' in window && Notification.permission==='granted') new Notification(title,{body});
}
function updateStats(){
  setText('stat-decode',FT8.stats.decodes);
  setText('stat-today',FT8.stats.today);
  setText('stat-worked',FT8.stats.worked);
  setText('stat-new',FT8.stats.newDxcc);
}
function escHtml(s){ return (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

if ('Notification' in window && Notification.permission==='default') Notification.requestPermission();
