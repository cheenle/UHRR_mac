#!/usr/bin/env python3
"""
FT8 Integration Module for MRRC
UDP ↔ WebSocket bridge for JTDX/WSJT-X remote control

Architecture:
  JTDX/WSJT-X (UDP 2237)  ←→  ft8_integration (UDP 2238 listen)
        ↑                          ↓
        └────── UDP sends ─────────┘
                                   ↓
                            WebSocket /WSFT8
                                   ↓
                            Browser frontend

Usage:
  - JTDX/WSJT-X must be configured to forward UDP to 127.0.0.1:2238
    (Settings → Reporting → UDP Secondary Port)
  - Listens on 2238 by default (configurable, never conflicts with JTDX's 2237)
  - Sends Reply/Free Text back to JTDX on 2237
"""

import json
import logging
import os
import re
import socket
import struct
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger('FT8')
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    h = logging.StreamHandler()
    h.setLevel(logging.DEBUG)
    h.setFormatter(logging.Formatter('FT8: %(message)s'))
    logger.addHandler(h)
    logger.propagate = False

# ── Constants ───────────────────────────────────────────────
LISTEN_PORT = 2238
JTDX_PORT = 2237
JTDX_HOST = "127.0.0.1"
WSJT_MAX_PACKET = 2048
CYCLE_15S = 15.0

# Magic numbers
MAGIC_WSJTX = 0xadbccbda
VALID_MAGICS = {MAGIC_WSJTX}

# Packet types (outgoing from JTDX)
PKT_STATUS = 1
PKT_DECODE = 2
PKT_CLEAR = 3
PKT_QSO_LOGGED = 5
PKT_CLOSE = 6
PKT_ADIF_LOGGED = 12

# Packet types (incoming to JTDX)
PKT_REPLY = 4
PKT_HALT_TX = 8
PKT_FREE_TEXT = 9


@dataclass
class CycleState:
    phase: float = 0.0
    is_tx: bool = False
    seconds_left: float = 15.0
    cycle_start: float = 0.0
    slot: int = 0

    def update(self):
        now = time.time()
        elapsed = now % CYCLE_15S
        self.phase = elapsed / CYCLE_15S
        self.seconds_left = CYCLE_15S - elapsed
        self.cycle_start = now - elapsed
        tot = int(now / CYCLE_15S)
        self.slot = tot % 2
        self.is_tx = (self.slot == 0)


@dataclass
class DecodeEntry:
    time: str
    snr: int
    freq: int
    mode: str
    message: str
    callsign: str = ""
    grid: str = ""
    dxcc_id: str = ""
    dxcc_name: str = ""
    dxcc_flag: str = ""
    time_ms: int = 0
    delta_time: float = 0.0
    delta_freq: int = 0


# ── DXCC Database ──────────────────────────────────────────
class DXCCDatabase:
    def __init__(self):
        self.db: List[Dict] = []
        for p in ["ft8/base.json", "base.json",
                   str(Path(__file__).parent / "ft8" / "base.json")]:
            if os.path.exists(p):
                try:
                    with open(p, 'r', encoding='utf-8') as f:
                        self.db = json.load(f)
                    logger.info(f"DXCC database loaded ({len(self.db)} entries) from {p}")
                except Exception as e:
                    logger.warning(f"Cannot load DXCC db from {p}: {e}")
                break

    def locate(self, call: str) -> Dict[str, str]:
        call = call.upper()
        for i in range(len(call), 0, -1):
            prefix = call[:i]
            for entry in self.db:
                if re.search(r'\b' + re.escape(prefix) + r'\b',
                             entry.get('licencia', ''), re.IGNORECASE):
                    return {
                        'id': str(entry.get('id', '')),
                        'flag': entry.get('flag', ''),
                        'name': entry.get('name', 'Unknown'),
                    }
        return {'id': '', 'flag': '', 'name': '?'}


# ── ADIF Processor ─────────────────────────────────────────
class ADIFProcessor:
    @staticmethod
    def parse(data: str) -> List[Dict]:
        qsos, cur = [], {}
        for m in re.finditer(r'<([A-Z0-9_]+):(\d+)(?::[A-Z])?>([^<]*)', data, re.I):
            f, _, v = m.group(1).lower(), m.group(2), m.group(3).strip()
            if v:
                cur[f] = v
            if f == 'eor':
                if cur:
                    qsos.append(cur.copy())
                cur = {}
        if cur:
            qsos.append(cur)
        return qsos

    @staticmethod
    def format(qso: Dict) -> str:
        parts = []
        for k, v in qso.items():
            if k == 'eor':
                continue
            parts.append(f"<{k.upper()}:{len(str(v))}>{v}")
        parts.append("<EOR>")
        return " ".join(parts)


# ── WSJT-X Protocol ────────────────────────────────────────
class WSJTXProtocol:
    @staticmethod
    def parse_header(data: bytes) -> Optional[Dict]:
        if len(data) < 12:
            return None
        magic = struct.unpack_from('>I', data, 0)[0]
        if magic not in VALID_MAGICS:
            return None
        schema = struct.unpack_from('>I', data, 4)[0]
        ptype = struct.unpack_from('>I', data, 8)[0]
        return {'magic': magic, 'schema': schema, 'type': ptype, 'data': data[12:]}

    @staticmethod
    def _read_utf8(data: bytes, offset: int) -> tuple:
        ln = struct.unpack_from('>I', data, offset)[0]
        offset += 4
        if ln == 0xFFFFFFFF:
            return '', offset
        s = data[offset:offset + ln].decode('utf-8', errors='replace')
        offset += ln
        return s, offset

    @classmethod
    def parse_status(cls, data: bytes) -> Dict:
        try:
            offset = 0
            software, offset = cls._read_utf8(data, offset)
            freq = struct.unpack_from('>Q', data, offset)[0]; offset += 8
            mode, offset = cls._read_utf8(data, offset)
            dx_call, offset = cls._read_utf8(data, offset)
            report, offset = cls._read_utf8(data, offset)
            tx_mode, offset = cls._read_utf8(data, offset)
            tx_enabled = bool(data[offset]); offset += 1
            transmitting = bool(data[offset]); offset += 1
            decoding = bool(data[offset]); offset += 1
            rx_df = struct.unpack_from('>i', data, offset)[0]; offset += 4
            tx_df = struct.unpack_from('>i', data, offset)[0]; offset += 4
            de_call, offset = cls._read_utf8(data, offset)
            de_grid, offset = cls._read_utf8(data, offset)
            dx_grid, offset = cls._read_utf8(data, offset)
            tx_watchdog = bool(data[offset]); offset += 1
            sub_mode, offset = cls._read_utf8(data, offset)
            fast_mode = bool(data[offset]); offset += 1
            tx_first = bool(data[offset]); offset += 1
            return {
                'type': 'status', 'software': software.strip(),
                'frequency': freq, 'mode': mode.strip(),
                'dx_call': dx_call.strip(), 'report': report.strip(),
                'tx_mode': tx_mode.strip(),
                'transmitting': transmitting,
                'tx_enabled': tx_enabled,
                'rx_df': rx_df, 'tx_df': tx_df,
                'de_call': de_call.strip(), 'de_grid': de_grid.strip(),
                'dx_grid': dx_grid.strip(),
            }
        except Exception as e:
            logger.warning(f"parse_status error: {e}")
            return {'type': 'status', 'software': '', 'frequency': 0, 'mode': ''}

    @classmethod
    def parse_decode(cls, data: bytes) -> Optional[Dict]:
        try:
            offset = 0
            software, offset = cls._read_utf8(data, offset)
            new_decode = bool(data[offset]); offset += 1
            time_ms = struct.unpack_from('>I', data, offset)[0]; offset += 4
            snr = struct.unpack_from('>i', data, offset)[0]; offset += 4
            delta_time = struct.unpack_from('>d', data, offset)[0]; offset += 8
            delta_freq = struct.unpack_from('>I', data, offset)[0]; offset += 4
            mode, offset = cls._read_utf8(data, offset)
            message, offset = cls._read_utf8(data, offset)
            if offset < len(data):
                low_conf = bool(data[offset]); offset += 1
            else:
                low_conf = False
            if offset < len(data):
                off_air = bool(data[offset])
            else:
                off_air = False
            msg_text = message.strip()
            callsign = ""
            grid = ""
            parts = msg_text.split()
            if len(parts) >= 2:
                if parts[0].upper() == "CQ" and len(parts) >= 2:
                    callsign = parts[1]
                    if len(parts) >= 3 and re.match(r'^[A-R]{2}\d{2}$', parts[2]):
                        grid = parts[2]
                elif len(parts) >= 2:
                    callsign = parts[0]
                    for p in parts[1:]:
                        if re.match(r'^[A-R]{2}\d{2}$', p.upper()):
                            grid = p.upper()
                            break
            mode_clean = mode.strip()
            if mode_clean in ('~', ''):
                mode_clean = 'FT8'
            elif mode_clean == '@':
                mode_clean = 'JT9'
            return {
                'type': 'decode', 'software': software.strip(),
                'new_decode': new_decode, 'time_ms': time_ms,
                'snr': snr, 'delta_time': delta_time,
                'delta_freq': delta_freq, 'mode': mode_clean,
                'message': msg_text,
                'callsign': callsign, 'grid': grid,
                'low_confidence': low_conf, 'off_air': off_air,
            }
        except Exception as e:
            logger.warning(f"parse_decode error: {e}")
            return None

    @classmethod
    def parse_qso_logged(cls, data: bytes) -> Optional[Dict]:
        try:
            offset = 0
            _, offset = cls._read_utf8(data, offset)
            date_msecs = struct.unpack_from('>q', data, offset)[0]; offset += 8
            _ = bool(data[offset]); offset += 1  # date spec (UTC)
            _ = bool(data[offset]); offset += 1  # dst
            _ = struct.unpack_from('>i', data, offset)[0]; offset += 4  # tz offset
            dx_call, offset = cls._read_utf8(data, offset)
            dx_grid, offset = cls._read_utf8(data, offset)
            tx_sig, offset = cls._read_utf8(data, offset)
            rx_sig, offset = cls._read_utf8(data, offset)
            tx_power, offset = cls._read_utf8(data, offset)
            return {
                'type': 'qso_logged', 'dx_call': dx_call.strip(),
                'dx_grid': dx_grid.strip(), 'time_off': date_msecs,
            }
        except Exception as e:
            logger.warning(f"parse_qso_logged error: {e}")
            return None

    @classmethod
    def parse_adif_logged(cls, data: bytes) -> Optional[Dict]:
        try:
            offset = 0
            _, offset = cls._read_utf8(data, offset)
            adif, offset = cls._read_utf8(data, offset)
            return {'type': 'adif_logged', 'adif': adif.strip()}
        except Exception as e:
            logger.warning(f"parse_adif error: {e}")
            return None

    @staticmethod
    def build_reply(decode_info: Dict) -> bytes:
        pkt = bytearray()
        pkt += struct.pack('>III', MAGIC_WSJTX, 2, PKT_REPLY)
        id_bytes = b"WSJT-X"
        pkt += struct.pack('>I', len(id_bytes)) + id_bytes
        pkt += struct.pack('>I', decode_info.get('time_ms', 0))
        pkt += struct.pack('>i', decode_info.get('snr', -20))
        pkt += struct.pack('>d', decode_info.get('delta_time', 0.0))
        pkt += struct.pack('>I', decode_info.get('delta_freq', 0))
        mode = decode_info.get('mode', 'FT8')
        mode_bytes = mode.encode('utf-8')
        if mode == 'FT8':
            mode_bytes = b'~'
        elif mode == 'JT9':
            mode_bytes = b'@'
        pkt += struct.pack('>I', len(mode_bytes)) + mode_bytes
        msg = decode_info.get('message', '')
        msg_bytes = msg.encode('utf-8')
        pkt += struct.pack('>I', len(msg_bytes)) + msg_bytes
        return bytes(pkt)

    @staticmethod
    def build_free_text(text: str) -> bytes:
        pkt = bytearray()
        pkt += struct.pack('>III', MAGIC_WSJTX, 2, PKT_FREE_TEXT)
        id_bytes = b"WSJT-X"
        pkt += struct.pack('>I', len(id_bytes)) + id_bytes
        msg_bytes = text.strip().encode('utf-8')
        pkt += struct.pack('>I', len(msg_bytes)) + msg_bytes
        return bytes(pkt)

    @staticmethod
    def build_halt_tx() -> bytes:
        pkt = bytearray()
        pkt += struct.pack('>III', MAGIC_WSJTX, 2, PKT_HALT_TX)
        pkt += struct.pack('>I', 0)
        return bytes(pkt)


# ── FT8 Integration ────────────────────────────────────────
class FT8Integration:
    def __init__(self, listen_port=LISTEN_PORT, jtdx_port=JTDX_PORT):
        self.listen_port = listen_port
        self.jtdx_port = jtdx_port
        self.protocol = WSJTXProtocol()
        self.dxcc = DXCCDatabase()
        self.adif = ADIFProcessor()

        self.websocket_clients: Set[Any] = set()
        self.lock = threading.Lock()
        self.decode_history: deque = deque(maxlen=200)
        self.qso_log: List[Dict] = []

        self.is_running = False
        self.udp_thread: Optional[threading.Thread] = None
        self.udp_sock: Optional[socket.socket] = None
        self.cycle = CycleState()
        self._ioloop = None

        self.jtdx_host: str = JTDX_HOST
        self.jtdx_addr: Optional[tuple] = None  # (host, port) auto-detected from received UDP packets

        self.my_callsign: str = ""
        self.my_grid: str = ""
        self.signal_threshold: int = -20
        self.auto_reply: bool = False
        self.worked_calls: Set[str] = set()
        self.excluded_calls: Set[str] = set()

        self.log_file = Path("ft8/wsjtx_log.adi")
        self._ensure_log()
        self._load_worked()

        logger.info(f"FT8Integration ready (listen={listen_port}, jtdx={jtdx_port})")

    def _ensure_log(self):
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        if not self.log_file.exists():
            self.log_file.touch()

    def _load_worked(self):
        try:
            content = self.log_file.read_text(encoding='utf-8')
            for qso in self.adif.parse(content):
                if 'call' in qso:
                    self.worked_calls.add(qso['call'].upper())
            logger.info(f"Loaded {len(self.worked_calls)} worked calls from log")
        except Exception as e:
            logger.warning(f"Cannot load log: {e}")

    # ── WebSocket management ──
    def add_client(self, client):
        with self.lock:
            self.websocket_clients.add(client)
        if self._ioloop is None:
            import tornado.ioloop
            self._ioloop = tornado.ioloop.IOLoop.instance()
        logger.info(f"WS client added ({len(self.websocket_clients)} total)")

    def remove_client(self, client):
        with self.lock:
            self.websocket_clients.discard(client)
        logger.info(f"WS client removed ({len(self.websocket_clients)} total)")

    def _enqueue_broadcast(self, msg: dict):
        if self._ioloop is None:
            return
        payload = json.dumps(msg, ensure_ascii=False)
        try:
            self._ioloop.add_callback(self._do_broadcast, payload)
        except Exception:
            pass

    def _do_broadcast(self, payload: str):
        dead = set()
        with self.lock:
            clients = list(self.websocket_clients)
        for c in clients:
            try:
                if hasattr(c, 'write_message'):
                    c.write_message(payload)
            except Exception:
                dead.add(c)
        if dead:
            with self.lock:
                self.websocket_clients -= dead

    # ── Packet handling ──
    def _on_decode(self, pkt: dict):
        msg_text = pkt.get('message', '')
        snr = pkt.get('snr', -30)
        mode = pkt.get('mode', 'FT8')
        freq = pkt.get('delta_freq', 0)
        callsign = pkt.get('callsign', '')
        grid = pkt.get('grid', '')
        time_ms = pkt.get('time_ms', 0)
        delta_time = pkt.get('delta_time', 0.0)
        delta_freq = pkt.get('delta_freq', 0)

        dxcc_info = self.dxcc.locate(callsign)

        entry = DecodeEntry(
            time=datetime.now(timezone.utc).strftime("%H%M%S"),
            snr=snr, freq=freq, mode=mode, message=msg_text,
            callsign=callsign, grid=grid,
            dxcc_id=dxcc_info['id'], dxcc_name=dxcc_info['name'],
            dxcc_flag=dxcc_info['flag'],
            time_ms=time_ms, delta_time=delta_time, delta_freq=delta_freq,
        )
        self.decode_history.append(entry)

        self._enqueue_broadcast({
            'type': 'decode',
            'data': {
                'time': entry.time, 'snr': entry.snr,
                'freq': entry.freq, 'mode': entry.mode,
                'message': entry.message,
                'callsign': entry.callsign, 'grid': entry.grid,
                'dxcc_id': entry.dxcc_id,
                'dxcc_name': entry.dxcc_name,
                'dxcc_flag': entry.dxcc_flag,
                'time_ms': entry.time_ms,
                'delta_time': entry.delta_time,
                'delta_freq': entry.delta_freq,
                'worked': entry.callsign.upper() in self.worked_calls,
                'excluded': entry.callsign.upper() in self.excluded_calls,
            }
        })

        if entry.callsign and not entry.callsign.upper() in self.worked_calls:
            parts = msg_text.split()
            if len(parts) >= 2 and (parts[0] == 'CQ' or parts[0] == 'QRZ'):
                if self.auto_reply and snr >= self.signal_threshold:
                    self._do_response(entry)

    def _on_status(self, pkt: dict):
        freq = pkt.get('frequency', 0)
        band = self._freq_to_band(freq)
        self._enqueue_broadcast({
            'type': 'status',
            'data': {
                'software': pkt.get('software', ''),
                'frequency': freq,
                'mode': pkt.get('mode', ''),
                'band': band,
                'transmitting': pkt.get('transmitting', False),
                'de_call': pkt.get('de_call', ''),
                'dx_call': pkt.get('dx_call', ''),
                'report': pkt.get('report', ''),
                'tx_enabled': pkt.get('tx_enabled', False),
            }
        })

    def _on_qso_logged(self, pkt: dict):
        call = pkt.get('dx_call', '')
        grid = pkt.get('dx_grid', '')
        if call:
            self.worked_calls.add(call.upper())
            qso = {
                'call': call, 'gridsquare': grid,
                'mode': 'FT8', 'qso_date': datetime.now(timezone.utc).strftime('%Y%m%d'),
                'time_on': datetime.now(timezone.utc).strftime('%H%M%S'), 'eor': '',
            }
            try:
                with open(self.log_file, 'a', encoding='utf-8') as f:
                    f.write(self.adif.format(qso) + '\n')
            except Exception as e:
                logger.error(f"Log write error: {e}")
            self._enqueue_broadcast({
                'type': 'qso_logged',
                'data': {'dx_call': call, 'dx_grid': grid}
            })

    def _do_response(self, entry: DecodeEntry):
        msg = f"{entry.callsign} {self.my_callsign}"
        if self.my_grid:
            msg += f" {self.my_grid}"
        decode_info = {
            'time_ms': entry.time_ms,
            'snr': entry.snr,
            'delta_time': entry.delta_time,
            'delta_freq': entry.delta_freq,
            'mode': entry.mode,
            'message': msg,
        }
        ok = self._send_udp(WSJTXProtocol.build_reply(decode_info))
        if not ok:
            # Fallback to FreeText
            self._send_udp(WSJTXProtocol.build_free_text(msg))
        logger.info(f"Auto-reply: {msg}")

    @staticmethod
    def _freq_to_band(f: int) -> str:
        mhz = f / 1e6
        for freq, name in [
            (1.8, '160m'), (3.5, '80m'), (5.3, '60m'), (7.0, '40m'),
            (10.1, '30m'), (14.0, '20m'), (18.1, '17m'), (21.0, '15m'),
            (24.9, '12m'), (28.0, '10m'), (50.0, '6m'),
        ]:
            if abs(mhz - freq) < 0.5:
                return name
        return f"{mhz:.1f}MHz"

    # ── UDP I/O ──
    def _send_udp(self, data: bytes) -> bool:
        host = self.jtdx_addr[0] if self.jtdx_addr else self.jtdx_host
        port = self.jtdx_port
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(1.0)
            sent = s.sendto(data, (host, port))
            s.close()
            logger.info(f"UDP sent {sent}B to {host}:{port} hex={data[:24].hex()}")
            if len(data) <= 80:
                logger.debug(f"Full packet: {data.hex()}")
            return True
        except Exception as e:
            logger.error(f"UDP send error → {host}:{port}: {e}")
            return False

    def _udp_loop(self):
        try:
            self.udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.udp_sock.bind(('0.0.0.0', self.listen_port))
            self.udp_sock.settimeout(0.5)
            logger.info(f"UDP listener started on port {self.listen_port}")
            logger.info(f"Configure JTDX → UDP secondary port to {self.listen_port}")
            last_cycle_update = 0.0

            while self.is_running:
                try:
                    data, addr = self.udp_sock.recvfrom(WSJT_MAX_PACKET)
                except socket.timeout:
                    pass
                else:
                    if self.jtdx_addr is None or self.jtdx_addr[0] != addr[0]:
                        self.jtdx_addr = addr
                        logger.info(f"JTDX source auto-detected: {addr[0]}:{addr[1]}")
                    hdr = self.protocol.parse_header(data)
                    if hdr:
                        ptype = hdr['type']
                        payload = hdr['data']
                        if ptype == PKT_DECODE:
                            pkt = self.protocol.parse_decode(payload)
                            if pkt:
                                self._on_decode(pkt)
                        elif ptype == PKT_STATUS:
                            pkt = self.protocol.parse_status(payload)
                            if pkt:
                                self._on_status(pkt)
                        elif ptype == PKT_QSO_LOGGED:
                            pkt = self.protocol.parse_qso_logged(payload)
                            if pkt:
                                self._on_qso_logged(pkt)
                        elif ptype == PKT_ADIF_LOGGED:
                            pkt = self.protocol.parse_adif_logged(payload)
                            if pkt:
                                logger.debug(f"ADIF logged: {pkt.get('adif','')[:60]}")
                        elif ptype == PKT_CLOSE:
                            logger.info("JTDX/WSJT-X closed connection")

                now = time.time()
                if now - last_cycle_update >= 1.0:
                    self.cycle.update()
                    last_cycle_update = now
                    self._enqueue_broadcast({
                        'type': 'cycle',
                        'data': {
                            'phase': self.cycle.phase,
                            'is_tx': self.cycle.is_tx,
                            'slot': self.cycle.slot,
                            'seconds_left': round(self.cycle.seconds_left, 1),
                        }
                    })
        except Exception as e:
            logger.error(f"UDP listener error: {e}")

    # ── Web commands ──
    def handle_command(self, command: str, params: dict = None) -> dict:
        params = params or {}
        if command == 'cq':
            msg = params.get('message', '')
            if not msg:
                c = self.my_callsign
                g = self.my_grid
                msg = f"CQ {c} {g}".strip()
            if not self._send_udp(WSJTXProtocol.build_free_text(msg)):
                return {'status': 'error', 'message': 'UDP send failed — check JTDX host/port'}
            logger.info(f"CQ: {msg}")
            return {'status': 'ok', 'command': 'cq', 'message': msg}

        elif command == 'reply':
            callsign = params.get('callsign', '')
            if not callsign:
                return {'status': 'error', 'message': 'No callsign'}

            # Use Reply packet type (4) when decode info is available
            if all(k in params for k in ('time_ms', 'snr', 'delta_time', 'delta_freq')):
                decode_info = {
                    'time_ms': params.get('time_ms', 0),
                    'snr': params.get('snr', -20),
                    'delta_time': params.get('delta_time', 0.0),
                    'delta_freq': params.get('delta_freq', 0),
                    'mode': params.get('mode', 'FT8'),
                    'message': params.get('message', ''),
                }
                ok = self._send_udp(WSJTXProtocol.build_reply(decode_info))
            else:
                msg = params.get('message', '')
                if not msg:
                    g = self.my_grid or 'AA00'
                    msg = f"{callsign} {self.my_callsign} {g}"
                ok = self._send_udp(WSJTXProtocol.build_free_text(msg))

            if not ok:
                return {'status': 'error', 'message': 'UDP send failed — check JTDX host/port'}
            logger.info(f"Reply: {callsign}")
            return {'status': 'ok', 'command': 'reply', 'callsign': callsign}

        elif command == 'rr73':
            callsign = params.get('callsign', '')
            if callsign:
                msg = f"{callsign} {self.my_callsign} RR73"
                if not self._send_udp(WSJTXProtocol.build_free_text(msg)):
                    return {'status': 'error', 'message': 'UDP send failed'}
                logger.info(f"RR73: {msg}")
                return {'status': 'ok', 'command': 'rr73', 'message': msg}
            return {'status': 'error', 'message': 'No callsign'}

        elif command == 'free_text':
            text = params.get('text', '')
            if text:
                if not self._send_udp(WSJTXProtocol.build_free_text(text)):
                    return {'status': 'error', 'message': 'UDP send failed'}
                return {'status': 'ok', 'command': 'free_text', 'message': text}
            return {'status': 'error', 'message': 'No text'}

        elif command == 'halt_tx':
            if not self._send_udp(WSJTXProtocol.build_halt_tx()):
                return {'status': 'error', 'message': 'UDP send failed'}
            return {'status': 'ok', 'command': 'halt_tx'}

        elif command == 'exclude':
            call = params.get('callsign', '').upper()
            if call:
                self.excluded_calls.add(call)
                return {'status': 'ok', 'command': 'exclude', 'callsign': call}
            return {'status': 'error', 'message': 'No callsign'}

        elif command == 'settings':
            if 'callsign' in params:
                self.my_callsign = params['callsign'].upper()
            if 'grid' in params:
                self.my_grid = params['grid'].upper()
            if 'threshold' in params:
                self.signal_threshold = int(params['threshold'])
            if 'auto_reply' in params:
                self.auto_reply = bool(params['auto_reply'])
            if 'jtdx_port' in params:
                try:
                    port = int(params['jtdx_port'])
                    if port > 0:
                        self.jtdx_port = port
                        logger.info(f"JTDX port set to {self.jtdx_port}")
                except (ValueError, TypeError):
                    pass
            if 'jtdx_host' in params and params['jtdx_host']:
                self.jtdx_host = str(params['jtdx_host'])
                self.jtdx_addr = None  # Reset auto-detected addr so new host is used
                logger.info(f"JTDX host set to {self.jtdx_host}")
            return {'status': 'ok', 'command': 'settings'}

        elif command == 'get_decodes':
            return {'status': 'ok', 'command': 'get_decodes', 'decodes': self.get_decodes(100)}

        elif command == 'get_status':
            return {'status': 'ok', 'command': 'get_status', 'status': self.get_status()}

        return {'status': 'error', 'message': f'Unknown command: {command}'}

    def get_status(self) -> dict:
        return {
            'connected': self.is_running,
            'my_callsign': self.my_callsign,
            'my_grid': self.my_grid,
            'signal_threshold': self.signal_threshold,
            'auto_reply': self.auto_reply,
            'worked_count': len(self.worked_calls),
            'excluded_count': len(self.excluded_calls),
            'decode_count': len(self.decode_history),
            'listen_port': self.listen_port,
            'jtdx_port': self.jtdx_port,
            'jtdx_host': self.jtdx_host,
            'jtdx_detected': f"{self.jtdx_addr[0]}:{self.jtdx_addr[1]}" if self.jtdx_addr else None,
            'cycle': {
                'phase': self.cycle.phase,
                'is_tx': self.cycle.is_tx,
                'slot': self.cycle.slot,
                'seconds_left': round(self.cycle.seconds_left, 1),
            },
        }

    def get_decodes(self, limit: int = 50) -> list:
        return [
            {
                'time': e.time, 'snr': e.snr, 'freq': e.freq,
                'mode': e.mode, 'message': e.message,
                'callsign': e.callsign, 'grid': e.grid,
                'dxcc_id': e.dxcc_id, 'dxcc_name': e.dxcc_name,
                'dxcc_flag': e.dxcc_flag,
                'time_ms': e.time_ms, 'delta_time': e.delta_time,
                'delta_freq': e.delta_freq,
                'worked': e.callsign.upper() in self.worked_calls,
                'excluded': e.callsign.upper() in self.excluded_calls,
            }
            for e in list(self.decode_history)[-limit:]
        ]

    # ── Lifecycle ──
    def start(self):
        if self.is_running:
            return
        self.is_running = True
        self.udp_thread = threading.Thread(target=self._udp_loop, daemon=True)
        self.udp_thread.start()
        logger.info("FT8 Integration started")

    def stop(self):
        self.is_running = False
        if self.udp_sock:
            try:
                self.udp_sock.close()
            except Exception:
                pass
        if self.udp_thread:
            self.udp_thread.join(timeout=2.0)
        logger.info("FT8 Integration stopped")


_singleton: Optional[FT8Integration] = None

def get_ft8_integration() -> FT8Integration:
    global _singleton
    if _singleton is None:
        _singleton = FT8Integration()
    return _singleton


if __name__ == '__main__':
    logger.info("Starting FT8 Integration standalone test...")
    svc = get_ft8_integration()
    svc.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        svc.stop()
