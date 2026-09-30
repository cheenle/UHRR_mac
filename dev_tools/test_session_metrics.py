#!/usr/bin/env python3
"""会话遥测模块测试：python3 dev_tools/test_session_metrics.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import session_metrics as m

fails = []


def check(ok, label):
    if not ok:
        fails.append(label)


m.bump('tx_frames', 3)
m.bump('tx_frames', 2)
m.bump('decode_fail')
check(m.counters().get('tx_frames') == 5, 'bump 累加')
check(m.counters().get('decode_fail') == 1, 'bump 默认 +1')

payload = m.render({'audiorx': 2, 'ctrlsx': 1}, {'pid': 4242})
check(payload['active'] == {'audiorx': 2, 'ctrlsx': 1}, 'render 保留 active')
check(payload['pid'] == 4242, 'render 合并 extra')
check(payload['counters']['tx_frames'] == 5, 'render 带计数器')
check(isinstance(payload['uptime_s'], int), 'uptime 为整数')

line = m.format_line(payload)
check('audiorx=2' in line and 'tx_frames=5' in line and 'uptime=' in line, '格式化为单行')
check('\n' not in line, '日志行不含换行')

check(m.format_line({'active': {}, 'counters': {}, 'uptime_s': 1}).count('none') == 2, '空值显示 none')
check(m.render(None)['active'] == {}, 'active 为 None 时不炸')

if fails:
    print(f'❌ {len(fails)} 项不合格: ' + '; '.join(fails))
    sys.exit(1)
print('✅ 会话遥测模块测试通过')
