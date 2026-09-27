#!/usr/bin/env python3
"""坏种子修复第二轮 — 针对 fix_bad_seeds.py 暴露的两个问题:

1. MRRC PTTSafetyMonitor TOT=120s 会在长 tune 会话中强制收 PTT
   (mrrc_radio1.log: "发射已持续 120.9s ... 强制收回 PTT"),
   TX 一断设备的 tune mode=2 被静默忽略 → 每个调谐点前重新 tune:false/true
   重置 ptt_start_time。
2. 确认学习需要继电器稳定 >8s, 脚本盲睡 22s 后自己切频会打断稳定窗
   (7180 的 L12/C44@1.07 因此没确认) → 改为轮询日志等到 "调谐确认学习"
   或超时再走。
"""
import asyncio, json, re, socket, time

SOCK = "/tmp/mrrc_radio1.sock"
LOG = "atr1000_radio1.log"
WS_URL = "wss://localhost:8891/WSCTRX"

# 设备全调谐 + 确认学习自动入库
TUNE_POINTS = [7160000, 7200000, 28450000, 28900000, 29300000]
# 只测不修 (体检 nodata 的 CL 拓扑点)
PROBE_POINTS = [(14000000, 1, 3, 10), (14020000, 1, 4, 10),
                (14050000, 1, 4, 11), (14090000, 1, 4, 12)]
# 直接改写 (已有实测依据)
DIRECT_FIX = [
    (7180000, 0, 12, 44, 1.07),   # 上轮设备实扫到 L12/C44@1.07 但稳定窗被打断未确认
    (21405000, 0, 0, 4, 1.20),    # 邻 21380 实测 1.0; 旧 CL L3/C12 实测 2.93
]


def load_cookie():
    for line in open("/tmp/mrrc_cj.txt"):
        if line.startswith("#") or not line.strip():
            continue
        p = line.strip().split("\t")
        if len(p) >= 7 and p[5] == "user":
            return p[6]
    raise RuntimeError("no cookie")


def proxy_cmd(c):
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(2.0)
    s.connect(SOCK)
    s.sendall((json.dumps(c) + "\n").encode())
    s.close()


class LogTail:
    def __init__(self):
        self.f = open(LOG)
        self.f.seek(0, 2)
        self.cur = None
        self.confirmed = []

    def collect(self):
        out = []
        for line in self.f.readlines():
            if "RX | RELAY" in line:
                r = re.search(r"SW=(\w+), L=(\d+), C=(\d+)", line)
                if r:
                    self.cur = (r.group(1), int(r.group(2)), int(r.group(3)))
            elif "METER" in line:
                r = re.search(r"功率=(\d+)W, SWR=([\d.]+)", line)
                if r and self.cur:
                    out.append((self.cur, float(r.group(2)), int(r.group(1))))
            if "调谐确认学习" in line:
                msg = line.split("- ATR1000-Proxy - INFO -")[-1].strip()
                self.confirmed.append(msg)
                print("   ", msg, flush=True)
        return out


def median(v):
    v = sorted(v)
    return v[len(v) // 2] if v else None


async def main():
    from tornado.websocket import websocket_connect, WebSocketClosedError
    from tornado.httpclient import HTTPRequest

    tail = LogTail()
    proxy_cmd({"action": "set_learning", "enabled": True})
    proxy_cmd({"action": "set_autotune", "enabled": False})

    cookie = load_cookie()

    async def connect():
        req = HTTPRequest(WS_URL, validate_cert=False, headers={"Cookie": f"user={cookie}"})
        ws = await websocket_connect(req)
        await ws.write_message("tune:true")
        return ws

    async def rearm_tone(ws):
        """重置 TOT 计时: tune:false -> true (PTT 下降沿+上升沿, ptt_start_time 重记)"""
        try:
            await ws.write_message("tune:false")
            await asyncio.sleep(0.8)
            await ws.write_message("tune:true")
        except WebSocketClosedError:
            ws = await connect()
        await asyncio.sleep(1.5)
        return ws

    async def set_freq(ws, f):
        try:
            await ws.write_message(f"setFreq:{f}")
        except WebSocketClosedError:
            ws = await connect()
            await asyncio.sleep(1.5)
            await ws.write_message(f"setFreq:{f}")
        return ws

    ws = await connect()
    try:
        print("tone ON, 预热 3s", flush=True)
        await asyncio.sleep(3.0)
        tail.collect()

        # --- 补测 nodata 点 (只测) ---
        for f, sw, ind, cap in PROBE_POINTS:
            ws = await rearm_tone(ws)
            ws = await set_freq(ws, f)
            await asyncio.sleep(1.2)
            proxy_cmd({"action": "set_freq", "freq": f, "no_tune": True})
            tail.collect()
            proxy_cmd({"action": "set_relay", "sw": sw, "ind": ind, "cap": cap})
            await asyncio.sleep(1.0)
            tail.collect()
            await asyncio.sleep(2.5)
            target = ("CL" if sw else "LC", ind, cap)
            samples = [s for st, s, pw in tail.collect() if st == target and pw >= 3]
            print(f"补测 {f/1e6:8.4f}MHz {target[0]} L{ind}/C{cap} -> SWR {median(samples)} (n={len(samples)})", flush=True)

        # --- 设备全调谐修复 (等确认学习, 不打断稳定窗) ---
        for f in TUNE_POINTS:
            ws = await rearm_tone(ws)
            ws = await set_freq(ws, f)
            await asyncio.sleep(1.2)
            proxy_cmd({"action": "set_freq", "freq": f, "no_tune": True})
            proxy_cmd({"action": "set_relay", "sw": 0, "ind": 0, "cap": 0})
            await asyncio.sleep(1.2)
            tail.collect()
            n_conf = len(tail.confirmed)
            print(f"🔧 tune {f/1e6:8.4f}MHz ...", flush=True)
            proxy_cmd({"action": "tune", "mode": 2})
            # 最多等 45s: 扫描 ~10s + 稳定 8s + 余量; 确认学习出现才走
            deadline = time.time() + 45
            ok = False
            while time.time() < deadline:
                await asyncio.sleep(2.0)
                tail.collect()
                if len(tail.confirmed) > n_conf:
                    ok = True
                    break
            if not ok:
                print(f"   ⚠️ {f/1e6:.4f}MHz 45s 内无确认学习", flush=True)

        await ws.write_message("tune:false")
        await ws.write_message("setPTT:false")
        await asyncio.sleep(1.0)
        print("tone OFF", flush=True)
    finally:
        try:
            await ws.write_message("tune:false")
            await ws.write_message("setPTT:false")
            await asyncio.sleep(0.8)
            ws.close()
        except Exception:
            pass
        proxy_cmd({"action": "set_learning", "enabled": True})
        proxy_cmd({"action": "set_autotune", "enabled": True})
        proxy_cmd({"action": "set_freq", "freq": 7050000})

    # --- 直接改写 ---
    for f, sw, ind, cap, swr in DIRECT_FIX:
        proxy_cmd({"action": "learn", "freq": f, "sw": sw, "ind": ind, "cap": cap,
                   "swr": swr, "force_update": True})
        print(f"✏️ 直接修复 {f/1e6:.4f}MHz -> {'CL' if sw else 'LC'} L{ind}/C{cap} @swr{swr}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
