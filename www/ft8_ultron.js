/**
 * FT8 Remote Control — WebSocket frontend for JTDX/WSJT-X
 * Protocol matches ft8_integration.py backend.
 *
 * Messages from server:
 *   {type:"connected", version, listen_port, jtdx_port}
 *   {type:"status", data:{software, frequency, mode, band, transmitting, callsign}}
 *   {type:"decode", data:{time, snr, freq, mode, message, callsign, grid, dxcc_id, dxcc_name, dxcc_flag, worked, excluded}}
 *   {type:"cycle", data:{phase, is_tx, slot, seconds_left}}
 *   {type:"qso_logged", data:{dx_call, dx_grid}}
 *   {type:"error", message}
 *
 * Messages to server:
 *   {type:"command", command:"cq|reply|rr73|free_text|halt_tx|settings|exclude", params:{}}
 */

function getCookie(name) {
  const m = document.cookie.match('(?:^|;)\\s*' + name + '=([^;]*)');
  return m ? decodeURIComponent(m[1]) : '';
}

function setCookie(name, val, days) {
  const d = new Date();
  d.setDate(d.getDate() + (days || 365));
  document.cookie = name + '=' + encodeURIComponent(val) + '; expires=' + d.toUTCString() + '; path=/';
}

const FT8 = {
  ws: null,
  reconnectTimer: null,
  connected: false,
  decodes: [],
  decodeMap: {},         // quick lookup by ID for transmit reply info
  selectedDecode: null,  // full decode data for current target
  settings: {
    callsign: getCookie('ft8_call') || '',
    grid: getCookie('ft8_grid') || '',
    threshold: parseInt(getCookie('ft8_thr')) || -20,
    autoReply: getCookie('ft8_ar') === '1',
    jtdx_host: getCookie('ft8_jtdx_host') || '',
    jtdx_port: parseInt(getCookie('ft8_jtdx_port')) || 0,
  },
  stats: { today: 0, worked: 0, newDxcc: 0, decodes: 0 },
  cycleSlot: -1,
  sepPending: false,
};

document.addEventListener('DOMContentLoaded', () => {
  applySettings();
  checkSetup();
  updateStats();
  connect();
});

function connect() {
  if (FT8.ws && FT8.ws.readyState === WebSocket.OPEN) return;
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const url = `${proto}//${window.location.host}/WSFT8`;
  console.log('[FT8] Connecting to', url);

  FT8.ws = new WebSocket(url);
  FT8.ws.onopen = () => {
    FT8.connected = true;
    setConnected(true);
    log('WebSocket connected', 'ok');
  };
  FT8.ws.onmessage = e => handleMsg(e.data);
  FT8.ws.onclose = () => {
    FT8.connected = false;
    setConnected(false);
    log('Disconnected, retry in 3s', 'err');
    clearTimeout(FT8.reconnectTimer);
    FT8.reconnectTimer = setTimeout(connect, 3000);
  };
  FT8.ws.onerror = () => log('Connection error', 'err');
}

function sendCmd(command, params = {}) {
  if (!FT8.ws || FT8.ws.readyState !== WebSocket.OPEN) {
    log('Not connected', 'err');
    return;
  }
  const payload = JSON.stringify({ type: 'command', command, params });
  FT8.ws.send(payload);
  console.log('[FT8] TX cmd:', command, params);
}

function handleMsg(raw) {
  let msg;
  try { msg = JSON.parse(raw); } catch { return; }

  switch (msg.type) {
    case 'connected':
      log(`FT8 connected — listen port ${msg.listen_port}, JTDX port ${msg.jtdx_port}`, 'ok');
      sendCmd('settings', FT8.settings);
      break;

    case 'decodes':
      if (Array.isArray(msg.data)) {
        msg.data.forEach(d => addDecode(d));
      }
      break;

    case 'decode':
      addDecode(msg.data);
      break;

    case 'status':
      setStatus(msg.data);
      break;

    case 'cycle':
      renderCycle(msg.data);
      break;

    case 'qso_logged':
      onQSOLogged(msg.data);
      break;

    case 'command_ack':
      if (msg.data && msg.data.status === 'error') {
        log('TX ERROR: ' + (msg.data.message || 'unknown'), 'err');
        alert('TX command failed: ' + (msg.data.message || 'unknown') +
          '\n\nCheck Settings → JTDX host/port.');
      } else if (msg.data && msg.data.command) {
        log('ACK: ' + msg.data.command + ' ' + (msg.data.status || ''), 'ok');
      }
      break;

    case 'error':
      log('Server: ' + msg.message, 'err');
      break;
  }
}

// ── Setup check ──
function checkSetup() {
  const c = FT8.settings.callsign;
  const notice = document.getElementById('setup-notice');
  const cqBtn = document.querySelector('.ctrl .cq');
  if (notice) notice.style.display = c ? 'none' : 'flex';
  if (cqBtn) cqBtn.style.opacity = c ? '1' : '0.4';
}

// ── Decodes ──
function addDecode(d) {
  if (FT8.sepPending) {
    FT8.decodes.unshift({ _sep: true });
    FT8.sepPending = false;
  }
  FT8.stats.decodes++;
  updateStats();
  d._id = Date.now() + Math.random();
  FT8.decodes.unshift(d);
  FT8.decodeMap[d._id] = d;  // store for transmit reply lookup
  if (FT8.decodes.length > 200) {
    const old = FT8.decodes.pop();
    if (old && old._id) delete FT8.decodeMap[old._id];
  }
  renderDecodes();

  if (!d.worked && !d.excluded && d.snr >= FT8.settings.threshold) {
    const parts = d.message.split(' ');
    if (parts[0] === 'CQ' || parts[0] === 'QRZ') {
      notify(`CQ: ${d.callsign}`, `${d.dxcc_name}  ${d.snr}dB`);
    }
  }
}

function renderDecodes() {
  const el = document.getElementById('decode-list');
  if (!el) return;
  if (!FT8.decodes.length) {
    el.innerHTML = '<div class="empty">Waiting for decodes…<br><small>Start JTDX/WSJT-X, set UDP forward → ' + window.location.hostname + ':2238</small></div>';
    return;
  }
  el.innerHTML = FT8.decodes.map(d => {
    if (d._sep) {
      return '<div class="cycle-sep"></div>';
    }
    let cls = 'decode-item';
    if (d.worked) cls += ' worked';
    if (d.excluded) cls += ' excluded';
    if (d.message.startsWith('CQ') && !d.worked && !d.excluded) cls += ' cq';
    if (d.dxcc_name && d.dxcc_name !== '?') cls += ' has-dxcc';

    const flag = d.dxcc_flag || '';
    const name = d.dxcc_name || '';

    return `<div class="${cls}" onclick="selectDecode('${d._id}')">
      <span class="time">${d.time}</span>
      <span class="snr ${d.snr < -20 ? 'weak' : ''}">${d.snr > 0 ? '+' : ''}${d.snr}</span>
      <span class="freq">${d.freq}Hz</span>
      <span class="msg"><span class="call">${escHtml(d.callsign || '')}</span> ${escHtml(d.message)}</span>
      <span class="dxcc">${flag} ${name}</span>
    </div>`;
  }).join('');
}

function selectDecode(id) {
  const d = FT8.decodeMap[id];
  if (!d) return;
  FT8.selectedDecode = d;
  document.getElementById('target-call').textContent = d.callsign || '';
  document.getElementById('target-msg').textContent = d.message || '';
  document.getElementById('target-panel').style.display = 'flex';
}

// ── Status & Cycle ──
function setStatus(d) {
  setText('sw-name', d.software || '-');
  setText('sw-freq', d.frequency ? (d.frequency / 1e6).toFixed(3) + ' MHz' : '-');
  setText('sw-mode', d.mode || '-');
  setText('sw-band', d.band || '-');
  setText('sw-callsign', d.de_call || d.dx_call || '-');

  // Show JTDX connection info from server status (initial connect only)
  if (d.jtdx_detected || d.jtdx_host) {
    const el = document.getElementById('set-jtdx-detected');
    if (el) {
      el.textContent = 'Detected: ' + (d.jtdx_detected || d.jtdx_host + ':' + (d.jtdx_port || '2237'));
    }
  }
}

function renderCycle(c) {
  const bar = document.getElementById('cycle-bar');
  const label = document.getElementById('cycle-label');
  if (bar) bar.style.width = (c.phase * 100) + '%';
  if (label) {
    const tx = c.is_tx ? 'TX' : 'RX';
    const n = Math.round(c.seconds_left);
    label.textContent = `${tx}  ${n}s / 15s`;
    label.className = c.is_tx ? 'tx' : 'rx';
  }
  if (FT8.cycleSlot !== -1 && c.slot !== FT8.cycleSlot) {
    FT8.sepPending = true;
  }
  FT8.cycleSlot = c.slot;
}

// ── QSO ──
function onQSOLogged(d) {
  FT8.stats.today++;
  FT8.stats.worked++;
  const call = d.dx_call || '';
  log(`QSO: ${call}`, 'ok');
  notify('QSO Logged', call);
}

// ── TX Controls ──
function sendCQ() {
  const c = FT8.settings.callsign;
  if (!c) { toggleSettings(); return; }
  const g = FT8.settings.grid || 'AA00';
  const msg = `CQ ${c} ${g}`;
  sendCmd('cq', { message: msg });
  log(`CQ: ${msg}`, 'tx');
}

function sendReply() {
  const call = document.getElementById('target-call').textContent;
  const c = FT8.settings.callsign;
  const g = FT8.settings.grid || 'AA00';
  if (!call || call === '-') { alert('No target callsign'); return; }
  const msg = `${call} ${c} ${g}`;

  const d = FT8.selectedDecode;
  if (d && d.time_ms !== undefined && d.snr !== undefined) {
    // Use Reply packet type with full decode info
    sendCmd('reply', {
      callsign: call,
      message: msg,
      time_ms: d.time_ms,
      snr: d.snr,
      delta_time: d.delta_time || 0.0,
      delta_freq: d.delta_freq || d.freq || 0,
      mode: d.mode || 'FT8',
    });
  } else {
    sendCmd('reply', { callsign: call, message: msg });
  }
  log(`Reply: ${msg}`, 'tx');
  hideTarget();
}

function sendRR73() {
  const call = document.getElementById('target-call').textContent;
  if (!call || call === '-') return;
  const c = FT8.settings.callsign;
  const msg = `${call} ${c} RR73`;
  sendCmd('rr73', { callsign: call, message: msg });
  log(`RR73: ${msg}`, 'tx');
  hideTarget();
}

function send73() {
  const call = document.getElementById('target-call').textContent;
  if (!call || call === '-') return;
  const c = FT8.settings.callsign;
  const msg = `${call} ${c} 73`;
  sendCmd('free_text', { text: msg });
  log(`73: ${msg}`, 'tx');
  hideTarget();
}

function sendCustom() {
  const el = document.getElementById('custom-text');
  const text = (el.value || '').trim().toUpperCase();
  if (!text) return;
  if (text.length > 30) { alert('Max 30 chars'); return; }
  sendCmd('free_text', { text });
  log(`Custom: ${text}`, 'tx');
  el.value = '';
}

function haltTX() {
  sendCmd('halt_tx');
  log('TX halted', 'tx');
}

function exclude() {
  const call = document.getElementById('target-call').textContent;
  if (call && call !== '-') {
    sendCmd('exclude', { callsign: call });
    log(`Excluded: ${call}`);
    hideTarget();
  }
}

function hideTarget() {
  document.getElementById('target-panel').style.display = 'none';
}

// ── Settings ──
function toggleSettings() {
  document.getElementById('settings-panel').classList.toggle('active');
}

function applySettings() {
  const s = FT8.settings;
  const byId = id => document.getElementById(id);
  if (byId('set-call')) byId('set-call').value = s.callsign;
  if (byId('set-grid')) byId('set-grid').value = s.grid;
  if (byId('set-threshold')) byId('set-threshold').value = s.threshold;
  if (byId('set-autoreply')) byId('set-autoreply').checked = s.autoReply;
  if (byId('set-jtdx-host')) byId('set-jtdx-host').value = s.jtdx_host;
  if (byId('set-jtdx-port')) byId('set-jtdx-port').value = s.jtdx_port || '';
}

function saveSettings() {
  const s = FT8.settings;
  s.callsign = (document.getElementById('set-call').value || '').toUpperCase();
  s.grid = (document.getElementById('set-grid').value || '').toUpperCase();
  s.threshold = parseInt(document.getElementById('set-threshold').value) || -20;
  s.autoReply = document.getElementById('set-autoreply').checked;
  s.jtdx_host = (document.getElementById('set-jtdx-host').value || '').trim();
  s.jtdx_port = parseInt(document.getElementById('set-jtdx-port').value) || 0;

  setCookie('ft8_call', s.callsign);
  setCookie('ft8_grid', s.grid);
  setCookie('ft8_thr', s.threshold);
  setCookie('ft8_ar', s.autoReply ? '1' : '0');
  setCookie('ft8_jtdx_host', s.jtdx_host);
  setCookie('ft8_jtdx_port', s.jtdx_port || '');

  sendCmd('settings', s);
  toggleSettings();
  checkSetup();
  log('Settings saved');
}

// ── UI helpers ──
function setConnected(on) {
  const dot = document.getElementById('conn-dot');
  const txt = document.getElementById('conn-text');
  if (!dot || !txt) return;
  dot.className = 'dot ' + (on ? 'online' : 'offline');
  txt.textContent = on ? 'Online' : 'Offline';
}

function setText(id, val) {
  const el = document.getElementById(id);
  if (el) el.textContent = val;
}

function log(msg, cls = '') {
  const el = document.getElementById('log-panel');
  if (!el) return;
  const d = document.createElement('div');
  d.className = 'log-line' + (cls ? ' ' + cls : '');
  d.textContent = `[${new Date().toLocaleTimeString()}] ${msg}`;
  el.appendChild(d);
  el.scrollTop = el.scrollHeight;
  while (el.children.length > 80) el.removeChild(el.firstChild);
}

function notify(title, body) {
  if ('Notification' in window && Notification.permission === 'granted') {
    new Notification(title, { body });
  }
}

function updateStats() {
  setText('stat-decode', FT8.stats.decodes);
  setText('stat-today', FT8.stats.today);
  setText('stat-worked', FT8.stats.worked);
  setText('stat-new', FT8.stats.newDxcc);
}

function escHtml(s) {
  if (!s) return '';
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

if ('Notification' in window && Notification.permission === 'default') {
  Notification.requestPermission();
}
