#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""跨平台文本 / 配置文件编码工具（Windows 中文环境回归修复）。

根因背景
--------
中文 Windows 上 Python 默认文件编码是 GBK(cp936)。MRRC 的历史代码里，
配置的**写侧**用 `open(path, 'w')`（locale = GBK），**读侧**却固定
`encoding='utf-8'`（V6.0.0 的修复）。当配置值含非 ASCII 时——例如
%LOCALAPPDATA% 路径带中文用户名（`C:/Users/张伟/...`）——写出的 GBK 文件
在下次启动被 UTF-8 读取，抛 UnicodeDecodeError，服务器直接起不来。

本模块统一策略，消除这类"读写编码不一致"故障：
- 读：UTF-8 优先，回退 UTF-16(BOM) / locale / GB18030 / Big5，最后 latin-1 兜底；
- 配置读到非 UTF-8 时自动迁移为 UTF-8（原文件保留为 .bak）；
- 写：固定 UTF-8 + 原子替换（临时文件 + os.replace）。

仅依赖标准库，可被 frozen（PyInstaller）的服务器与启动器共用。
"""
from __future__ import annotations

import io
import locale
import os

_UTF8_NAMES = {"utf8", "utf8sig"}  # 与 _normalize() 的输出保持一致


def _normalize(name: str) -> str:
    return name.lower().replace("-", "").replace("_", "")


def _candidate_encodings():
    """按优先级返回候选编码；保证最后有 latin-1 兜底（不会抛错）。"""
    encodings = ["utf-8-sig", "utf-8"]
    seen = {_normalize(e) for e in encodings}
    try:
        preferred = locale.getpreferredencoding(False)
    except Exception:
        preferred = None
    for enc in (preferred, "gb18030", "gbk", "big5"):
        if enc and _normalize(enc) not in seen:
            encodings.append(enc)
            seen.add(_normalize(enc))
    encodings.append("latin-1")
    return encodings


def decode_bytes(raw: bytes) -> tuple[str, str]:
    """解码字节串，返回 (text, encoding)。UTF-16 BOM 优先，最后 latin-1 兜底。"""
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        try:
            return raw.decode("utf-16"), "utf-16"
        except UnicodeDecodeError:
            pass
    for enc in _candidate_encodings():
        try:
            return raw.decode(enc), enc
        except (UnicodeDecodeError, LookupError):
            continue
    # latin-1 理论上不会失败，这里是最后保险
    return raw.decode("latin-1", errors="replace"), "latin-1"


def read_text(path: str) -> str | None:
    """容错读取文本文件；文件不存在或不可读时返回 None。"""
    try:
        with open(path, "rb") as f:
            raw = f.read()
    except OSError:
        return None
    text, _ = decode_bytes(raw)
    return text


def write_text(path: str, text: str) -> None:
    """固定 UTF-8 原子写入（临时文件 + os.replace）。"""
    tmp = str(path) + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _migrate_to_utf8(path: str, raw: bytes, text: str) -> bool:
    """把非 UTF-8 的配置文件迁移为 UTF-8，原文件备份为 <path>.bak。"""
    try:
        backup = str(path) + ".bak"
        if not os.path.exists(backup):
            with open(backup, "wb") as f:
                f.write(raw)
        write_text(path, text)
        return True
    except OSError:
        return False


def should_migrate(encoding: str | None) -> bool:
    """该来源编码的配置是否会被自动迁移为 UTF-8。"""
    return bool(encoding) and _normalize(encoding) not in _UTF8_NAMES and encoding != "latin-1"


def read_config(parser, path: str):
    """用容错编码读取 INI 配置到 parser，必要时迁移为 UTF-8。

    返回实际使用的编码名；文件不存在返回 None（与 configparser.read 一致）。
    读到非 UTF-8（且不是 latin-1 兜底）时，自动改写为 UTF-8 并保留 .bak，
    避免"写 GBK / 读 UTF-8"的乱码与崩溃反复出现。
    """
    try:
        with open(path, "rb") as f:
            raw = f.read()
    except FileNotFoundError:
        return None

    text, encoding = decode_bytes(raw)
    parser.read_string(text)

    if should_migrate(encoding):
        _migrate_to_utf8(path, raw, text)
    return encoding


def write_config(parser, path: str) -> None:
    """固定 UTF-8 原子写入 INI 配置。"""
    buf = io.StringIO()
    parser.write(buf)
    write_text(path, buf.getvalue())


if __name__ == "__main__":  # 简易自检
    import tempfile

    d = tempfile.mkdtemp(prefix="config_io_selftest_")
    p = os.path.join(d, "x.conf")
    with open(p, "w", encoding="gbk") as f:
        f.write("[A]\nk = 张伟\n")
    import configparser

    cp = configparser.ConfigParser()
    enc = read_config(cp, p)
    assert cp.get("A", "k") == "张伟", cp.get("A", "k")
    assert enc and _normalize(enc) not in _UTF8_NAMES, enc
    assert read_text(p) == "[A]\nk = 张伟\n"
    assert os.path.exists(p + ".bak")
    print(f"config_io self-test OK (source encoding: {enc})")
