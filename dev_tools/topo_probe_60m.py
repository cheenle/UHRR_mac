#!/usr/bin/env python3
"""拓扑判别实测: 固定 5351.5kHz + tune 音, 依次手动设三组继电器, 各停留 dwell 秒。

拓扑A(sw=0=LC: 串L+负载侧并C)预测: L29/C43->1.35, L35/C41->1.04, L44/C34->1.81
拓扑B(sw=0=CL: 源侧并C+串L)预测:    L29/C43->1.39, L35/C41->1.99, L44/C34->4.6
"""
import asyncio, json, socket, sys, time

FREQ = 5351500
STEPS = [(31, 44), (29, 43), (31, 44)]
DWELL = 4.0
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

    t_marks = []
    # 暂停学习+自动调谐, 防污染/防守卫插手
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
        await asyncio.sleep(3.0)  # 载波稳定
        for ind, cap in STEPS:
            proxy_cmd({"action": "set_relay", "sw": 0, "ind": ind, "cap": cap})
            t_marks.append((time.time(), ind, cap))
            print(f"[{time.strftime('%H:%M:%S')}] set relay L{ind}/C{cap}")
            await asyncio.sleep(DWELL)
        await ws.write_message("tune:false")
        await asyncio.sleep(1.0)  # 等 flush —— 立即 close 会丢消息, 音停不掉
        print("tone OFF")
    finally:
        ws.close()
        proxy_cmd({"action": "set_relay", "sw": 0, "ind": 29, "cap": 43})
        proxy_cmd({"action": "set_learning", "enabled": True})
        proxy_cmd({"action": "set_autotune", "enabled": True})
        print("learning/autotune re-enabled, relay restored L29/C43")
    print("MARKS " + json.dumps(t_marks))


if __name__ == "__main__":
    asyncio.run(main())
