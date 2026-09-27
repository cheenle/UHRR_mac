#!/usr/bin/env python3
"""全波段种子体检: 逐个验证 atr1000_tuner.json 里种子/学习参数在今天的真实成色。

原理:
  对每个 (波段, sw, ind, cap) 参数簇取代表频点, QSY 过去 + tune 音常开,
  手动设继电器为该簇参数, 从 proxy 日志按"最后继电器回显==目标"归属采样,
  取中位 SWR 与记录值对比。判定: OK<=1.8, marginal<=2.5, bad>2.5, nodata。

用法:
  venv/bin/python dev_tools/seed_healthcheck.py              # 只体检种子 (n=0)
  venv/bin/python dev_tools/seed_healthcheck.py --learned    # 只体检已学习记录
  venv/bin/python dev_tools/seed_healthcheck.py --full       # 全部
  venv/bin/python dev_tools/seed_healthcheck.py --tune-bad   # 体检后对 bad 簇逐一触发设备全调谐自修复
"""
import asyncio, json, re, socket, sys, time
from collections import defaultdict

SOCK = "/tmp/mrrc_radio1.sock"
LOG = "atr1000_radio1.log"
TUNER_JSON = "atr1000_tuner.json"
REPORT = "dev_tools/seed_health_report.json"
WS_URL = "wss://localhost:8891/WSCTRX"

BANDS = [("80m", 3500, 3900), ("60m", 5300, 5400), ("40m", 7000, 7200),
         ("30m", 10100, 10150), ("20m", 14000, 14350), ("17m", 18068, 18168),
         ("15m", 21000, 21450), ("12m", 24890, 24990), ("10m", 28000, 29700)]


def band_of(khz):
    for name, lo, hi in BANDS:
        if lo <= khz <= hi:
            return name
    return "other"


def load_cookie():
    for line in open("/tmp/mrrc_cj.txt"):
        if line.startswith("#") or not line.strip():
            continue
        p = line.strip().split("\t")
        if len(p) >= 7 and p[5] == "user":
            return p[6]
    raise RuntimeError("no cookie — 先 curl 登录拿 /tmp/mrrc_cj.txt")


def proxy_cmd(c):
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(2.0)
    s.connect(SOCK)
    s.sendall((json.dumps(c) + "\n").encode())
    s.close()


class LogTail:
    """增量读 proxy 日志, 按继电器回显归属 METER 样本。

    cur 必须跨 collect() 调用保持: 继电器回显通常被"丢弃段"的 collect 消费掉,
    采样段的 collect 里只有 METER 没有 RELAY —— cur 若每次重置会全部 nodata。"""

    def __init__(self):
        self.f = open(LOG)
        self.f.seek(0, 2)
        self.cur = None

    def collect(self):
        """返回自上次调用以来的 [(relay_state, swr, power)] 样本。"""
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
        return out


def median(v):
    v = sorted(v)
    return v[len(v) // 2] if v else None


async def main():
    do_learned = "--learned" in sys.argv
    do_full = "--full" in sys.argv
    tune_bad = "--tune-bad" in sys.argv

    recs = json.load(open(TUNER_JSON))["records"]
    if do_full:
        sel = recs
    elif do_learned:
        sel = [r for r in recs if r.get("sample_count", 0) > 0]
    else:
        sel = [r for r in recs if r.get("sample_count", 0) == 0]

    # 按 (波段, sw, ind, cap) 聚簇, 代表频点 = 簇内中位频率
    clusters = defaultdict(list)
    for r in sel:
        clusters[(band_of(r["freq"] // 1000), r["sw"], r["ind"], r["cap"])].append(r["freq"])
    plan = []
    for (band, sw, ind, cap), freqs in clusters.items():
        freqs.sort()
        plan.append({"band": band, "sw": sw, "ind": ind, "cap": cap,
                     "freq": freqs[len(freqs) // 2], "n_seeds": len(freqs),
                     "freqs": freqs})
    plan.sort(key=lambda p: p["freq"])
    skipped = [p for p in plan if p["band"] == "other"]
    plan = [p for p in plan if p["band"] != "other"]
    if skipped:
        print(f"跳过非业余频段 {len(skipped)} 簇: "
              + ", ".join(f"{p['freq']/1e6:.3f}M" for p in skipped))
    print(f"体检计划: {len(sel)} 条记录 -> {len(plan)} 个参数簇")

    from tornado.websocket import websocket_connect, WebSocketClosedError
    from tornado.httpclient import HTTPRequest

    tail = LogTail()
    proxy_cmd({"action": "set_learning", "enabled": False})
    proxy_cmd({"action": "set_autotune", "enabled": False})

    cookie = load_cookie()

    async def connect():
        req = HTTPRequest(WS_URL, validate_cert=False,
                          headers={"Cookie": f"user={cookie}"})
        ws = await websocket_connect(req)
        await ws.write_message("tune:true")
        return ws

    async def stop_tone(ws):
        # 先等 flush 再 close —— 立即 close 会丢掉 tune:false (probe_18m 的教训:
        # 音没停成, 18 分钟常发)。两条命令 + setPTT 双保险。
        for msg in ("tune:false", "setPTT:false"):
            try:
                await ws.write_message(msg)
            except Exception:
                pass
        await asyncio.sleep(1.0)

    ws = await connect()
    results = []
    try:
        print("tone ON, 预热 3s")
        await asyncio.sleep(3.0)
        tail.collect()  # 清掉预热段

        for i, p in enumerate(plan):
            target = ("CL" if p["sw"] else "LC", p["ind"], p["cap"])
            try:
                await ws.write_message(f"setFreq:{p['freq']}")
            except WebSocketClosedError:
                print("  WS 断开, 重连...")
                ws = await connect()
                await asyncio.sleep(2.0)
                await ws.write_message(f"setFreq:{p['freq']}")
            await asyncio.sleep(1.2)
            proxy_cmd({"action": "set_freq", "freq": p["freq"], "no_tune": True})
            tail.collect()  # 丢弃 QSY 与 MRRC 自动应用段的样本
            proxy_cmd({"action": "set_relay", "sw": p["sw"], "ind": p["ind"], "cap": p["cap"]})
            await asyncio.sleep(0.9)  # 继电器稳定 + 冲掉切换沿
            tail.collect()
            await asyncio.sleep(2.2)  # 采样窗
            samples = [s for st, s, pw in tail.collect() if st == target and pw >= 3]
            med = median(samples)
            verdict = ("nodata" if med is None else
                       "OK" if med <= 1.8 else "marginal" if med <= 2.5 else "bad")
            results.append({**p, "measured_swr": med, "n_samples": len(samples),
                            "verdict": verdict})
            print(f"[{i+1:2d}/{len(plan)}] {p['freq']/1e6:9.4f}MHz {p['band']:5s} "
                  f"{target[0]} L{p['ind']}/C{p['cap']} x{p['n_seeds']}种子 "
                  f"-> SWR {med if med else '-'}  {verdict}", flush=True)

        if tune_bad:
            bads = [r for r in results if r["verdict"] == "bad"]
            for r in bads:
                print(f"🔧 自修复 {r['freq']/1e6:.4f}MHz: 全调谐...", flush=True)
                proxy_cmd({"action": "set_freq", "freq": r["freq"], "no_tune": True})
                try:
                    await ws.write_message(f"setFreq:{r['freq']}")
                except WebSocketClosedError:
                    ws = await connect()
                    await asyncio.sleep(2.0)
                    await ws.write_message(f"setFreq:{r['freq']}")
                await asyncio.sleep(1.5)
                proxy_cmd({"action": "tune", "mode": 2})
                await asyncio.sleep(25.0)
        await stop_tone(ws)
        print("tone OFF")
    finally:
        try:
            await stop_tone(ws)
        except Exception:
            pass
        try:
            ws.close()
        except Exception:
            pass
        proxy_cmd({"action": "set_learning", "enabled": True})
        proxy_cmd({"action": "set_autotune", "enabled": True})
        proxy_cmd({"action": "set_freq", "freq": 7050000})  # 回到 40m 常用频点

    json.dump({"ts": time.time(), "results": results},
              open(REPORT, "w"), ensure_ascii=False, indent=1)
    n_bad = sum(1 for r in results if r["verdict"] == "bad")
    n_ok = sum(1 for r in results if r["verdict"] == "OK")
    print(f"\n体检完成: OK={n_ok} bad={n_bad} / {len(results)}  报告 -> {REPORT}")


if __name__ == "__main__":
    asyncio.run(main())
