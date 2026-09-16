"""补丁覆盖层（hotfix overlay）的单元测试。

运行：python3 -m unittest discover -s tests -v
（Windows 打包脚本 build.ps1 也会跑这套测试；失败会中止打包。）

覆盖的行为：
  * 覆盖层目录解析（环境变量 / 配置文件同级 / 显式指定）
  * www 覆盖文件查找 + 目录穿越防护
  * http 层：覆盖层文件真的替换了内置资源，未覆盖的仍回落到内置
  * 清单/哈希（给热修包的 manifest 与状态接口用）
"""

import hashlib
import importlib
import json
import os
import pathlib
import shutil
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import patch_overlay  # noqa: E402


class PatchOverlayTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="mrrc-patch-test-")
        self.patch_dir = os.path.join(self.tmp, "patch")
        self.bundled = os.path.join(self.tmp, "bundled")
        for rel in ("www/sub/original.js", "app/base.py"):
            target = os.path.join(self.bundled, rel)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(target, "w", encoding="utf-8") as fh:
                fh.write("bundled:" + rel)
        patch_overlay.configure(patch_dir=self.patch_dir, resource_dir=self.bundled,
                                runtime_dir=self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)
        os.environ.pop(patch_overlay.PATCH_DIR_ENV, None)
        patch_overlay._state["configured"] = False

    # ---- 路径解析 ----
    def test_explicit_patch_dir_wins(self):
        self.assertEqual(patch_overlay.patch_dir(), os.path.abspath(self.patch_dir))

    def test_env_var_used_when_no_explicit_dir(self):
        env_dir = os.path.join(self.tmp, "from-env")
        os.makedirs(os.path.join(env_dir, "vendor"))
        os.environ[patch_overlay.PATCH_DIR_ENV] = env_dir
        patch_overlay._state["configured"] = False
        patch_overlay.configure(resource_dir=self.bundled, runtime_dir=self.tmp)
        self.assertEqual(patch_overlay.patch_dir(), os.path.abspath(env_dir))
        self.assertEqual(patch_overlay.dll_dirs()[0], os.path.abspath(os.path.join(env_dir, "vendor")))

    def test_patch_dir_defaults_next_to_config(self):
        cfg = os.path.join(self.tmp, "MRRC.conf")
        patch_overlay._state["configured"] = False
        patch_overlay.configure(config_path=cfg, resource_dir=self.bundled, runtime_dir=self.tmp)
        self.assertEqual(patch_overlay.patch_dir(), os.path.join(os.path.abspath(self.tmp), "patch"))

    def test_missing_patch_dir_is_inactive_not_an_error(self):
        patch_overlay.configure(patch_dir=os.path.join(self.tmp, "nope"), resource_dir=self.bundled,
                                runtime_dir=self.tmp)
        info = patch_overlay.describe()
        self.assertFalse(info["active"])
        self.assertEqual(info["fileCount"], 0)
        self.assertEqual(patch_overlay.dll_dirs(), [])

    # ---- www 查找 ----
    def test_www_candidate_hit_and_miss(self):
        overlay = os.path.join(self.patch_dir, "www", "sub", "original.js")
        os.makedirs(os.path.dirname(overlay), exist_ok=True)
        with open(overlay, "w", encoding="utf-8") as fh:
            fh.write("patched")
        self.assertEqual(patch_overlay.www_candidate("sub/original.js"), overlay)
        self.assertIsNone(patch_overlay.www_candidate("sub/other.js"))
        self.assertIsNone(patch_overlay.www_candidate(""))

    def test_www_candidate_blocks_traversal(self):
        os.makedirs(os.path.join(self.tmp, "secret"), exist_ok=True)
        with open(os.path.join(self.tmp, "secret", "x.js"), "w", encoding="utf-8") as fh:
            fh.write("secret")
        self.assertIsNone(patch_overlay.www_candidate("../secret/x.js"))
        self.assertIsNone(patch_overlay.www_candidate("..\\secret\\x.js"))

    # ---- 清单 / 哈希 ----
    def test_list_overlay_files_and_hashes(self):
        for rel, content in (("www/a.js", "AAA"), ("app/m.py", "BBB")):
            target = os.path.join(self.patch_dir, rel)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(target, "w", encoding="utf-8") as fh:
                fh.write(content)
        files = patch_overlay.list_overlay_files(with_hash=True)
        self.assertEqual([f["path"] for f in files], ["app/m.py", "www/a.js"])
        import hashlib
        self.assertEqual(files[1]["sha256"], hashlib.sha256(b"AAA").hexdigest())
        self.assertEqual(patch_overlay.describe()["fileCount"], 2)

    def test_log_status_mentions_file_count(self):
        target = os.path.join(self.patch_dir, "www", "a.js")
        os.makedirs(os.path.dirname(target), exist_ok=True)
        open(target, "w", encoding="utf-8").write("A")
        lines = []
        patch_overlay.log_status(lines.append)
        self.assertEqual(len(lines), 1)
        self.assertIn("已启用", lines[0])
        self.assertIn("1", lines[0])

    # ---- sys.path 顺序 ----
    def test_apply_python_path_puts_overlay_first(self):
        os.makedirs(os.path.join(self.patch_dir, "app"), exist_ok=True)
        os.makedirs(os.path.join(self.bundled, "app"), exist_ok=True)
        ordered = patch_overlay.apply_python_path()
        overlay_app = os.path.join(self.patch_dir, "app")
        bundled_app = os.path.join(self.bundled, "app")
        self.assertEqual(ordered[0], overlay_app)
        self.assertLess(sys.path.index(overlay_app), sys.path.index(bundled_app))
        for path in ordered:
            sys.path.remove(path)

    # ---- DLL 搜索顺序 ----
    def test_dll_dirs_prefer_overlay(self):
        os.makedirs(os.path.join(self.patch_dir, "vendor"), exist_ok=True)
        dirs = patch_overlay.dll_dirs()
        self.assertEqual(dirs[0], os.path.join(self.patch_dir, "vendor"))
        self.assertIn(self.patch_dir, dirs)


class HttpOverlayTest(unittest.TestCase):
    """真实起一个 tornado 服务，验证覆盖层文件确实替换了内置资源。"""

    def setUp(self):
        try:
            from tornado.testing import AsyncHTTPTestCase
        except ImportError:                      # pragma: no cover - tornado 是运行依赖
            self.skipTest("tornado not installed")
        self.tmp = tempfile.mkdtemp(prefix="mrrc-patch-http-")
        self.bundled = os.path.join(self.tmp, "bundled")
        self.patch_dir = os.path.join(self.tmp, "patch")
        for rel, content in (("www/controls.js", "BUNDLED-JS"), ("www/keep.js", "KEEP")):
            target = os.path.join(self.bundled, rel)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(target, "w", encoding="utf-8") as fh:
                fh.write(content)
        overlay = os.path.join(self.patch_dir, "www", "controls.js")
        os.makedirs(os.path.dirname(overlay), exist_ok=True)
        with open(overlay, "w", encoding="utf-8") as fh:
            fh.write("HOTFIX-JS")
        patch_overlay.configure(patch_dir=self.patch_dir, resource_dir=self.bundled,
                                runtime_dir=self.tmp)

        import tornado.web
        from tornado.testing import AsyncHTTPTestCase
        from tornado.web import StaticFileHandler

        bundled = self.bundled

        class Handler(patch_overlay.OverlayStaticFilesMixin, StaticFileHandler):
            pass

        class HttpCase(AsyncHTTPTestCase):
            def get_app(self):
                return tornado.web.Application([
                    (r"/(.*)", Handler, {"path": os.path.join(bundled, "www")}),
                ])

            def runTest(self):          # unittest 需要一个测试方法
                pass

        self.http = HttpCase()
        self.http.setUp()

    def tearDown(self):
        try:
            self.http.tearDown()
        finally:
            shutil.rmtree(self.tmp, ignore_errors=True)
            patch_overlay._state["configured"] = False

    def test_overlay_file_replaces_bundled(self):
        response = self.http.fetch("/controls.js")
        self.assertEqual(response.code, 200)
        self.assertEqual(response.body.decode(), "HOTFIX-JS")

    def test_non_overlaid_file_falls_back_to_bundled(self):
        response = self.http.fetch("/keep.js")
        self.assertEqual(response.code, 200)
        self.assertEqual(response.body.decode(), "KEEP")

    def test_missing_file_is_404(self):
        self.assertEqual(self.http.fetch("/nope.js").code, 404)


if __name__ == "__main__":
    unittest.main(verbosity=2)


class MakeHotfixTest(unittest.TestCase):
    """热修包生成器：映射规则、拒绝规则、manifest/zip 内容。"""

    def setUp(self):
        import importlib.util
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "packaging", "hotfix", "make_hotfix.py")
        spec = importlib.util.spec_from_file_location("make_hotfix", path)
        self.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.mod)
        self.tmp = tempfile.mkdtemp(prefix="mrrc-hotfix-")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_classify_mapping(self):
        loose = ["wdsp_wrapper", "audio_interface"]
        self.assertEqual(self.mod.classify("www/controls.js", loose), ("www/controls.js", "www"))
        self.assertEqual(self.mod.classify("MRRC", loose), ("app/MRRC", "app"))
        self.assertEqual(self.mod.classify("wdsp_wrapper.py", loose),
                         ("app/wdsp_wrapper.py", "app"))
        self.assertEqual(self.mod.classify("vendor/wdsp/windows/bin/x64/libwdsp.dll", loose),
                         ("vendor/wdsp/windows/bin/x64/libwdsp.dll", "vendor"))
        # 不可热修
        self.assertIsNone(self.mod.classify("requirements.txt", loose))
        self.assertIsNone(self.mod.classify("windows/launcher.py", loose))
        self.assertIsNone(self.mod.classify("audioop.py", ["other_module"]))

    def test_spec_loose_modules_match_packaging(self):
        loose = self.mod.loose_app_modules()
        self.assertIn("wdsp_wrapper", loose)
        self.assertIn("audio_interface", loose)
        self.assertIn("patch_overlay", loose)

    def test_build_pack_writes_manifest_and_zip(self):
        out = pathlib.Path(self.tmp)
        result = self.mod.build_pack("9.9.9", ["www/mobile_modern.html", "patch_overlay.py"],
                                     notes="测试", requires="6.0.3", out_dir=out)
        pack = out / "hotfix-9.9.9.zip"
        self.assertTrue(pack.is_file())
        with zipfile.ZipFile(pack) as archive:
            names = set(archive.namelist())
            self.assertIn("manifest.json", names)
            self.assertIn("www/mobile_modern.html", names)
            self.assertIn("app/patch_overlay.py", names)
            manifest = json.loads(archive.read("manifest.json"))
            self.assertEqual(manifest["version"], "9.9.9")
            paths = {f["path"] for f in manifest["files"]}
            self.assertEqual(paths, {"www/mobile_modern.html", "app/patch_overlay.py"})
            for entry in manifest["files"]:
                data = archive.read(entry["path"])
                self.assertEqual(hashlib.sha256(data).hexdigest(), entry["sha256"])
        patch_json = json.loads((out / "patch.json").read_text(encoding="utf-8"))
        self.assertEqual(patch_json["latest"], "9.9.9")
        self.assertIn("hotfix-9.9.9.zip", patch_json["url"])
        self.assertEqual(patch_json["sha256"], hashlib.sha256(pack.read_bytes()).hexdigest())
        self.assertEqual(result["requires"], "6.0.3")
