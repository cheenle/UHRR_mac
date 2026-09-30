#!/usr/bin/env python3
"""路径前缀（Cloud Hub 路径反代入口）守卫测试。

运行：python3 dev_tools/test_path_prefix.py

守三件事：
  ① base_path 模块的行为（前缀为空时一切照旧）
  ② 资产里不再有"站点根绝对引用"（那会让页面挂在前缀下时请求打错地方）
  ③ 服务端确实接了前缀：路由、登录回跳、以及 **Cookie 的 path** ——
     最后这条最容易被忽略，而它一旦漏了，同 origin 上的另一个产品会与它互相覆盖会话。
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

failures, notes = [], []
import base_path as bp

checks = [
    (bp.normalize('') == '' and bp.normalize('/a/b/') == 'a/b' and bp.normalize('/') == '', 'normalize 规范成 '' 或 ''a/b'''),
    (bp.url('', '/login') == '/login', '空前缀时 URL 不变（默认行为 = 改造前）'),
    (bp.url('a/b', '/login') == '/a/b/login', '带前缀时 URL 拼接'),
    (bp.cookie_path('') == '/' and bp.cookie_path('a/b') == '/a/b', 'Cookie path 限定到前缀'),
    ([x[0] for x in bp.apply_to_handlers([(r'/login', object)], '')] == [r'/login'], '空前缀时路由表不变'),
    (bp.apply_to_handlers([(r'/login', object)], 'a/b')[0][0] == '/a/b/login', '路由加前缀'),
    (bp.apply_to_handlers([(r'/(panfft.*)', object)], 'x')[0][0] == '/x/(panfft.*)', '正则路由加前缀'),
    (bp.apply_to_handlers([(r'/a', object, {'k': 1})], 'x')[0][2] == {'k': 1}, 'handler 与 kwargs 原样保留'),
]
for ok, label in checks:
    if not ok:
        failures.append(f'base_path: {label} 不成立')

for path in sorted((ROOT / 'www').glob('*.html')):
    for i, line in enumerate(path.read_text(encoding='utf-8', errors='replace').splitlines(), 1):
        for m in re.finditer(r'(?:href|src)="(/[^/"][^"]*)"', line):
            failures.append(f'{path.name}:{i} 站点根绝对引用 {m.group(1)}')

for path in sorted((ROOT / 'www').glob('*.js')):
    text = path.read_text(encoding='utf-8', errors='replace')
    for i, line in enumerate(text.splitlines(), 1):
        if re.search(r"""fetch\(\s*['"]/""", line):
            failures.append(f'{path.name}:{i} fetch 用了站点根绝对路径')
        if 'location.href.split' in line and 'wss://' in line:
            failures.append(f'{path.name}:{i} 用 href.split 拼 WS 地址（前缀不安全）')
    # 只看非注释行：注释里出现 WS 路径是正常的（实测 pad.js 即为误报）
    code = '\n'.join(l for l in text.splitlines()
                      if not l.lstrip().startswith(('//', '*', '#')))
    if re.search(r"""['"]/WS[a-zA-Z]+['"]""", code) and '__mrrcUrl' not in text and '__wsURL' not in text:
        notes.append(f'{path.name}: 出现 WS 路径字面量但未见前缀化助手，请复核')

src = (ROOT / 'MRRC').read_text(encoding='utf-8')
if src.count('app = base_path.application(') != 2:
    failures.append('MRRC: 两处 Application 未走 base_path.application')
if src.count('_base_path.cookie_path(BASE_PATH)') < 5:
    failures.append('MRRC: Cookie 的 path 未全部限定（同 origin 多产品会互踩）')
if '_base_path.url(BASE_PATH' not in src:
    failures.append('MRRC: 登录/回跳 URL 未加前缀')
conf = (ROOT / 'MRRC.conf').read_text(encoding='utf-8')
if 'base_path' not in conf:
    failures.append('MRRC.conf: 缺少 base_path 配置项')
if 'SW_BASE + ' not in (ROOT / 'www' / 'sw.js').read_text(encoding='utf-8'):
    failures.append('sw.js: 预缓存清单未按部署前缀推导')
if 'COPY base_path.py' not in (ROOT / 'Dockerfile').read_text(encoding='utf-8'):
    failures.append('Dockerfile: 未包含 base_path.py（容器内会 ImportError）')

for note in notes:
    print(f'  提示: {note}')
if failures:
    print(f'❌ {len(failures)} 项不合格:')
    for f in failures:
        print('   -', f)
    sys.exit(1)
print(f'✅ 路径前缀守卫通过（{len(checks)} 项模块行为 + 资产扫描 + 服务端接线 + 打包）')
