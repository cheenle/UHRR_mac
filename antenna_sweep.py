#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""antenna_sweep.py — 天线 SWR 扫频引擎（天调 bypass 模式）

用途：在 ATR-1000 直通（L=0/C=0）状态下，按指定步进逐点发射短促 tune 载波，
从 ATR-1000 电表读数记录各频点的裸天线 SWR/功率，形成天线阻抗画像的实测底稿。
典型用法：干/湿环境各扫一次，对比雨致失谐（见 docs/current/antenna/）。

设计（与 support_bundle.py 同风格：松散模块、回调注入、可独立单测）：
- 引擎不认识 MRRC/rigctld/代理的任何细节，全部通过 callbacks 注入：
    set_freq(hz) -> bool        电台 QSY
    ptt(on: bool) -> bool       键控/释放
    tone(on: bool)              tune 音播放开关（MRRC 的 start_tune/stop_tune）
    get_meter() -> dict|None    最新电表 {"power": W, "swr": x}
    proxy_cmd(dict) -> bool     发 ATR 代理命令（set_freq(no_tune)/set_relay/set_learning/set_autotune）
- 安全：逐点最大键控时间、全局中止、异常时强制释放 PTT 并恢复学习开关；
  结束后恢复原频率并由代理重新应用该频点的学习参数（退出 bypass）。
- 结果：antenna_sweeps/sweep_<YYYYMMDD_HHMMSS>.json + 同名单点数组，另维护 latest.json。

扫描点 plan：HAM_BANDS 默认七段（40/30/20/17/15/12/10m），step_khz 默认 10。
"""
import json
import os
import statistics
import threading
import time

HAM_BANDS = {
    # name: (lo_khz, hi_khz)
    "40m": (7000, 7300),
    "30m": (10100, 10150),
    "20m": (14000, 14350),
    "17m": (18068, 18168),
    "15m": (21000, 21450),
    "12m": (24890, 24990),
    "10m": (28000, 29700),
}

RESULTS_DIR = "antenna_sweeps"


class SweepError(Exception):
    pass


class AntennaSweepEngine:
    """单实例扫频引擎。start() 起后台线程；stop() 请求中止；status() 线程安全快照。"""

    def __init__(self, set_freq, ptt, tone, get_meter, proxy_cmd, results_dir=RESULTS_DIR,
                 logger=None):
        self._cb_set_freq = set_freq
        self._cb_ptt = ptt
        self._cb_tone = tone
        self._cb_get_meter = get_meter
        self._cb_proxy = proxy_cmd
        self.results_dir = results_dir
        self._log = logger or (lambda msg: print(msg))
        self._lock = threading.Lock()
        self._thread = None
        self._abort = threading.Event()
        self._state = self._fresh_state()

    @staticmethod
    def _fresh_state():
        return {
            "running": False, "phase": "idle", "error": None,
            "config": None, "points_total": 0, "points_done": 0,
            "current_freq_khz": None, "current_band": None,
            "started_at": None, "finished_at": None, "result_file": None,
            "points": [],   # [{freq_khz, power_w, swr, samples, ts}]
        }

    # ---------------- 公共接口 ----------------

    def status(self):
        with self._lock:
            s = dict(self._state)
            s["points"] = list(self._state["points"])
            return s

    def start(self, bands=None, step_khz=10, dwell_s=1.2, settle_s=0.5, note="",
              freqs_khz=None):
        if self._state["running"]:
            raise SweepError("sweep already running")
        step_khz = max(1, min(100, int(step_khz)))
        dwell_s = max(0.5, min(10.0, float(dwell_s)))
        settle_s = max(0.2, min(5.0, float(settle_s)))

        if freqs_khz:
            # 自定义频点列表（如复测掉读点）；波段标签尽力归入业余段
            plan = []
            for f in sorted({int(round(float(x))) for x in freqs_khz}):
                if not (1000 <= f <= 60000):
                    raise SweepError(f"freq out of range: {f}kHz")
                band = next((b for b, (lo, hi) in HAM_BANDS.items() if lo <= f <= hi),
                            "custom")
                plan.append((band, f))
        else:
            bands = bands or list(HAM_BANDS.keys())
            for b in bands:
                if b not in HAM_BANDS:
                    raise SweepError(f"unknown band {b}")
            plan = []
            for b in bands:
                lo, hi = HAM_BANDS[b]
                f = lo
                while f <= hi:
                    plan.append((b, f))
                    f += step_khz
        if not plan:
            raise SweepError("empty plan")

        self._abort.clear()
        with self._lock:
            self._state = self._fresh_state()
            self._state.update({
                "running": True, "phase": "starting",
                "config": {"bands": bands if not freqs_khz else None,
                           "freqs_khz": sorted({int(round(float(x))) for x in freqs_khz}) if freqs_khz else None,
                           "step_khz": step_khz,
                           "dwell_s": dwell_s, "settle_s": settle_s, "note": note},
                "points_total": len(plan), "started_at": time.time(),
            })
        self._thread = threading.Thread(target=self._run, args=(plan,),
                                        name="antenna-sweep", daemon=True)
        self._thread.start()
        return {"points_total": len(plan)}

    def stop(self):
        self._abort.set()

    # ---------------- 内部 ----------------

    def _set(self, **kw):
        with self._lock:
            self._state.update(kw)

    def _add_point(self, p):
        with self._lock:
            self._state["points"].append(p)
            self._state["points_done"] += 1

    def _sample_meter(self, dwell_s):
        """在 dwell 窗口内收集电表读数，返回 (median_power, median_swr, n)"""
        samples = []
        t_end = time.time() + dwell_s
        while time.time() < t_end and not self._abort.is_set():
            m = self._cb_get_meter()
            if m and m.get("power", 0) >= 1.0:
                samples.append((float(m["power"]), float(m.get("swr", 0))))
            time.sleep(0.15)
        if not samples:
            return 0.0, 0.0, 0
        pw = statistics.median([s[0] for s in samples])
        sw = statistics.median([s[1] for s in samples])
        return pw, sw, len(samples)

    def _run(self, plan):
        orig_freq = None
        learning_paused = False
        autotune_paused = False
        keyed = False
        tone_on = False
        empty_run = 0
        error = None
        try:
            # 1) 进入 bypass：关闭学习 + 关闭 SWR 自动调谐守卫 → 继电器直通 L=0/C=0
            self._set(phase="enter_bypass")
            if not self._cb_proxy({"action": "set_learning", "enabled": False}):
                raise SweepError("ATR 代理不可写（学习关闭失败，为避免污染学习库，扫描中止）")
            learning_paused = True
            if not self._cb_proxy({"action": "set_autotune", "enabled": False}):
                raise SweepError("ATR 代理不可写（自动调谐守卫关闭失败，裸 SWR>2 会触发调谐破坏测量，扫描中止）")
            autotune_paused = True
            if not self._cb_proxy({"action": "set_relay", "sw": 0, "ind": 0, "cap": 0}):
                raise SweepError("ATR 代理不可写（bypass 设置失败）")
            time.sleep(0.6)  # 继电器稳定

            # 2) tune 音常开（只切换 PTT，避免每点重建音频流 —— RC-001 教训）
            #    音频流打开有延迟（p.open 可能上百毫秒），给足预热再扫第一个点
            self._cb_tone(True)
            tone_on = True
            time.sleep(1.5)

            # 3) 逐点扫描
            for band, fkhz in plan:
                if self._abort.is_set():
                    break
                self._set(phase="sweeping", current_band=band, current_freq_khz=fkhz)
                if not self._cb_set_freq(int(fkhz * 1000)):
                    raise SweepError(f"set_freq 失败 @ {fkhz}kHz")
                # 通知代理频率上下文（no_tune：不应用学习参数，保持 bypass）
                self._cb_proxy({"action": "set_freq", "freq": int(fkhz * 1000), "no_tune": True})
                time.sleep(0.25)  # QSY 稳定

                if not self._cb_ptt(True):
                    raise SweepError(f"PTT 键控失败 @ {fkhz}kHz")
                keyed = True
                t0 = time.time()
                time.sleep(0.4)  # 载波/电表建立
                pw, sw, n = self._sample_meter(self._state["config"]["dwell_s"])
                self._cb_ptt(False)
                keyed = False
                self._add_point({
                    "freq_khz": fkhz, "band": band,
                    "power_w": round(pw, 1), "swr": round(sw, 3),
                    "samples": n, "ts": round(t0, 1),
                })
                # 连续无功率样本 = 载波没出去（tone/音频链没工作），继续下去全是空数据
                if n == 0:
                    empty_run += 1
                    if empty_run >= 5:
                        raise SweepError("连续 5 个频点无载波功率读数（tune 音/音频链未工作？），扫描中止")
                else:
                    empty_run = 0
                # 键控保险：单点总键控不超过 dwell+3s（_sample_meter 已被 dwell 限制，
                # 这里只是防御性歇隔，让功放/继电器喘息）
                time.sleep(0.35)

            self._set(phase="finishing")
        except Exception as e:  # noqa: BLE001 — 任何异常都必须落到 finally 清理
            error = f"{type(e).__name__}: {e}"
            self._log(f"⚠️ 扫频异常: {error}")
        finally:
            if keyed:
                try:
                    self._cb_ptt(False)
                except Exception:
                    pass
            if tone_on:
                try:
                    self._cb_tone(False)
                except Exception:
                    pass
            if learning_paused:
                try:
                    self._cb_proxy({"action": "set_learning", "enabled": True})
                except Exception:
                    pass
            if autotune_paused:
                try:
                    self._cb_proxy({"action": "set_autotune", "enabled": True})
                except Exception:
                    pass
            # 退出 bypass：用当前频率触发一次正常的学习参数应用
            try:
                cur = self._state.get("current_freq_khz")
                if cur:
                    self._cb_proxy({"action": "set_freq", "freq": int(cur * 1000)})
            except Exception:
                pass
            result_file = None
            try:
                result_file = self._save(error)
            except Exception as e:  # noqa: BLE001
                self._log(f"⚠️ 扫频结果保存失败: {e}")
            self._set(running=False, phase="aborted" if self._abort.is_set() else (
                "error" if error else "done"), error=error,
                finished_at=time.time(), result_file=result_file,
                current_freq_khz=None, current_band=None)
            self._log(f"📊 扫频结束: {self._state['points_done']}/{self._state['points_total']} 点"
                      f" {'(中止)' if self._abort.is_set() else ''} -> {result_file}")

    def _save(self, error):
        os.makedirs(self.results_dir, exist_ok=True)
        st = time.strftime("%Y%m%d_%H%M%S", time.localtime(self._state["started_at"] or time.time()))
        path = os.path.join(self.results_dir, f"sweep_{st}.json")
        with self._lock:
            payload = {
                "version": 1,
                "started_at": self._state["started_at"],
                "finished_at": time.time(),
                "config": self._state["config"],
                "error": error,
                "aborted": self._abort.is_set(),
                "points": list(self._state["points"]),
            }
        with open(path, "w", encoding="utf-8") as fp:
            json.dump(payload, fp, ensure_ascii=False, indent=1)
        latest = os.path.join(self.results_dir, "latest.json")
        try:
            with open(latest, "w", encoding="utf-8") as fp:
                json.dump(payload, fp, ensure_ascii=False, indent=1)
        except OSError:
            pass
        return path

    # ---------------- 结果查询 ----------------

    def list_results(self):
        if not os.path.isdir(self.results_dir):
            return []
        out = []
        for name in sorted(os.listdir(self.results_dir), reverse=True):
            if not (name.startswith("sweep_") and name.endswith(".json")):
                continue
            path = os.path.join(self.results_dir, name)
            try:
                with open(path, encoding="utf-8") as fp:
                    head = json.load(fp)
                out.append({
                    "file": name,
                    "started_at": head.get("started_at"),
                    "config": head.get("config"),
                    "n_points": len(head.get("points", [])),
                    "aborted": head.get("aborted", False),
                    "error": head.get("error"),
                })
            except (OSError, ValueError):
                continue
        return out

    def load_result(self, name):
        if "/" in name or ".." in name or not name.endswith(".json"):
            raise SweepError("bad file name")
        path = os.path.join(self.results_dir, name)
        with open(path, encoding="utf-8") as fp:
            return json.load(fp)
