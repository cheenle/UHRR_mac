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
                'decoding': decoding,
                'rx_df': rx_df, 'tx_df': tx_df,
                'de_call': de_call.strip(), 'de_grid': de_grid.strip(),
                'dx_grid': dx_grid.strip(),
                'tx_watchdog': tx_watchdog,
                'sub_mode': sub_mode.strip(),
                'fast_mode': fast_mode,
                'tx_first': tx_first,
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
    def _pack_utf8(s: str) -> bytes:
        """QDataStream QByteArray: 0xFFFFFFFF for null, else length-prefixed."""
        if s is None:
            return struct.pack('>I', 0xFFFFFFFF)
        b = s.encode('utf-8')
        return struct.pack('>I', len(b)) + b

    @staticmethod
    def build_reply(decode_info: Dict) -> bytes:
        """Reply (type 4). Makes JTDX act as if the decode was double-clicked.

        WSJT-X schema 3 layout after the common header:
          Id (utf8), Time (quint32 ms since midnight), snr (qint32),
          Delta time (qreal/double), Delta frequency (quint32),
          Mode (utf8), Message (utf8), Low confidence (bool), Modifiers (quint8)
        The trailing bool+quint8 are REQUIRED — without them QDataStream
        deserialization fails and JTDX silently drops the packet.
        """
        P = WSJTXProtocol
        pkt = bytearray()
        pkt += struct.pack('>III', MAGIC_WSJTX, 2, PKT_REPLY)
        pkt += P._pack_utf8("WSJT-X")
        pkt += struct.pack('>I', int(decode_info.get('time_ms', 0)) & 0xFFFFFFFF)
        pkt += struct.pack('>i', int(decode_info.get('snr', -20)))
        pkt += struct.pack('>d', float(decode_info.get('delta_time', 0.0)))
        pkt += struct.pack('>I', int(decode_info.get('delta_freq', 0)) & 0xFFFFFFFF)
        mode = decode_info.get('mode', 'FT8')
        if mode == 'FT8':
            mode_str = '~'
        elif mode == 'JT9':
            mode_str = '@'
        else:
            mode_str = mode
        pkt += P._pack_utf8(mode_str)
        pkt += P._pack_utf8(decode_info.get('message', ''))
        pkt += struct.pack('>B', 1 if decode_info.get('low_confidence') else 0)
        pkt += struct.pack('>B', int(decode_info.get('modifiers', 0)) & 0xFF)
        return bytes(pkt)

    @staticmethod
    def build_free_text(text: str, send: bool = True) -> bytes:
        """Free Text (type 9): Id (utf8), Text (utf8), Send (bool).

        The trailing Send bool is REQUIRED: when true JTDX loads the text
        AND transmits it; without the byte the text is set but never sent.
        """
        P = WSJTXProtocol
        pkt = bytearray()
        pkt += struct.pack('>III', MAGIC_WSJTX, 2, PKT_FREE_TEXT)
        pkt += P._pack_utf8("WSJT-X")
        pkt += P._pack_utf8(text.strip())
        pkt += struct.pack('>B', 1 if send else 0)
        return bytes(pkt)

    @staticmethod
    def build_halt_tx(auto_only: bool = False) -> bytes:
        """Halt Tx (type 8): Id (utf8), Auto Tx Only (bool).

        auto_only=False stops transmission immediately; True only disables
        further auto-sequenced transmissions but lets the current one finish.
        """
        P = WSJTXProtocol
        pkt = bytearray()
        pkt += struct.pack('>III', MAGIC_WSJTX, 2, PKT_HALT_TX)
        pkt += P._pack_utf8("WSJT-X")
        pkt += struct.pack('>B', 1 if auto_only else 0)
        return bytes(pkt)


# ── QSO Auto-Sequencer ─────────────────────────────────────
# Drives a standard FT8 QSO end-to-end the way JTDX "Auto Seq" does, but
# server-side so a remote browser user gets the same hands-off experience.
#
# Two entry paths:
#   answer_cq(dx, snr)  — reply to someone else's CQ
#   call_cq()           — call CQ ourselves and work the first replier
#
# State machine (our perspective):
#   IDLE
#   CQ        we are calling CQ, waiting for an answer "<MY> <DX> <grid>"
#   CALLING   we answered a CQ, sent "<DX> <MY> <grid>", waiting for a report
#   REPORTED  we sent "<DX> <MY> <±rpt>", waiting for "R±rpt"
#   ROGERED   we sent "<DX> <MY> R±rpt" (or RR73), waiting for RR73/73
#   DONE      QSO complete / logged
REPORT_RE = re.compile(r'^R?[+-]\d{2}$')
GRID_RE = re.compile(r'^[A-R]{2}\d{2}$', re.IGNORECASE)


class QSOSequencer:
    def __init__(self, integ):
        self.integ = integ
        self.lock = threading.Lock()
        self.state = "IDLE"
        self.dx_call = ""
        self.dx_grid = ""
        self.rx_snr = -15           # SNR we heard the DX at → report we send
        self.pending_msg = ""       # message we want JTDX to transmit
        self.last_decode_info = None  # for Reply-packet replies
        self.cycles_waiting = 0
        self.max_cycles = 6         # give up after this many idle cycles
        self.enabled = False

    # ── helpers ──
    @staticmethod
    def _fmt_report(snr: int) -> str:
        snr = max(-30, min(30, int(snr)))
        return f"{snr:+03d}"

    def _emit_state(self):
        self.integ._enqueue_broadcast({
            'type': 'qso_state',
            'data': {
                'state': self.state,
                'dx_call': self.dx_call,
                'dx_grid': self.dx_grid,
                'enabled': self.enabled,
            }
        })

    def _reply_to(self, orig_message: str):
        """Trigger TX by sending a Reply packet referencing the ORIGINAL decode.

        This is the ONLY reliable way to make JTDX/WSJT-X transmit over UDP:
        a Reply (type 4) is equivalent to double-clicking the decode. JTDX
        matches `message` against its decode list, arms Tx, and — because its
        own AutoSequence is enabled — drives the rest of the QSO itself.
        A Free Text packet merely loads the message and does NOT key the radio.
        """
        di = dict(self.last_decode_info or {})
        di['message'] = orig_message
        ok = self.integ._send_udp(WSJTXProtocol.build_reply(di))
        logger.info(f"[SEQ:{self.state}] Reply → {orig_message} ({'ok' if ok else 'FAIL'})")
        return ok

    def _send(self, msg: str, use_reply: bool = False):
        """Free-text fallback (used only when JTDX AutoSequence is OFF)."""
        self.pending_msg = msg
        self.cycles_waiting = 0
        self.integ._send_udp(WSJTXProtocol.build_free_text(msg, send=True))
        logger.info(f"[SEQ:{self.state}] FreeText → {msg}")

    def _reset(self, reason: str = ""):
        self.state = "IDLE"
        self.dx_call = ""
        self.dx_grid = ""
        self.pending_msg = ""
        self.last_decode_info = None
        self.cycles_waiting = 0
        if reason:
            logger.info(f"[SEQ] reset: {reason}")
        self._emit_state()

    # ── public control ──
    def stop(self):
        with self.lock:
            self.enabled = False
            self.integ._send_udp(WSJTXProtocol.build_halt_tx(auto_only=False))
            self._reset("stopped by user")

    def answer_cq(self, dx: str, snr: int, decode_info: dict = None,
                  orig_message: str = ""):
        """Answer a CQ. Fires a single Reply packet; JTDX auto-sequences the QSO.

        decode_info / orig_message come straight from the decode the user
        clicked. The Reply references that exact decode so JTDX knows which
        station to work and keys the radio.
        """
        with self.lock:
            my = self.integ.my_callsign
            if not my:
                logger.warning("[SEQ] answer_cq ignored: no callsign set")
                return
            self.enabled = True
            self.dx_call = dx.upper()
            self.rx_snr = int(snr)
            self.last_decode_info = decode_info or {}
            self.state = "CALLING"
            self.cycles_waiting = 0
            if not orig_message:
                # Reconstruct a plausible CQ string if the UI didn't supply one.
                orig_message = f"CQ {self.dx_call} {self.integ.my_grid}".strip()
            ok = self._reply_to(orig_message)
            if not ok:
                # JTDX unreachable → fall back to free text (won't auto-seq).
                grid = self.integ.my_grid or ""
                self._send(f"{self.dx_call} {my} {grid}".strip())
            self._emit_state()

    def call_cq(self):
        with self.lock:
            my = self.integ.my_callsign
            if not my:
                logger.warning("[SEQ] call_cq ignored: no callsign set")
                return
            self.enabled = True
            self.dx_call = ""
            self.last_decode_info = None
            grid = self.integ.my_grid or ""
            self.state = "CQ"
            self._send(f"CQ {my} {grid}".strip())
            self._emit_state()

    # ── decode-driven state tracking ──
    def on_decode(self, entry: "DecodeEntry"):
        """Track QSO progress for the UI.

        After our initial Reply, JTDX (AutoSequence=true) drives the actual
        transmissions itself: report → R-report → RR73 → 73 → logs the QSO.
        We only OBSERVE the exchange here to update the UI state badge and to
        capture the DX grid/report — we do NOT transmit (Free Text wouldn't key
        the radio anyway, and a second Reply would fight JTDX's sequencer).
        """
        if not self.enabled or self.state in ("IDLE", "DONE"):
            return
        my = self.integ.my_callsign.upper()
        if not my:
            return
        parts = entry.message.upper().split()
        if len(parts) < 2 or parts[0] != my:
            return  # not addressed to us

        with self.lock:
            sender = parts[1]
            if self.state == "CQ":
                self.dx_call = sender
                self.rx_snr = entry.snr
            elif sender != self.dx_call:
                return  # a different station — ignore during an active QSO

            self.cycles_waiting = 0  # heard from DX → reset idle timeout
            rest = parts[2:]
            tok = rest[0] if rest else ""

            if tok in ("73", "RR73", "RRR") or "73" in rest:
                # DX confirmed — JTDX logs it; we just finalize UI state.
                self.state = "DONE"
                self.enabled = False
                self._emit_state()
                return
            if REPORT_RE.match(tok) and tok.startswith("R"):
                self.state = "ROGERED"      # got R-report; JTDX will send RR73
                self._emit_state()
                return
            if REPORT_RE.match(tok):
                self.state = "REPORTED"      # got bare report; JTDX sends R-rpt
                self._emit_state()
                return
            if GRID_RE.match(tok):
                self.dx_grid = tok           # answer to our CQ; JTDX sends report
                self.state = "REPORTED"
                self._emit_state()
                return

    def on_cycle(self):
        """Once per 15s cycle: give up if the DX stops answering."""
        if not self.enabled or self.state in ("IDLE", "DONE"):
            return
        with self.lock:
            self.cycles_waiting += 1
            if self.cycles_waiting >= self.max_cycles:
                # Stop JTDX's auto-sequence too so it doesn't keep calling.
                self.integ._send_udp(WSJTXProtocol.build_halt_tx(auto_only=True))
                self._reset(f"timed out after {self.max_cycles} cycles")
                self.enabled = False

    def _log_qso(self):
        call = self.dx_call
        if not call:
            return
        self.integ._log_qso_record(call, self.dx_grid,
                                   self._fmt_report(self.rx_snr))


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
        self.worked_grids: Set[str] = set()      # for "new grid" highlight
        self.worked_dxcc: Set[str] = set()        # dxcc id strings already worked
        self.excluded_calls: Set[str] = set()

        # Latest radio/JTDX state (populated from Status packets)
        self.last_status: Dict[str, Any] = {}

        # Tx message slots (JTDX Tx1-Tx6). {N} placeholders expanded at send time.
        self.tx_slots: Dict[int, str] = {
            1: "{DxCall} {MyCall} {MyGrid}",
            2: "{DxCall} {MyCall} {Report}",
            3: "{DxCall} {MyCall} R{Report}",
            4: "{DxCall} {MyCall} RR73",
            5: "{DxCall} {MyCall} 73",
            6: "CQ {MyCall} {MyGrid}",
        }

        # Server-side QSO auto-sequencer
        self.auto_seq: bool = False               # MRRC drives the QSO automatically
        self.seq = QSOSequencer(self)

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
                call = qso.get('call', '')
                if call:
                    call = call.upper()
                    self.worked_calls.add(call)
                    grid = (qso.get('gridsquare', '') or '')[:4].upper()
                    if grid:
                        self.worked_grids.add(grid)
                    info = self.dxcc.locate(call)
                    if info.get('id'):
                        self.worked_dxcc.add(info['id'])
            logger.info(
                f"Loaded {len(self.worked_calls)} calls, "
                f"{len(self.worked_grids)} grids, {len(self.worked_dxcc)} DXCC from log"
            )
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

        # ── Classification for JTDX-style coloring ──
        call_u = callsign.upper()
        parts = msg_text.upper().split()
        is_cq = bool(parts) and parts[0] in ('CQ', 'QRZ')
        # Addressed to me: my callsign is the first token of the message.
        to_me = bool(self.my_callsign) and bool(parts) and parts[0] == self.my_callsign
        worked = call_u in self.worked_calls
        new_dxcc = bool(dxcc_info['id']) and dxcc_info['id'] not in self.worked_dxcc
        new_grid = bool(grid) and grid[:4].upper() not in self.worked_grids

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
                'worked': worked,
                'excluded': call_u in self.excluded_calls,
                'is_cq': is_cq,
                'to_me': to_me,
                'new_dxcc': new_dxcc,
                'new_grid': new_grid,
            }
        })

        # ── Feed the auto-sequencer (handles replies addressed to us) ──
        if self.auto_seq:
            try:
                self.seq.on_decode(entry)
            except Exception as e:
                logger.error(f"Sequencer on_decode error: {e}")

        # ── Legacy single-shot auto-reply (only when sequencer is off) ──
        elif self.auto_reply and is_cq and not worked and call_u not in self.excluded_calls:
            if snr >= self.signal_threshold:
                self._do_response(entry)

    def _on_status(self, pkt: dict):
        freq = pkt.get('frequency', 0)
        band = self._freq_to_band(freq)
        status = {
            'software': pkt.get('software', ''),
            'frequency': freq,
            'mode': pkt.get('mode', ''),
            'sub_mode': pkt.get('sub_mode', ''),
            'band': band,
            'transmitting': pkt.get('transmitting', False),
            'de_call': pkt.get('de_call', ''),
            'de_grid': pkt.get('de_grid', ''),
            'dx_call': pkt.get('dx_call', ''),
            'dx_grid': pkt.get('dx_grid', ''),
            'report': pkt.get('report', ''),
            'tx_enabled': pkt.get('tx_enabled', False),
            'tx_first': pkt.get('tx_first', False),
            'rx_df': pkt.get('rx_df', 0),
            'tx_df': pkt.get('tx_df', 0),
        }
        # Cache latest radio state so the sequencer / slot expansion can use it.
        # TEMP DIAG: log tx flags so we can see if JTDX ever arms/keys TX.
        prev = self.last_status or {}
        if (prev.get('tx_enabled') != status['tx_enabled']
                or prev.get('transmitting') != status['transmitting']):
            logger.info(f"[STATUS] tx_enabled={status['tx_enabled']} "
                        f"transmitting={status['transmitting']} "
                        f"tx_df={status['tx_df']} dx={status['dx_call']}")
        self.last_status = status
        # Adopt JTDX's own callsign/grid if the operator hasn't set one yet.
        if not self.my_callsign and status['de_call']:
            self.my_callsign = status['de_call'].upper()
        if not self.my_grid and status['de_grid']:
            self.my_grid = status['de_grid'].upper()
        self._enqueue_broadcast({'type': 'status', 'data': status})

    def _on_qso_logged(self, pkt: dict):
        # QSO logged by JTDX itself (e.g. operator clicked Log QSO there).
        self._log_qso_record(pkt.get('dx_call', ''), pkt.get('dx_grid', ''),
                             pkt.get('report_sent', ''), from_jtdx=True)

    def _log_qso_record(self, call: str, grid: str = "",
                         report: str = "", from_jtdx: bool = False):
        """Append a QSO to the ADIF log and update worked sets + frontend.

        Used both by JTDX's QSO-logged packets and the server-side sequencer.
        De-duplicates so the sequencer and JTDX don't double-log the same QSO.
        """
        call = (call or '').strip().upper()
        if not call:
            return
        grid4 = (grid or '')[:4].upper()
        # Update in-memory worked sets for live coloring.
        already = call in self.worked_calls
        self.worked_calls.add(call)
        if grid4:
            self.worked_grids.add(grid4)
        info = self.dxcc.locate(call)
        if info.get('id'):
            self.worked_dxcc.add(info['id'])

        # Only write a new ADIF record once per call per session run.
        if not already:
            qso = {
                'call': call, 'gridsquare': grid,
                'mode': 'FT8', 'qso_date': datetime.now(timezone.utc).strftime('%Y%m%d'),
                'time_on': datetime.now(timezone.utc).strftime('%H%M%S'),
            }
            if report:
                qso['rst_sent'] = report
            qso['eor'] = ''
            try:
                with open(self.log_file, 'a', encoding='utf-8') as f:
                    f.write(self.adif.format(qso) + '\n')
            except Exception as e:
                logger.error(f"Log write error: {e}")

        self._enqueue_broadcast({
            'type': 'qso_logged',
            'data': {
                'dx_call': call, 'dx_grid': grid,
                'report': report, 'from_jtdx': from_jtdx,
                'new_dxcc': bool(info.get('id')) and info['id'] in self.worked_dxcc,
            }
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

    def _expand_slot(self, template: str, dx_call: str = "") -> str:
        """Expand Tx-slot placeholders into a ready-to-send message.

        Placeholders: {MyCall} {MyGrid} {DxCall} {DxGrid} {Report}
        {Report} uses the DX's last-heard SNR if known, else our threshold.
        """
        dx = (dx_call or self.last_status.get('dx_call', '') or '').upper()
        dx_grid = self.last_status.get('dx_grid', '')
        # Report: SNR we heard the DX at, taken from the sequencer if active.
        snr = self.seq.rx_snr if self.seq and self.seq.dx_call == dx else -15
        report = f"{max(-30, min(30, int(snr))):+03d}"
        out = (template
               .replace('{MyCall}', self.my_callsign)
               .replace('{MyGrid}', self.my_grid)
               .replace('{DxCall}', dx)
               .replace('{DxGrid}', dx_grid)
               .replace('{Report}', report))
        # Collapse whitespace from any empty substitutions.
        return ' '.join(out.split())

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
        # JTDX/WSJT-X binds its UDP socket to an EPHEMERAL source port and both
        # sends datagrams from and listens for Reply/Halt requests on it. So we
        # MUST reply to the exact source address:port of the packets we received
        # (e.g. 127.0.0.1:55991), NOT the configured UDPServerPort — that port
        # may be taken by another logger (RUMlogNG, etc.) and JTDX isn't there.
        if self.jtdx_addr:
            host, port = self.jtdx_addr[0], self.jtdx_addr[1]
        else:
            host, port = self.jtdx_host, self.jtdx_port
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
                    # Track the FULL source address (host AND ephemeral port).
                    # JTDX/WSJT-X listens for Reply/Halt on the same socket it
                    # sends from — an ephemeral port (e.g. 55991), NOT the
                    # configured 2237. Replying to a fixed port lands on the
                    # wrong process and TX never happens. Re-latch whenever
                    # either host or port changes (e.g. JTDX restart).
                    if self.jtdx_addr != addr:
                        self.jtdx_addr = addr
                        logger.info(f"JTDX source auto-detected: {addr[0]}:{addr[1]} (reply target)")
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
                    prev_slot = self.cycle.slot
                    self.cycle.update()
                    last_cycle_update = now
                    # Fire the sequencer once per 15s slot boundary.
                    if self.cycle.slot != prev_slot and self.auto_seq:
                        try:
                            self.seq.on_cycle()
                        except Exception as e:
                            logger.error(f"Sequencer on_cycle error: {e}")
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

            # A Reply packet's `message` MUST be the ORIGINAL decoded message
            # (e.g. "CQ BG6UFQ OM88"). JTDX matches it against its decode list,
            # arms Tx, and generates the actual reply itself. Putting our own
            # outgoing text there makes JTDX drop the packet → no transmission.
            orig = params.get('orig_message', '') or params.get('message', '')
            if orig and all(k in params for k in ('time_ms', 'snr', 'delta_time', 'delta_freq')):
                decode_info = {
                    'time_ms': params.get('time_ms', 0),
                    'snr': params.get('snr', -20),
                    'delta_time': params.get('delta_time', 0.0),
                    'delta_freq': params.get('delta_freq', 0),
                    'mode': params.get('mode', 'FT8'),
                    'message': orig,
                }
                ok = self._send_udp(WSJTXProtocol.build_reply(decode_info))
            else:
                # No decode reference → fall back to Free Text (loads only;
                # JTDX must already have Tx armed for this to transmit).
                msg = params.get('out_message', '')
                if not msg:
                    g = self.my_grid or 'AA00'
                    msg = f"{callsign} {self.my_callsign} {g}"
                ok = self._send_udp(WSJTXProtocol.build_free_text(msg, send=True))

            if not ok:
                return {'status': 'error', 'message': 'UDP send failed — check JTDX host/port'}
            logger.info(f"Reply: {callsign} (orig='{orig}')")
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
            if 'auto_seq' in params:
                self.auto_seq = bool(params['auto_seq'])
                logger.info(f"Auto-sequencer {'ON' if self.auto_seq else 'OFF'}")
            return {'status': 'ok', 'command': 'settings'}

        # ── QSO auto-sequencer control ──
        elif command == 'answer_cq':
            # Reply to a CQ and let JTDX (AutoSequence) drive the whole QSO.
            callsign = (params.get('callsign', '') or '').upper()
            if not callsign:
                return {'status': 'error', 'message': 'No callsign'}
            if not self.my_callsign:
                return {'status': 'error', 'message': 'Set your callsign first'}
            self.auto_seq = True
            decode_info = {
                'time_ms': params.get('time_ms', 0),
                'snr': params.get('snr', -20),
                'delta_time': params.get('delta_time', 0.0),
                'delta_freq': params.get('delta_freq', 0),
                'mode': params.get('mode', 'FT8'),
            }
            orig = params.get('orig_message', '') or params.get('message', '')
            self.seq.answer_cq(callsign, int(params.get('snr', -15)),
                               decode_info, orig_message=orig)
            return {'status': 'ok', 'command': 'answer_cq', 'callsign': callsign}

        elif command == 'call_cq':
            if not self.my_callsign:
                return {'status': 'error', 'message': 'Set your callsign first'}
            self.auto_seq = True
            self.seq.call_cq()
            return {'status': 'ok', 'command': 'call_cq'}

        elif command == 'stop_qso':
            self.seq.stop()
            return {'status': 'ok', 'command': 'stop_qso'}

        elif command == 'set_auto_seq':
            self.auto_seq = bool(params.get('enabled', False))
            if not self.auto_seq:
                self.seq.stop()
            return {'status': 'ok', 'command': 'set_auto_seq', 'enabled': self.auto_seq}

        # ── Tx message slots (Tx1-Tx6) ──
        elif command == 'set_tx_msg':
            try:
                slot = int(params.get('slot', 0))
            except (ValueError, TypeError):
                slot = 0
            if slot < 1 or slot > 6:
                return {'status': 'error', 'message': 'slot must be 1-6'}
            self.tx_slots[slot] = str(params.get('text', ''))
            return {'status': 'ok', 'command': 'set_tx_msg', 'slot': slot}

        elif command == 'send_tx_slot':
            try:
                slot = int(params.get('slot', 0))
            except (ValueError, TypeError):
                slot = 0
            if slot not in self.tx_slots:
                return {'status': 'error', 'message': 'slot must be 1-6'}
            msg = self._expand_slot(self.tx_slots[slot], params.get('dx_call', ''))
            if not msg:
                return {'status': 'error', 'message': 'Empty message (missing callsign?)'}
            if not self._send_udp(WSJTXProtocol.build_free_text(msg, send=True)):
                return {'status': 'error', 'message': 'UDP send failed'}
            logger.info(f"Tx{slot}: {msg}")
            return {'status': 'ok', 'command': 'send_tx_slot', 'slot': slot, 'message': msg}

        elif command == 'get_tx_slots':
            return {'status': 'ok', 'command': 'get_tx_slots', 'slots': self.tx_slots}

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
            'auto_seq': self.auto_seq,
            'tx_slots': self.tx_slots,
            'qso': {
                'state': self.seq.state,
                'dx_call': self.seq.dx_call,
                'dx_grid': self.seq.dx_grid,
                'enabled': self.seq.enabled,
            },
            'radio': self.last_status,
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
