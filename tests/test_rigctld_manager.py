"""rigctld 生命周期管理单元测试。

背景（2026-09-17 用户上报 20260917-073700-14ef / 20260917-085736-ebd2，两次同因）：
Windows 安装版既不带 rigctld.exe 也没人拉起它 → TRXRIG 探测 127.0.0.1:4532 失败 →
"Running in simulation mode"，用户看到的就是"连不上电台"。修好之后：

  * 配置里指向哪台电台，就按 [INSTANCE_SETTINGS] instance_rigctl_* → [HAMLIB] 的顺序
    组装 rigctld 参数（与 mrrc_control.sh 同源，不能各写一套）；
  * 已经有监听者时**绝不抢端口**（macOS 的 mrrc_control.sh / mrrc_multi.sh 仍按老流程管）；
  * 自己拉起的进程要能被认出来（pid/参数指纹），改机型重启后换掉旧进程。

这些断言都是"参数构造 / 复用判定"的纯逻辑，不真的拉进程。
"""

import configparser
import json
import os
import socket
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import rigctld_manager as R  # noqa: E402


CONF_TWO_SECTIONS = """
[HAMLIB]
rig_pathname = COM3
rig_model = IC-M710
rig_rate = 4800
stop_bits = 2
data_bits = 8
serial_parity = None

[INSTANCE_SETTINGS]
instance_rigctl_model = 1036
instance_rigctl_device = COM8
instance_rigctl_speed = 38400
"""


def _cfg(text):
    cfg = configparser.ConfigParser()
    cfg.read_string(text)
    return cfg


def _fake_proc(pid, running=True):
    """假进程：wait() 默认阻塞（看护线程不会误判退出），带 timeout 时立即返回；
    poll() 反映运行状态。"""
    proc = mock.Mock()
    proc.pid = pid
    proc.returncode = None if running else 3
    proc.poll.return_value = None if running else 3

    def _wait(*args, **kwargs):
        if kwargs.get("timeout"):
            return None
        threading.Event().wait()

    proc.wait.side_effect = _wait
    return proc


MODELS = [
    {"id": 1, "name": "Dummy", "mfg": "Hamlib", "version": "x", "status": 3},
    {"id": 1036, "name": "FT-891", "mfg": "Yaesu", "version": "x", "status": 3},
    {"id": 30003, "name": "IC-M710", "mfg": "Icom", "version": "x", "status": 3},
]


class SettingsTest(unittest.TestCase):
    def test_instance_keys_win_over_hamlib_section(self):
        s = R.rigctld_settings(_cfg(CONF_TWO_SECTIONS), models=MODELS, environ={})
        self.assertEqual(s["model"], 1036)
        self.assertEqual(s["device"], "COM8")
        self.assertEqual(s["speed"], "38400")
        # 串口细分参数没有 instance_* 键 → 从 [HAMLIB] 兜底（mrrc_control.sh 同样的兜底顺序）
        self.assertEqual(s["stop_bits"], "2")
        self.assertEqual(s["data_bits"], "8")
        self.assertEqual(s["host"], "127.0.0.1")
        self.assertEqual(s["port"], 4532)

    def test_hamlib_model_name_resolved_to_numeric_id(self):
        cfg = _cfg("[HAMLIB]\nrig_pathname = COM8\nrig_model = FT-891\nrig_rate = 38400\n")
        s = R.rigctld_settings(cfg, models=MODELS, environ={})
        self.assertEqual(s["model"], 1036)
        self.assertEqual(s["model_text"], "FT-891")

    def test_instance_port_and_host_override(self):
        cfg = _cfg(CONF_TWO_SECTIONS + "\ninstance_rigctl_port = 4540\ninstance_rigctl_host = 192.168.1.9\n")
        s = R.rigctld_settings(cfg, models=MODELS, environ={})
        self.assertEqual(s["port"], 4540)
        self.assertEqual(s["host"], "192.168.1.9")

    def test_autostart_auto_requires_bundled_binary(self):
        cfg = _cfg(CONF_TWO_SECTIONS)
        with mock.patch.object(R, "find_binary", return_value=""):
            self.assertFalse(R.rigctld_settings(cfg, models=MODELS, environ={})["autostart"])
        with mock.patch.object(R, "find_binary", return_value="/opt/bin/rigctld"):
            self.assertTrue(R.rigctld_settings(cfg, models=MODELS, environ={})["autostart"])

    def test_autostart_true_false_and_env_override(self):
        true_cfg = _cfg("[HAMLIB]\nrig_pathname = COM8\nrig_model = 1036\nrigctld_autostart = true\n")
        with mock.patch.object(R, "find_binary", return_value=""):
            self.assertTrue(R.rigctld_settings(true_cfg, models=MODELS, environ={})["autostart"])
        false_cfg = _cfg("[HAMLIB]\nrig_pathname = COM8\nrig_model = 1036\nrigctld_autostart = false\n")
        with mock.patch.object(R, "find_binary", return_value="/opt/bin/rigctld"):
            self.assertFalse(R.rigctld_settings(false_cfg, models=MODELS, environ={})["autostart"])
            # 环境变量优先于配置文件（排障/多实例应急）
            self.assertTrue(R.rigctld_settings(false_cfg, models=MODELS,
                                               environ={"MRRC_RIGCTLD": "1"})["autostart"])
            self.assertFalse(R.rigctld_settings(true_cfg, models=MODELS,
                                                environ={"MRRC_RIGCTLD": "0"})["autostart"])

    def test_no_device_means_no_radio(self):
        cfg = _cfg("[HAMLIB]\nrig_model = FT-891\n")
        s = R.rigctld_settings(cfg, models=MODELS, environ={})
        self.assertEqual(s["device"], "")
        self.assertEqual(s["spawn_blocker"], "device")


class BuildArgvTest(unittest.TestCase):
    def test_full_argv(self):
        s = R.rigctld_settings(_cfg(CONF_TWO_SECTIONS), models=MODELS, environ={})
        s["binary"] = "/x/rigctld.exe"
        argv = R.build_argv(s)
        self.assertEqual(argv[0], "/x/rigctld.exe")
        self.assertEqual(argv[1:3], ["-m", "1036"])
        self.assertIn("-r", argv)
        self.assertEqual(argv[argv.index("-r") + 1], "COM8")
        self.assertEqual(argv[argv.index("-s") + 1], "38400")
        self.assertEqual(argv[argv.index("-T") + 1], "127.0.0.1")
        self.assertEqual(argv[argv.index("-t") + 1], "4532")
        # 串口参数走 -C <token>=<value>，空值不能塞进去（否则 hamlib 直接起不来）
        self.assertIn("-C", argv)
        pairs = [a for a in argv if "=" in a]
        self.assertIn("stop_bits=2", pairs)
        self.assertIn("data_bits=8", pairs)
        self.assertNotIn("serial_parity=None", pairs)

    def test_empty_serial_options_are_skipped(self):
        cfg = _cfg("[HAMLIB]\nrig_pathname = COM8\nrig_model = 1036\nrig_rate = 38400\n"
                   "stop_bits = \ndata_bits = \nserial_parity = \nserial_handshake = \n"
                   "dtr_state = \nrts_state = \n")
        s = R.rigctld_settings(cfg, models=MODELS, environ={})
        s["binary"] = "rigctld"
        self.assertNotIn("-C", R.build_argv(s))

    def test_model_name_unresolved_is_blocker(self):
        cfg = _cfg("[HAMLIB]\nrig_pathname = COM8\nrig_model = NO-SUCH-RIG\n")
        s = R.rigctld_settings(cfg, models=MODELS, environ={})
        self.assertIsNone(s["model"])
        self.assertEqual(s["spawn_blocker"], "model")


class ProbeTest(unittest.TestCase):
    def _serve_once(self, reply=b"145000000\n", port=0):
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("127.0.0.1", port))
        srv.listen(4)
        stop = threading.Event()

        def loop():
            while not stop.is_set():
                try:
                    srv.settimeout(0.2)
                    conn, _ = srv.accept()
                except socket.timeout:
                    continue
                except OSError:
                    return
                try:
                    conn.recv(64)
                    if reply:                    # reply=None = 有人监听但不回答
                        conn.sendall(reply)
                except OSError:
                    pass
                finally:
                    conn.close()

        t = threading.Thread(target=loop, daemon=True)
        t.start()
        return srv, stop, srv.getsockname()[1]

    def test_ok_when_daemon_answers(self):
        srv, stop, port = self._serve_once()
        try:
            ok, detail = R.probe("127.0.0.1", port, timeout=2.0)
            self.assertTrue(ok, detail)
            self.assertEqual(detail, "")
        finally:
            stop.set()
            srv.close()

    def test_not_ok_when_nothing_listens(self):
        srv, stop, port = self._serve_once()
        stop.set()
        srv.close()
        ok, detail = R.probe("127.0.0.1", port, timeout=1.0)
        self.assertFalse(ok)
        self.assertIn(detail, ("refused", "timeout", "error"))

    def test_silent_listener_is_reported_as_timeout(self):
        """端口有人监听但不回答（rigctld 卡在串口上）：必须区分于 refused。"""
        srv, stop, port = self._serve_once(reply=None)
        try:
            ok, detail = R.probe("127.0.0.1", port, timeout=0.5)
            self.assertFalse(ok)
            self.assertEqual(detail, "timeout")
        finally:
            stop.set()
            srv.close()


class ManagerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rigctld-test-")
        self.cfg_path = os.path.join(self.tmp, "MRRC.conf")
        with open(self.cfg_path, "w", encoding="utf-8") as fh:
            fh.write(CONF_TWO_SECTIONS)
        self.cfg = _cfg(CONF_TWO_SECTIONS)
        self.mgr = R.RigctldManager()

    def tearDown(self):
        self.mgr.stop()

    def _settings(self, **over):
        s = R.rigctld_settings(self.cfg, models=MODELS, environ={})
        s["binary"] = over.pop("binary", "/x/rigctld.exe")
        s["autostart"] = over.pop("autostart", True)
        s["spawn_blocker"] = over.pop("spawn_blocker", "")
        s.update(over)
        return s

    def test_existing_daemon_is_reused_without_spawning(self):
        with mock.patch.object(R, "probe", return_value=(True, "")), \
             mock.patch.object(R, "rigctld_settings", return_value=self._settings()), \
             mock.patch("subprocess.Popen") as popen:
            self.assertTrue(self.mgr.ensure(self.cfg, config_path=self.cfg_path))
            popen.assert_not_called()
        self.assertEqual(self.mgr.status()["mode"], "external")

    def test_spawn_writes_state_and_reports_ready(self):
        calls = {"n": 0}

        def fake_probe(host, port, timeout=2.0):
            calls["n"] += 1
            return (calls["n"] > 1, "")          # 第一次探测：没有 → 拉起后成功

        fake_proc = _fake_proc(4242)
        with mock.patch.object(R, "probe", side_effect=fake_probe), \
             mock.patch.object(R, "rigctld_settings", return_value=self._settings()), \
             mock.patch.object(R, "find_binary", return_value="/x/rigctld.exe"), \
             mock.patch("subprocess.Popen", return_value=fake_proc) as popen:
            self.assertTrue(self.mgr.ensure(self.cfg, config_path=self.cfg_path))
            self.assertEqual(popen.call_count, 1)
            argv = popen.call_args[0][0]
            self.assertEqual(argv[1:3], ["-m", "1036"])
        self.assertEqual(self.mgr.status()["mode"], "managed")
        self.assertEqual(self.mgr.status()["pid"], 4242)
        with open(R.state_path(self.cfg_path), encoding="utf-8") as fh:
            state = json.load(fh)
        self.assertEqual(state["pid"], 4242)
        self.assertEqual(state["argv"][1:3], ["-m", "1036"])

    def test_spawn_failure_returns_false_without_raising(self):
        fake_proc = _fake_proc(1, running=False)   # 立刻退出（串口打不开）
        with mock.patch.object(R, "probe", return_value=(False, "refused")), \
             mock.patch.object(R, "rigctld_settings", return_value=self._settings()), \
             mock.patch.object(R, "find_binary", return_value="/x/rigctld.exe"), \
             mock.patch("subprocess.Popen", return_value=fake_proc):
            self.assertFalse(self.mgr.ensure(self.cfg, config_path=self.cfg_path, wait_s=0.2))
        self.assertEqual(self.mgr.status()["mode"], "failed")
        self.assertTrue(self.mgr.status()["last_error"])

    def test_autostart_off_never_spawns(self):
        with mock.patch.object(R, "probe", return_value=(False, "refused")), \
             mock.patch.object(R, "rigctld_settings",
                               return_value=self._settings(autostart=False)), \
             mock.patch("subprocess.Popen") as popen:
            self.assertFalse(self.mgr.ensure(self.cfg, config_path=self.cfg_path))
            popen.assert_not_called()
        self.assertEqual(self.mgr.status()["mode"], "disabled")

    def test_stale_managed_process_with_other_args_is_killed(self):
        with open(R.state_path(self.cfg_path), "w", encoding="utf-8") as fh:
            json.dump({"pid": 777, "fingerprint": "old-args", "argv": ["rigctld", "-m", "30003"]}, fh)
        fake_proc = _fake_proc(888)
        with mock.patch.object(R, "probe", return_value=(True, "")), \
             mock.patch.object(R, "rigctld_settings", return_value=self._settings()), \
             mock.patch.object(R, "process_name", return_value="rigctld.exe"), \
             mock.patch.object(R, "kill_pid") as killer, \
             mock.patch("subprocess.Popen", return_value=fake_proc):
            self.mgr.ensure(self.cfg, config_path=self.cfg_path)
        killer.assert_called_once_with(777)

    def test_same_fingerprint_is_not_killed(self):
        s = self._settings()
        with open(R.state_path(self.cfg_path), "w", encoding="utf-8") as fh:
            json.dump({"pid": 777, "fingerprint": R.fingerprint(s), "argv": R.build_argv(s)}, fh)
        with mock.patch.object(R, "probe", return_value=(True, "")), \
             mock.patch.object(R, "rigctld_settings", return_value=s), \
             mock.patch.object(R, "process_name", return_value="rigctld.exe"), \
             mock.patch.object(R, "kill_pid") as killer, \
             mock.patch("subprocess.Popen") as popen:
            self.assertTrue(self.mgr.ensure(self.cfg, config_path=self.cfg_path))
        killer.assert_not_called()
        popen.assert_not_called()
        self.assertEqual(self.mgr.status()["mode"], "managed")


class LogTest(unittest.TestCase):
    def test_rotation_keeps_prev(self):
        tmp = tempfile.mkdtemp(prefix="rigctld-log-")
        path = os.path.join(tmp, "rigctld.log")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("x" * 300)
        R.rotate_log(path, max_bytes=100)
        self.assertFalse(os.path.exists(path))
        self.assertTrue(os.path.exists(path + ".prev"))
        R.rotate_log(os.path.join(tmp, "none.log"), max_bytes=100)   # 不存在也不能炸


if __name__ == "__main__":
    unittest.main()
