"""Windows 音频设备（主机 API）选择的单元测试。

背景：Windows 上同一个物理设备会在 MME / DirectSound / WASAPI 下**同名重复枚举**，
PortAudio 的宿主 API 顺序又是 MME 最先 —— 按“第一个名字命中”会选中 MME（延迟最高、
最易 overflow、阻塞读按驱动周期成块返数据 → 客户端听到秒级卡顿）。
`audio_interface._match_devices()` 按 [AUDIO] hostapi_preference 挑选，这里用**合成设备表**
验证选择逻辑（构建机/CI 上往往没有真实音频硬件，只能这样覆盖）。
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import audio_interface as ai
    _IMPORT_ERROR = None
except Exception as exc:                      # 没有 pyaudio 等依赖时跳过
    ai = None
    _IMPORT_ERROR = exc


class FakePyAudio:
    """最小化的 PyAudio 替身：只提供 _match_devices/_hostapi_name 需要的接口。"""

    def __init__(self, apis, devices):
        self._apis = apis            # [name, ...]
        self._devices = devices      # [(name, api_index, max_in, max_out), ...]

    def get_host_api_count(self):
        return len(self._apis)

    def get_host_api_info_by_index(self, index):
        return {"name": self._apis[index], "index": index}

    def get_device_count(self):
        return len(self._devices)

    def get_device_info_by_index(self, index):
        name, api_index, max_in, max_out = self._devices[index]
        return {"name": name, "hostApi": api_index, "index": index,
                "maxInputChannels": max_in, "maxOutputChannels": max_out,
                "defaultLowInputLatency": 0.01, "defaultLowOutputLatency": 0.01,
                "defaultSampleRate": 48000.0}


WINDOWS_APIS = ["MME", "Windows DirectSound", "Windows WASAPI", "ASIO", "Windows WDM-KS"]


@unittest.skipIf(ai is None, f"audio_interface 不可用（{_IMPORT_ERROR}）")
class HostApiPreferenceTest(unittest.TestCase):
    def setUp(self):
        # 同一个 USB CODEC 在三个 API 下同名重复；MME 索引最小（旧代码就会选它）
        self.p = FakePyAudio(WINDOWS_APIS, [
            ("USB Audio CODEC", 0, 2, 0),      # MME      index 0
            ("USB Audio CODEC", 1, 2, 0),      # DirectSound index 1
            ("USB Audio CODEC", 2, 2, 0),      # WASAPI   index 2
            ("Microphone (Realtek)", 0, 1, 0),  # 无关设备
            ("Speakers (USB Audio CODEC)", 2, 0, 2),  # 输出设备
        ])

    def test_prefers_wasapi_over_mme_for_identical_names(self):
        matches = ai._match_devices(self.p, "USB Audio CODEC", need_input=True)
        self.assertTrue(matches, "应能匹配到同名设备")
        index, api, _info = matches[0]
        self.assertEqual(api, "Windows WASAPI", "同名设备必须优先选 WASAPI 而不是 MME")
        self.assertEqual(index, 2)
        self.assertEqual([a for _i, a, _info in matches],
                         ["Windows WASAPI", "Windows DirectSound", "MME"],
                         "候选项应按优先度排序")

    def test_configurable_preference_can_pin_mme(self):
        matches = ai._match_devices(self.p, "USB Audio CODEC", need_input=True,
                                    preference="mme,wasapi")
        self.assertEqual(matches[0][1], "MME")
        self.assertEqual(matches[0][0], 0)

    def test_output_and_input_filters(self):
        ins = [i for i, _a, _x in ai._match_devices(self.p, "Audio", need_input=True)]
        outs = [i for i, _a, _x in ai._match_devices(self.p, "Audio", need_output=True)]
        self.assertIn(0, ins)
        self.assertNotIn(4, ins)            # 纯输出设备不能当输入
        self.assertIn(4, outs)
        self.assertNotIn(0, outs)           # 纯输入设备不能当输出

    def test_env_is_not_required_and_preference_override_applies(self):
        ai.set_hostapi_preference("directsound,wasapi")
        try:
            names = [a for _i, a, _x in ai._match_devices(self.p, "USB Audio CODEC", need_input=True)]
            self.assertEqual(names[0], "Windows DirectSound")
        finally:
            ai.set_hostapi_preference(None)

    def test_non_windows_order_unchanged(self):
        # Core Audio（macOS）：API 名不匹配任何 token → 全部同分，退回索引顺序
        mac = FakePyAudio(["Core Audio"], [
            ("USB Audio CODEC", 0, 2, 2),
            ("MacBook Pro Microphone", 0, 1, 0),
            ("USB Audio CODEC", 0, 0, 2),     # 同名但只有输出
        ])
        matches = ai._match_devices(mac, "usb audio", need_input=True)
        self.assertEqual([i for i, _a, _x in matches], [0], "macOS 上行为应保持不变")

    def test_describe_device_mentions_api_and_latency(self):
        _i, api, info = ai._match_devices(self.p, "USB Audio CODEC", need_input=True)[0]
        text = ai._describe_device(api, info)
        self.assertIn("Windows WASAPI", text)
        self.assertIn("USB Audio CODEC", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
