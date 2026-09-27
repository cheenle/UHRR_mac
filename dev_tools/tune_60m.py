#!/usr/bin/env python3
"""60m 实测 tune 驱动: setFreq -> tune 音常开 -> 等守卫触发/显式 tune -> 停。

用法: venv/bin/python dev_tools/tune_60m.py <freq_hz> [wait_s]
"""
import asyncio, json, socket, sys, time

FREQ = int(sys.argv[1]) if len(sys.argv) > 1 else 5351500
WAIT = float(sys.argv[2]) if len(sys.argv) > 2 else 25.0
PROXY_SOCK = "/tmp/mrrc_radio1.sock"


def load_cookie():
    for line in open("/tmp/mrrc_cj.txt"):
        if line.startswith("#") or not line.strip():
            continue
        parts = line.strip().split("\t")
        if len(parts) >= 7 and parts[5] == "user":
            return parts[6]
    raise RuntimeError("no user cookie")


def proxy_cmd(cmd):
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(2.0)
    s.connect(PROXY_SOCK)
    s.sendall((json.dumps(cmd) + "\n").encode())
    try:
        return s.recv(4096).decode()
    except socket.timeout:
        return ""
    finally:
        s.close()


async def main():
    from tornado.websocket import websocket_connect
    from tornado.httpclient import HTTPRequest

    req = HTTPRequest("wss://localhost:8891/WSCTRX", validate_cert=False,
                      headers={"Cookie": f"user={load_cookie()}"})
    ws = await websocket_connect(req)
    print("WS connected")

    await ws.write_message(f"setFreq:{FREQ}")
    await asyncio.sleep(1.5)
    print(f"freq set -> {FREQ}Hz, sync to ATR proxy")
    print("proxy:", proxy_cmd({"action": "set_freq", "freq": FREQ}).strip()[:120])

    await ws.write_message("tune:true")
    print(f"tune tone ON, {WAIT}s 窗口（守卫 ~4s 内自动触发全调谐，日志为准）...")
    await asyncio.sleep(WAIT)

    await ws.write_message("tune:false")
    await ws.write_message("setPTT:false")
    await asyncio.sleep(1.0)  # 等 flush —— 立即 close 会丢消息, 音停不掉
    print("tune tone OFF, done")
    ws.close()


if __name__ == "__main__":
    asyncio.run(main())
