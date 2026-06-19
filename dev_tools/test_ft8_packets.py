#!/usr/bin/env python3
"""
Validate the WSJT-X UDP packet builders in ft8_integration.py against the
documented NetworkMessage wire format (schema 2/3) and round-trip the parsers.

Run:  python3 dev_tools/test_ft8_packets.py
Exit code 0 = all good.
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ft8_integration import WSJTXProtocol, MAGIC_WSJTX, PKT_REPLY, PKT_FREE_TEXT, PKT_HALT_TX  # noqa: E402

P = WSJTXProtocol
fail = 0


def check(name, cond, detail=""):
    global fail
    mark = "ok " if cond else "FAIL"
    if not cond:
        fail += 1
    print(f"  [{mark}] {name}" + (f"  — {detail}" if detail and not cond else ""))


def read_utf8(data, off):
    ln = struct.unpack_from('>I', data, off)[0]
    off += 4
    if ln == 0xFFFFFFFF:
        return '', off
    return data[off:off + ln].decode('utf-8', 'replace'), off + ln


def header(pkt):
    magic, schema, ptype = struct.unpack_from('>III', pkt, 0)
    return magic, schema, ptype, 12


print("Free Text (type 9)")
ft = P.build_free_text("CQ VE3KBR FN15", send=True)
magic, schema, ptype, off = header(ft)
check("magic", magic == MAGIC_WSJTX)
check("type==9", ptype == PKT_FREE_TEXT)
ident, off = read_utf8(ft, off)
check("id==WSJT-X", ident == "WSJT-X", ident)
text, off = read_utf8(ft, off)
check("text round-trips", text == "CQ VE3KBR FN15", text)
check("trailing Send bool present", off + 1 == len(ft), f"off={off} len={len(ft)}")
check("Send byte == 1", ft[off] == 1, str(ft[off]))
# send=False must set the bool to 0
ft0 = P.build_free_text("TEST", send=False)
check("send=False → byte 0", ft0[-1] == 0, str(ft0[-1]))

print("Reply (type 4)")
info = {'time_ms': 123456, 'snr': -12, 'delta_time': 0.2,
        'delta_freq': 1500, 'mode': 'FT8', 'message': 'VE3KBR JA1ABC R-12'}
rp = P.build_reply(info)
magic, schema, ptype, off = header(rp)
check("magic", magic == MAGIC_WSJTX)
check("type==4", ptype == PKT_REPLY)
ident, off = read_utf8(rp, off)
check("id==WSJT-X", ident == "WSJT-X", ident)
t_ms = struct.unpack_from('>I', rp, off)[0]; off += 4
check("time_ms", t_ms == 123456, str(t_ms))
snr = struct.unpack_from('>i', rp, off)[0]; off += 4
check("snr", snr == -12, str(snr))
dt = struct.unpack_from('>d', rp, off)[0]; off += 8
check("delta_time", abs(dt - 0.2) < 1e-9, str(dt))
dfq = struct.unpack_from('>I', rp, off)[0]; off += 4
check("delta_freq", dfq == 1500, str(dfq))
mode, off = read_utf8(rp, off)
check("mode FT8 → '~'", mode == '~', mode)
msg, off = read_utf8(rp, off)
check("message round-trips", msg == 'VE3KBR JA1ABC R-12', msg)
# REQUIRED trailing low_confidence (bool) + modifiers (quint8)
check("low_confidence + modifiers present", off + 2 == len(rp), f"off={off} len={len(rp)}")
check("low_confidence == 0", rp[off] == 0)
check("modifiers == 0", rp[off + 1] == 0)

print("Halt Tx (type 8)")
ht = P.build_halt_tx(auto_only=False)
magic, schema, ptype, off = header(ht)
check("magic", magic == MAGIC_WSJTX)
check("type==8", ptype == PKT_HALT_TX)
ident, off = read_utf8(ht, off)
check("id==WSJT-X", ident == "WSJT-X", ident)
check("auto_only bool present", off + 1 == len(ht), f"off={off} len={len(ht)}")
check("auto_only == 0", ht[off] == 0)
ht2 = P.build_halt_tx(auto_only=True)
check("auto_only=True → byte 1", ht2[-1] == 1)

print()
if fail:
    print(f"❌ {fail} check(s) failed")
    sys.exit(1)
print("✅ All packet checks passed")
