#!/usr/bin/env python3
"""rigctld 轮询纪律 + 第三方改频联动守卫：python3 dev_tools/test_rig_polling.py

两条纪律（2026-10-04，F9）：

① **S 表"不支持就别再问"**：本机 IC-M710 的 hamlib 后端起 get_level 全失败
   （`l STRENGTH` → `RPRT -1`），而 `ticksTRXRIG` 每 0.5s 问一次 —— 实测 rigctld 日志
   99% 被这条告警刷满（约 2 条/秒），还白占一轮进程往返。守卫：连续失败到阈值必须
   **闩住**（`_strength_unsupported`），且闩锁判断要在建立连接**之前**（否则照样连）。

② **外部改频要广播给页面**：`FrequencySyncThread`（V4.9.2 就是为第三方软件联动建的：
   RUMlogNG/JTDX/flrig 直接经 rigctld 改频）原先只把频率喂给 ATR-1000 代理，网页不跟随
   （实测：RUMlogNG 点 DX spot 改频 → 电台 QSY、页面显示旧频率）。守卫：同步线程必须
   广播 `getFreq:<值>`，且广播经 `MAIN_IOLOOP.add_callback`（后台线程不能直接写
   WebSocket），而页面端必须认得这个消息。
"""
import re
import sys
import ast
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
src = (ROOT / 'MRRC').read_text(encoding='utf-8')

fails, notes = [], []

# ---- ① S 表闩锁 -----------------------------------------------------------
get_strength = src[src.index('def _rigctld_get_signal_strength'):
                   src.index('def ', src.index('def _rigctld_get_signal_strength') + 10)]
if '_strength_unsupported' not in get_strength:
    fails.append('S 表：_rigctld_get_signal_strength 没有"不支持就停"的闩锁')
else:
    # 闩锁判断必须在建立连接之前（否则闩住了还照样连）
    guard_at = get_strength.index('if self._strength_unsupported')
    connect_at = get_strength.index('socket.socket(')
    if guard_at > connect_at:
        fails.append('S 表：闩锁判断在 connect 之后（应该在最前面直接 return）')
    else:
        notes.append('S 表：闩锁在连接之前生效')
if 'self._strength_fail_count' not in src:
    fails.append('S 表：缺少失败计数（无法判断"连续失败"）')
if '不支持信号强度电平' not in src:
    fails.append('S 表：闩住时没有给运维的可见提示（print）')
if not re.search(r'if\s+self\._strength_fail_count\s*>=\s*\d+\s+and\s+not\s+self\._strength_unsupported',
                 src):
    fails.append('S 表：提示只在首次闩住时打印的保护缺失（会反复刷屏）')
# F9d：只有 RPRT -1（本机不支持该电平）才入计数 —— 瞬时错误（-5/-6/-9/-11、串口抖动、
# 电台忙、rigctld 重启）不能在别的机型上误闩。FT-817 这类本人读得到 S 表的机型尤其如此。
if 'RPRT -1' not in get_strength:
    fails.append('S 表：闩锁没区分“不支持(RPRT -1)”与瞬时错误码 → 会误闩别的机型')
else:
    if get_strength.index('RPRT -1') > get_strength.index('self._strength_fail_count += 1'):
        fails.append('S 表：瞬时错误的过滤写在计数之后（等于没过滤）')
    else:
        notes.append('S 表：只对 RPRT -1 计数（能读 S 表的机型不会被瞬时错误误闩）')

# ---- ② 外部改频广播 -------------------------------------------------------
if 'def _broadcast_freq_to_clients' not in src:
    fails.append('联动：缺少 _broadcast_freq_to_clients（外部改频不会广播给页面）')
else:
    bc = src[src.index('def _broadcast_freq_to_clients'):
             src.index('class FrequencySyncThread')]
    if 'getFreq:' not in bc:
        fails.append('联动：广播的不是页面认得的 getFreq:<值> 消息')
    if 'MAIN_IOLOOP.add_callback' not in bc:
        fails.append('联动：广播没有走 MAIN_IOLOOP.add_callback（后台线程直接写 WS 不安全）')

sync_start = src.index('class FrequencySyncThread')
sync = src[sync_start:src.index('load_optimized_configs()', sync_start)]
if '_broadcast_freq_to_clients(' not in sync:
    fails.append('联动：FrequencySyncThread 检测到外部改频后没有调用广播')

controls = (ROOT / 'www' / 'controls.js').read_text(encoding='utf-8')
if 'getFreq' not in controls or 'showTRXfreq' not in controls:
    fails.append('联动：www/controls.js 不处理服务端主动下发的 getFreq（页面无法跟随）')

# ---- ③ 频率读回 0 不得污染状态（F10）-----------------------------------------
get_freq = src[src.index('\tdef getFreq(self):'):]
get_freq = get_freq[:get_freq.index('\n\tdef ')]
if 'if freq > 0:' not in get_freq:
    fails.append('频率：getFreq 没有">0 才写入"的保护（rigctld 回 0 会污染 infos["FREQ"]）')
if '无历史值可恢复' not in get_freq:
    fails.append('频率：读回 0 且无历史值时没有给运维的可见提示（print，且应限流）')
if '_freq_zero_warn_at' not in get_freq:
    fails.append('频率：0 值提示没有限流（同步线程每 2s 一次会刷屏）')

# ---- ④ rigctld 不用 -vvv（TRACE 级噪音）------------------------------------
multi = (ROOT / 'mrrc_multi.sh').read_text(encoding='utf-8')
if re.search(r'-vvv\s*>\s*"\$RIGCTLD_LOG"', multi):
    fails.append('rigctld：启动参数退回 -vvv（TRACE 级“nothing to scan”会以 2~3 条/秒刷满日志）')
if not re.search(r'-vv\s*>\s*"\$RIGCTLD_LOG"', multi):
    fails.append('rigctld：未按 F9 用 -vv 启动（应保留 ptt 审计行、去掉 TRACE 噪音）')
if 'MRRC_RIGCTLD_BIN' not in multi:
    fails.append('rigctld：不支持 MRRC_RIGCTLD_BIN 覆盖（打过补丁的 rigctld 无法接入）')
if 'INSTANCE_RIGCTLD_BIN' not in multi or "'rigctld_bin'" not in multi:
    fails.append('rigctld：未从实例配置读 [HAMLIB] rigctld_bin（F12 要求可持久指定补丁版）')

# ---- ⑤ 虚拟后端要记住“最后一次设置”（F11）-----------------------------------
# IC-M710 的 hamlib 后端起 get_freq/get_mode 只回它内存里“最后一次设置”的副本；
# rigctld 一重启副本归零 → 读频率恒 0。所以应用必须落盘并在启动/读 0 时重写一遍。
missing = [label for needle, label in [
    ('RIG_STATE_FILE =', '状态文件名'),
    ('def load_rig_state', 'load_rig_state'),
    ('def save_rig_state', 'save_rig_state'),
    ('def reassert_rig_state', 'reassert_rig_state'),
    ('save_rig_state(freq=frequency)', 'setFreq 成功后落盘'),
    ('save_rig_state(mode=MODE.upper())', 'setMode 成功后落盘'),
    ("reassert_rig_state('检测到读频率为 0", '读回 0 时按上次值恢复'),
] if needle not in src]
for label in missing:
    fails.append(f'F11 缺失：{label}')
if not missing:
    notes.append('F11：虚拟后端状态有落盘 + 恢复路径')

boot = src[src.index('CTRX = TRXRIG()'):][:600]
if "reassert_rig_state('启动')" not in boot:
    fails.append('F11 缺失：启动后没有把上次已知的频率/模式写回 rigctld')

# F11b：先读后写 —— 会回答查询的机型（FT-817/FT-818 等）以电台自报值为准，
# 不能用记忆值覆盖操作员在应用关着时手动调过的频率/模式。
_re_start = src.index('def reassert_rig_state')
reassert = src[_re_start:src.index('\ndef ', _re_start + 10)]
if "_rigctld_command('f')" not in reassert or 'CTRX.setFreq(freq)' not in reassert:
    fails.append('F11b 缺失：reassert 里没有“先读频率再决定要不要写”')
elif reassert.index("_rigctld_command('f')") > reassert.index('CTRX.setFreq(freq)'):
    fails.append('F11b：读频率写在 setFreq 之后（先写后读等于覆盖了电台自己的值）')
elif 'if now_hz > 0:' not in reassert or 'save_rig_state(freq=now_hz)' not in reassert:
    fails.append('F11b：读回非 0 时没有采用电台自报值（仍会覆盖）')
else:
    notes.append('F11b：reassert 先读后写，电台能回答时以电台为准')
if "_rigctld_command('m')" not in reassert or "now_mode != 'None'" not in reassert:
    fails.append('F11b：模式同样需要“先读后写”（且 rigctld 对空模式回的 None 不能当成模式名）')

# ---- ⑥ 行为级验证：AST 抽函数单独执行（同 test_atr1000_proxy_manager.py）-------
# 上面的断言都是“代码里有没有这句话”；这一节把函数抽出来真跑，验证行为本身。
# 这两条都是“机型无关的安全化”：不能在其它电台（FT-817/FT-818…）上误伤。

def _load_func(name, extra=None, as_method=False):
    tree = ast.parse(src)
    node = next(n for n in ast.walk(tree)
                if isinstance(n, ast.FunctionDef) and n.name == name)
    body: list[ast.stmt] = [node]
    if as_method:
        node.name = 'call_under_test'
        body = [ast.ClassDef(name='Rig', bases=[], keywords=[], body=[node],
                             decorator_list=[])]
    mod = ast.Module(body=body, type_ignores=[])
    ast.fix_missing_locations(mod)
    quiet = lambda *a, **k: None                                      # noqa: E731
    g = {'print': quiet, 'logger': types.SimpleNamespace(debug=quiet, warning=quiet)}
    g.update(extra or {})
    exec(compile(mod, str(ROOT / 'MRRC'), 'exec'), g)
    return (g['Rig'] if as_method else g[name]), g


class _Sock:
    """假 rigctld 连接：recv 按 box['reply'] 回话。"""

    def __init__(self, box):
        self.box = box

    def settimeout(self, _):
        pass

    def connect(self, _):
        pass

    def sendall(self, _):
        pass

    def recv(self, _):
        return self.box['reply'].encode()

    def close(self):
        pass


def _strength_after(replies):
    box = {'reply': ''}
    Rig, _ = _load_func('_rigctld_get_signal_strength', {
        'socket': types.SimpleNamespace(AF_INET=2, SOCK_STREAM=1, socket=lambda *a: _Sock(box)),
    }, as_method=True)
    rig = Rig()
    rig._strength_unsupported = False
    rig._strength_fail_count = 0
    rig.rigctld_host, rig.rigctld_port = '127.0.0.1', 4531
    for reply in replies:
        box['reply'] = reply
        rig.call_under_test()
    return rig._strength_unsupported


if not _strength_after(['RPRT -1'] * 3):
    fails.append('S 表行为：连续 3 次 RPRT -1（机型不支持）没有闩住')
else:
    notes.append('S 表行为：RPRT -1 ×3 → 闩住（IC-M710 场景）')
if _strength_after(['RPRT -11'] * 3 + ['RPRT -6'] * 2):
    fails.append('S 表行为：瞬时错误码（-11/-6）把 S 表误闩了 —— 别的机型会白丢 S 表')
else:
    notes.append('S 表行为：瞬时错误码不入计数、不误闩（FT-817 这类能读的机型安全）')


class _Ctrx:
    """假电台控制对象：记录应用到底写了什么。"""

    def __init__(self, freq, mode):
        self.freq, self.mode, self.wrote = freq, mode, []

    def _rigctld_command(self, cmd):
        if cmd == 'f':
            return '' if not self.freq else f'{self.freq}\n'
        if cmd == 'm':
            # 真实 rigctld 的回复是“模式行 + 通带行”；副本为空时**首行是空的**
            # （只有 2200）—— 曾经这里被当成模式名取用。不要“美化”这个假实现。
            return '\n2200\n' if not self.mode else f'{self.mode}\n2200\n'
        return ''

    def setFreq(self, freq):
        self.wrote.append(('f', freq))
        self.freq = freq

    def setMode(self, mode):
        self.wrote.append(('m', mode))
        self.mode = mode


def _reassert(saved, rig_freq, rig_mode):
    fn, g = _load_func('reassert_rig_state')
    g['_rig_state'] = dict(saved)
    g['save_rig_state'] = lambda **kw: g['_rig_state'].update({k: v for k, v in kw.items() if v})
    ctrx = _Ctrx(rig_freq, rig_mode)
    g['CTRX'] = ctrx
    fn('守卫测试')
    return ctrx, g['_rig_state']


ctrx, state = _reassert({'freq': 7060000, 'mode': 'USB'}, 7050000, 'LSB')
if ctrx.wrote:
    fails.append(f'F11b 行为：电台能回答（f={7050000}/LSB）时仍写了 {ctrx.wrote} —— '
                 '会把操作员手动调过的频率/模式覆盖掉')
elif state['freq'] != 7050000 or state['mode'] != 'LSB':
    fails.append(f'F11b 行为：采用电台自报值后没有更新记忆：{state}')
else:
    notes.append('F11b 行为：电台能回答 → 以电台为准，一个字都不写（FT-817 场景）')
ctrx, _ = _reassert({'freq': 7060000, 'mode': 'USB'}, 0, '')
if ('f', 7060000) not in ctrx.wrote or ('m', 'USB') not in ctrx.wrote:
    fails.append(f'F11b 行为：读回 0/空时没有恢复记忆值（只写了 {ctrx.wrote}）')
else:
    notes.append('F11b 行为：读回 0/空（虚拟副本丢失）→ 恢复记忆值（IC-M710 场景）')
# 副本为空时 rigctld 对 `m` 回的是“空首行 + 2200”，绝不能被当成模式名“2200”采用
ctrx, state = _reassert({'freq': 7060000, 'mode': 'USB'}, 0, '')
if state.get('mode') == '2200':
    fails.append('F11b 行为：把通带宽度 2200 当成模式名写进记忆文件（副本为空的真实回复）')
else:
    notes.append('F11b 行为：空首行 + 2200 的通带行不会被误认为模式')

for n in notes:
    print(f'  提示: {n}')
if fails:
    print(f'❌ {len(fails)} 项不合格:')
    for f in fails:
        print('   -', f)
    sys.exit(1)
print('✅ rigctld 轮询纪律守卫通过（S 表不支持即闩住并只提示一次；外部改频广播给页面、'
      '走 IOLoop、页面侧认得）')
