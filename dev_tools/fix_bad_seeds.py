#!/usr/bin/env python3
"""定点修复体检发现的坏种子。

三类手段:
  TUNE_POINTS : 设备全调谐 + 确认学习自动入库 (10m 全族、40m 上边沿)
  PROBE_POINTS: 只测不修 (体检 nodata 补测)
  DIRECT_FIX  : 直接强制改写 (邻近有实测可信参数的误学习点)
"""
import asyncio, json, re, socket, time

SOCK = "/tmp/mrrc_radio1.sock"
LOG = "atr1000_radio1.log"
WS_URL = "wss://localhost:8891/WSCTRX"

TUNE_POINTS = [7160000, 7180000, 7200000, 28074000, 28450000, 28900000, 29300000, 29600000]
PROBE_POINTS = [(10110000, 0, 15, 0), (14000000, 1, 3, 10), (14020000, 1, 4, 10),
                (14050000, 1, 4, 11), (14090000, 1, 4, 12)]
DIRECT_FIX = [  # (freq, sw, ind, cap, swr) — 依据邻近实测锚点
    (3855000, 0, 43, 127, 1.45),   # 误学习 L49/C82(实测15.8); 邻 3850/3860 L42-44/C127
    (7063000, 0, 8, 46, 1.30),     # 误学习 L0/C16(实测2.33); 邻 7060/7065 L8/C44-47
    (7110000, 0, 15, 44, 1.50),    # n=1 CL 记录(实测2.35); 改 LC, 邻 7100 L14/C45 / 7120 L16/C43
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
                print("   ", line.split("- ATR1000-Proxy - INFO -")[-1].strip(), flush=True)
        return out


def median(v):
    v = sorted(v)
    return v[len(v) // 2] if v else None


async def main():
    from tornado.websocket import websocket_connect, WebSocketClosedError
    from tornado.httpclient import HTTPRequest

    tail = LogTail()
    proxy_cmd({"action": "set_learning", "enabled": True})   # 确认学习需要
    proxy_cmd({"action": "set_autotune", "enabled": False})  # 防守卫与显式 tune 打架

    cookie = load_cookie()

    async def connect():
        req = HTTPRequest(WS_URL, validate_cert=False, headers={"Cookie": f"user={cookie}"})
        ws = await websocket_connect(req)
        await ws.write_message("tune:true")
        return ws

    async def set_freq(ws, f):
        try:
            await ws.write_message(f"setFreq:{f}")
        except WebSocketClosedError:
            ws2 = await connect()
            await asyncio.sleep(2.0)
            await ws2.write_message(f"setFreq:{f}")
            return ws2
        return ws

    ws = await connect()
    try:
        print("tone ON, 预热 3s", flush=True)
        await asyncio.sleep(3.0)
        tail.collect()

        # --- 补测 nodata 点 (只测) ---
        for f, sw, ind, cap in PROBE_POINTS:
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

        # --- 设备全调谐修复 ---
        for f in TUNE_POINTS:
            ws = await set_freq(ws, f)
            await asyncio.sleep(1.2)
            proxy_cmd({"action": "set_freq", "freq": f, "no_tune": True})
            proxy_cmd({"action": "set_relay", "sw": 0, "ind": 0, "cap": 0})  # bypass 起跑
            await asyncio.sleep(1.2)
            tail.collect()
            print(f"🔧 tune {f/1e6:8.4f}MHz ...", flush=True)
            proxy_cmd({"action": "tune", "mode": 2})
            await asyncio.sleep(22.0)
            tail.collect()  # 打印确认学习行

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
