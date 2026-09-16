"""支持诊断包（support bundle）：收集、脱敏、打包、体检摘要。

用途：用户在「🐞 遇到问题」页面点一下，就得到一个**脱敏且自证**的诊断包，维护者不必来回问
"你的日志呢"。详见 `docs/superpowers/specs/2026-09-16-support-log-upload-design.md`。

设计约束（安全优先，改动前先读）：

1. **白名单**：配置只导出 `CONFIG_WHITELIST` 里列出的键，白名单外的节整节丢弃；
2. **密钥替换**：所有被采集文本再过一遍 `SECRET_KEY_RE`，命中记数写进 manifest；
3. **永不打包**：`MRRC_users.db`、证书/私钥（见 `FORBIDDEN_SUBSTRINGS`）；
4. **只读尾部**：日志按行边界截断到 ≤2 MB，避免包过大；
5. 纯标准库、不 import tornado → 可单测、可作为松散模块热修。
"""

import os
import re

# --------------------------------------------------------------------------- #
# 脱敏
# --------------------------------------------------------------------------- #
SECRET_KEY_RE = re.compile(
    r"(?i)\b(cookie[_-]?secret|pass(?:word|wd)?|secret|token|api[_-]?key|credential)\b"
    r"(\s*[=:]\s*)(\S+)")

# 允许出现在诊断包中的配置键（其余一律不进包）。新增配置项时要同步这里。
CONFIG_WHITELIST = {
    "SERVER": {"port", "host"},
    "HAMLIB": {"rig_model", "rig_pathname", "rig_rate", "stop_bits", "data_bits",
               "serial_parity", "serial_handshake", "trxautopower", "retry"},
    "AUDIO": {"inputdevice", "outputdevice", "hostapi_preference", "diag"},
    "WDSP": {"sample_rate", "buffer_size", "nr2_level", "nr2_enabled", "nb_enabled",
             "anf_enabled", "agc_mode", "bandpass_low", "bandpass_high", "nr2_max_atten_db",
             "nr2_dry", "agc_top_db", "panel_gain", "nr2_ae_psi", "nr2_ae_zeta_thresh"},
    "CTRL": {"interval_smeter_update"},
    "ATR1000": {"enabled"},
    "INSTANCE_SETTINGS": {"instance_rigctl_model", "instance_rigctl_port",
                          "instance_unix_socket", "atr1000_proxy_transport",
                          "atr1000_proxy_host", "atr1000_proxy_port"},
    "RNNOISE": {"suppress_level"},
    "UPDATE": {"enabled", "autoDownload", "channel"},
    "HOTFIX": {"enabled"},
}

# 文件名/路径里出现这些片段就不进包（用户库、证书、私钥）
FORBIDDEN_SUBSTRINGS = ("mrrc_users.db", "cert", ".pem", ".key", ".crt", ".p12")


def redact_text(text):
    """把密钥类键值替换为 <redacted>；返回 (新文本, 命中数)。"""
    return SECRET_KEY_RE.subn(lambda m: f"{m.group(1)}{m.group(2)}<redacted>", text or "")


def redact_config_text(text):
    """按白名单裁剪配置文本，并对保留下来的行再做一次密钥替换。"""
    out, section, allow_section = [], None, True
    for line in (text or "").splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped[1:-1].strip()
            allow_section = section in CONFIG_WHITELIST
            if allow_section:
                out.append(line)
            else:
                out.append(f"; <已省略白名单外的节: {section}>")
            continue
        if section is None or not allow_section or "=" not in line:
            if allow_section:
                out.append(line)
            continue
        key = line.split("=", 1)[0].strip()
        if key not in CONFIG_WHITELIST.get(section, set()):
            continue                                  # 白名单外的键：整行丢弃
        cleaned, _ = redact_text(line)
        out.append(cleaned)
    return "\n".join(out) + "\n"


def count_omitted_config_keys(text):
    """统计因白名单被丢弃的配置键行数（这些也属于"已脱敏"）。"""
    omitted, section, allowed = 0, None, True
    for line in (text or "").splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped[1:-1].strip()
            allowed = section in CONFIG_WHITELIST
            continue
        if section is None or not allowed or "=" not in line:
            continue
        if line.split("=", 1)[0].strip() not in CONFIG_WHITELIST.get(section, set()):
            omitted += 1
    return omitted


def is_collectable(relative_path):
    """该路径是否允许进诊断包（用户库/证书/私钥一律拒绝）。"""
    lowered = str(relative_path).lower()
    return not any(token in lowered for token in FORBIDDEN_SUBSTRINGS)


# --------------------------------------------------------------------------- #
# 日志尾部读取
# --------------------------------------------------------------------------- #
DEFAULT_TAIL_BYTES = 2 * 1024 * 1024


def tail_lines(path, max_bytes=DEFAULT_TAIL_BYTES):
    """读取文件尾部 ≤max_bytes，并对齐到完整行；文件不存在/无权限返回 ''。"""
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as fh:
            if size > max_bytes:
                fh.seek(size - max_bytes)
                fh.readline()                         # 丢掉可能被截断的半行
            data = fh.read()
    except OSError:
        return ""
    return data.decode("utf-8", "replace")


# --------------------------------------------------------------------------- #
# 自动体检摘要（维护者第一眼看的文件）
# --------------------------------------------------------------------------- #
SUMMARY_PATTERNS = [
    ("Traceback", re.compile(r"Traceback \(most recent call last\)")),
    ("ERROR", re.compile(r"\bERROR\b")),
    ("异常标记 ❌", re.compile("❌")),
    ("告警 ⚠️", re.compile("⚠️")),
    ("IOLoop 卡顿", re.compile(r"IOLoop stall")),
    ("ATR-1000", re.compile(r"ATR-1000")),
    ("PTT", re.compile(r"\bPTT\b")),
    ("热修覆盖层", re.compile("补丁覆盖层")),
]
AUDIO_HEALTH_RE = re.compile(r"🎧 音频健康.*?([0-9]+\.[0-9])%")


def summarize_log(text):
    """把日志尾部归类计数（每类最近 3 条）+ 结论区（音频/热修/WDSP）。"""
    lines = (text or "").splitlines()
    parts = []
    for label, pattern in SUMMARY_PATTERNS:
        hits = [ln.strip()[:300] for ln in lines if pattern.search(ln)]
        if not hits:
            continue
        parts.append(f"== {label}：{len(hits)} 条 ==")
        parts.extend(f"   - {h}" for h in hits[-3:])
        parts.append("")

    conclusions = []
    percents = [float(p) for p in AUDIO_HEALTH_RE.findall(text or "")]
    if percents:
        worst = min(percents)
        verdict = ("低于 99%：采集流水线跟不上（查 CPU/WDSP 设置/主机 API）"
                   if worst < 99 else "正常")
        conclusions.append(f"音频采集：最低健康度 {worst:.1f}%（{verdict}）")
    else:
        conclusions.append("音频采集：日志里没有 🎧 音频健康 行（可能未启动采集或日志被截断）")
    conclusions.append("热修覆盖层：" + ("有启用记录" if "补丁覆盖层已启用" in (text or "")
                                      else "未见启用记录"))
    conclusions.append("WDSP：" + ("加载成功" if "WDSP 库加载成功" in (text or "")
                                 else "未见成功记录"))

    head = ["=== 自动体检结论 ==="] + [f"  * {c}" for c in conclusions] + ["", "=== 命中明细 ==="]
    return "\n".join(head + parts + [""])


def collect_env_snapshot(version="", extra=None):
    """环境快照：版本/平台/Python/是否冻结/CPU 数 + 调用方补充项。"""
    import platform
    import sys

    snap = {
        "version": version,
        "frozen": bool(getattr(sys, "frozen", False)),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "cpuCount": os.cpu_count(),
    }
    snap.update(extra or {})
    return snap


# --------------------------------------------------------------------------- #
# 打包
# --------------------------------------------------------------------------- #
README_TEXT = (
    "本包由 MRRC「🐞 遇到问题 → 上传日志」生成。\n\n"
    "包含：\n"
    "  * logs/         日志尾部（当前日志 + 上一份 + 服务端 stdout + 天调日志）\n"
    "  * state/        脱敏后的配置快照、热修覆盖层状态\n"
    "  * diagnostics/  环境快照、音频设备表、自动体检摘要（summary.txt 先看这个）\n\n"
    "不含：登录用户数据库、证书与私钥、任何会话签名密钥或密码令牌（生成时已脱敏）。\n"
)


def build_bundle(out_dir, problem="", contact="", env=None, log_files=None,
                 config_text="", include_audio=None, extra_files=None,
                 manifest_extra=None):
    """生成诊断包。

    返回 {id, path, size, files, redactions, warnings}；任何单项失败只记 warning，
    保证仍能产出可用包（最小包降级）。
    """
    import json
    import time
    import zipfile

    os.makedirs(out_dir, exist_ok=True)
    bundle_id = time.strftime("%Y%m%d-%H%M%S") + "-" + os.urandom(2).hex()
    zip_path = os.path.join(out_dir, f"support-{bundle_id}.zip")
    warnings, redactions, collected = [], 0, []
    hashes = {}

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        def add(name, data):
            if isinstance(data, str):
                data = data.encode("utf-8")
            archive.writestr(name, data)
            collected.append(name)
            hashes[name] = __import__("hashlib").sha256(data).hexdigest()

        add("problem.txt", f"# 问题描述\n{problem or '(未填写)'}\n\n"
                           f"# 联系方式\n{contact or '(未填写)'}\n")
        add("README.txt", README_TEXT)

        summary_source = ""
        for name, path in (log_files or {}).items():
            if not is_collectable(name):
                warnings.append(f"跳过受限文件：{name}")
                continue
            text = tail_lines(path)
            if not text:
                warnings.append(f"日志不存在、为空或无权限：{name}")
                continue
            cleaned, hits = redact_text(text)
            redactions += hits
            summary_source += cleaned
            add(name, cleaned)

        cleaned_cfg, hits = redact_text(redact_config_text(config_text))
        redactions += hits + count_omitted_config_keys(config_text)
        add("state/config-redacted.ini", cleaned_cfg)
        add("diagnostics/summary.txt", summarize_log(summary_source))
        add("diagnostics/env.json", json.dumps(env or {}, ensure_ascii=False, indent=2))

        for name, data in (extra_files or {}).items():
            if not is_collectable(name):
                warnings.append(f"跳过受限文件：{name}")
                continue
            add(name, data)

        if include_audio:
            add("audio/rx-5s.wav", include_audio)

        manifest = {
            "id": bundle_id,
            "createdAt": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "problem": problem or "",
            "contact": contact or "",
            "files": collected,
            "sha256": hashes,
            "redactions": redactions,
            "warnings": warnings,
        }
        manifest.update(manifest_extra or {})
        add("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))

    return {
        "id": bundle_id,
        "path": zip_path,
        "size": os.path.getsize(zip_path),
        "files": collected,
        "redactions": redactions,
        "warnings": warnings,
    }
