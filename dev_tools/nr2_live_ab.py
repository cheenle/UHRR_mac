#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""在线端到端测试：连 /WSCTRX，用服务自己的录音功能，在同一段实时信号上
分别录 NR2=0 与 NR2=2，然后对比服务实际输出的音频（recording 是 WDSP 之后）。

用法: venv/bin/python3 dev_tools/nr2_live_ab.py [每段秒数]
"""
import configparser, glob, os, ssl, sys, time
import websocket
from tornado.web import create_signed_value

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONF = os.path.join(ROOT, "MRRC.radio1.conf")
URL = "wss://localhost:8891/WSCTRX"
SEC = int(sys.argv[1]) if len(sys.argv) > 1 else 25

c = configparser.ConfigParser(); c.read(CONF)
secret = c["SERVER"]["cookie_secret"]
cookie = create_signed_value(secret, "user", "selftest").decode()
print(f"cookie_secret 已加载（{len(secret)} 字符），签名 cookie {len(cookie)} 字节")

ws = websocket.create_connection(
    URL, sslopt={"cert_reqs": ssl.CERT_NONE, "check_hostname": False}, timeout=60,
    header=[f"Cookie: user={cookie}", "Origin: https://localhost:8891"],
    origin="https://localhost:8891")
print("✅ 已连接 /WSCTRX")


def drain(t):
    out = []
    end = time.time() + t
    ws.settimeout(0.5)
    while time.time() < end:
        try:
            out.append(ws.recv())
        except Exception:
            pass
    return out


drain(1.0)


def record(level, seconds):
    ws.send(f"setWDSPNR2Level:{level}")
    time.sleep(1.0)
    st = [m for m in drain(0.8) if "wdsp" in m.lower() or "NR2" in m]
    ws.send("startRecording")
    time.sleep(0.5)
    r = [m for m in drain(1.0) if "recording" in m]
    print(f"  NR2 level={level}: {[m[:60] for m in (st + r)][:2]}")
    time.sleep(seconds)
    ws.send("stopRecording")
    time.sleep(1.5)
    r2 = [m for m in drain(2.0) if "recording" in m]
    print(f"  NR2 level={level}: {[m[:80] for m in r2][:2]}")
    return r2


before = set(glob.glob(os.path.join(ROOT, "recordings/*.mp3")))
print(f"录制 NR2=0（{SEC}s）…")
record(0, SEC)
print(f"录制 NR2=2（{SEC}s）…")
record(2, SEC)
new = sorted(set(glob.glob(os.path.join(ROOT, "recordings/*.mp3"))) - before, key=os.path.getmtime)
print("\n新录音:")
for f in new:
    print("  " + os.path.basename(f), f"{os.path.getsize(f)/1024:.0f} KB")
ws.close()
with open("/tmp/nr2_live_ab_files.txt", "w") as f:
    f.write("\n".join(new))
