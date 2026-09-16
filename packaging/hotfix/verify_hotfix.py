#!/usr/bin/env python3
"""在真实打包产物上验收热修通道（Windows / 任意平台都可跑）。

验收目标（即 A+B 的核心承诺）：**不改动安装目录、不重新打包，就能修 bug**。

做法：
  1. 现场合成一个热修包：
       www/hotfix_probe.js        ← 前端覆盖（浏览器刷新即生效）
       app/patch_overlay.py       ← Python 覆盖（追加探针，让 describe() 多返回一个键）
  2. 按启动器的方式（`launcher.apply_hotfix_pack`）解到 %LOCALAPPDATA%\\MRRC\\patch
  3. 用给定的配置启动 `MRRC-Server.exe`
  4. 验证：HTTP 取到覆盖层的前端文件；`getPatchStatus` 里出现 Python 探针键
  5. 清理：停服务、删掉本次写入的覆盖层文件

用法（在构建机上）：

    venv\\Scripts\\python.exe packaging\\hotfix\\verify_hotfix.py `
        --app dist\\windows\\MRRC `
        --config "$env:LOCALAPPDATA\\MRRC\\MRRC.conf"

退出码 0 = 通过；非 0 = 失败（并打印原因）。
"""

from __future__ import annotations

import argparse
import configparser
import hashlib
import json
import os
import ssl
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile
from pathlib import Path

PROBE_JS = "/* MRRC-HOTFIX-PROBE-OK */\n"
PROBE_KEY = "hotfixProbe"
PROBE_MARKER = "MRRC-HOTFIX-PY-PROBE-OK"
# 探针追加到惰性导入的模块上（MRRC 在启动时函数内 import hamlib_wrapper）：
# 这样源码模式与冻结模式都能被覆盖层截获，且不需要电台。
PROBE_TARGET = "hamlib_wrapper.py"
PROBE_PY = '''

# --- 验收探针（由 verify_hotfix.py 追加）---
import sys as _probe_sys
print("''' + PROBE_MARKER + '''", file=_probe_sys.stderr, flush=True)
'''


def _force_utf8_output():
    """中文 Windows 控制台默认 cp936，直接 print emoji 会 UnicodeEncodeError。"""
    for stream in ("stdout", "stderr"):
        target = getattr(sys, stream, None)
        if target is not None and hasattr(target, "reconfigure"):
            try:
                target.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


_force_utf8_output()


def log(message: str) -> None:
    print(message, flush=True)


def build_probe_pack(app_dir: Path, out_zip: Path, notes: str, version: str) -> list[str]:
    """合成热修包（只含探针文件），返回写入的覆盖层相对路径。"""
    loose_source = None
    for candidate in (app_dir / "_internal" / "app" / PROBE_TARGET,         # 冻结安装
                      app_dir / PROBE_TARGET):                              # 源码模式
        if candidate.is_file():
            loose_source = candidate
            break
    if loose_source is None:
        raise SystemExit(f"❌ 在 {app_dir} 下找不到松散的应用代码（_internal/app/{PROBE_TARGET}）"
                         f" —— 这不是松散代码打包，Python 热修在此安装上不可能生效")
    staged = []
    with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        entries = []

        def add(name: str, data: bytes):
            archive.writestr(name, data)
            entries.append({"path": name, "kind": name.split("/")[0],
                            "sha256": hashlib.sha256(data).hexdigest(), "size": len(data)})
            staged.append(name)

        add("www/hotfix_probe.js", PROBE_JS.encode("utf-8"))
        add("app/" + PROBE_TARGET, loose_source.read_bytes() + PROBE_PY.encode("utf-8"))
        archive.writestr("manifest.json", json.dumps(
            {"version": version, "createdAt": time.strftime("%Y-%m-%dT%H:%M:%S"),
             "requires": "6.0.0", "notes": notes, "files": entries},
            indent=2, ensure_ascii=False))
    return staged


def load_launcher(repo_root: Path):
    import importlib.util
    path = repo_root / "windows" / "launcher.py"
    spec = importlib.util.spec_from_file_location("mrrc_launcher_verify", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    parser = argparse.ArgumentParser(description="验收 MRRC 热修通道")
    parser.add_argument("--app", required=True, help="打包后的应用目录（含 MRRC-Server.exe）")
    parser.add_argument("--config", help="要使用的 MRRC.conf（默认自动找 %LOCALAPPDATA%\\MRRC\\MRRC.conf）")
    parser.add_argument("--repo", default=os.getcwd(), help="仓库根（默认当前目录）")
    parser.add_argument("--version", default="6.0.0-verify", help="探针包版本号")
    parser.add_argument("--keep-server", action="store_true", help="验收后不关服务（调试用）")
    args = parser.parse_args()

    app_dir = Path(args.app).resolve()
    repo_root = Path(args.repo).resolve()
    exe = app_dir / "MRRC-Server.exe"
    if not exe.is_file():
        exe = app_dir / "MRRC-Server"          # 非 Windows 打包产物
    source_mode = False
    if not exe.is_file() and (app_dir / "MRRC").is_file():
        source_mode = True                     # 源码模式：用当前解释器跑 MRRC
        exe = app_dir / "MRRC"
    if not exe.is_file():
        return fail(f"找不到服务端可执行文件：{app_dir}")

    cfg = Path(args.config) if args.config else None
    if cfg is None:
        local = os.environ.get("LOCALAPPDATA")
        cfg = Path(local) / "MRRC" / "MRRC.conf" if local else None
        if cfg and not cfg.is_file():
            cfg = None
    if cfg is None and (app_dir / "MRRC.conf").is_file():
        cfg = app_dir / "MRRC.conf"
    if cfg is None or not Path(cfg).is_file():
        return fail("找不到 MRRC.conf（用 --config 指定）")
    cfg = Path(cfg).resolve()

    version_file = app_dir / "version.txt"
    installed = version_file.read_text(encoding="utf-8").strip() if version_file.is_file() else "0.0.0"
    log(f"安装目录 : {app_dir}")
    log(f"配置文件 : {cfg}")
    log(f"版本标记 : {installed}")

    launcher = load_launcher(repo_root)
    # 覆盖层目录必须用 MRRC 的规则（配置文件同级的 patch/），而不是启动器的默认目录：
    # 两者只在 Windows 标准布局下重合；显式传 MRRC_PATCH_DIR 让双方确定一致
    # （Windows 启动器也是这么传给服务端的）。
    patch_root = cfg.parent / "patch"
    log(f"覆盖层   : {patch_root}")

    with tempfile.TemporaryDirectory(prefix="mrrc-verify-") as tmp:
        pack = Path(tmp) / f"hotfix-{args.version}.zip"
        staged = build_probe_pack(app_dir, pack, "热修通道验收探针", args.version)
        log(f"合成探针包: {pack}（{pack.stat().st_size} bytes；{len(staged)} 个文件）")

        written = launcher.apply_hotfix_pack(pack, patch_root)
        log(f"已应用    : {', '.join(written)}")

        cfg_parser = configparser.ConfigParser()
        cfg_parser.read(cfg, encoding="utf-8")
        port = cfg_parser.get("SERVER", "port", fallback="8877")
        secret = cfg_parser.get("SERVER", "cookie_secret", fallback="")
        url = f"https://localhost:{port}"

        command = ([sys.executable, str(exe), str(cfg)] if source_mode
                   else [str(exe), str(cfg)])
        log(f"启动      : {' '.join(command)}")
        child_env = os.environ.copy()
        child_env["MRRC_PATCH_DIR"] = str(patch_root)
        server_log = Path(tmp) / "server.log"
        log(f"服务端输出: {server_log}")
        # 输出写文件而不是 pipe：pipe 上的 read() 会阻塞；stderr 不缓冲，探针打点能立刻落盘
        with open(server_log, "wb") as sink:
            proc = subprocess.Popen(command, cwd=str(app_dir), env=child_env,
                                    stdout=sink, stderr=subprocess.STDOUT)
        try:
            if not wait_for_port(port, proc, timeout=45):
                return fail(f"服务未在 45s 内监听 {port}\n--- 输出 ---\n"
                            + server_log.read_text(encoding="utf-8", errors="replace")[-2000:])

            ok_www = check_www(url, secret)
            ok_status = check_patch_status(url, secret)
            ok_py = PROBE_MARKER in server_log.read_text(encoding="utf-8", errors="replace")
            log("")
            if not (ok_www and ok_py):
                tail = server_log.read_text(encoding="utf-8", errors="replace").splitlines()[-25:]
                log("--- 服务端日志尾部 ---")
                for line in tail:
                    log("   " + line[:160])
            log(f"① 前端热修（www/）      : {'✅ 生效' if ok_www else '❌ 未生效'}")
            log(f"② Python 热修（app/*.py）: {'✅ 生效' if ok_py else '❌ 未生效'}"
                f"（探针 {PROBE_TARGET} 的导入打点）")
            log(f"③ 覆盖层对服务端可见    : {'✅' if ok_status else '❌'}（getPatchStatus）")
            if ok_www and ok_py:
                log("\n✅ 热修通道验收通过：覆盖层可在不改安装目录的情况下生效")
                return 0
            return fail("热修通道验收未通过（见上）")
        finally:
            if not args.keep_server:
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()
            cleanup_overlay(patch_root, written)
            log("已清理本次写入的覆盖层文件（回退到内置版本）")


def fail(message: str) -> int:
    log(f"\n❌ {message}")
    return 1


def wait_for_port(port: str, proc: subprocess.Popen, timeout: float = 45) -> bool:
    import socket
    deadline = time.time() + timeout
    while time.time() < deadline:
        if proc.poll() is not None:
            return False
        try:
            with socket.create_connection(("127.0.0.1", int(port)), timeout=2):
                return True
        except OSError:
            time.sleep(1)
    return False


def _cookie(secret: str) -> str:
    from tornado.web import create_signed_value
    return create_signed_value(secret, "user", "hotfix-verify").decode()


def check_www(url: str, secret: str) -> bool:
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    request = urllib.request.Request(f"{url}/hotfix_probe.js",
                                     headers={"Cookie": f"user={_cookie(secret)}"})
    try:
        body = urllib.request.urlopen(request, context=context, timeout=15).read().decode()
    except Exception as exc:
        log(f"取 /hotfix_probe.js 失败: {exc}")
        return False
    return "MRRC-HOTFIX-PROBE-OK" in body


def check_patch_status(url: str, secret: str) -> bool:
    import websocket            # websocket-client（运行依赖里已有）
    ws_url = url.replace("https://", "wss://") + "/WSCTRX"
    try:
        ws = websocket.create_connection(ws_url,
                                         sslopt={"cert_reqs": ssl.CERT_NONE, "check_hostname": False},
                                         timeout=20,
                                         header=[f"Cookie: user={_cookie(secret)}", f"Origin: {url}"],
                                         origin=url)
    except Exception as exc:
        log(f"WebSocket 连接失败: {exc}")
        return False
    try:
        ws.settimeout(0.5)
        time.sleep(1)
        drain(ws)
        ws.send("getPatchStatus")
        deadline = time.time() + 6
        while time.time() < deadline:
            try:
                message = ws.recv()
            except Exception:
                continue
            if "patchStatus" in message:
                status = json.loads(message.split("patchStatus:", 1)[1])
                log(f"getPatchStatus: {json.dumps({k: status.get(k) for k in ('active', 'fileCount', 'patchDir')}, ensure_ascii=False)}")
                return bool(status.get('active')) and int(status.get('fileCount') or 0) >= 2
        log("未收到 patchStatus 响应")
        return False
    finally:
        ws.close()


def drain(ws) -> None:
    end = time.time() + 1.0
    while time.time() < end:
        try:
            ws.recv()
        except Exception:
            pass


def cleanup_overlay(patch_root: Path, written: list[str]) -> None:
    for rel in written:
        target = patch_root / rel
        try:
            if target.is_file():
                target.unlink()
        except OSError:
            pass
    for rel in ("www/hotfix_probe.js",):
        try:
            (patch_root / rel).unlink(missing_ok=True)
        except OSError:
            pass


if __name__ == "__main__":
    sys.exit(main())
