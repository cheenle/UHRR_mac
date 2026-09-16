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
