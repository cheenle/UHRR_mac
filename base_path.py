"""路径前缀支持（Cloud Hub 路径反代入口）。

实例可能被挂在 https://www.vlsc.net/<产品段>/<呼号>/ 之类的路径下，此时：
  - 路由表要整体加前缀
  - 登录/回跳 URL 要带前缀
  - Cookie 的 path 必须限定到前缀，否则同 origin 上的另一个产品会与它互相覆盖

约定：base_path 为空字符串时，一切行为与改造前完全一致（默认值即此）。
"""
from __future__ import annotations

import re

_CLEAN = re.compile(r"^[A-Za-z0-9._~!$&'()*+,;=:@/-]*$")


def normalize(value) -> str:
    """把配置里的 base_path 规范成 ''/不含首尾斜杠/lowercase 保留原样。"""
    if value is None:
        return ''
    text = str(value).strip()
    if text in ('', '/', '0', 'false', 'False', 'None'):
        return ''
    text = text.strip('/')
    if '//' in text or '..' in text.split('/'):
        raise ValueError(f'base_path 不合法: {value!r}')
    if not _CLEAN.match(text):
        raise ValueError(f'base_path 含非法字符: {value!r}')
    return text


def url(base: str, path: str) -> str:
    """把站点根相对路径拼上前缀。path 必须是 '/xxx' 形式。"""
    if not path.startswith('/'):
        path = '/' + path
    return ('/' + base + path) if base else path


def cookie_path(base: str) -> str:
    """Cookie 的 path：带前缀时限定在前缀上，避免同 origin 多产品互踩。"""
    return ('/' + base) if base else '/'


def apply_to_handlers(handlers, base: str):
    """给 Tornado 的 handlers 列表中每条路由加前缀。

    Tornado 的 pattern 是对整个 path 做匹配（正则），所以直接在前缀上拼一段
    正则转义后的 base 即可；handler 与 kwargs 原样保留。
    """
    if not base:
        return list(handlers)
    prefix = '/' + re.escape(base)
    out = []
    for item in handlers:
        pattern, rest = item[0], list(item[1:])
        if isinstance(pattern, str) and pattern.startswith('/'):
            pattern = prefix + pattern
        out.append(tuple([pattern] + rest))
    return out


def application(handlers, **kwargs):
    """等价于 tornado.web.Application(handlers, **kwargs)，但路由自动加前缀。

    这样调用点只需改函数名，参数列表原样保留 —— 括号结构不动，改动面最小。
    """
    import tornado.web  # 惰性导入：本模块在纯测试环境下不需要 tornado
    return tornado.web.Application(apply_to_handlers(handlers, _ACTIVE_BASE), **kwargs)


_ACTIVE_BASE = ''
