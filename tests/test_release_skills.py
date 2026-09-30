"""发布技能（.pi/skills/*）的一致性测试。

技能是给人读的散文，但它里面的仓库路径、命令、权威声明都是"事实"。
这些事实会在文件改名/删除后悄悄失效——本测试把它们钉住。
"""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS_DIR = ROOT / ".pi" / "skills"

RELEASE_SKILLS = ("mrrc-release", "windows-installer")

# 会被校验存在性的顶层目录（只认这些，避免把 dist/ 之类运行时路径误判）
REPO_DIRS = ("dev_tools/", "packaging/", "windows/", "macos/", "www/",
             "website/", "tests/", "docs/", ".pi/", "DSP/", "certs/")

FRONTMATTER = re.compile(r"^---\n(.*?)\n---\n", re.S)


def read_skill(name):
    return (SKILLS_DIR / name / "SKILL.md").read_text(encoding="utf-8")


def frontmatter(text):
    m = FRONTMATTER.match(text)
    if not m:
        raise AssertionError("SKILL.md 缺少 YAML frontmatter")
    fields = {}
    for line in m.group(1).splitlines():
        if ":" in line and not line.startswith(" "):
            key, _, value = line.partition(":")
            fields[key.strip()] = value.strip()
    if "metadata" in m.group(1):
        meta = re.search(r"metadata:\n((?:  .*\n)+)", m.group(1))
        if meta:
            fields["_metadata"] = meta.group(1)
    return fields


def referenced_repo_paths(text):
    """取出反引号里、以已知顶层目录开头的仓库相对路径。"""
    found = set()
    for token in re.findall(r"`([^`\n]+)`", text):
        token = token.strip()
        if not any(token.startswith(d) for d in REPO_DIRS):
            continue
        if any(ch in token for ch in "*<>%$?") or " " in token:
            continue          # glob / 占位符 / 环境变量路径不是文件
        token = token.split(":")[0].rstrip(".,;")
        found.add(token)
    return found


class SkillFrontmatterTests(unittest.TestCase):
    def test_all_release_skills_exist(self):
        for name in RELEASE_SKILLS:
            with self.subTest(skill=name):
                self.assertTrue((SKILLS_DIR / name / "SKILL.md").is_file())

    def test_frontmatter_matches_mrrc_house_style(self):
        for name in RELEASE_SKILLS:
            with self.subTest(skill=name):
                text = read_skill(name)
                fm = frontmatter(text)
                self.assertEqual(fm.get("name"), name,
                                 "frontmatter name 必须等于目录名（sync_skills.sh 依赖）")
                self.assertIn("license", fm)
                self.assertIn("metadata", fm)
                self.assertIn("repo: HAM/mrrc", fm["_metadata"])
                desc = fm.get("description", "")
                self.assertTrue(desc.endswith("使用。"),
                                "description 需以“使用。”收尾（mrrc 文风）")
                self.assertGreater(len(desc), 40)


class SkillFactTests(unittest.TestCase):
    def test_referenced_repo_paths_exist(self):
        for name in RELEASE_SKILLS:
            for rel in sorted(referenced_repo_paths(read_skill(name))):
                with self.subTest(skill=name, path=rel):
                    self.assertTrue((ROOT / rel).exists(),
                                    f"{name} 引用了不存在的路径：{rel}")

    def test_release_skill_states_the_real_authority(self):
        """版本权威必须是 iss 的 MyAppVersion，且必须警告别沿用 mrrc_modern 的习惯。"""
        text = read_skill("mrrc-release")
        self.assertIn("packaging/windows/MRRC.iss", text)
        self.assertIn("MyAppVersion", text)
        self.assertIn("mrrc_modern", text)

    def test_release_skill_uses_the_checker(self):
        text = read_skill("mrrc-release")
        self.assertIn("dev_tools/release_check.py", text)
        self.assertIn("--strict", text)

    def test_release_skill_demands_explicit_requires(self):
        """热修包的 requires 默认值是陷阱，技能必须点名。"""
        text = read_skill("mrrc-release")
        self.assertIn("--requires", text)
        self.assertIn("6.0.3", text)

    def test_release_skill_covers_the_hotfix_publish_step(self):
        """静默失败的那一步：把补丁放到站点。"""
        text = read_skill("mrrc-release")
        self.assertIn("dist/hotfix", text)
        self.assertIn("website/downloads", text)
        self.assertIn("patch.json", text)

    def test_release_skill_records_the_site_must_be_in_git(self):
        """rsync --delete 会清掉没入库的站点文件（2026-09-16 真实事故）。"""
        text = read_skill("mrrc-release")
        self.assertIn("rsync --delete", text)
        self.assertIn("previous", text)

    def test_release_skill_records_the_tmp_size_trap(self):
        text = read_skill("mrrc-release")
        self.assertIn("454 MB tmpfs", text)

    def test_release_skill_points_at_the_hotfixable_file_table(self):
        """决定“发版还是热修”的依据表必须被指名。"""
        text = read_skill("mrrc-release")
        self.assertIn("release-process.md", text)

    def test_release_skill_requires_server_side_hash_check(self):
        text = read_skill("mrrc-release")
        self.assertIn("sha256sum", text)
        self.assertIn("installer.sha256", text)

    def test_windows_skill_names_the_real_gate_script(self):
        text = read_skill("windows-installer")
        self.assertIn("packaging/windows/build.ps1", text)
        self.assertIn("_APP_MODULES", text)

    def test_windows_skill_demands_artifact_proof(self):
        """退出码不是证据——技能必须教人去认产物。"""
        text = read_skill("windows-installer")
        self.assertIn("Get-FileHash", text)
        self.assertIn("version.txt", text)
        self.assertIn("CArchiveReader", text)

    def test_windows_skill_release_script_line_refs_are_current(self):
        """技能正文里的 release_windows.sh 行号必须指向它自称的那一行。

        Task 2 写技能时 :83/:86 是对的；Task 3 给 release_windows.sh 加了一行，
        行号随即漂到 :84/:87——路径存在性测试抓不到这种任务间漂移，本测试把
        每条行号引用钉到它引用内容所在的行上。
        """
        text = read_skill("windows-installer")
        rw_lines = (ROOT / "dev_tools" / "release_windows.sh").read_text(
            encoding="utf-8", errors="replace").splitlines()
        cases = [
            (r"`release_windows\.sh:(\d+)` 只把 `build exit=", "build exit="),
            (r"`release_windows\.sh:(\d+)` 会在打包产物上跑", "verify_hotfix.py"),
        ]
        for pattern, needle in cases:
            with self.subTest(needle=needle):
                m = re.search(pattern, text)
                if m is None:
                    self.fail(f"技能里找不到 {needle!r} 的行号引用（pattern={pattern!r}）——"
                              "若改了措辞，请同步本测试的锚点")
                n = int(m.group(1))
                self.assertLessEqual(n, len(rw_lines))
                self.assertIn(needle, rw_lines[n - 1],
                              f"技能说 release_windows.sh:{n} 是 {needle!r}，"
                              f"实际该行是：{rw_lines[n - 1].strip()[:90]!r}")


class SkillSyncTests(unittest.TestCase):
    def test_sync_script_targets_the_skills_dir(self):
        text = (ROOT / "dev_tools" / "sync_skills.sh").read_text(encoding="utf-8")
        self.assertIn(".pi/skills", text)
        self.assertIn("~/.pi", text.replace("${HOME}", "~"))


if __name__ == "__main__":
    unittest.main()
