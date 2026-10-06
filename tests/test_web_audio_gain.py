"""www 音频增益量程守卫（F13，2026-10-04）

差点发生的事故：`C_af`（接收音量滑块）量程从 **0-100** 改成 **0-1000** 之后，
`www/audio_rx.js::AudioRX_SetGAIN()` 仍按 `value/100` 换算 —— 对 0-1000 的滑块会算出
**5.0 的增益，把音量顶爆 10 倍**（`controls.js` 侧早已修好并留了注释，`audio_rx.js` 漏了）。
该文件已被标记 DEPRECATED、且没有任何页面加载它（`modern.html` 的 H17 已移除；原因是它与
tagged wire format 不兼容），所以这是"未爆发的死代码" —— 但死代码迟早会被复活，
量程必须与新约定一致。

本测试两层：
  ① 结构检查（无需 node）：量程声明 / 换算写法 / 废弃文件不得被页面加载；
  ② 行为检查（需要 node，没有则跳过）：把 `AudioRX_SetGAIN`、`normalizeCAfScale` 抽出来
     **真跑一遍**，验证 0-1000 → 0-1 的映射、旧量程的一次性迁移、以及越界值被夹紧。
"""

import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

WWW = REPO / "www"

# 量程约定（改这两个常量就等于改约定，测试跟着变）
CAF_MAX = 1000          # 接收音量滑块：0-1000，线性增益 = value/1000
CMG_MAX = 200           # 发射麦克风增益滑块：0-200，线性增益 = value/100 → 0-2.0

# node 行为测试的挂具：从源文件里按大括号配对抽出函数，塞进假的 DOM/localStorage 里执行。
NODE_HARNESS = r"""
const fs = require('fs');
function extract(src, name) {
  const idx = src.indexOf('function ' + name + '(');
  if (idx < 0) return '';
  let depth = 0, started = false;
  for (let j = src.indexOf('{', idx); j < src.length; j++) {
    if (src[j] === '{') { depth++; started = true; }
    else if (src[j] === '}') { depth--; if (started && depth === 0) return src.slice(idx, j + 1); }
  }
  return '';
}
function runOne(spec) {
  const src = fs.readFileSync(spec.file, 'utf8');
  const need = ['normalizeCAfScale', 'AudioRX_SetGAIN'];
  const code = need.map(n => extract(src, n)).filter(Boolean).join('\n\n');
  const store = {};
  if (spec.preMarker) store['mrrc_caf_scale_v2'] = '1';
  const got = {};
  const document = {
    getElementById: (id) => (spec.caf === null ? null : { value: String(spec.caf) }),
  };
  const localStorage = {
    getItem: (k) => (k in store ? store[k] : null),
    setItem: (k, v) => { store[k] = String(v); },
  };
  const AudioRX_gain_node = { gain: { setValueAtTime: (v) => { got.gain = v; } } };
  const AudioRX_context = { currentTime: 0 };
  const body = code
    + '\nreturn { setGain: typeof AudioRX_SetGAIN === "function" ? AudioRX_SetGAIN : null,'
    + ' normalize: typeof normalizeCAfScale === "function" ? normalizeCAfScale : null };';
  const fn = new Function('document', 'localStorage', 'poweron', 'AudioRX_gain_node',
                          'AudioRX_context', 'isFinite', 'parseFloat', 'Math',
                          body);
  const api = fn(document, localStorage, spec.poweron !== false, AudioRX_gain_node,
                 AudioRX_context, isFinite, parseFloat, Math);
  if (spec.call === 'normalize') {
    if (!api.normalize) throw new Error('找不到 normalizeCAfScale');
    return { value: api.normalize(spec.raw), store: store };
  }
  if (!api.setGain) throw new Error('找不到 AudioRX_SetGAIN: ' + spec.file);
  api.setGain();
  return { gain: got.gain === undefined ? null : got.gain, store: store };
}
const specs = JSON.parse(process.argv[2]);
const out = [];
for (const spec of specs) {
  try { out.push(runOne(spec)); }
  catch (e) { out.push({ error: String(e && e.message || e) }); }
}
process.stdout.write(JSON.stringify(out));
"""


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _without_html_comments(text: str) -> str:
    return re.sub(r"<!--.*?-->", "", text, flags=re.S)


def _without_line_comments(text: str) -> str:
    """只去掉整行注释，避免误伤含 `//` 的字符串（如 URL）。"""
    keep = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("*") or stripped.startswith("/*"):
            continue
        keep.append(line)
    return "\n".join(keep)


class AudioGainScaleStructureTest(unittest.TestCase):
    """① 结构检查：量程声明与换算写法。"""

    def test_deprecated_audio_rx_is_not_loaded_by_any_page(self):
        """audio_rx.js 已被标记 DEPRECATED（与 wire format 不兼容），页面不得再加载它。"""
        loaded = []
        for html in sorted(WWW.glob("*.html")):
            body = _without_html_comments(_read(html))
            if re.search(r"""src\s*=\s*["']audio_rx\.js["']""", body):
                loaded.append(html.name)
        self.assertEqual(loaded, [], f"这些页面又加载了废弃的 audio_rx.js：{loaded}")

    def test_caf_range_declared_consistently(self):
        """每个 C_af 滑块都必须声明 min=0 / max=1000（否则换算与用户预期不符）。"""
        checked, bad = 0, []
        for html in sorted(WWW.glob("*.html")):
            for tag in re.findall(r"<input[^>]*id=[\"']C_af[\"'][^>]*>", _read(html)):
                checked += 1
                if f'max="{CAF_MAX}"' not in tag or 'min="0"' not in tag:
                    bad.append(f"{html.name}: {tag[:90]}")
        self.assertGreater(checked, 0, "没找到任何 C_af 滑块，路径可能写错")
        self.assertEqual(bad, [], "C_af 量程不是 0-1000：\n" + "\n".join(bad))

    def test_no_legacy_caf_div_by_100(self):
        """C_af 的增益必须是 /1000；出现 /100（旧量程）会把音量顶爆 10 倍。"""
        offenders = []
        for path in sorted(list(WWW.glob("*.js")) + list(WWW.glob("*.html"))):
            text = _without_line_comments(_read(path))
            text = _without_html_comments(text) if path.suffix == ".html" else text
            for n, line in enumerate(text.splitlines(), 1):
                if "C_af" not in line:
                    continue
                if re.search(r"/\s*100(?![0-9])", line) or re.search(r"\*\s*100\b", line):
                    offenders.append(f"{path.name}:{n}: {line.strip()[:100]}")
        self.assertEqual(offenders, [], "C_af 又出现了旧量程换算：\n" + "\n".join(offenders))

    def test_cmg_scale_declared_and_applied_consistently(self):
        """发射麦克风增益滑块 0-200 → /100 得 0-2.0；声明与调用点都不能串档。"""
        bad = []
        for html in sorted(WWW.glob("*.html")):
            for tag in re.findall(r"<input[^>]*id=[\"']C_mg[\"'][^>]*>", _read(html)):
                if f'max="{CMG_MAX}"' not in tag or 'min="0"' not in tag:
                    bad.append(f"{html.name}: {tag[:90]}")
        offenders = []
        for path in sorted(list(WWW.glob("*.js")) + list(WWW.glob("*.html"))):
            text = _without_line_comments(_read(path))
            for n, line in enumerate(text.splitlines(), 1):
                m = re.search(r"AudioTX_SetGAIN\s*\(([^)]*)\)", line)
                if not m:
                    continue
                arg = m.group(1)
                if re.search(r"/\s*1000\b", arg) or re.search(r"\*\s*100\b", arg):
                    offenders.append(f"{path.name}:{n}: {line.strip()[:100]}")
        self.assertEqual(bad + offenders, [],
                         "C_mg 量程/换算不一致：\n" + "\n".join(bad + offenders))


class AudioGainScaleBehaviourTest(unittest.TestCase):
    """② 行为检查：用 node 实跑两个 AudioRX_SetGAIN 实现。"""

    def _run_node(self, cases):
        node = shutil.which("node")
        if not node:
            self.skipTest("未安装 node，跳过音频增益的行为验证")
        with tempfile.TemporaryDirectory() as tmp:
            harness = Path(tmp) / "harness.js"
            harness.write_text(NODE_HARNESS, encoding="utf-8")
            proc = subprocess.run([node, str(harness), json.dumps(cases)],
                                  capture_output=True, text=True, timeout=60)
            self.assertEqual(proc.returncode, 0, f"node 执行失败：{proc.stderr[:400]}")
            return json.loads(proc.stdout)

    def _expect(self, impl, caf, want, pre_marker=False, label=""):
        impl_file = str(WWW / impl)
        result = self._run_node([{"file": impl_file, "caf": caf, "preMarker": pre_marker}])[0]
        self.assertNotIn("error", result, f"{impl}{label} 执行出错：{result.get('error')}")
        self.assertAlmostEqual(result["gain"], want, places=4,
                               msg=f"{impl}（C_af={caf}{label}）算出增益 {result['gain']}，期望 {want}")

    def test_caf_maps_to_linear_gain(self):
        """0-1000 → 0-1 的线性映射；越界值夹紧；取不到元素时用 0.5 默认值。"""
        for impl in ("controls.js", "audio_rx.js"):
            for caf, want in ((0, 0.0), (250, 0.25), (500, 0.5), (1000, 1.0),
                              (5000, 1.0), (None, 0.5)):
                with self.subTest(impl=impl, caf=caf):
                    self._expect(impl, caf, want)

    def test_controls_setgain_does_not_migrate_itself(self):
        """controls.js 的约定：迁移发生在读 cookie 的那一步（ui_utils.js → normalizeCAfScale），
        SetGAIN 只按新量程换算 —— 元素里的值已经是 0-1000。这里把它钉死，避免两边各写一套。"""
        self._expect("controls.js", 100, 0.1)                       # 新量程的 10%
        self._expect("controls.js", 100, 0.1, pre_marker=True)

    def test_normalize_caf_scale_migrates_once(self):
        """ui_utils.js 调用的一次性迁移：旧量程（0-100）×10，且只迁一次。"""
        impl_file = str(WWW / "controls.js")

        def norm(raw, pre_marker=False):
            spec = {"file": impl_file, "raw": raw, "call": "normalize", "preMarker": pre_marker}
            result = self._run_node([spec])[0]
            self.assertNotIn("error", result, f"normalizeCAfScale({raw}) 出错：{result.get('error')}")
            return result["value"]

        self.assertEqual(norm(100), 1000)          # 旧量程满刻度 → 迁移后满刻度
        self.assertEqual(norm(50), 500)            # 旧量程 50% → 新量程 50%
        self.assertEqual(norm(100, pre_marker=True), 100)      # 迁移过：不再 ×10
        self.assertEqual(norm(500, pre_marker=True), 500)      # 新量程值原样
        self.assertEqual(norm(None), 500)          # 取不到 → 0.5 默认

    def test_audio_rx_standalone_migrates_legacy_values(self):
        """audio_rx.js 是独立文件（没有 ui_utils.js 的 cookie 恢复路径），所以它自带同一把尺：
        有 controls.js 的 helper 时用它，没有时自己做一次性迁移 —— 两条路径都要对。
        已知歧义（与 controls.js 的 helper 相同）：新量程下 ≤100 的小音量，若迁移标记丢失
        会被当成旧量程放大一次；一键清理 localStorage 后偶发，重建音量即可。
        """
        with self.subTest(phase="首次（未迁移）→ 旧量程满刻度"):
            self._expect("audio_rx.js", 100, 1.0)
        with self.subTest(phase="已迁移过 → 不再 ×10"):
            self._expect("audio_rx.js", 100, 0.1, pre_marker=True)
        with self.subTest(phase="新量程大音量不受迁移影响"):
            self._expect("audio_rx.js", 250, 0.25)
            self._expect("audio_rx.js", 1000, 1.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
