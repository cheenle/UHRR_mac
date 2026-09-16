"""一键升级的纯逻辑（平台无关、可单测）。

设计见 `docs/superpowers/specs/2026-09-16-one-click-upgrade-design.md`：

* **安装版本唯一权威**：`version.txt`（构建时由 `MRRC.iss` 的 `MyAppVersion` 写入）；
  热补丁不改安装版本 → 用 `requires`（最低安装版本）+ 已应用集合判重；
* **拒绝降级**：`latest <= installed` 一律不动作；`installed < minSupported` 时禁用热修；
* **下载必须原子**：先写 `.part` → SHA256 校验 → `os.replace()`；失败只清 `.part`，
  绝不动现有安装；
* **进程间通信**：启动器与页面通过 `<data>/updates/` 下的 `state.json` 与 `upgrade.request`
  交互（比 IPC 简单可靠，Windows 上无需额外依赖）。

本模块只依赖标准库，且不 import tornado —— 因此既能在启动器（PyInstaller 冻结）里用，
也能在服务端与单测里用。
"""

import hashlib
import json
import os
import socket
import threading
import time
import urllib.request

DEFAULT_MANIFEST_URL = "https://www.vlsc.net/mrrc/downloads/latest.json"
LEGACY_PATCH_URL = "https://www.vlsc.net/mrrc/downloads/patch.json"


# --------------------------------------------------------------------------- #
# 版本与清单
# --------------------------------------------------------------------------- #
def version_tuple(text):
    """'6.0.10' → (6, 0, 10)；'v6.1' → (6, 1, 0, 0)；无法解析的部分按 0。"""
    parts = []
    for chunk in str(text or "").replace("v", "").split("."):
        digits = "".join(ch for ch in chunk if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts[:4])


def manifest_url():
    """清单地址：允许 MRRC_UPDATE_MANIFEST 覆盖（内网镜像 / 测试用）。"""
    return (os.environ.get("MRRC_UPDATE_MANIFEST") or "").strip() or DEFAULT_MANIFEST_URL


def fetch_manifest(url=None, timeout=10, fallback_url=LEGACY_PATCH_URL):
    """拉取升级清单；返回 (manifest|None, 失败原因)。latest.json 不可用时回退 patch.json。

    回退是为了向后兼容：老的 patch.json 只有 latest/hotfix 语义，plan_upgrade() 会把它
    当成"只有热修"，行为与今天一致。
    """
    reason = "未尝试"
    url = url or manifest_url()
    for candidate in (url, fallback_url):
        if not candidate:
            continue
        try:
            with urllib.request.urlopen(candidate, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            if isinstance(data, dict) and data.get("latest"):
                data.setdefault("_source", candidate)
                return data, None
            reason = "清单里没有 latest 字段"
        except Exception as exc:
            reason = f"{type(exc).__name__}: {exc}"
    return None, reason


def plan_upgrade(installed, manifest, applied_hotfixes=()):
    """给当前安装版本与清单，算出该做什么（纯函数、无副作用）。"""
    installed = str(installed or "0.0.0").strip() or "0.0.0"
    installed_t = version_tuple(installed)
    manifest = manifest or {}
    latest = str(manifest.get("latest") or "").strip()
    latest_t = version_tuple(latest)
    min_supported = str(manifest.get("minSupported") or "").strip()
    applied = {str(v) for v in (applied_hotfixes or [])}

    plan = {
        "installed": installed,
        "latest": latest,
        "minSupported": min_supported,
        "notes": manifest.get("notes", ""),
        "source": manifest.get("_source", ""),
        "installer": {"available": False},
        "hotfix": {"available": False},
        "previous": {"available": False},
    }

    installer = manifest.get("installer") or {}
    if installer.get("url") and installer.get("sha256") and latest_t > installed_t:
        plan["installer"] = {
            "available": True,
            "version": latest,
            "url": installer["url"],
            "sha256": str(installer["sha256"]).lower(),
            "size": int(installer.get("size") or 0),
            "mandatory": bool(manifest.get("mandatory")),
        }

    hotfix = manifest.get("hotfix") or {}
    requires = str(hotfix.get("requires") or min_supported or "").strip()
    if hotfix.get("url") and hotfix.get("sha256") and latest_t > installed_t and latest not in applied:
        if not requires or installed_t >= version_tuple(requires):
            plan["hotfix"] = {
                "available": True,
                "version": latest,
                "url": hotfix["url"],
                "sha256": str(hotfix["sha256"]).lower(),
                "requires": requires,
                "notes": hotfix.get("notes", ""),
            }
        else:
            plan["hotfix"] = {"available": False,
                              "blockedReason": f"需要安装版本 >= {requires}（本机 {installed}）"}

    previous = manifest.get("previous") or {}
    if previous.get("version") and previous.get("url"):
        plan["previous"] = {
            "available": True,
            "version": str(previous["version"]),
            "url": previous["url"],
            "sha256": str(previous.get("sha256") or "").lower(),
        }
    return plan


# --------------------------------------------------------------------------- #
# 状态文件与哨兵（启动器 ↔ 服务端）
# --------------------------------------------------------------------------- #
def updates_dir(base_dir):
    path = os.path.join(str(base_dir), "updates")
    os.makedirs(path, exist_ok=True)
    return path


def state_path(base_dir):
    return os.path.join(updates_dir(base_dir), "state.json")


# 下载线程与升级线程都会读-改-写 state.json：不加锁会互相覆盖
# （2026-09-16 VM 实测：下载完成覆盖了 lastResult，失败时无痕可查）。
_STATE_LOCK = threading.RLock()
_DOWNLOAD_LOCK = threading.Lock()      # 同一时刻只允许一个下载（避免两个线程抢同一个 .part）

# 默认 socket 超时：VM 实测过一次“0 字节 .part 挂死”（DNS/连接阶段卡住，不是读超时），
# 没有这个的话后台预下载线程会永久占着 _DOWNLOAD_LOCK，把升级看护线程也拖死。
socket.setdefaulttimeout(30)


def request_path(base_dir):
    return os.path.join(updates_dir(base_dir), "upgrade.request")


def _read_json(path):
    try:
        # utf-8-sig：容忍 BOM。Windows 工具（记事本 / PowerShell 的 Set-Content -Encoding utf8）
        # 默认会写 BOM，而 json.load 遇到 BOM 直接抛错 → 升级会被静默忽略（6.1.0 端到端实测）。
        with open(path, encoding="utf-8-sig") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _write_json_atomic(path, payload):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def read_state(base_dir):
    return _read_json(state_path(base_dir)) or {}


def write_state(base_dir, **fields):
    with _STATE_LOCK:
        state = read_state(base_dir)
        state.update(fields)
        _write_json_atomic(state_path(base_dir), state)
        return state


def record_result(base_dir, status, version="", detail=""):
    """记录最近一次升级结果（页面显示用）。status 取值见规格 §4。"""
    return write_state(base_dir, lastResult={
        "status": str(status), "version": str(version), "detail": str(detail)[:2000],
        "at": time.strftime("%Y-%m-%dT%H:%M:%S")})


def write_upgrade_request(base_dir, version):
    _write_json_atomic(request_path(base_dir),
                       {"version": str(version), "at": time.strftime("%Y-%m-%dT%H:%M:%S")})


def read_upgrade_request(base_dir):
    return _read_json(request_path(base_dir))


def clear_upgrade_request(base_dir):
    try:
        os.remove(request_path(base_dir))
    except OSError:
        pass


def installer_filename(version):
    return f"MRRC-Setup-{version}.exe"


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(262144), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_installer(url, sha256, base_dir, version, timeout=60, progress=None):
    """下载 → 校验 → 原子落盘，并写 `state.staged`。

    失败时：删除 `.part`、记录 `lastResult`、**绝不动已有安装**。
    返回 `{ok, path, size, sha256} | {ok: False, reason, path}`。
    """
    target = os.path.join(updates_dir(base_dir), installer_filename(version))
    # 临时文件按进程区分：曾出现两个启动器实例同时下同一个 .part，一个下完改名时
    # 另一个正开着它 → Windows 直接 PermissionError [WinError 32]（VM 实测）。
    part = target + f".part{os.getpid()}"
    expected = str(sha256 or "").lower()
    # 互斥：启动检查的后台下载与升级请求的下载都调这里，两个线程抢同一个 .part 会互相踩。
    # 但**绝不能无限等锁**：VM 实测后台预下载卡在连接阶段时，升级看护线程会一起被拖死
    # → 用户点了【立即升级】毫无反应（2026-09-16 真机复现）。拿不到就返回 busy，让上层重试。
    if not _DOWNLOAD_LOCK.acquire(timeout=1.0):
        return {"ok": False, "reason": "download_busy（另一次下载正在进行，稍后自动重试）",
                "path": target}
    try:
        try:
            with urllib.request.urlopen(url, timeout=timeout) as resp, open(part, "wb") as fh:
                total = int(resp.headers.get("Content-Length") or 0)
                done = 0
                while True:
                    chunk = resp.read(262144)
                    if not chunk:
                        break
                    fh.write(chunk)
                    done += len(chunk)
                    if progress:
                        try:
                            progress(done, total)
                        except Exception:
                            pass
            actual = sha256_file(part)
            if expected and actual != expected:
                os.remove(part)
                record_result(base_dir, "sha_mismatch", version,
                              f"{actual[:12]}… != {expected[:12]}…")
                return {"ok": False, "reason": f"sha256 不符（{actual[:12]}… != {expected[:12]}…）",
                        "path": target}
            for _try in range(6):                          # 杀软/索引器可能短暂占用
                try:
                    os.replace(part, target)               # 原子：只有校验通过才成为正式文件
                    break
                except PermissionError:
                    if _try == 5:
                        raise
                    time.sleep(1.0)
            write_state(base_dir, staged={
                "version": str(version), "sha256": actual, "path": target,
                "size": os.path.getsize(target), "at": time.strftime("%Y-%m-%dT%H:%M:%S")})
            return {"ok": True, "path": target, "size": os.path.getsize(target), "sha256": actual}
        except Exception as exc:
            try:
                if os.path.exists(part):
                    os.remove(part)                        # 只管自己的临时文件
            except OSError:
                pass
            record_result(base_dir, "download_failed", version, f"{type(exc).__name__}: {exc}")
            return {"ok": False, "reason": f"{type(exc).__name__}: {exc}", "path": target}
    finally:
        _DOWNLOAD_LOCK.release()

def staged_matches(state, version, sha256=None):
    """`state.staged` 是否就是目标版本且文件仍在（用于跳过重复下载）。"""
    staged = (state or {}).get("staged") or {}
    if str(staged.get("version")) != str(version):
        return False
    if sha256 and str(staged.get("sha256", "")).lower() != str(sha256).lower():
        return False
    return os.path.isfile(str(staged.get("path", "")))
