#!/usr/bin/env python3
"""ssl_bootstrap.sign_for 的 SAN 行为守卫（F8）：证书要同时覆盖 hub 入口名与老直连入口。

背景（2026-10-04，RC-003 附带）：实例改服 Cloud Hub 证书（CN=<标签>.mrrc.vlsc.net）之后，
直连本机 IPv6 的老书签 `https://radio.vlsc.net:8891/mobile` 因**域名不匹配**被浏览器拒绝
（日志每 0.5 秒一条 SSL CERTIFICATE_UNKNOWN，页面打不开）。修法：把这类老入口名放进证书
SAN（`[SERVER] cert_extra_names`），hub 入口不受影响（边缘用 Let's Encrypt 真证书终止）。

钉住两件事：① SAN = [hub 入口名] + extra_names（去重、忽略空项）；② CN 仍是 hub 入口名
（hub 的 /enroll 按这个名字校验，不能被 extra 顶掉）；③ 不传 extra 时行为与从前完全一致。
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 用 Any 声明：这两个名字在 except 分支里会被置空，运行时由 skipIf 拦下，
# 静态检查器不需要为“导入失败时不存在”这条不可能路径报错。
x509: Any = None
NameOID: Any = None
ssl_bootstrap: Any = None
_IMPORT_ERROR: Exception | None = None
try:
    from cryptography import x509 as _x509_mod
    from cryptography.x509.oid import NameOID as _NameOID_mod
    import ssl_bootstrap as _ssl_bootstrap_mod
    x509, NameOID, ssl_bootstrap = _x509_mod, _NameOID_mod, _ssl_bootstrap_mod
except Exception as exc:                       # 没有 cryptography 时跳过
    _IMPORT_ERROR = exc


def _read_cert(path):
    return x509.load_pem_x509_certificate(Path(path).read_bytes())


def _san_names(cert):
    ext = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName)
    # get_values_for_type 对 DNSName 直接返回字符串值
    return list(ext.value.get_values_for_type(x509.DNSName))


def _cn(cert):
    return cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value


@unittest.skipIf(_IMPORT_ERROR is not None, f"缺少依赖：{_IMPORT_ERROR!r}")
class SignForSanTests(unittest.TestCase):

    HUB = "bg6lh-legacy.mrrc.vlsc.net"
    LEGACY = "radio.vlsc.net"

    def test_extra_names_are_added_and_cn_stays_the_hub_name(self):
        with tempfile.TemporaryDirectory() as td:
            pair = ssl_bootstrap.sign_for(self.HUB, Path(td), extra_names=[self.LEGACY])
            self.assertIsNotNone(pair, "sign_for 返回 None（签发失败）")
            cert = _read_cert(pair[0])
            self.assertEqual(_san_names(cert), [self.HUB, self.LEGACY])
            self.assertEqual(_cn(cert), self.HUB)

    def test_default_is_unchanged(self):
        """不传 extra 时 SAN 只有 hub 名——其它实例的行为不受本次改动影响。"""
        with tempfile.TemporaryDirectory() as td:
            pair = ssl_bootstrap.sign_for(self.HUB, Path(td))
            cert = _read_cert(pair[0])
            self.assertEqual(_san_names(cert), [self.HUB])

    def test_dedupes_and_ignores_blank_items(self):
        with tempfile.TemporaryDirectory() as td:
            pair = ssl_bootstrap.sign_for(self.HUB, Path(td),
                                          extra_names=[self.HUB, "", "  ", self.LEGACY])
            cert = _read_cert(pair[0])
            self.assertEqual(_san_names(cert), [self.HUB, self.LEGACY])

    def test_key_file_is_0600(self):
        with tempfile.TemporaryDirectory() as td:
            pair = ssl_bootstrap.sign_for(self.HUB, Path(td), extra_names=[self.LEGACY])
            if os.name != "nt":
                mode = Path(pair[1]).stat().st_mode & 0o777
                self.assertEqual(mode, 0o600, f"私钥权限应为 0600，实际 {oct(mode)}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
