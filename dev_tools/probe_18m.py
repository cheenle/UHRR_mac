#!/usr/bin/env python3
"""18.1MHz 综合实测探针。

阶段1: bypass(L0/C0) 4s        -> 当前真实裸 SWR
阶段2: 学习库参数 L0/C31 4s    -> 该参数今天是否还成立
阶段3: 种子参数 L8/C4 4s       -> fit 种子是否成立
阶段4: 回 bypass, 开守卫 50s   -> 设备自己全调谐, 确认学习入库
"""
import asyncio, json, socket, time

FREQ = 18100000
SOCK = "/tmp/mrrc_radio1.sock"


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


async def main():
    from tornado.websocket import websocket_connect
    from tornado.httpclient import HTTPRequest

    proxy_cmd({"action": "set_learning", "enabled": False})
    proxy_cmd({"action": "set_autotune", "enabled": False})

    req = HTTPRequest("wss://localhost:8891/WSCTRX", validate_cert=False,
                      headers={"Cookie": f"user={load_cookie()}"})
    ws = await websocket_connect(req)
    try:
        await ws.write_message(f"setFreq:{FREQ}")
        await asyncio.sleep(1.0)
        proxy_cmd({"action": "set_freq", "freq": FREQ, "no_tune": True})
        await ws.write_message("tune:true")
        print("tone ON")
        await asyncio.sleep(3.0)

        for tag, ind, cap in (("bypass", 0, 0), ("learned_L0C31", 0, 31), ("seed_L8C4", 8, 4)):
            proxy_cmd({"action": "set_relay", "sw": 0, "ind": ind, "cap": cap})
            print(f"[{time.strftime('%H:%M:%S')}] phase {tag}: L{ind}/C{cap}")
            await asyncio.sleep(4.0)

        # 阶段4: 回 bypass, 开学习+守卫, 等设备自动全调谐
        proxy_cmd({"action": "set_relay", "sw": 0, "ind": 0, "cap": 0})
        proxy_cmd({"action": "set_learning", "enabled": True})
        proxy_cmd({"action": "set_autotune", "enabled": True})
        print(f"[{time.strftime('%H:%M:%S')}] phase auto-tune: guard armed, waiting 55s")
        await asyncio.sleep(55.0)

        await ws.write_message("tune:false")
        await ws.write_message("setPTT:false")
        await asyncio.sleep(1.0)  # 等 flush —— 立即 close 会丢消息, 音停不掉
        print("tone OFF")
    finally:
        ws.close()
        proxy_cmd({"action": "set_learning", "enabled": True})
        proxy_cmd({"action": "set_autotune", "enabled": True})
        print("learning/autotune on")


if __name__ == "__main__":
    asyncio.run(main())
