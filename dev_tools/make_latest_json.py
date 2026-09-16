#!/usr/bin/env python3
"""生成升级清单 `latest.json`（供启动器判断是否升级）。

用法（发版脚本会调用）：
    python3 dev_tools/make_latest_json.py --version 6.0.10 \
        --installer dist/windows/MRRC-Setup.exe [--previous 6.0.7] \
        [--notes "面向用户的一句话"] [--out website/downloads/latest.json]

要点：
  * installer.sha256 必须与**带版本名**的那个产物一致（`MRRC-Setup-<ver>.exe`），
    否则启动器会因校验失败拒绝安装；
  * previous 段用于"回退到上一版"：指向站点上保留的旧安装包；
  * hotfix 段直接复用现有 patch.json（热修通道独立发布，不改安装版本）；
  * mandatory=False 默认；做成紧急更新时加 --mandatory。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time

DOWNLOAD_BASE = "https://www.vlsc.net/mrrc/downloads"


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(262144), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_manifest(version, installer_path, downloads_dir, previous=None,
                   notes="", mandatory=False, min_supported="6.0.3", base=DOWNLOAD_BASE):
    exe_name = f"MRRC-Setup-{version}.exe"
    installer = {"url": f"{base}/{exe_name}", "sha256": sha256_file(installer_path),
                 "size": os.path.getsize(installer_path)}
    manifest = {"latest": str(version), "installer": installer,
                "minSupported": str(min_supported), "mandatory": bool(mandatory),
                "releasedAt": time.strftime("%Y-%m-%dT%H:%M:%S"), "notes": notes}
    patch_path = os.path.join(downloads_dir, "patch.json")
    if os.path.isfile(patch_path):
        try:
            patch = json.load(open(patch_path, encoding="utf-8"))
            if patch.get("url") and patch.get("sha256"):
                manifest["hotfix"] = {"url": patch["url"], "sha256": patch["sha256"],
                                      "requires": patch.get("requires", min_supported),
                                      "notes": patch.get("notes", "")}
        except Exception as exc:
            print(f"⚠ 读取 patch.json 失败（忽略热修段）：{exc}", file=sys.stderr)
    if previous:
        prev_exe = os.path.join(downloads_dir, f"MRRC-Setup-{previous}.exe")
        if os.path.isfile(prev_exe):
            manifest["previous"] = {"version": str(previous), "url": f"{base}/{os.path.basename(prev_exe)}",
                                    "sha256": sha256_file(prev_exe)}
        else:
            print(f"⚠ 未找到上一版安装包 {prev_exe}，latest.json 里不会有回退入口", file=sys.stderr)
    return manifest


def main():
    parser = argparse.ArgumentParser(description="生成 MRRC 升级清单 latest.json")
    parser.add_argument("--version", required=True)
    parser.add_argument("--installer", required=True, help="待发布的安装包（会被复制成带版本名的一份）")
    parser.add_argument("--previous", default="", help="上一版版本号（站点上已有 MRRC-Setup-<prev>.exe）")
    parser.add_argument("--notes", default="")
    parser.add_argument("--mandatory", action="store_true")
    parser.add_argument("--min-supported", default="6.0.3")
    parser.add_argument("--downloads-dir", default=os.path.join("website", "downloads"))
    parser.add_argument("--out", default=os.path.join("website", "downloads", "latest.json"))
    args = parser.parse_args()

    versioned = os.path.join(args.downloads_dir, f"MRRC-Setup-{args.version}.exe")
    if os.path.abspath(args.installer) != os.path.abspath(versioned):
        with open(args.installer, "rb") as src, open(versioned, "wb") as dst:
            dst.write(src.read())
        print(f"已复制产物 → {versioned}")
    manifest = build_manifest(args.version, versioned, args.downloads_dir,
                              previous=args.previous or None, notes=args.notes,
                              mandatory=args.mandatory, min_supported=args.min_supported)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=2)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
