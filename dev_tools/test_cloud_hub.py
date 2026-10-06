#!/usr/bin/env python3
"""接入云端（Cloud Hub）模块与接线守卫：python3 dev_tools/test_cloud_hub.py

参照系是 mrrc_modern v1.25.0 的 cloud_hub.py + tests/test_cloud_endpoints.py；
本产品的差异（JSON 状态文件、frpc 发现、Tornado 接线）都在覆盖范围内。
"""
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import cloud_hub as ch

fails = []


def check(ok, label):
    if not ok:
        fails.append(label)


# ---- frpc 配置文本 -----------------------------------------------------------
text = ch.frpc_config_text('bg1sb-legacy', 'tok123', 8877, 18803,
                           log_file='C:\\Users\\x\\fleet\\frpc.log')
check('serverAddr = "tunnel.mrrc.vlsc.net"' in text, 'frpc: hub 地址')
check('serverPort = 8989' in text, 'frpc: 控制口')
check('auth.token = "tok123"' in text, 'frpc: 令牌')
check('name = "bg1sb-legacy"' in text, 'frpc: 代理名')
check('localPort = 8877' in text and 'remotePort = 18803' in text, 'frpc: 端口对')
check(text.endswith('\n'), 'frpc: 末尾换行')
try:
    text.encode('ascii')
    _ascii_ok = True
except UnicodeEncodeError:
    _ascii_ok = False
check(_ascii_ok, 'frpc: 纯 ASCII（BOM/中文会让 frpc 拒解析）')
check('C:/Users/x/fleet/frpc.log' in text and '\\U' not in text,
      'frpc: Windows 路径转前斜杠（反斜杠在 TOML 里是转义）')

# ---- 门户地址：V0.21 前的旧写法全部改写到现网 --------------------------------
_captured = []


def _fake_post_once(portal, route, payload, timeout):
    _captured.append((portal, route, payload))
    return {'ok': True}


_orig_post_once = ch._post_once
ch._post_once = _fake_post_once
try:
    for legacy in ('https://portal.mrrc.vlsc.net:8899',
                   'https://www.vlsc.net/mrrc_portal',
                   'https://portal.mrrc.vlsc.net/mrrc_portal'):
        _captured.clear()
        ch._post(legacy, '/status', {'callsign': 'X', 'token': 'Y'})
        check(_captured and _captured[0][0] == ch.PORTAL_DEFAULT,
              f'旧门户地址改写: {legacy}')
    _captured.clear()
    ch._post('https://portal.example.com/', '/status', {})
    check(_captured[0][0] == 'https://portal.example.com', '自定义门户不被改写（去尾斜杠）')
finally:
    ch._post_once = _orig_post_once

# 不可达（502/网络错）要包装成一句话，而不是把 _Unreachable 抛给界面
def _raise_unreach(portal, route, payload, timeout):
    raise ch._Unreachable('boom')


ch._post_once = _raise_unreach
try:
    try:
        ch._post(ch.PORTAL_DEFAULT, '/status', {})
        check(False, '不可达应抛 CloudHubError')
    except ch.CloudHubError as exc:
        check('portal did not answer' in str(exc), '不可达包装成一句话')
finally:
    ch._post_once = _orig_post_once

# ---- apply / claim / status 的报文形状 ----------------------------------------
_calls = []


def _fake_post(portal, route, payload, timeout=ch.TIMEOUT):
    _calls.append((route, payload))
    if route == '/status':
        return {'status': 'pending'}
    return {'request_token': 'tok-1', 'status': 'applied'}


_orig_post = ch._post
ch._post = _fake_post
try:
    r = ch.apply('p', 'BG1SB', 'ops@example.com', 'legacy')
    check(r['request_token'] == 'tok-1', 'apply 返回令牌')
    check(_calls[-1] == ('/apply', {'callsign': 'BG1SB', 'contact': 'ops@example.com',
                                    'product': 'legacy'}), 'apply 报文（product=legacy → 带后缀标签）')
    r = ch.claim('p', 'BG1SB', 'sec')
    check(_calls[-1] == ('/claim', {'callsign': 'BG1SB', 'secret': 'sec'}), 'claim 报文')
    ch.status('p', 'BG1SB', 'tok-1')
    check(_calls[-1] == ('/status', {'callsign': 'BG1SB', 'token': 'tok-1'}), 'status 报文')

    ch._post = lambda *a, **k: {}
    try:
        ch.apply('p', 'BG1SB')
        check(False, '无令牌应答应抛错')
    except ch.CloudHubError:
        check(True, '')
finally:
    ch._post = _orig_post

# ---- 状态文件（mrrc_cloud.json 的纯逻辑层） ------------------------------------
with tempfile.TemporaryDirectory() as td:
    sp = Path(td) / 'sub' / 'mrrc_cloud.json'
    st = ch.save_state(sp, {'callsign': 'BG1SB', 'token': 'tok-1'})
    check(st['callsign'] == 'BG1SB', 'save_state 返回合并后状态')
    st = ch.save_state(sp, {'label': 'bg1sb-legacy', 'port': 18803})
    check(st['token'] == 'tok-1' and st['label'] == 'bg1sb-legacy', 'save_state 是合并不是覆盖')
    check(ch.load_state(sp)['port'] == 18803, 'load_state 读回')
    check(sp.exists() and not Path(str(sp) + '.tmp').exists(), '原子写不留 .tmp')
    if os.name != 'nt':
        check((sp.stat().st_mode & 0o777) == 0o600, '状态文件 0600（含申请令牌）')
    sp.write_text('not json', encoding='utf-8')
    check(ch.load_state(sp) == {}, '坏 JSON → 空状态而不是异常')
    check(ch.load_state(Path(td) / 'nope.json') == {}, '缺文件 → 空状态')

# ---- connect()：批准之后的完整接入 ---------------------------------------------
class _FakeTunnel:
    def __init__(self):
        self.started = False
        self.frpc = None
        self.conf = None

    def start(self):
        self.started = True


_sign_calls = []


def _fake_sign_for(name, cert_dir, extra_names=None):
    # F8：connect() 必须把 [SERVER] cert_extra_names 透传给签发（否则老直连入口
    # radio.vlsc.net 会因域名不匹配被浏览器拒绝）——这里把它记录下来供断言。
    _sign_calls.append({'name': name, 'extra_names': list(extra_names or [])})
    cert_dir = Path(cert_dir)
    cert_dir.mkdir(parents=True, exist_ok=True)
    cert = cert_dir / 'fullchain.pem'
    key = cert_dir / (name.split('.')[0] + '.key')
    cert.write_text('-----BEGIN CERTIFICATE-----\nFAKE\n-----END CERTIFICATE-----\n')
    key.write_text('-----BEGIN PRIVATE KEY-----\nFAKE\n-----END PRIVATE KEY-----\n')
    return cert, key


with tempfile.TemporaryDirectory() as td:
    td = Path(td)
    _enrolled = []

    def _fake_post_connect(portal, route, payload, timeout=ch.TIMEOUT):
        if route == '/status':
            return {'status': 'granted', 'label': 'bg1sb-legacy', 'port': 18803,
                    'enroll_secret': 'esec', 'hub_token': 'htok'}
        if route == '/enroll':
            _enrolled.append(payload)
            return {'ok': True}
        raise AssertionError(f'unexpected route {route}')

    ch._post = _fake_post_connect
    _orig_sign = ch.ssl_bootstrap.sign_for
    ch.ssl_bootstrap.sign_for = _fake_sign_for
    try:
        tun = _FakeTunnel()
        result = ch.connect('p', 'BG1SB', 'tok-1',
                            state_path=td / 'mrrc_cloud.json', cert_dir=td / 'certs',
                            data_dir=td / 'fleet', local_port=8877,
                            frpc=Path('/usr/local/bin/frpc'), tunnel=tun,  # type: ignore[arg-type]
                            extra_names=['radio.vlsc.net'])
        check(_sign_calls and _sign_calls[0]['name'] == 'bg1sb-legacy.mrrc.vlsc.net'
              and _sign_calls[0]['extra_names'] == ['radio.vlsc.net'],
              'connect: extra_names 透传到证书签发（F8）')
        check(result['connected'] is True, 'connect: 已接入')
        check(result['entry'] == 'https://bg1sb-legacy.mrrc.vlsc.net/', 'connect: 入口 URL')
        check(result['tunnel_started'] is True and tun.started, 'connect: 隧道已拉起')
        check(tun.frpc == Path('/usr/local/bin/frpc'), 'connect: 隧道拿到发现的 frpc')
        conf = (td / 'fleet' / 'frpc-bg1sb-legacy.toml').read_text(encoding='ascii')
        check('remotePort = 18803' in conf and 'localPort = 8877' in conf
              and 'auth.token = "htok"' in conf, 'connect: frpc 配置内容')
        st = ch.load_state(td / 'mrrc_cloud.json')
        check(st.get('label') == 'bg1sb-legacy' and st.get('cert', '').endswith('fullchain.pem'),
              'connect: 状态落盘（重启后服务新证书的依据）')
        check(len(_enrolled) == 1 and 'FAKE' in _enrolled[0].get('cert', '')
              and _enrolled[0].get('secret') == 'esec', 'connect: 公钥已登记到 hub')

        # 未批准：不签证书、不起隧道
        ch._post = lambda *a, **k: {'status': 'verified'}
        r2 = ch.connect('p', 'BG1SB', 'tok-1',
                        state_path=td / 's2.json', cert_dir=td / 'c2',
                        data_dir=td / 'f2', local_port=8877)
        check(r2['connected'] is False and r2['status'] == 'verified', 'connect: 未批准不接入')
        check(not (td / 'c2').exists(), 'connect: 未批准不签证书')

        # 门户回了非数字端口：必须是一句话，不是 ValueError
        ch._post = lambda *a, **k: {'status': 'granted', 'label': 'x', 'port': 'abc',
                                    'enroll_secret': 's'}
        try:
            ch.connect('p', 'BG1SB', 'tok-1',
                       state_path=td / 's3.json', cert_dir=td / 'c3',
                       data_dir=td / 'f3', local_port=8877)
            check(False, '非数字端口应抛 CloudHubError')
        except ch.CloudHubError as exc:
            check('port' in str(exc), 'connect: 非数字端口是一句话')

        # granted 但缺字段
        ch._post = lambda *a, **k: {'status': 'granted', 'label': '', 'port': 1,
                                    'enroll_secret': ''}
        try:
            ch.connect('p', 'BG1SB', 'tok-1',
                       state_path=td / 's4.json', cert_dir=td / 'c4',
                       data_dir=td / 'f4', local_port=8877)
            check(False, '缺 label/secret 应抛错')
        except ch.CloudHubError:
            check(True, '')
    finally:
        ch._post = _orig_post
        ch.ssl_bootstrap.sign_for = _orig_sign

# ---- find_frpc：发现顺序与 MRRC_FRPC 覆盖 --------------------------------------
with tempfile.TemporaryDirectory() as td:
    fake = Path(td) / 'frpc'
    fake.write_text('#!/bin/sh\n')
    os.environ['MRRC_FRPC'] = str(fake)
    try:
        check(ch.find_frpc(Path(td) / 'fleet') == fake, 'find_frpc: MRRC_FRPC 环境变量优先')
    finally:
        del os.environ['MRRC_FRPC']
    # 无覆盖时至少不炸；本机 ~/bin/frpc 存在则应被发现（首台机器的真实位置）
    home_bin = Path.home() / 'bin' / ('frpc.exe' if os.name == 'nt' else 'frpc')
    found = ch.find_frpc(Path(td) / 'fleet')
    if home_bin.exists():
        check(found is not None, 'find_frpc: 能找到 ~/bin/frpc')
    check(ch.find_frpc(Path(td) / 'nope') is None or found is not None, 'find_frpc: 找不到时返回 None')

# ---- 接线守卫（本产品这一侧） ----------------------------------------------------
src = (ROOT / 'MRRC').read_text(encoding='utf-8')
check("import cloud_hub as _cloud_hub" in src, 'MRRC: 引入 cloud_hub')
check("(r'/api/cloud/.*', CloudApiHandler)" in src, 'MRRC: /api/cloud 路由')
check(src.count('_cloud_start_autoconnect(') >= 2, 'MRRC: 启动时 + 申请后各起一次轮询')
check('_SERVING_CERT_PATH = cert_path' in src, 'MRRC: 记录实际服务的证书（cert_reload_required 的依据）')
check('run_in_executor' in src and 'class CloudApiHandler' in src,
      'MRRC: 云接口存在且 IO 走 executor（RC-001：不得阻塞 IOLoop）')

dockerfile = (ROOT / 'Dockerfile').read_text(encoding='utf-8')
check('COPY cloud_hub.py' in dockerfile, 'Dockerfile: COPY cloud_hub.py（漏了容器内 ImportError）')

page = ROOT / 'www' / 'cloud.html'
check(page.exists(), 'www/cloud.html 存在')
if page.exists():
    html = page.read_text(encoding='utf-8')
    check("api/cloud/state" in html and "api/cloud/apply" in html
          and "api/cloud/refresh" in html and "api/cloud/restart" in html,
          'cloud.html: 四个接口齐全')
    check("fetch('/api/" not in html and 'fetch("/api/' not in html,
          'cloud.html: 接口用相对路径（前缀安全）')

for ui in ('index.html', 'mobile_modern.html'):
    body = (ROOT / 'www' / ui).read_text(encoding='utf-8')
    check('cloud.html' in body, f'{ui}: 有接入云端入口')

# ---- 陈旧 frpc 清理（RC-003 附带修复）-----------------------------------------
# 2026-10-04 实测：macOS 上 5 个 frpc 抢同一个隧道名（99050/21607/23064/23256/25305），
# 每次重启泄漏一个，日志每 10s 一条 "proxy already exists"，隧道实际由早已失去父进程的
# 孤儿 frpc 持有。根因：_kill_stale_frpc() 第一行是 `if os.name != "nt": return` ——
# 只写了 wmic/taskkill，POSIX 平台直接跳过。这段守两件事：
#   ① 非 Windows 真的会去找（ps）并杀（SIGTERM→宽限→SIGKILL）；
#   ② 只认本实例自己的配置路径，不误杀另一实例的 frpc / 别的进程。
_ps_out = (
    "  1234 /Users/x/bin/frpc -c /tmp/a/frpc-bg6lh-legacy.toml\n"
    "  5678 /Users/x/bin/frpc -c /tmp/b/frpc-bg1sb-legacy.toml\n"
    "  9012 /opt/homebrew/bin/python -u /Users/x/MRRC /Users/x/MRRC.radio1.conf\n"
    "  7777 /Users/x/bin/frpc                     -c /tmp/a/frpc-bg6lh-legacy.toml\n"
    "  frpc.exe -c /tmp/a/frpc-bg6lh-legacy.toml 42\n"   # Windows wmic 行末是 PID
)
_pids = ch._stale_frpc_pids(Path('/tmp/a/frpc-bg6lh-legacy.toml'), ps_output=_ps_out)
check(sorted(_pids) == [42, 1234, 7777], f'陈旧 frpc: 只选中本实例的 frpc（得到 {_pids}）')
check(5678 not in _pids and 9012 not in _pids, '陈旧 frpc: 不误杀另一实例/非 frpc 进程')
_cfg_meta = Path('/tmp/a/frpc-bg6lh-legacy.toml')
check(ch._stale_frpc_pids(_cfg_meta, ps_output='') == [], '陈旧 frpc: 无匹配时返回空')

_hub_src = (ROOT / 'cloud_hub.py').read_text(encoding='utf-8')
check('if os.name != "nt":\n        return' not in _hub_src,
      'cloud_hub: _kill_stale_frpc 不再在 POSIX 上一行返回')
check('ps", "-eo", "pid=,command=' in _hub_src or 'ps", "-eo", "pid=,command"' in _hub_src,
      'cloud_hub: POSIX 用 ps 找进程')
check('os.kill(' in _hub_src, 'cloud_hub: POSIX 用 os.kill 清陈旧 frpc')

fails = [f for f in fails if f]
if fails:
    print(f'❌ {len(fails)} 项不合格: ' + '; '.join(fails))
    sys.exit(1)
print('✅ 接入云端（Cloud Hub）模块与接线守卫通过')
