#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MRRC 配置文件编码健壮性测试（Windows 中文环境回归）。

背景（根因）：
- 启动读取固定 UTF-8：`config.read(path, encoding='utf-8')`（V6.0.0 修复）
- 但写侧仍是 locale 编码：`open(tmp, 'w')` 在中文 Windows 上是 GBK（cp936）
- 配置值含中文时（%LOCALAPPDATA% 路径带中文用户名、手工编辑等），
  写出的 GBK 文件在下次启动被 UTF-8 读取 → UnicodeDecodeError，服务器起不来。

本测试锁定该失败模式，并验证 config_io 的容错读取 + UTF-8 迁移。
用法: python3 dev_tools/test_config_encoding.py
"""
import configparser
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

GBC_CONFIG = (
    "[SERVER]\n"
    "port = 8877\n"
    "certfile = C:/Users/张伟/AppData/Local/MRRC/certs/server.crt\n"
    "keyfile = C:/Users/张伟/AppData/Local/MRRC/certs/server.key\n"
    "log_file = C:/Users/张伟/AppData/Local/MRRC/MRRC.log\n"
    "\n"
    "[HAMLIB]\n"
    "rig_pathname = COM3\n"
)
UTF8_CONFIG = GBC_CONFIG  # same content, encoded differently

failures = []


def check(name, cond, detail=""):
    print(f"{'PASS' if cond else 'FAIL'}  {name}{(' — ' + detail) if detail and not cond else ''}")
    if not cond:
        failures.append(name)


def write(path, text, encoding):
    with open(path, "w", encoding=encoding) as f:
        f.write(text)


def main():
    import config_io

    tmpdir = tempfile.mkdtemp(prefix="mrrc_cfg_test_")

    # ------------------------------------------------------------------
    # 1. 复现线上故障：GBK 写的配置 + UTF-8 读 = UnicodeDecodeError
    # ------------------------------------------------------------------
    gbk_path = os.path.join(tmpdir, "gbk.conf")
    write(gbk_path, GBC_CONFIG, "gbk")
    parser = configparser.ConfigParser()
    reproduced = False
    try:
        parser.read(gbk_path, encoding="utf-8")
    except UnicodeDecodeError:
        reproduced = True
    check("1. 复现: GBK 配置被 UTF-8 读取抛 UnicodeDecodeError", reproduced)

    # ------------------------------------------------------------------
    # 2. config_io.read_config: 容错读取 GBK，值正确，并迁移为 UTF-8
    # ------------------------------------------------------------------
    parser = configparser.ConfigParser()
    enc = config_io.read_config(parser, gbk_path)
    check("2a. read_config 不抛异常", True)
    check("2b. 中文值解码正确", parser.get("SERVER", "log_file").endswith("张伟/AppData/Local/MRRC/MRRC.log"),
          parser.get("SERVER", "log_file", fallback="<missing>"))
    check("2c. 普通值正确", parser.get("HAMLIB", "rig_pathname") == "COM3")
    check("2d. 非 UTF-8 被迁移为 UTF-8", enc not in ("utf-8", "utf-8-sig"), f"enc={enc}")
    with open(gbk_path, "r", encoding="utf-8") as f:
        migrated = f.read()
    check("2e. 迁移后文件内容是 UTF-8 且中文完好", "张伟" in migrated)
    check("2f. 迁移前原文件已备份", os.path.exists(gbk_path + ".bak"))
    with open(gbk_path + ".bak", "rb") as f:
        backup = f.read()
    check("2g. 备份保留原始 GBK 字节", b"\xd5\xc5\xce\xb0" in backup)

    # ------------------------------------------------------------------
    # 3. 正常 UTF-8 配置：值正确且文件不被改写
    # ------------------------------------------------------------------
    utf8_path = os.path.join(tmpdir, "utf8.conf")
    write(utf8_path, UTF8_CONFIG, "utf-8")
    before = os.stat(utf8_path).st_mtime_ns
    parser = configparser.ConfigParser()
    enc = config_io.read_config(parser, utf8_path)
    check("3a. UTF-8 配置读取正常", parser.get("HAMLIB", "rig_pathname") == "COM3")
    check("3b. UTF-8 文件不迁移", enc in ("utf-8", "utf-8-sig"))
    check("3c. UTF-8 文件未被改写", os.stat(utf8_path).st_mtime_ns == before)
    check("3d. 不生成多余备份", not os.path.exists(utf8_path + ".bak"))

    # ------------------------------------------------------------------
    # 4. UTF-8 BOM（Notepad 另存 UTF-8 带 BOM）也能读
    # ------------------------------------------------------------------
    bom_path = os.path.join(tmpdir, "bom.conf")
    write(bom_path, UTF8_CONFIG, "utf-8-sig")
    parser = configparser.ConfigParser()
    config_io.read_config(parser, bom_path)
    check("4. UTF-8 BOM 配置可读", parser.get("SERVER", "port") == "8877")

    # ------------------------------------------------------------------
    # 5. 文件不存在：与 configparser 行为一致，不抛异常
    # ------------------------------------------------------------------
    parser = configparser.ConfigParser()
    try:
        enc = config_io.read_config(parser, os.path.join(tmpdir, "nope.conf"))
        check("5. 缺失文件不抛异常", enc is None and not parser.sections())
    except Exception as e:
        check("5. 缺失文件不抛异常", False, repr(e))

    # ------------------------------------------------------------------
    # 6. write_config: 永远 UTF-8，且能回读
    # ------------------------------------------------------------------
    out_path = os.path.join(tmpdir, "written.conf")
    parser = configparser.ConfigParser()
    parser["SERVER"] = {"log_file": "C:/Users/张伟/MRRC.log"}
    config_io.write_config(parser, out_path)
    with open(out_path, "rb") as f:
        raw = f.read()
    check("6a. 写入为 UTF-8 字节", "张伟".encode("utf-8") in raw and "张伟".encode("gbk") not in raw)
    parser2 = configparser.ConfigParser()
    config_io.read_config(parser2, out_path)
    check("6b. 回读值正确", parser2.get("SERVER", "log_file") == "C:/Users/张伟/MRRC.log")
    check("6c. 无残留 .tmp", not os.path.exists(out_path + ".tmp"))

    # ------------------------------------------------------------------
    # 7. 通用文本读写（memory_channels.json / MRRC_users.db 同类问题）
    # ------------------------------------------------------------------
    text = '{"BG1SB": ["7.050", "14.270"]}'  # ASCII 内容 + 中文键场景
    gbk_text = os.path.join(tmpdir, "gbk_users.db")
    write(gbk_text, "# 注释\nBG1SB 密码\n", "gbk")
    got = config_io.read_text(gbk_text)
    check("7a. read_text 容错读取 GBK", got is not None and "密码" in got, repr(got))
    utf8_out = os.path.join(tmpdir, "utf8_users.db")
    config_io.write_text(utf8_out, "# 注释\nBG1SB 密码\n")
    with open(utf8_out, "rb") as f:
        raw = f.read()
    check("7b. write_text 固定 UTF-8", "密码".encode("utf-8") in raw)
    check("7c. read_text 读缺失文件返回 None", config_io.read_text(os.path.join(tmpdir, "nope.txt")) is None)

    # ------------------------------------------------------------------
    # 8. Windows 启动器（windows/launcher.py）自身也不得在 GBK 配置上崩溃
    # ------------------------------------------------------------------
    launcher_cfg = os.path.join(tmpdir, "launcher_gbk.conf")
    write(launcher_cfg, "[SERVER]\nport = 8877\nlog_file = C:/Users/张伟/MRRC.log\n", "gbk")
    import importlib.util
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    spec = importlib.util.spec_from_file_location("mrrc_launcher_under_test",
                                                  os.path.join(repo_root, "windows", "launcher.py"))
    launcher = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(launcher)
    try:
        launcher.apply_simple_defaults(launcher_cfg)
        port, host = launcher._read_config_port_host(launcher_cfg)
        check("8a. launcher 读取 GBK 配置不崩溃", True)
        check("8b. launcher 解析出正确端口", port == "8877", port)
        check("8c. launcher 处理后文件为 UTF-8", "张伟".encode("utf-8") in open(launcher_cfg, "rb").read())
    except UnicodeDecodeError as e:
        check("8a. launcher 读取 GBK 配置不崩溃", False, repr(e))

    print()
    if failures:
        print(f"FAILED ({len(failures)}): {failures}")
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    try:
        import config_io  # noqa: F401
    except ImportError:
        print("FAIL  config_io 模块尚不存在（TDD 第一步：预期失败）")
        sys.exit(1)
    sys.exit(main())
