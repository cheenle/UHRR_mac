#!/usr/bin/env python3
"""生成热修补丁包（hotfix pack）——不重新打包就能修已发布版本的 bug。

产物（放进 `website/downloads/` 后跑 `./deploy_website.sh` 即生效）：

    hotfix-<version>.zip    覆盖层同构布局：app/、www/、vendor/
                            （内含 manifest.json：每个文件的 SHA256）
    patch.json              更新通道清单，启动器读它（latest/url/sha256/requires/notes）

用法示例：

    # 改完 www/controls.js 和 wdsp_wrapper.py 后
    python3 packaging/hotfix/make_hotfix.py --version 6.0.4 \
        --notes "修复 S 表在 iOS 上的闪烁" \
        www/controls.js wdsp_wrapper.py

    # 也可以直接给 git 区间，自动挑出可热修的文件
    python3 packaging/hotfix/make_hotfix.py --version 6.0.4 --range v6.0.2..HEAD

能力边界（工具会强制检查，见 LOOSE_APP_MODULES）：

  * `www/**`             → 覆盖 `_internal/www/**`，刷新浏览器即生效
  * 松散应用模块 .py      → 覆盖 `_internal/app/*.py`，重启服务生效（需 6.0.3+ 安装包）
  * `MRRC` 主程序         → 同上（`app/MRRC`）
  * `*.dll`（vendor 布局）→ 覆盖 `vendor/...`，重启生效
  * 其它文件（新增依赖、C 扩展、启动器）→ 拒绝：必须重新打包
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC = REPO_ROOT / "packaging" / "pyinstaller" / "mrrc_server.spec"
ISS = REPO_ROOT / "packaging" / "windows" / "MRRC.iss"
DEFAULT_OUT = REPO_ROOT / "dist" / "hotfix"
DOWNLOAD_BASE = "https://www.vlsc.net/mrrc/downloads"


def loose_app_modules() -> list[str]:
    """从 server spec 里读出"已改为松散文件"的应用模块（保证工具与实际打包一致）。"""
    text = SPEC.read_text(encoding="utf-8")
    block = re.search(r"_APP_MODULES\s*=\s*\[(.*?)\]", text, re.S)
    if not block:
        raise SystemExit(f"❌ 无法从 {SPEC} 解析 _APP_MODULES")
    return re.findall(r'"([^"]+)"', block.group(1))


def current_version() -> str:
    match = re.search(r'MyAppVersion\s+"([^"]+)"', ISS.read_text(encoding="utf-8"))
    return match.group(1) if match else "0.0.0"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(262144), b""):
            digest.update(chunk)
    return digest.hexdigest()


def classify(relative: str, loose: list[str]) -> tuple[str, str] | None:
    """把仓库里的路径映射成覆盖层里的路径；不可热修则返回 None。"""
    rel = relative.replace("\\", "/").lstrip("./")
    if rel.startswith("www/"):
        return rel, "www"
    if rel == "MRRC":
        return "app/MRRC", "app"
    if rel in {f"{m}.py" for m in loose}:
        return f"app/{rel}", "app"
    if rel.startswith("vendor/") and rel.lower().endswith(".dll"):
        return rel, "vendor"
    return None


def changed_files_from_git(rev_range: str) -> list[str]:
    out = subprocess.run(["git", "diff", "--name-only", rev_range], cwd=REPO_ROOT,
                         capture_output=True, text=True, check=True).stdout
    return [line.strip() for line in out.splitlines() if line.strip()]


def build_pack(version: str, files: list[str], notes: str, requires: str,
               out_dir: Path, base_url: str = DOWNLOAD_BASE) -> dict:
    loose = loose_app_modules()
    entries, rejected = [], []
    for rel in sorted(set(files)):
        source = REPO_ROOT / rel
        if not source.is_file():
            rejected.append((rel, "文件不存在"))
            continue
        mapped = classify(rel, loose)
        if mapped is None:
            rejected.append((rel, "不属于可热修范围（新增依赖/C 扩展/启动器需重新打包）"))
            continue
        target, kind = mapped
        entries.append({"repoPath": rel, "path": target, "kind": kind,
                        "sha256": _sha256(source), "size": source.stat().st_size,
                        "source": source})

    if rejected:
        print("以下文件不能热修：")
        for rel, why in rejected:
            print(f"  ✗ {rel} —— {why}")
    if not entries:
        raise SystemExit("❌ 没有可热修的文件，未生成补丁包")

    out_dir.mkdir(parents=True, exist_ok=True)
    pack = out_dir / f"hotfix-{version}.zip"
    manifest = {
        "version": version,
        "createdAt": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "requires": requires,
        "notes": notes,
        "files": [{k: e[k] for k in ("path", "kind", "sha256", "size")} for e in entries],
    }
    with zipfile.ZipFile(pack, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        archive.writestr("manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False))
        for entry in entries:
            archive.write(entry["source"], entry["path"])

    patch_json = {
        "latest": version,
        "url": f"{base_url}/hotfix-{version}.zip",
        "sha256": _sha256(pack),
        "size": pack.stat().st_size,
        "requires": requires,
        "notes": notes,
        "files": [e["path"] for e in entries],
    }
    (out_dir / "patch.json").write_text(json.dumps(patch_json, indent=2, ensure_ascii=False),
                                        encoding="utf-8")

    total = pack.stat().st_size
    print(f"\n✅ {pack}  ({total/1024:.1f} KB)")
    print(f"✅ {out_dir / 'patch.json'}")
    print(f"   版本 {version}（仓库当前 {current_version()}），要求安装 ≥ {requires}")
    for entry in entries:
        print(f"   + {entry['path']}  ({entry['size']} bytes, {entry['sha256'][:12]}…)")
    print("\n发布：cp dist/hotfix/* website/downloads/ && ./deploy_website.sh")
    print("（patch.json 会被启动器读取，自动应用到 %LOCALAPPDATA%\\MRRC\\patch\\)")
    return patch_json


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


def main() -> int:
    parser = argparse.ArgumentParser(description="生成 MRRC 热修补丁包")
    parser.add_argument("files", nargs="*", help="改动的仓库文件（相对仓库根）")
    parser.add_argument("--version", required=True, help="热修版本号，例如 6.0.4")
    parser.add_argument("--requires", default="6.0.3", help="要求的最低安装版本（默认 6.0.3）")
    parser.add_argument("--notes", default="", help="说明文字（会显示在 patch.json 与启动器日志里）")
    parser.add_argument("--range", dest="rev_range", help="用 git 区间自动列出改动（如 v6.0.2..HEAD）")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="输出目录（默认 dist/hotfix）")
    args = parser.parse_args()

    files = list(args.files)
    if args.rev_range:
        files += changed_files_from_git(args.rev_range)
    if not files:
        parser.error("没有指定文件（也可用 --range）")

    build_pack(args.version, files, args.notes, args.requires, Path(args.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
