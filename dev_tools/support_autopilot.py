#!/usr/bin/env python3
"""MRRC 产品支持自动驾驶（support autopilot）

端到端闭环：**轮询接收端 → 取最新上报 → 交给 pi 分析 → 生成答复卡 → 发布答复页**。

配套 skill：`.pi/skills/mrrc-product-support/SKILL.md`（判定规则与答复格式）

用法
----
    # 检查并处理新上报（默认只分析、不发布）
    python3 dev_tools/support_autopilot.py --once

    # 处理并自动发布（commit + deploy_website.sh）
    python3 dev_tools/support_autopilot.py --once --publish

    # 强制重跑某条（只分析不发布；加 --publish 才发）
    python3 dev_tools/support_autopilot.py --id 20260917-062314-35dc --force

    # 一键诊断包的内容也能先看一眼（不调用 pi）
    python3 dev_tools/support_autopilot.py --inspect 20260917-062314-35dc

    # 安装 crontab（默认每 10 分钟）与查看状态
    python3 dev_tools/support_autopilot.py --install-cron 10
    python3 dev_tools/support_autopilot.py --status
    python3 dev_tools/support_autopilot.py --uninstall-cron

设计要点
--------
* **幂等**：已处理的上报 id 记在 state.json，重复运行不会重复回答；
* **不擅自发布**：默认 `--publish` 关闭（只产出答复卡草稿到 ``dist/support_answers/``）；
* **可热修的那套安全约定**：答复页只放可公开结论，凭据只从本地文件读；
* **失败不影响 cron**：任何异常都写日志并以 0 退出（除配置缺失）。
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

LIST_URL = "https://www.vlsc.net/mrrc/support/api/list"
ANSWER_BASE = "https://www.vlsc.net/mrrc/answers/#"
ANSWERS_PAGE = REPO / "website" / "answers" / "index.html"
CREDS = Path.home() / ".mrrc-support-credentials.txt"
DATA_DIR = Path.home() / ".mrrc-support-autopilot"
STATE = DATA_DIR / "state.json"
RUN_LOG = DATA_DIR / "autopilot.log"
DRAFTS = REPO / "dist" / "support_answers"
SKILL = ".pi/skills/mrrc-product-support/SKILL.md"

class NonBundlePayload(RuntimeError):
    """该上报没有可分析的诊断包主体（半包/仅元数据）。"""


# 单次运行最多自动处理几条（防止一次涌入大量上报时长时间占用）
MAX_PER_RUN = 2
PI_TIMEOUT = 900          # pi 单条分析上限（秒）
HTTP_TIMEOUT = 90


# --------------------------------------------------------------------------- #
# 基础设施
# --------------------------------------------------------------------------- #
def log(msg: str) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}"
    print(line, flush=True)
    try:
        with open(RUN_LOG, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError:
        pass


def load_state() -> dict:
    try:
        data = json.loads(STATE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_state(state: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(STATE)


def password() -> str:
    try:
        return CREDS.read_text(encoding="utf-8").strip().splitlines()[0].strip()
    except Exception:
        return ""


def http_get(url: str, auth: bool = True) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "mrrc-support-autopilot/1.0"})
    if auth:
        pw = password()
        if pw:
            token = base64.b64encode(f"mrrc:{pw}".encode()).decode()
            req.add_header("Authorization", f"Basic {token}")
    with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
        return resp.read()


# --------------------------------------------------------------------------- #
# 接收端：列表 / 取包
# --------------------------------------------------------------------------- #
def list_reports() -> list[dict]:
    """解析接收端列表页（HTML）。返回 [{id, size, version, problem}, ...] 新→旧。"""
    html = http_get(LIST_URL).decode("utf-8", "replace")
    out = []
    for blk in re.findall(r"<li>(.*?)</li>", html, re.S):
        m = re.search(r"<b>([^<]+)</b>", blk)
        if not m:
            continue
        rid = m.group(1).strip()
        prob = re.search(r"class='p'>([^<]*)</span>", blk)
        meta = re.search(r"·\s*([0-9.]+ ?[KMG]B)\s*·\s*([0-9.]+)\s*·", blk)
        out.append({
            "id": rid,
            "problem": (prob.group(1).strip() if prob else ""),
            "size": (meta.group(1).strip() if meta else ""),
            "version": (meta.group(2).strip() if meta else ""),
        })
    return out


def fetch_bundle(rid: str, dest_dir: Path) -> Path:
    """下载并解包一条上报，返回解包目录。"""
    dest_dir.mkdir(parents=True, exist_ok=True)
    raw = http_get(f"https://www.vlsc.net/mrrc/support/api/{urllib.parse.quote(rid)}/bundle")
    zip_path = dest_dir / "bundle.zip"
    zip_path.write_bytes(raw)
    import zipfile
    try:
        zf = zipfile.ZipFile(zip_path)
    except zipfile.BadZipFile:
        raise NonBundlePayload(f"载荷不是 zip（{len(raw)} 字节，可能是只上传了元数据的半包）")
    with zf:
        for name in zf.namelist():
            # 防穿越：只解到 dest_dir 内
            target = (dest_dir / name).resolve()
            if str(target).startswith(str(dest_dir.resolve())):
                zf.extract(name, dest_dir)
    return dest_dir


# --------------------------------------------------------------------------- #
# 摘要：给 pi 的最小必要上下文（不是把整个包塞进去）
# --------------------------------------------------------------------------- #
def _read(path: Path, limit: int = 4000) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    return text if len(text) <= limit else text[:limit] + f"\n…（截断，原长 {len(text)}）"


def build_digest(bundle_dir: Path, meta: dict) -> str:
    """把诊断包压缩成给模型看的摘要：结论 + 关键证据 + 必要配置。"""
    import support_bundle as sb                     # 复用仓库里的摘要逻辑（可热修）

    log_path = bundle_dir / "logs" / "server-stdout.log"
    log_text = ""
    try:
        log_text = log_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        pass
    auto = sb.summarize_log(log_text, freshness_hours=0.02) if log_text else "（无服务端日志）"

    tail = "\n".join(log_text.splitlines()[-40:]) if log_text else "（无）"
    return "\n".join([
        f"# 上报编号\n{meta.get('id','')}",
        f"# 用户描述\n{_read(bundle_dir / 'problem.txt', 800) or '（空）'}",
        f"# 元信息\n体积={meta.get('size','?')} 上报版本={meta.get('version','?')}",
        f"# 自动体检摘要（工具生成，可信）\n{auto}",
        f"# 环境快照 diagnostics/env.json\n{_read(bundle_dir / 'diagnostics' / 'env.json', 2500)}",
        f"# 脱敏配置 state/config-redacted.ini\n{_read(bundle_dir / 'state' / 'config-redacted.ini', 2500)}",
        f"# 服务端日志末尾 40 行\n{tail}",
    ])


# --------------------------------------------------------------------------- #
# 分析：调用 pi（非交互）
# --------------------------------------------------------------------------- #
PROMPT_TEMPLATE = """你是 MRRC 项目的支持工程师。下面是用户通过「🐞 遇到问题」上传的诊断包摘要。
请阅读仓库里的 skill：{skill}（判定规则与答复格式），以及需要的仓库文件，然后给出结论。

要求：
1. 只输出**一个 JSON 对象**（不要任何解释文字、不要 markdown 代码块围栏），字段：
   {{
     "verdict": "一句话结论（中文，≤40字）",
     "status": "answered|needs_fix|need_more_info",
     "category": "环境|使用问题|产品缺陷|网络|升级|音频|电台|其他",
     "diagnosis": ["诊断要点，每条一句，最多5条，附关键证据"],
     "solution": ["用户可执行步骤，最多6条，按顺序"],
     "evidence": ["支撑结论的原始行/字段，最多5条，必须来自上面材料"],
     "keys": ["搜索关键词，含编号、用户原话、现象词，8~14个"],
     "needs_code_change": false,
     "code_hint": "若需要改代码：指出文件与函数（没有就空字符串）"
   }}
2. 判定要保守：材料不足时给 "need_more_info"，并把"需要用户补充什么"写进 solution。
3. 只有确实属于产品缺陷时才 needs_fix=true；环境类（无声卡、无 rigctld、虚拟机、
   未接电台、缺少外部程序）属于"环境"，不要判成缺陷。
4. solution 必须是用户自己能做的动作（不要写"等维护者修改"）。
5. 不要泄露凭据；不要把配置原文大段贴出来。

诊断包摘要如下：
--------
{digest}
--------
"""


def pi_binary() -> str:
    """定位 pi 可执行文件（cron 的 PATH 很窄，必须显式解析）。"""
    env = os.environ.get("PI_BIN")
    if env and Path(env).exists():
        return env
    found = shutil.which("pi")
    if found:
        return found
    for cand in ("/opt/homebrew/bin/pi", "/usr/local/bin/pi",
                 str(Path.home() / ".hermes/node/bin/pi"),
                 str(Path.home() / ".local/bin/pi")):
        if Path(cand).exists():
            return cand
    raise RuntimeError("找不到 pi 可执行文件（设 PI_BIN 环境变量，或把 pi 装到 PATH 里）")


def run_pi(digest: str, rid: str, model: str = "") -> dict:
    """调用 pi 非交互分析，返回解析后的 JSON。"""
    prompt = PROMPT_TEMPLATE.format(skill=SKILL, digest=digest)
    cmd = [pi_binary(), "--name", f"support-{rid}", "--tools", "read,grep,find,ls",
           "--thinking", "high", "-p", prompt]
    if model:
        cmd[1:1] = ["--model", model]
    log(f"[{rid}] 调用 pi 分析（超时 {PI_TIMEOUT}s）…")
    proc = subprocess.run(cmd, cwd=str(REPO), capture_output=True, text=True,
                          timeout=PI_TIMEOUT)
    out = (proc.stdout or "") + "\n" + (proc.stderr or "")
    if proc.returncode != 0:
        log(f"[{rid}] pi 退出码 {proc.returncode}")
    data = _extract_json(out)
    if not data:
        raise RuntimeError(f"pi 未返回可解析 JSON（输出末尾：{out[-400:].strip()}）")
    return data


def _extract_json(text: str) -> dict | None:
    """从模型输出里抽出最后一个完整 JSON 对象（容忍围栏/前后噪声）。"""
    if not text:
        return None
    text = re.sub(r"```(?:json)?", "", text)
    starts = [m.start() for m in re.finditer(r"\{", text)]
    for start in reversed(starts):
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        data = json.loads(text[start:i + 1])
                        if isinstance(data, dict) and "verdict" in data:
                            return data
                    except Exception:
                        pass
                    break
    return None


# --------------------------------------------------------------------------- #
# 渲染 + 插入答复页
# --------------------------------------------------------------------------- #
def _esc(text: str) -> str:
    return (str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def render_card(rid: str, meta: dict, answer: dict, created: str = "") -> str:
    status = str(answer.get("status") or "answered")
    pill = {"answered": ("ok", "已答复"),
            "needs_fix": ("no", "已答复 · 待修复"),
            "need_more_info": ("", "需要补充信息")}.get(status, ("", "已答复"))
    cat = _esc(answer.get("category") or "")
    keys = " ".join([rid, str(meta.get("problem") or ""), cat, *map(str, answer.get("keys") or [])])

    def items(key: str, ordered: bool) -> str:
        vals = [str(v) for v in (answer.get(key) or [])]
        if not vals:
            return ""
        tag = "ol" if ordered else "ul"
        return f"    <{tag}>\n" + "\n".join(f"      <li>{_esc(v)}</li>" for v in vals) + f"\n    </{tag}>\n"

    return f'''  <div class="card" data-keys="{_esc(keys)}">
    <div class="row" style="justify-content:space-between">
      <h3 style="margin:0">编号 <span class="id">{_esc(rid)}</span></h3>
      <span class="pill {pill[0]}">{pill[1]}{(' · ' + cat) if cat else ''}</span>
    </div>
    <p class="muted" style="margin:8px 0 2px">上报时间 {_esc(created or '—')} · 描述：<strong>{_esc(meta.get('problem') or '（未填写）')}</strong></p>
    <p class="muted" style="margin:2px 0 10px">上报版本 {_esc(meta.get('version') or '?')} · 包体积 {_esc(meta.get('size') or '?')}</p>

    <h3>结论</h3>
    <p>{_esc(answer.get('verdict') or '')}</p>

    <h3>诊断</h3>
{items('diagnosis', False)}
    <h3>你要做的</h3>
{items('solution', True)}
    <h3>证据（原始行）</h3>
{items('evidence', False)}
  </div>

'''


def insert_card(card_html: str) -> bool:
    """把卡片插到答复列表最前面（最新在上）。"""
    page = ANSWERS_PAGE.read_text(encoding="utf-8")
    marker = '  <h2>答复列表</h2>\n\n'
    if marker not in page:
        raise RuntimeError("答复页缺少 '答复列表' 锚点")
    page = page.replace(marker, marker + card_html, 1)
    ANSWERS_PAGE.write_text(page, encoding="utf-8")
    return True


def publish(rid: str) -> None:
    """提交并部署答复页。"""
    subprocess.run(["git", "add", "website/answers/index.html"], cwd=str(REPO), check=True)
    subprocess.run(["git", "commit", "-m",
                    f"support(answers): 自动答复 {rid}（support autopilot）"],
                   cwd=str(REPO), check=True)
    subprocess.run(["git", "push", "origin", "main"], cwd=str(REPO), check=True)
    subprocess.run(["./deploy_website.sh"], cwd=str(REPO), check=True)
    log(f"[{rid}] 已发布并部署")


# --------------------------------------------------------------------------- #
# 主流程
# --------------------------------------------------------------------------- #
def process_one(rep: dict, publish_it: bool, model: str) -> str:
    rid = rep["id"]
    state = load_state()
    work = Path(tempfile.mkdtemp(prefix=f"mrrc-support-{rid}-"))
    try:
        bundle = fetch_bundle(rid, work)
        digest = build_digest(bundle, rep)
        DRAFTS.mkdir(parents=True, exist_ok=True)
        (DRAFTS / f"{rid}.digest.md").write_text(digest, encoding="utf-8")

        answer = run_pi(digest, rid, model=model)
        (DRAFTS / f"{rid}.answer.json").write_text(
            json.dumps(answer, ensure_ascii=False, indent=2), encoding="utf-8")

        manifest = {}
        try:
            manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
        except Exception:
            pass
        card = render_card(rid, rep, answer, created=str(manifest.get("createdAt") or ""))
        (DRAFTS / f"{rid}.card.html").write_text(card, encoding="utf-8")

        if publish_it:
            insert_card(card)
            log(f"[{rid}] 答复卡已插入答复页（{answer.get('status')} / {answer.get('category')}）")
        else:
            log(f"[{rid}] 未改动答复页（草稿见 {DRAFTS}/{rid}.card.html）")
        if answer.get("needs_code_change"):
            log(f"[{rid}] ⚠️ 需改代码：{answer.get('code_hint') or '（未指明）'}")

        done = state.setdefault("done", {})
        done[rid] = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                     "status": answer.get("status"),
                     "category": answer.get("category"),
                     "published": bool(publish_it)}
        save_state(state)

        if publish_it:
            publish(rid)
        else:
            log(f"[{rid}] 未发布（加 --publish 才发）。草稿：{DRAFTS}/{rid}.card.html")
        return "published" if publish_it else "drafted"
    finally:
        shutil.rmtree(work, ignore_errors=True)


def cmd_once(args) -> int:
    if not password():
        log("⚠️ 找不到接收端口令（~/.mrrc-support-credentials.txt）——跳过本轮")
        return 0
    state = load_state()
    done = state.setdefault("done", {})
    try:
        reports = list_reports()
    except Exception as exc:
        log(f"⚠️ 拉取上报列表失败（忽略本轮）：{type(exc).__name__}: {exc}")
        return 0

    todo = [r for r in reports if args.force or r["id"] not in done]
    if args.id:
        todo = [r for r in reports if r["id"] == args.id] or \
               ([{"id": args.id, "problem": "(仅给 id，未在列表中找到)", "size": "?", "version": "?"}]
                if args.force else [])
    todo = todo[:MAX_PER_RUN if not args.id else 1]
    if not todo:
        log(f"没有新上报（共 {len(reports)} 条，已处理 {len(done)} 条）")
        return 0

    log(f"发现 {len(todo)} 条待处理：{[r['id'] for r in todo]}")
    for rep in todo:
        try:
            process_one(rep, publish_it=args.publish, model=args.model)
        except NonBundlePayload as exc:
            done = load_state().setdefault("done", {})
            done[rep["id"]] = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                               "status": "skip", "category": "半包",
                               "published": False, "note": str(exc)}
            save_state(load_state())
            log(f"[{rep['id']}] ⏭️ 跳过：{exc}")
        except subprocess.TimeoutExpired:
            log(f"[{rep['id']}] ❌ pi 分析超时（{PI_TIMEOUT}s），留待下一轮")
        except Exception as exc:
            log(f"[{rep['id']}] ❌ 处理失败：{type(exc).__name__}: {exc}")
    state = load_state()
    state["lastRun"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    save_state(state)
    return 0


def cmd_inspect(args) -> int:
    rid = args.inspect
    work = Path(tempfile.mkdtemp(prefix=f"mrrc-support-{rid}-"))
    try:
        bundle = fetch_bundle(rid, work)
        print(build_digest(bundle, {"id": rid, "size": "?", "version": "?"}))
        print(f"\n（解包目录：{bundle}）")
    finally:
        pass
    return 0


def cmd_status(args) -> int:
    state = load_state()
    done = state.get("done", {})
    print(f"状态文件：{STATE}")
    print(f"已处理：{len(done)} 条")
    for rid, info in list(done.items())[-10:]:
        print(f"  {rid}  {info.get('at','')}  {info.get('status','')}  "
              f"{info.get('category','')}  published={info.get('published')}")
    print(f"最近运行：{state.get('lastRun','—')}")
    print(f"运行日志：{RUN_LOG}")
    print(f"草稿目录：{DRAFTS}")
    return 0


CRON_MARK = "# MRRC support autopilot"


def cmd_install_cron(args) -> int:
    minutes = max(1, int(args.install_cron))
    # cron 的 PATH 很窄：python 用仓库 venv 的绝对路径，PATH 里显式带上 pi 所在目录，
    # 否则会拿到系统 Python（版本/依赖不同）并且找不到 pi。
    py = REPO / "venv" / "bin" / "python3"
    py = str(py) if py.exists() else "/usr/bin/env python3"
    path = f"{Path.home()}/.hermes/node/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
    line = (f"*/{minutes} * * * * cd {REPO} && PATH={path} {py} dev_tools/support_autopilot.py "
            f"--once --publish >> {RUN_LOG} 2>&1 {CRON_MARK}")
    cur = subprocess.run(["crontab", "-l"], capture_output=True, text=True).stdout
    kept = [l for l in cur.splitlines() if CRON_MARK not in l]
    new = "\n".join(kept + [line]).strip() + "\n"
    subprocess.run(["crontab", "-"], input=new, text=True, check=True)
    print(f"✅ crontab 已安装（每 {minutes} 分钟）：\n{line}")
    return 0


def cmd_uninstall_cron(args) -> int:
    cur = subprocess.run(["crontab", "-l"], capture_output=True, text=True).stdout
    kept = [l for l in cur.splitlines() if CRON_MARK not in l]
    subprocess.run(["crontab", "-"], input="\n".join(kept).strip() + "\n", text=True, check=True)
    print("✅ crontab 条目已移除")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="MRRC 产品支持自动驾驶")
    ap.add_argument("--once", action="store_true", help="检查并处理新上报")
    ap.add_argument("--publish", action="store_true", help="分析后自动提交并部署答复页")
    ap.add_argument("--id", default="", help="只处理指定编号")
    ap.add_argument("--force", action="store_true", help="忽略已处理记录")
    ap.add_argument("--model", default="", help="传给 pi 的 --model")
    ap.add_argument("--inspect", default="", metavar="ID", help="只打印某条上报的摘要")
    ap.add_argument("--status", action="store_true", help="显示状态")
    ap.add_argument("--install-cron", nargs="?", const="10", default="",
                    metavar="MIN", help="安装 crontab（默认每 10 分钟）")
    ap.add_argument("--uninstall-cron", action="store_true", help="移除 crontab 条目")
    args = ap.parse_args()

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if args.install_cron:
        return cmd_install_cron(args)
    if args.uninstall_cron:
        return cmd_uninstall_cron(args)
    if args.status:
        return cmd_status(args)
    if args.inspect:
        return cmd_inspect(args)
    if args.once or args.id:
        return cmd_once(args)
    ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
