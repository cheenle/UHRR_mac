#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""在线 4 档对比（NR2 关 / L1 / L2 / L4）——中低信号强度场景。

拉丁方轮转顺序抵消时间漂移；每段 4s；同轮内尽量贴近。
指标：p10(噪声底) / p90(信号) / 动态(p90-p10, 信噪比代理) / RMS(电平)
"""
import configparser, glob, json, os, ssl, subprocess, time
import numpy as np
import websocket
from tornado.web import create_signed_value

ROOT = "/Users/cheenle/HAM/mrrc"
SR, SEC, ROUNDS = 48000, 4.0, 4
LEVELS = [0, 1, 2, 4]
NAMES = {0: "关", 1: "L1(-6dB)", 2: "L2(-12dB)", 4: "L4(-20dB)"}

c = configparser.ConfigParser(); c.read(f"{ROOT}/MRRC.radio1.conf")
cookie = create_signed_value(c["SERVER"]["cookie_secret"], "user", "selftest").decode()
ws = websocket.create_connection("wss://localhost:8891/WSCTRX",
                                sslopt={"cert_reqs": ssl.CERT_NONE, "check_hostname": False}, timeout=60,
                                header=[f"Cookie: user={cookie}", "Origin: https://localhost:8891"],
                                origin="https://localhost:8891")


def drain(t=0.5):
    out = []; end = time.time() + t; ws.settimeout(0.4)
    while time.time() < end:
        try: out.append(ws.recv())
        except Exception: pass
    return out


def status():
    ws.send("getWDSPStatus"); time.sleep(1.2)
    for m in drain(1.0):
        if "wdspStatus" in m:
            return json.loads(m.split("wdspStatus:", 1)[1])
    return {}


drain(1.0)
ws.send("setWDSPEnabled:true"); time.sleep(3.0); drain(1.0)
st = status()
print(f"WDSP enabled={st.get('enabled')} agcMode={st.get('agcMode')}")
assert st.get("enabled"), "WDSP 未开启"


def rec(level, sec):
    ws.send(f"setWDSPNR2Level:{level}"); time.sleep(0.7); drain(0.3)
    before = set(glob.glob(f"{ROOT}/recordings/*.mp3"))
    ws.send("startRecording"); time.sleep(0.3); drain(0.5)
    time.sleep(sec)
    ws.send("stopRecording"); time.sleep(1.0); drain(0.8)
    new = sorted(set(glob.glob(f"{ROOT}/recordings/*.mp3")) - before, key=os.path.getmtime)
    return new[-1] if new else None


def stat(f):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", f, "-f", "f32le", "-acodec", "pcm_f32le",
                          "-ac", "1", "-ar", str(SR), "-"], capture_output=True).stdout
    x = np.frombuffer(raw, dtype=np.float32).astype(np.float64)
    n = 1024; hop = 512
    e = np.array([10 * np.log10(np.sum(x[i * hop:i * hop + n] ** 2) + 1e-20)
                  for i in range((len(x) - n) // hop)])
    return dict(p10=np.percentile(e, 10), p90=np.percentile(e, 90),
                dyn=np.percentile(e, 90) - np.percentile(e, 10),
                rms=20 * np.log10(np.sqrt(np.mean(x ** 2)) + 1e-12))


data = {lv: [] for lv in LEVELS}
print(f"\n{'轮':>3s} " + " ".join(f"{NAMES[lv]:>22s}" for lv in LEVELS))
for r in range(ROUNDS):
    order = LEVELS[r:] + LEVELS[:r]           # 拉丁方轮转
    row = {}
    for lv in order:
        f = rec(lv, SEC)
        if not f:
            continue
        row[lv] = stat(f)
        data[lv].append(row[lv])
    print(f"{r:3d} " + " ".join(
        f"{'p10 %6.1f p90 %6.1f 动态 %5.1f' % (row[lv]['p10'], row[lv]['p90'], row[lv]['dyn']) if lv in row else ' ' * 22:>22s}"
        for lv in LEVELS))
st2 = status()
print(f"\n结束状态: nr2Level={st2.get('nr2Level')}  （测试后恢复为 2）")
ws.send("setWDSPNR2Level:2"); ws.close()

print(f"\n{'档位':>10s} {'p10噪声底':>10s} {'p90信号':>9s} {'动态(SNR代理)':>13s} {'RMS电平':>9s}")
base = None
for lv in LEVELS:
    if not data[lv]:
        continue
    m = {k: float(np.mean([d[k] for d in data[lv]])) for k in ('p10', 'p90', 'dyn', 'rms')}
    if lv == 0:
        base = m
    rel = "" if base is None else f"  (Δp10 {m['p10']-base['p10']:+.1f}  Δp90 {m['p90']-base['p90']:+.1f}  Δ动态 {m['dyn']-base['dyn']:+.1f}  ΔRMS {m['rms']-base['rms']:+.1f})"
    print(f"{NAMES[lv]:>10s} {m['p10']:10.1f} {m['p90']:9.1f} {m['dyn']:13.1f} {m['rms']:9.1f}{rel}")
