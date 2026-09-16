#!/usr/bin/env python3
"""测量 RX 音频 WebSocket 的投递节奏（判断"卡顿"出在服务器还是网络/客户端）。

用途：在**客户端机器**上运行，连到正在跑的服务端，量 /WSaudioRX 消息的到达间隔与空隙。
配合 `dev_tools/ws_audio_jitter.py --url wss://server:port` 使用；登录用 MRRC.conf 里的
cookie_secret 现签 cookie（或者用 --user/--password 走 /login）。

判读标准（50 fps ⇒ 每帧 20ms）：
  * median ≈ 20ms、p95 < 40ms、max < 120ms  → 服务器投递健康，卡顿在客户端缓冲/浏览器
  * median ≈ 20ms 但出现规律性 0.5–1s 空隙   → 服务器周期性停顿（IOLoop 被阻塞或采集抖动）
  * median 明显 > 20ms / p95 很大            → 网络或服务器 CPU 不足
  * 长时间 0 帧                               → 采集没起来 / 被 PTT 半双工屏蔽

用法：
  python3 dev_tools/ws_audio_jitter.py --url wss://localhost:8891 \
      --conf MRRC.radio1.conf --seconds 20
  python3 dev_tools/ws_audio_jitter.py --url wss://radio.example:8877 \
      --cookie-secret '<secret>' --seconds 20      # 远程：给 secret 或直接在服务端机器上跑
"""

from __future__ import annotations

import argparse
import configparser
import json
import os
import statistics
import ssl
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def log(msg):
    print(msg, flush=True)


def make_cookie(secret: str, user: str = "jitter-probe") -> str:
    from tornado.web import create_signed_value
    return create_signed_value(secret, "user", user).decode()


def summarize(gaps):
    if not gaps:
        return "没有收到任何音频帧"
    gaps_ms = [g * 1000 for g in gaps]
    return ("帧数={n} 中位={med:.1f}ms p90={p90:.1f}ms p99={p99:.1f}ms max={mx:.1f}ms "
            "| >200ms的空隙={big} 个（{big_ms:.0f}ms 合计）").format(
        n=len(gaps_ms), med=statistics.median(gaps_ms),
        p90=sorted(gaps_ms)[int(len(gaps_ms) * 0.9)] if len(gaps_ms) > 1 else gaps_ms[0],
        p99=sorted(gaps_ms)[int(len(gaps_ms) * 0.99)] if len(gaps_ms) > 1 else gaps_ms[0],
        mx=max(gaps_ms),
        big=sum(1 for g in gaps_ms if g > 200),
        big_ms=sum(g for g in gaps_ms if g > 200),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="RX 音频 WS 投递节奏探针")
    parser.add_argument("--url", required=True, help="例如 wss://localhost:8891")
    parser.add_argument("--conf", help="服务端 MRRC.conf（本机跑时用来签 cookie）")
    parser.add_argument("--cookie-secret", help="服务端 cookie_secret（远程时用）")
    parser.add_argument("--user", default="jitter-probe")
    parser.add_argument("--seconds", type=float, default=20.0)
    parser.add_argument("--enable-opus", action="store_true",
                        help="先请求服务端按 Opus 发送（前端默认走这条路径）")
    args = parser.parse_args()

    secret = args.cookie_secret
    if not secret and args.conf:
        cfg = configparser.ConfigParser()
        cfg.read(args.conf, encoding="utf-8")
        secret = cfg.get("SERVER", "cookie_secret", fallback=None)
    if not secret:
        log("❌ 需要 --cookie-secret 或 --conf（用于签登录 cookie）")
        return 2

    try:
        import websocket                       # websocket-client
    except ImportError:
        log("❌ 需要 websocket-client（服务端 venv 里已有）")
        return 2

    cookie = make_cookie(secret, args.user)
    url = args.url.rstrip("/") + "/WSaudioRX"
    log(f"连接 {url} …")
    ws = websocket.create_connection(
        url, sslopt={"cert_reqs": ssl.CERT_NONE, "check_hostname": False}, timeout=20,
        header=[f"Cookie: user={cookie}", f"Origin: {args.url}"], origin=args.url)
    log("已连接，开始测量（请保持静默/正常接收；TX 期间不发 RX 音频属正常）")

    try:
        ws.settimeout(1.0)
        if args.enable_opus:
            for cmd in ('opusRxEnable', 'setOpusRx:1', 'rxOpusEnable'):
                try:
                    ws.send(cmd)
                except Exception:
                    pass
        gaps, sizes, prev = [], [], None
        deadline = time.time() + args.seconds
        while time.time() < deadline:
            try:
                data = ws.recv()
            except Exception:
                continue
            now = time.time()
            if isinstance(data, str):          # 文本消息（状态/控制）不计入音频节奏
                continue
            if prev is not None:
                gaps.append(now - prev)
            sizes.append(len(data))
            prev = now
        log("")
        log("结果：" + summarize(gaps))
        if sizes:
            log(f"      帧大小：中位 {statistics.median(sizes):.0f} B，"
                f"最小 {min(sizes)} B，最大 {max(sizes)} B（PCM 20ms≈1920B / Opus≈80B）")
        if gaps:
            big = sorted(((g, i) for i, g in enumerate(gaps)), reverse=True)[:5]
            log("      最大的 5 个空隙：" + ", ".join(f"{g*1000:.0f}ms" for g, _ in big))
    finally:
        ws.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
