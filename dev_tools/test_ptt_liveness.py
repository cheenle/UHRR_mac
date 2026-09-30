#!/usr/bin/env python3
"""PTT 活性闸门守卫测试：python3 dev_tools/test_ptt_liveness.py

闸门逻辑早已存在（发射期间连续未收帧即收回 PTT）。本测试守**重构没改变它**，另外守一条
今天真踩到的坑：**配置段名必须真实存在于 MRRC.conf** —— 代码里有个运行期对象叫 CTRX，
很容易被误当成配置段名写进 config['CTRX']，那会在启动时 KeyError 崩掉主程序，
而 py_compile 查不出来。
"""
import configparser
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
src = (ROOT / 'MRRC').read_text(encoding='utf-8')
conf_text = (ROOT / 'MRRC.conf').read_text(encoding='utf-8')
cp = configparser.ConfigParser()
cp.read_string(conf_text)

fails, notes = [], []

# ① 配置段/键的真实性（今天踩过的坑）
m = re.search(r"config\['([A-Z]+)'\]\.get\('tx_liveness_s'", src)
if not m:
    fails.append('MRRC 未从配置读取 tx_liveness_s')
else:
    sec = m.group(1)
    if sec == 'CTRX':
        fails.append("配置段写成了 'CTRX'（那是运行期对象，不是配置段）")
    elif not cp.has_section(sec):
        fails.append(f"MRRC.conf 不存在配置段 [{sec}]")
    else:
        notes.append(f'阈值读取自 [{sec}]（配置段存在）')

default = 5.0
if cp.has_option(m.group(1), 'tx_liveness_s') if m else False:
    default = cp.getfloat(m.group(1), 'tx_liveness_s')
else:
    notes.append('MRRC.conf 未显式写 tx_liveness_s —— 使用代码默认 5.0（等效原行为）')

# ② 默认值 = 原行为（约 5 秒 / 25 次 × 0.2s）
poll = re.search(r'^_TX_POLL_S\s*=\s*([\d.]+)', src, re.M)
if not poll:
    fails.append('MRRC 未定义 _TX_POLL_S')
    eff, secs = 25, 5.0
else:
    p = float(poll.group(1))
    eff, secs = int(round(default / p)), int(round(default / p)) * p
    if not (12 <= eff <= 50):
        fails.append(f'默认折算 {eff} 次超出合理范围（原 25 次）')
    if abs(secs - 5.0) > 0.51:
        fails.append(f'默认阈值 {secs:.2f}s 偏离原行为 5.0s')

# ③ 看门狗未退化
wd = src[src.index('def stoppttontimeout'):src.index('def _start_tx_init_async')]
for ok, label in [
    ('last_AudioTXHandler_msg_time + 0.2' not in wd, '仍残留硬编码 0.2'),
    ('miss_count >= 25' not in wd, '仍残留硬编码 25'),
    ('CTRX.setPTT("false")' in wd, '未走既有释放路径 CTRX.setPTT("false")'),
    ('_TX_MISS_LIMIT and' in wd, '关闭开关（_TX_MISS_LIMIT = 0）未生效'),
    ('tune_playing or cq_playing' in wd, 'tune/CQ 播放期间跳过检查的保护被破坏'),
]:
    if not ok:
        fails.append(label)

for n in notes:
    print(f'  提示: {n}')
if fails:
    print(f'❌ {len(fails)} 项不合格:')
    for f in fails:
        print('   -', f)
    sys.exit(1)
print(f'✅ PTT 活性闸门守卫通过（默认 ≈{secs:.1f}s = 原行为；配置段真实存在；0=关闭；走既有释放路径）')
