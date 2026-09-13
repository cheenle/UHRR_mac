#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""在线 NR2 开/关 配对 A/B（中低信号强度场景）。

设计要点：
  * 先强制 WDSP=on 并校验，测试前/后都打印状态（防止被测方不小心关掉 WDSP）
  * 每对 4s，同一对内 关/开 紧邻；对与对之间顺序交替（关开 / 开关）抵消时间漂移
  * 指标：帧能量 p10(噪声底)/p50/p90(信号)、动态范围、RMS
用法: venv/bin/python3 dev_tools/nr2_live_pair.py [每段秒数] [对数]
"""
import configparser, glob, json, os, ssl, subprocess, sys, time
import numpy as np
import websocket
from tornado.web import create_signed_value

ROOT = "/Users/cheenle/HAM/mrrc"
SR = 48000
SEC = float(sys.argv[1]) if len(sys.argv) > 1 else 4.0
PAIRS = int(sys.argv[2]) if len(sys.argv) > 2 else 6

c = configparser.ConfigParser(); c.read(f"{ROOT}/MRRC.radio1.conf")
cookie = create_signed_value(c["SERVER"]["cookie_secret"], "user", "selftest").decode()
ws = websocket.create_connection(
    "wss://localhost:8891/WSCTRX",
    sslopt={"cert_reqs": ssl.CERT_NONE, "check_hostname": False}, timeout=60,
    header=[f"Cookie: user={cookie}", "Origin: https://localhost:8891"],
    origin="https://localhost:8891")


def drain(t=0.5):
    out = []
    end = time.time() + t
    ws.settimeout(0.4)
    while time.time() < end:
        try:
            out.append(ws.recv())
        except Exception:
            pass
    return out


def status():
    ws.send("getWDSPStatus")
    time.sleep(1.2)
    for m in drain(1.0):
        if "wdspStatus" in m:
            return json.loads(m.split("wdspStatus:", 1)[1])
    return {}


drain(1.0)
ws.send("setWDSPEnabled:true"); time.sleep(3.0); drain(1.0)
st = status()
print(f"WDSP 状态: enabled={st.get('enabled')} nr2Level={st.get('nr2Level')} agcMode={st.get('agcMode')} "
      f"bp={st.get('bpLow')}-{st.get('bpHigh')}")
if not st.get("enabled"):
    print("❌ WDSP 未开启，终止"); ws.close(); sys.exit(1)


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
    return dict(p10=np.percentile(e, 10), p50=np.percentile(e, 50), p90=np.percentile(e, 90),
                rms=20 * np.log10(np.sqrt(np.mean(x ** 2)) + 1e-12),
                peak=20 * np.log10(np.max(np.abs(x)) + 1e-12), n=len(x) / SR)


print(f"\n{'对':>3s} {'顺序':>7s} {'关p10':>7s} {'开p10':>7s} {'Δp10':>7s} | "
      f"{'关p90':>7s} {'开p90':>7s} {'Δp90':>7s} | {'关动态':>7s} {'开动态':>7s}")
pairs = []
for i in range(PAIRS):
    order = (0, 2) if i % 2 == 0 else (2, 0)
    fa = rec(order[0], SEC); fb = rec(order[1], SEC)
    if not (fa and fb):
        print(f"{i:3d} 录音失败"); continue
    A, B = stat(fa), stat(fb)
    a, b = (A, B) if order == (0, 2) else (B, A)      # a=关, b=开
    pairs.append((a, b))
    print(f"{i:3d} {'关->开' if order == (0, 2) else '开->关':>7s} "
          f"{a['p10']:7.1f} {b['p10']:7.1f} {b['p10'] - a['p10']:+7.1f} | "
          f"{a['p90']:7.1f} {b['p90']:7.1f} {b['p90'] - a['p90']:+7.1f} | "
          f"{a['p90'] - a['p10']:7.1f} {b['p90'] - b['p10']:7.1f}")

st2 = status()
print(f"\n结束状态: enabled={st2.get('enabled')} nr2Level={st2.get('nr2Level')}")
ws.close()
if pairs:
    d10 = np.array([b["p10"] - a["p10"] for a, b in pairs])
    d90 = np.array([b["p90"] - a["p90"] for a, b in pairs])
    ddyn = np.array([(b["p90"] - b["p10"]) - (a["p90"] - a["p10"]) for a, b in pairs])
    drms = np.array([b["rms"] - a["rms"] for a, b in pairs])
    print(f"\n配对差（NR2开 − 关, n={len(pairs)}, 每段{SEC:.0f}s 实时空中信号）:")
    print(f"  噪声底 Δp10 : {d10.mean():+.2f} ± {d10.std():.2f} dB   （负 {int((d10 < 0).sum())}/{len(d10)} 对下降）")
    print(f"  信号   Δp90 : {d90.mean():+.2f} ± {d90.std():.2f} dB")
    print(f"  动态   Δ    : {ddyn.mean():+.2f} ± {ddyn.std():.2f} dB   （正=语音对比度变好）")
    print(f"  总电平 ΔRMS : {drms.mean():+.2f} ± {drms.std():.2f} dB")
