#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
WDSP (Warren Pratt's Digital Signal Processing) Library Python Wrapper
for MRRC - Mobile Remote Radio Control

WDSP is a high-quality DSP library from the OpenHPSDR project, providing:
- NR: LMS Adaptive Noise Reduction
- NR2: Spectral Noise Reduction ( superior quality )
- NB/NB2: Noise Blanker for pulse interference
- SNB: Spectral Noise Blanker
- ANF: Automatic Notch Filter
- AGC: Automatic Gain Control
- Bandpass filters

This wrapper provides a Pythonic interface to the WDSP C library using ctypes.
"""

import ctypes
import numpy as np
import threading

# WDSP 诊断开关 - 设为 True 开启详细调试日志
WDSP_DEBUG = False
import os
import platform
from typing import Optional, Tuple

# WDSP Constants
class WDSPMode:
    LSB = 0
    USB = 1
    DSB = 2
    CWL = 3
    CWU = 4
    FM = 5
    AM = 6
    DIGU = 7
    SPEC = 8
    DIGL = 9
    SAM = 10
    DRM = 11

class WDSPAGCMode:
    OFF = 0
    LONG = 1
    SLOW = 2
    MED = 3
    FAST = 4

class WDSPMeterType:
    S_PK = 0
    S_AV = 1
    ADC_PK = 2
    ADC_AV = 3
    AGC_GAIN = 4
    AGC_PK = 5
    AGC_AV = 6


class WDSPNR2Level:
    """NR2（EMNR）SSB 语音保护等级表。

    主轴是“每 bin 最大衰减”：EMNR 的最小统计噪声估计会把语音自身当噪声
    （实测干净单音 mask=0.022、真实语音段平均 -18dB 且不区分信噪比），
    限制每 bin 衰减可直接消除“声音变形过度”。psi/zeta 为辅助（抑音乐噪声）。
    """
    # 2026-09-17 水声闭环实测（dev_tools/nr2_loop_opt.py，真实波段录音 ×2）：
    #   -12dB 深度仅 +0.8dB 但吃字 26.7%、音乐噪声 ×1.22；-9dB 吃字降到 8.2%。
    #   -16/-20 深度不再增长而吃字 32-33%。整体下移一档：-6/-9/-12/-16。
    MAX_ATTEN_DB = {1: -6.0, 2: -9.0, 3: -12.0, 4: -16.0}
    PSI = {1: 8.0, 2: 12.0, 3: 14.0, 4: 18.0}
    ZETA_THRESH = {1: 0.70, 2: 0.65, 3: 0.60, 4: 0.55}

# Try to load WDSP library
def _load_wdsp_library():
    """Load the WDSP shared library"""
    import platform
    import sys
    system = platform.system()

    # Base directory: repo root in source mode, dist root when frozen.
    if getattr(sys, "frozen", False):
        base_dir = os.path.dirname(os.path.abspath(sys.executable))
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))

    # Search paths
    search_paths = [
        os.path.dirname(os.path.abspath(__file__)),  # Same directory
        "/usr/local/lib",
        "/opt/homebrew/lib",  # macOS Homebrew ARM64
        "/opt/local/lib",      # macOS Homebrew x86-64
        "/usr/lib",
        "/tmp/wdsp",  # Build directory
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "DSP", "wdsp"),  # 项目目录
        os.path.join(base_dir, "vendor", "wdsp", "windows", "bin", "x64"),  # bundled Windows DLL
        ".",
    ]

    # 补丁覆盖层优先：%LOCALAPPDATA%\MRRC\patch\vendor\... 或 patch\libwdsp.dll
    # （热修 DLL 不必重新打包/重装，见 patch_overlay.py）
    try:
        import patch_overlay
        overlay_dirs = [d for d in patch_overlay.dll_dirs() if d not in search_paths]
        if overlay_dirs:
            search_paths = overlay_dirs + search_paths
    except Exception:
        pass

    if system == "Darwin":
        lib_names = ["libwdsp.dylib"]
    elif system == "Windows":
        lib_names = ["libwdsp.dll", "wdsp.dll"]
    else:
        lib_names = ["libwdsp.so"]

    print(f"🔍 WDSP: 正在搜索库文件: {lib_names}")

    for lib_name in lib_names:
        for path in search_paths:
            lib_path = os.path.join(path, lib_name)
            if os.path.exists(lib_path):
                print(f"🔍 WDSP: 找到库文件: {lib_path}")
                try:
                    lib = ctypes.CDLL(lib_path)
                    print(f"✅ WDSP: 成功加载库: {lib_path}")
                    return lib
                except OSError as e:
                    print(f"⚠️ WDSP: 加载失败 {lib_path}: {e}")
                    continue

    # Try system library by name
    for lib_name in lib_names:
        try:
            lib = ctypes.CDLL(lib_name)
            print(f"✅ WDSP: 从系统加载: {lib_name}")
            return lib
        except OSError as e:
            print(f"⚠️ WDSP: 系统加载失败: {lib_name}: {e}")

    print(f"❌ WDSP: 未找到库文件！")
    return None

# Load WDSP library
_wdsp = _load_wdsp_library()
WDSP_AVAILABLE = _wdsp is not None

if WDSP_AVAILABLE:
    print(f"✅ WDSP 库加载成功")
else:
    print(f"⚠️ WDSP 库未找到！请编译安装: cd /tmp && git clone https://github.com/g0orx/wdsp.git && cd wdsp && make")


# ═══════════════════════════════════════════════════════════════════════════════
# C 函数符号绑定辅助
# ═══════════════════════════════════════════════════════════════════════════════

def _bind(name: str, argtypes: list, restype=ctypes.c_int):
    """
    动态绑定 WDSP C 函数符号，缺失时优雅降级。
    """
    if not WDSP_AVAILABLE:
        return
    try:
        func = getattr(_wdsp, name)
        func.argtypes = argtypes
        func.restype = restype
    except AttributeError:
        if WDSP_DEBUG:
            print(f"   ⚠️ WDSP 符号缺失: {name} (libwdsp 版本可能过旧)")


# ═══════════════════════════════════════════════════════════════════════════════
# TX 发射链 C 函数签名绑定 (OpenHPSDR 广播级处理链)
# ═══════════════════════════════════════════════════════════════════════════════

def _bind_tx_signatures():
    """绑定 TX 面板控制、DEXP 噪声门、TX AGC 话务压缩、TX EQ 塑形"""
    c_int = ctypes.c_int
    c_double = ctypes.c_double
    c_pointer = ctypes.POINTER(ctypes.c_double)

    # ── TX 面板总开关 ──
    _bind("SetTXAMode",        [c_int, c_int], c_int)
    _bind("SetTXAPanelRun",    [c_int, c_int], c_int)

    # ── DEXP (发射级智能向下扩展噪声门 — 斩杀空调/风扇环境杂音) ──
    _bind("SetDEXPRun",              [c_int, c_int],    c_int)
    _bind("SetDEXPAttackThreshold",  [c_int, c_double], c_int)
    _bind("SetDEXPReleaseTime",      [c_int, c_double], c_int)

    # ── TX AGC (RF Speech Compressor — 绝不泼溅的强推功率) ──
    _bind("SetTXAAGCMode",    [c_int, c_int],    c_int)
    _bind("SetTXAAGCThresh",  [c_int, c_double], c_int)

    # ── TX EQ (十段发射均衡器 — 打造完美低音/高音 HAM 磁性听感) ──
    _bind("SetTXAEQRun",      [c_int, c_int],                    c_int)
    _bind("SetTXAEQProfile",  [c_int, c_int, c_pointer],         c_int)


# ═══════════════════════════════════════════════════════════════════════════════
# 空间分集接收 (Spatial Diversity RX) 函数签名
# ═══════════════════════════════════════════════════════════════════════════════

def _bind_diversity_signatures():
    """绑定双通道交换 & 分集矩阵控制"""
    c_int = ctypes.c_int
    c_double = ctypes.c_double
    c_pointer_double = ctypes.POINTER(ctypes.c_double)
    c_pointer_int = ctypes.POINTER(ctypes.c_int)

    # fexchange2 — 双通道零拷贝复数交换 (Diversity 核心)
    _bind("fexchange2", [c_int, c_pointer_double, c_pointer_double,
                         c_pointer_double, c_pointer_double, c_pointer_int], c_int)

    # 分集矩阵控制
    _bind("SetEXTDIVRun",    [c_int, c_int],    c_int)
    _bind("SetEXTDIVRotate", [c_int, c_double], c_int)


def _bind_nr2_signatures():
    """绑定 NR2 (EMNR) 参数 — 直接控制频谱减法“音乐噪声/水音”与 SSB 语音保护。

    ae.psi:     掩码跨 bin 平滑宽度系数，越大平滑越宽 → 音乐噪声越少（默认10）
    ae.zetaThresh: AE 触发阈值，越小 AE 越常触发（默认0.75）
    maxAttenDb: 每 bin 最大衰减（dB，<0）→ 限制 EMNR 对语音的“吃掉量”
    dry:        干湿混合 mask' = dry + (1-dry)*mask（0~1）
    """
    c_int = ctypes.c_int
    c_double = ctypes.c_double
    _bind("SetRXAEMNRaePsi",        [c_int, c_double], c_int)
    _bind("SetRXAEMNRaeZetaThresh", [c_int, c_double], c_int)
    _bind("SetRXAEMNRmaxAttenDb",   [c_int, c_double], c_int)
    _bind("SetRXAEMNRdry",          [c_int, c_double], c_int)


# ── 执行绑定 ──
if WDSP_AVAILABLE:
    _bind_tx_signatures()
    _bind_diversity_signatures()
    _bind_nr2_signatures()


class WDSPProcessor:
    """
    WDSP Audio Processor for SSB voice communication.
    
    Provides professional-grade noise reduction and audio processing:
    - NR2: Spectral noise reduction (recommended for SSB)
    - NB: Noise blanker for pulse interference
    - ANF: Automatic notch filter
    - AGC: Automatic gain control
    - Bandpass filtering
    """
    
    def __init__(self,
                 sample_rate: int = 48000,
                 buffer_size: int = 256,
                 mode: int = WDSPMode.USB,
                 enable_nr2: bool = True,
                 enable_nb: bool = False,
                 enable_anf: bool = False,
                 agc_mode: int = WDSPAGCMode.MED,
                 nr2_ae_psi: float = 12.0,
                 nr2_ae_zeta_thresh: float = 0.65,
                 nr2_max_atten_db: float = None,
                 nr2_dry: float = 0.0,
                 agc_top_db: float = 20.0,
                 panel_gain: float = 0.35):
        """
        Initialize WDSP processor.

        Args:
            sample_rate: Audio sample rate (48000 or 16000 recommended)
            buffer_size: Processing buffer size
            mode: WDSP mode (LSB, USB, etc.)
            enable_nr2: Enable spectral noise reduction (NR2)
            enable_nb: Enable noise blanker
            enable_anf: Enable automatic notch filter
            agc_mode: AGC mode (OFF, LONG, SLOW, MED, FAST)
            nr2_ae_psi: EMNR 自动均衡掩码平滑宽度（越大音乐噪声越少，默认20）
            nr2_ae_zeta_thresh: EMNR 自动均衡触发阈值（越小越常触发，默认0.5）
        """
        if not WDSP_AVAILABLE:
            raise RuntimeError("WDSP library not available")

        self.sample_rate = sample_rate
        self.buffer_size = buffer_size
        self.mode = mode
        self.channel = 0  # Default channel

        # State tracking - 正确初始化启用状态
        self._initialized = False
        self._nr2_enabled = enable_nr2   # 修复：使用参数值
        self._nb_enabled = enable_nb     # 修复：使用参数值
        self._anf_enabled = enable_anf   # 修复：使用参数值
        self._notches_enabled = False    # 手动陷波滤波器（NF）
        self._agc_mode = agc_mode
        self._nr2_ae_psi = nr2_ae_psi
        self._nr2_ae_zeta_thresh = nr2_ae_zeta_thresh
        # SSB 语音保护：每 bin 最大衰减（None=跟随等级表，<0 生效，>=0 关闭=旧行为）/ 干湿混合
        self._nr2_max_atten_db = nr2_max_atten_db
        self._nr2_dry = nr2_dry
        # 增益级：AGC 最大补偿增益 / 输出电势
        self._agc_top_db = agc_top_db
        self._panel_gain = panel_gain
        # -2 饥饿时保持上一块输出（绝不注入原始输入）
        self._last_output = None
        self.starved_blocks = 0
        # Buffers for WDSP processing (float64 - WDSP 库要求)
        self._in_buffer = np.zeros(buffer_size * 2, dtype=np.float64)
        self._out_buffer = np.zeros(buffer_size * 2, dtype=np.float64)
        # H9: C 库访问锁。process() 在捕获线程，notch/setter 可能在 Tornado 线程并发调用；
        # fexchange0 与 SetRXA* 并发会损坏 WDSP 内部状态。RLock 允许构造期嵌套调用。
        self._lock = threading.RLock()
        
        # Initialize WDSP channel
        self._init_wdsp()
    
    def _init_wdsp(self):
        """Initialize WDSP channel with configured settings"""
        try:
            # Open channel with type 0 (RX)
            # Args: channel, in_size, dsp_size, input_samplerate, dsp_rate, output_samplerate, 
            #       type, state, tdelayup, tslewup, tdelaydown, tslewdown, bfo
            _wdsp.OpenChannel(
                ctypes.c_int(self.channel),
                ctypes.c_int(self.buffer_size),
                ctypes.c_int(self.buffer_size),
                ctypes.c_int(self.sample_rate),
                ctypes.c_int(self.sample_rate),
                ctypes.c_int(self.sample_rate),
                ctypes.c_int(0),  # Type: 0 = RX
                ctypes.c_int(1),  # State: 1 = ON
                ctypes.c_double(0.0),  # tdelayup
                ctypes.c_double(0.0),  # tslewup
                ctypes.c_double(0.0),  # tdelaydown
                ctypes.c_double(0.0),  # tslewdown
                ctypes.c_int(0)  # bfo
            )
            
            # Set RX mode
            _wdsp.SetRXAMode(ctypes.c_int(self.channel), ctypes.c_int(self.mode))
            
            # 设置面板增益为 0.06，进一步减少削波风险
            # 测试显示：PanelGain=0.06时，实际增益更保守
            _wdsp.SetRXAPanelGain1(ctypes.c_int(self.channel), ctypes.c_double(self._panel_gain))
            
            # 注意：暂时禁用带通滤波器，因为测试显示它会导致信号被错误衰减
            # 后续需要进一步调试带通滤波器参数
            # self.set_bandpass(300.0, 2700.0)
            
            self._initialized = True
            print(f"🔧 WDSP Processor initialized: SR={self.sample_rate}Hz, Mode={self.mode}")
            print(f"   NR2={'ON' if self._nr2_enabled else 'OFF'}, "
                  f"NB={'ON' if self._nb_enabled else 'OFF'}, "
                  f"ANF={'ON' if self._anf_enabled else 'OFF'}, "
                  f"AGC={self._agc_mode}")
            
            # Configure AGC (必须在 OpenChannel 后、其他模块前设置)
            self.set_agc_mode(self._agc_mode)
            
            # Configure Noise Reduction (NR2 - Spectral)
            if self._nr2_enabled:
                self._setup_nr2()
            
            # Configure Noise Blanker
            if self._nb_enabled:
                self._setup_nb()
            
            # Configure ANF
            if self._anf_enabled:
                self._setup_anf()
            
        except Exception as e:
            print(f"❌ WDSP initialization error: {e}")
            raise
    
    def _setup_nr2(self):
        """Setup Spectral Noise Reduction (NR2) - 默认 Gaussian 温和降噪"""
        try:
            _wdsp.SetRXAANRRun(ctypes.c_int(self.channel), ctypes.c_int(0))

            _wdsp.SetRXAEMNRRun(ctypes.c_int(self.channel), ctypes.c_int(1))

            # 默认参数: Gaussian(自然), OSMS(平滑), AE=ON(消音乐噪音)
            _wdsp.SetRXAEMNRgainMethod(ctypes.c_int(self.channel), ctypes.c_int(0))
            _wdsp.SetRXAEMNRnpeMethod(ctypes.c_int(self.channel), ctypes.c_int(0))
            _wdsp.SetRXAEMNRaeRun(ctypes.c_int(self.channel), ctypes.c_int(1))
            # Position=0: 在 AGC 之前降噪，避免 AGC 放大残留噪声
            _wdsp.SetRXAEMNRPosition(ctypes.c_int(self.channel), ctypes.c_int(0))
            # 调强 AE 掩码平滑（psi=20, zetaThresh=0.5），压制频谱减法"水音"音乐噪声
            self.set_nr2_ae(self._nr2_ae_psi, self._nr2_ae_zeta_thresh)
            # SSB 语音保护：限制每 bin 最大衰减（默认跟随等级表：L2 = -12dB）
            self._apply_nr2_voice_protection(2)
            if self._nr2_dry > 0.0:
                self.set_nr2_dry(self._nr2_dry)

            self._nr2_enabled = True
            self._nr2_level = 2  # 默认温和
            eff_db = (self._nr2_max_atten_db if self._nr2_max_atten_db is not None
                      else WDSPNR2Level.MAX_ATTEN_DB.get(2, -12.0))
            print(f"   NR2 (EMNR) configured - Gaussian, MMSE, AE=ON(psi={self._nr2_ae_psi},"
                  f"zeta={self._nr2_ae_zeta_thresh}), max_atten={eff_db}dB, Pre-AGC")
        except Exception as e:
            print(f"   ⚠️ NR2 setup error: {e}")

    def set_nr2_max_atten(self, db: float):
        """限制 NR2 每 bin 最大衰减（SSB 语音保护）。

        db < 0：掩码下限 = 10^(db/20)，即最多衰减少于 |db|；db >= 0（或 None）：不限制（旧行为）。
        依据：EMNR 最小统计会把语音本身当噪声（实测单音 mask=0.022，语音段平均 -18dB），
        导致语音被整段削。限制后单音从 -37dB 提升到 ~-15dB，而降噪仅损失几 dB。
        """
        if not self._initialized:
            return
        try:
            if db is not None:
                self._nr2_max_atten_db = db
            _wdsp.SetRXAEMNRmaxAttenDb(ctypes.c_int(self.channel),
                                       ctypes.c_double(self._nr2_max_atten_db or -12.0))
        except Exception as e:
            print(f"⚠️ NR2 max atten setup error: {e}")

    def set_nr2_dry(self, dry: float):
        """NR2 干湿混合：mask' = dry + (1-dry)*mask（0=纯湿，比硬下限更平滑）。"""
        if not self._initialized:
            return
        self._nr2_dry = dry
        try:
            _wdsp.SetRXAEMNRdry(ctypes.c_int(self.channel), ctypes.c_double(dry))
        except Exception as e:
            print(f"⚠️ NR2 dry setup error: {e}")

    def set_nr2_ae(self, psi: float = None, zeta_thresh: float = None):
        """调 NR2 (EMNR) 自动均衡(AE) 参数，抑制频谱减法"水音/音乐噪声"。

        psi: 掩码跨 bin 平滑宽度系数。越大 → 平滑越宽 → 音乐噪声越少。
             但过大(>40)会抹掉窄带噪声细节。默认 20（WDSP 出厂 10）。
        zeta_thresh: AE 触发阈值，越小 AE 越常触发。默认 0.5（WDSP 出厂 0.75）。
        """
        if not self._initialized:
            return
        if psi is not None:
            self._nr2_ae_psi = psi
        if zeta_thresh is not None:
            self._nr2_ae_zeta_thresh = zeta_thresh
        try:
            _wdsp.SetRXAEMNRaePsi(ctypes.c_int(self.channel),
                                  ctypes.c_double(self._nr2_ae_psi))
            _wdsp.SetRXAEMNRaeZetaThresh(ctypes.c_int(self.channel),
                                         ctypes.c_double(self._nr2_ae_zeta_thresh))
        except Exception as e:
            print(f"⚠️ NR2 AE setup error: {e}")

    def set_nr2_level(self, level: int):
        """
        Set NR2 intensity level.

        等级主轴 = **每 bin 最大衰减**（SSB 语音保护），psi/zeta 为辅助，
        估计器用 MMSE(npe=1)：实测它不会把平稳信号（长音/持续共振峰）当噪声。

        Args:
            level: 0-4
                0 = OFF
                1 = MIN  — 最多衰减 -6dB，几乎不动语音
                2 = LOW  — -12dB（日常推荐）
                3 = MED  — -16dB（中等噪声）
                4 = HIGH — -20dB（强噪声，接受更多变形）
        """
        if not self._initialized:
            return

        try:
            if level == 0:
                _wdsp.SetRXAEMNRRun(ctypes.c_int(self.channel), ctypes.c_int(0))
                _wdsp.SetRXAANRRun(ctypes.c_int(self.channel), ctypes.c_int(0))
                self._nr2_enabled = False
                self._nr2_level = 0
                print(f"🔧 WDSP NR2: OFF")
            else:
                _wdsp.SetRXAANRRun(ctypes.c_int(self.channel), ctypes.c_int(0))
                _wdsp.SetRXAEMNRRun(ctypes.c_int(self.channel), ctypes.c_int(1))

                # 估计器固定 MMSE(npe=1)：最小统计(OSMS)在平稳段会把信号当噪声
                # （实测单音 mask=0.022、语音段平均 -18dB）。gainMethod 0=Gaussian。
                gain_method = 0
                npe_method = 1
                ae_run = 1 if level >= 2 else 0

                _wdsp.SetRXAEMNRgainMethod(ctypes.c_int(self.channel), ctypes.c_int(gain_method))
                _wdsp.SetRXAEMNRnpeMethod(ctypes.c_int(self.channel), ctypes.c_int(npe_method))
                _wdsp.SetRXAEMNRaeRun(ctypes.c_int(self.channel), ctypes.c_int(ae_run))
                # 保持 Position=0 (AGC 前)
                _wdsp.SetRXAEMNRPosition(ctypes.c_int(self.channel), ctypes.c_int(0))
                # 等级驱动 psi/zeta + 每 bin 最大衰减（SSB 语音保护）
                self._nr2_ae_psi = WDSPNR2Level.PSI.get(level, 12.0)
                self._nr2_ae_zeta_thresh = WDSPNR2Level.ZETA_THRESH.get(level, 0.65)
                self.set_nr2_ae()
                self._apply_nr2_voice_protection(level)

                self._nr2_enabled = True
                self._nr2_level = level
                level_names = {1: 'MIN(极温和)', 2: 'LOW(温和)', 3: 'MED(中等)', 4: 'HIGH(强力)'}
                db = (self._nr2_max_atten_db if self._nr2_max_atten_db is not None
                      else WDSPNR2Level.MAX_ATTEN_DB.get(level, -12.0))
                print(f"🔧 WDSP NR2: {level_names.get(level, level)} "
                      f"(max_atten={db}dB, psi={self._nr2_ae_psi}, ae={ae_run})")
        except Exception as e:
            print(f"⚠️ NR2 level error: {e}")

    def _apply_nr2_voice_protection(self, level: int):
        """按等级（或配置覆盖）设置每 bin 最大衰减 / 干湿混合。

        旧 libwdsp（未搭载 2026-09-13 patch）没有 SetRXAEMNRmaxAttenDb/SetRXAEMNRdry：
        此时只告警一次并继续（估计器已固定为 MMSE，最关键的那半修复仍然生效）。
        """
        if not self._initialized:
            return
        if not hasattr(_wdsp, "SetRXAEMNRmaxAttenDb"):
            if not getattr(self, "_nr2_voice_protect_warned", False):
                self._nr2_voice_protect_warned = True
                print("⚠️ 当前 libwdsp 不支持每 bin 最大衰减（缺 SetRXAEMNRmaxAttenDb）；"
                      "NR2 语音保护不可用，请用 DSP/patches/2026-09-13-nr2-ssb-voice-protection.patch 重编库")
            return
        try:
            db = (self._nr2_max_atten_db if self._nr2_max_atten_db is not None
                  else WDSPNR2Level.MAX_ATTEN_DB.get(level, -12.0))
            _wdsp.SetRXAEMNRmaxAttenDb(ctypes.c_int(self.channel), ctypes.c_double(db))
            if self._nr2_dry and self._nr2_dry > 0.0 and hasattr(_wdsp, "SetRXAEMNRdry"):
                _wdsp.SetRXAEMNRdry(ctypes.c_int(self.channel), ctypes.c_double(self._nr2_dry))
        except Exception as e:
            print(f"⚠️ NR2 voice protection error: {e}")

    def set_nr2_voice_protection(self, max_atten_db: float = None, dry: float = None):
        """运行时调“语气保真度”：max_atten_db<0 钉死每 bin 衰减上限；dry=0~1 干湿混合。

        max_atten_db=None 表示跟随 nr2_level 等级表；0 表示不限制（旧行为）。
        """
        if max_atten_db is not None:
            self._nr2_max_atten_db = max_atten_db
        if dry is not None:
            self._nr2_dry = dry
        level = getattr(self, '_nr2_level', 0) or 2
        self._apply_nr2_voice_protection(level)

    def set_agc_top(self, db: float = None):
        """限制 AGC 最大补偿增益(dB)。默认 +20dB。

        旧行为 max_gain=10000（+80dB）：EMNR 砍完 20~30dB 后 AGC 再狂补，
        把 NR2 的残渣与掩码起伏放大回满量程 → 听感“变形/抽吸”。
        """
        if not self._initialized:
            return
        if db is not None:
            self._agc_top_db = db
        try:
            _wdsp.SetRXAAGCTop(ctypes.c_int(self.channel), ctypes.c_double(self._agc_top_db))
        except Exception as e:
            print(f"⚠️ AGC top error: {e}")
    
    def _setup_nb(self):
        """Setup Noise Blanker"""
        try:
            # Enable SNBA (Spectral Noise Blanker Advanced)
            _wdsp.SetRXASNBARun(ctypes.c_int(self.channel), ctypes.c_int(1))
            self._nb_enabled = True
            print(f"   NB (Spectral) configured")
        except Exception as e:
            print(f"   ⚠️ NB setup error: {e}")
    
    def _setup_anf(self):
        """Setup Automatic Notch Filter"""
        try:
            _wdsp.SetRXAANFRun(ctypes.c_int(self.channel), ctypes.c_int(1))
            self._anf_enabled = True
            print(f"   ANF configured")
        except Exception as e:
            print(f"   ⚠️ ANF setup error: {e}")
    
    def set_bandpass(self, low_freq: float, high_freq: float):
        """
        Set SSB bandpass filter frequencies.

        走 always-on 的 nbp0 FIR（`SetRXANBPFreqs`），不再依赖 bp1：
        bp1 在"非 NR 模块驱动"状态下会输出全零（实测 NR2 关闭初始化 + 改频点 → RX 静音），
        且其增益/掩码激活路径不可靠。bp1 的开关完全交给 WDSP 的 RXAbp1Set 管理。
        nbp0 位于 NR 之前，带外噪声先被滤掉，EMNR 的噪声估计更准。

        Args:
            low_freq: Low cutoff frequency in Hz
            high_freq: High cutoff frequency in Hz
        """
        if not self._initialized:
            return
        
        try:
            if hasattr(_wdsp, "SetRXANBPFreqs"):
                _wdsp.SetRXANBPFreqs(ctypes.c_int(self.channel),
                                     ctypes.c_double(low_freq), ctypes.c_double(high_freq))
            else:   # 旧库回退：无 nbp setter 时仍用 bp1
                _wdsp.SetRXABandpassRun(ctypes.c_int(self.channel), ctypes.c_int(1))
                _wdsp.SetRXABandpassFreqs(
                    ctypes.c_int(self.channel),
                    ctypes.c_double(low_freq),
                    ctypes.c_double(high_freq)
                )
            self._bandpass_low = low_freq
            self._bandpass_high = high_freq
            print(f"🔧 WDSP Bandpass: {low_freq}Hz - {high_freq}Hz (nbp0)")
        except Exception as e:
            print(f"⚠️ Bandpass setup error: {e}")
    
    def set_agc_mode(self, mode: int):
        """
        Set AGC mode.
        
        Args:
            mode: WDSPAGCMode (OFF, LONG, SLOW, MED, FAST)
        """
        if not self._initialized:
            return
        
        try:
            _wdsp.SetRXAAGCMode(ctypes.c_int(self.channel), ctypes.c_int(mode))
            
            # Configure AGC parameters based on mode
            if mode == WDSPAGCMode.OFF:
                # AGC OFF：固定增益走 fixed_gain（SetRXAAGCFixed 单位是 dB！）
                _wdsp.SetRXAAGCAttack(ctypes.c_int(self.channel), ctypes.c_int(0))
                _wdsp.SetRXAAGCDecay(ctypes.c_int(self.channel), ctypes.c_int(0))
                _wdsp.SetRXAAGCHang(ctypes.c_int(self.channel), ctypes.c_int(0))
                # 0 dB = 线性 1.0（旧代码传 1.0 实际是 +1 dB）
                _wdsp.SetRXAAGCFixed(ctypes.c_int(self.channel), ctypes.c_double(0.0))
                # print(f"🔧 WDSP AGC: OFF (固定增益 0dB)")
            elif mode == WDSPAGCMode.MED:
                # SSB 语音：稍慢的 decay/hang，减少音节间抽吸
                _wdsp.SetRXAAGCAttack(ctypes.c_int(self.channel), ctypes.c_int(6))
                _wdsp.SetRXAAGCDecay(ctypes.c_int(self.channel), ctypes.c_int(500))
                _wdsp.SetRXAAGCHang(ctypes.c_int(self.channel), ctypes.c_int(500))
                # _wdsp.SetRXAAGCTarget(ctypes.c_int(self.channel), ctypes.c_float(-3.0))  # 默认目标 -3dB
            elif mode == WDSPAGCMode.FAST:
                _wdsp.SetRXAAGCAttack(ctypes.c_int(self.channel), ctypes.c_int(2))
                _wdsp.SetRXAAGCDecay(ctypes.c_int(self.channel), ctypes.c_int(150))
                _wdsp.SetRXAAGCHang(ctypes.c_int(self.channel), ctypes.c_int(150))
            elif mode == WDSPAGCMode.SLOW:
                _wdsp.SetRXAAGCAttack(ctypes.c_int(self.channel), ctypes.c_int(6))
                _wdsp.SetRXAAGCDecay(ctypes.c_int(self.channel), ctypes.c_int(750))
                _wdsp.SetRXAAGCHang(ctypes.c_int(self.channel), ctypes.c_int(750))
            elif mode == WDSPAGCMode.LONG:
                _wdsp.SetRXAAGCAttack(ctypes.c_int(self.channel), ctypes.c_int(8))
                _wdsp.SetRXAAGCDecay(ctypes.c_int(self.channel), ctypes.c_int(1200))
                _wdsp.SetRXAAGCHang(ctypes.c_int(self.channel), ctypes.c_int(1200))

            # 限制 AGC 最大补偿增益：避免"EMNR 砍完 20~30dB 后 AGC 再狂补"把残渣放大到满量程
            self.set_agc_top()
            # 输出电势（panel）：AGC 输出(~0.98) × panel_gain
            _wdsp.SetRXAPanelGain1(ctypes.c_int(self.channel), ctypes.c_double(self._panel_gain))

        except Exception as e:
            print(f"⚠️ AGC setup error: {e}")
    
    def set_nr2_enabled(self, enabled: bool):
        """
        Enable/disable NR2 (Spectral Noise Reduction) dynamically.
        
        Args:
            enabled: True to enable, False to disable
        """
        if not self._initialized:
            return
        
        try:
            _wdsp.SetRXAEMNRRun(ctypes.c_int(self.channel), ctypes.c_int(1 if enabled else 0))
            self._nr2_enabled = enabled
            print(f"🔧 WDSP NR2 {'enabled' if enabled else 'disabled'} (dynamic)")
        except Exception as e:
            print(f"⚠️ NR2 dynamic control error: {e}")
    
    def set_nb_enabled(self, enabled: bool):
        """
        Enable/disable Noise Blanker dynamically.
        
        Args:
            enabled: True to enable, False to disable
        """
        if not self._initialized:
            return
        
        try:
            # SNB - Spectral Noise Blanker
            _wdsp.SetRXASNBARun(ctypes.c_int(self.channel), ctypes.c_int(1 if enabled else 0))
            self._nb_enabled = enabled
            print(f"🔧 WDSP NB {'enabled' if enabled else 'disabled'} (dynamic)")
        except Exception as e:
            print(f"⚠️ NB dynamic control error: {e}")
    
    def set_anf_enabled(self, enabled: bool):
        """
        Enable/disable Automatic Notch Filter dynamically.
        
        Args:
            enabled: True to enable, False to disable
        """
        if not self._initialized:
            return
        
        try:
            _wdsp.SetRXAANFRun(ctypes.c_int(self.channel), ctypes.c_int(1 if enabled else 0))
            self._anf_enabled = enabled
            print(f"🔧 WDSP ANF {'enabled' if enabled else 'disabled'} (dynamic)")
        except Exception as e:
            print(f"⚠️ ANF dynamic control error: {e}")
    
    def set_notches_enabled(self, enabled: bool):
        """
        Enable/disable Manual Notch Filter (NF).
        
        手动陷波滤波器允许设置特定中心频率来消除单频干扰（如CW噪音）。
        注意：需要启用NBP (Notched BandPass) filter才能工作。
        
        Args:
            enabled: True to enable, False to disable
        """
        if not self._initialized:
            return
        
        try:
            # H9: 持锁，与 process() 的 fexchange0 互斥
            with self._lock:
                # 启用NBP (Notched BandPass) filter本身
                _wdsp.RXANBPSetRun(ctypes.c_int(self.channel), ctypes.c_int(1 if enabled else 0))

                # 启用notches
                _wdsp.RXANBPSetNotchesRun(ctypes.c_int(self.channel), ctypes.c_int(1 if enabled else 0))

                self._notches_enabled = enabled
            print(f"🔧 WDSP NF (Notched BandPass) {'enabled' if enabled else 'disabled'} (dynamic)")
        except Exception as e:
            print(f"⚠️ NF dynamic control error: {e}")
    
    def add_notch(self, fcenter: float, fwidth: float = 100.0, active: int = 1) -> int:
        """
        Add a manual notch filter at specified frequency.
        
        手动添加陷波点，用于消除特定频率的干扰（如CW噪音）。
        
        Args:
            fcenter: Center frequency in Hz (e.g., 800 for 800Hz CW tone)
            fwidth: Notch width in Hz (default 100Hz, range 10-1000)
            active: 1 = active, 0 = inactive
            
        Returns:
            Notch index (>=0 success, <0 error)
        """
        if not self._initialized:
            return -1
        
        try:
            # H9: 持锁，与 process() 的 fexchange0 互斥
            with self._lock:
                result = _wdsp.RXANBPAddNotch(
                    ctypes.c_int(self.channel),
                    ctypes.c_int(0),  # Add at next available position
                    ctypes.c_double(fcenter),
                    ctypes.c_double(fwidth),
                    ctypes.c_int(active)
                )
            if result >= 0:
                print(f"🔧 WDSP NF: Added notch at {fcenter}Hz (width={fwidth}Hz, index={result})")
            return result
        except Exception as e:
            print(f"⚠️ NF add notch error: {e}")
            return -1
    
    def edit_notch(self, notch: int, fcenter: float, fwidth: float = 100.0, active: int = 1) -> bool:
        """
        Edit an existing notch filter.
        
        Args:
            notch: Notch index to edit
            fcenter: New center frequency in Hz
            fwidth: New notch width in Hz
            active: 1 = active, 0 = inactive
            
        Returns:
            True if success, False if error
        """
        if not self._initialized:
            return False
        
        try:
            # H9: 持锁，与 process() 的 fexchange0 互斥
            with self._lock:
                result = _wdsp.RXANBPEditNotch(
                    ctypes.c_int(self.channel),
                    ctypes.c_int(notch),
                    ctypes.c_double(fcenter),
                    ctypes.c_double(fwidth),
                    ctypes.c_int(active)
                )
            if result == 0:
                print(f"🔧 WDSP NF: Edited notch {notch} at {fcenter}Hz (width={fwidth}Hz)")
            return result == 0
        except Exception as e:
            print(f"⚠️ NF edit notch error: {e}")
            return False
    
    def delete_notch(self, notch: int) -> bool:
        """
        Delete a notch filter.
        
        Args:
            notch: Notch index to delete
            
        Returns:
            True if success, False if error
        """
        if not self._initialized:
            return False
        
        try:
            # H9: 持锁，与 process() 的 fexchange0 互斥
            with self._lock:
                result = _wdsp.RXANBPDeleteNotch(
                    ctypes.c_int(self.channel),
                    ctypes.c_int(notch)
                )
            if result == 0:
                print(f"🔧 WDSP NF: Deleted notch {notch}")
            return result == 0
        except Exception as e:
            print(f"⚠️ NF delete notch error: {e}")
            return False
    
    def get_num_notches(self) -> int:
        """
        Get number of configured notches.
        
        Returns:
            Number of active notches
        """
        if not self._initialized:
            return 0
        
        try:
            nnotches = ctypes.c_int(0)
            _wdsp.RXANBPGetNumNotches(ctypes.c_int(self.channel), ctypes.byref(nnotches))
            return nnotches.value
        except Exception as e:
            print(f"⚠️ NF get num notches error: {e}")
            return 0
    
    def get_notch(self, notch: int) -> dict:
        """
        Get notch information.
        
        Args:
            notch: Notch index
            
        Returns:
            Dict with 'fcenter', 'fwidth', 'active' or None if error
        """
        if not self._initialized:
            return None
        
        try:
            fcenter = ctypes.c_double(0)
            fwidth = ctypes.c_double(0)
            active = ctypes.c_int(0)
            result = _wdsp.RXANBPGetNotch(
                ctypes.c_int(self.channel),
                ctypes.c_int(notch),
                ctypes.byref(fcenter),
                ctypes.byref(fwidth),
                ctypes.byref(active)
            )
            if result == 0:
                return {
                    'fcenter': fcenter.value,
                    'fwidth': fwidth.value,
                    'active': active.value
                }
            return None
        except Exception as e:
            print(f"⚠️ NF get notch error: {e}")
            return None

    def process(self, audio_data: np.ndarray) -> np.ndarray:
        """
        Process audio through WDSP.
        
        Args:
            audio_data: Input audio as numpy array (float32 or int16)
            
        Returns:
            Processed audio as numpy array (same format as input)
        """
        if not self._initialized or not WDSP_AVAILABLE:
            return audio_data
        
        try:
            # Convert to float64 for WDSP
            if audio_data.dtype == np.int16:
                float_data = audio_data.astype(np.float64) / 32768.0
            else:
                float_data = audio_data.astype(np.float64)
            
            # 调试：检查输入数据范围
            if WDSP_DEBUG:
                in_min, in_max = float_data.min(), float_data.max()
                in_rms = np.sqrt(np.mean(float_data**2))
            
            # Ensure correct size
            if len(float_data) != self.buffer_size:
                # Handle buffer size mismatch
                if len(float_data) < self.buffer_size:
                    # Pad with zeros
                    padded = np.zeros(self.buffer_size, dtype=np.float64)
                    padded[:len(float_data)] = float_data
                    float_data = padded
                else:
                    # Truncate
                    float_data = float_data[:self.buffer_size]
            
            # WDSP expects interleaved I/Q data
            # For mono audio, I=audio, Q=0
            # H9: 持锁保护 fexchange0 与并发 SetRXA* 调用互斥
            with self._lock:
                self._in_buffer[0::2] = float_data  # I channel
                self._in_buffer[1::2] = 0.0  # Q channel

                # Process through WDSP
                error = ctypes.c_int(0)
                _wdsp.fexchange0(
                    ctypes.c_int(self.channel),
                    self._in_buffer.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
                    self._out_buffer.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
                    ctypes.byref(error)
                )

                # Extract output (I channel only for mono)
                output = self._out_buffer[0::2].copy()
            
            # error -2：输出未就绪（DSP 线程落后于消费速度）。
            # 绝不能拿原始输入顶替：原始输入比处理后的输出高约 18dB
            # （EMNR 已削 20~30dB），会造成 5.3ms 响 click + 时间线跳变。
            # 改为保持上一块输出（首次无历史则静音）。
            if error.value == -2:
                self.starved_blocks += 1
                if self.starved_blocks % 200 == 1:
                    print(f"⚠️ WDSP 输出饥饿(-2) 累计 {self.starved_blocks} 次，保持上一块输出")
                if self._last_output is not None and len(self._last_output) == len(audio_data):
                    return self._last_output.copy()
                return np.zeros_like(audio_data)
            elif error.value != 0:
                print(f"⚠️ WDSP processing error: {error.value}")

            # 软削波保护：当峰值超过 1.0 时进行软压缩
            out_peak = np.max(np.abs(output))
            if out_peak > 1.0:
                # 软压缩：超过 1.0 的部分按 0.5 比例缩小
                mask = np.abs(output) > 1.0
                output[mask] = np.sign(output[mask]) * (1.0 + (np.abs(output[mask]) - 1.0) * 0.5)
            
            # 调试：检查输出数据范围
            if WDSP_DEBUG:
                in_min, in_max = float_data.min(), float_data.max()
                in_rms = np.sqrt(np.mean(float_data**2))
                out_min, out_max = output.min(), output.max()
                out_rms = np.sqrt(np.mean(output**2))
                
                # 检查是否输出异常（可能引入噪音）
                if out_rms > in_rms * 2:
                    print(f"⚠️ WDSP 输出异常增大: in_rms={in_rms:.6f}, out_rms={out_rms:.6f}, ratio={out_rms/in_rms:.2f}")
            
            # Convert back to original format
            if audio_data.dtype == np.int16:
                output = np.clip(output * 32767, -32768, 32767).astype(np.int16)
            else:
                output = output.astype(audio_data.dtype)

            result = output[:len(audio_data)]
            self._last_output = result   # 供 -2 饥饿时保持
            return result
            
        except Exception as e:
            print(f"⚠️ WDSP processing error: {e}")
            return audio_data
    
    def get_meter(self, meter_type: int = WDSPMeterType.S_PK) -> float:
        """
        Get meter reading.
        
        Args:
            meter_type: Type of meter (S_PK, S_AV, AGC_GAIN, etc.)
            
        Returns:
            Meter value in dB
        """
        if not self._initialized:
            return 0.0
        
        try:
            return _wdsp.GetRXAMeter(ctypes.c_int(self.channel), ctypes.c_int(meter_type))
        except Exception as e:
            return 0.0
    
    def close(self):
        """Close WDSP channel and cleanup"""
        if self._initialized:
            try:
                _wdsp.SetChannelState(ctypes.c_int(self.channel), ctypes.c_int(0), ctypes.c_int(0))
                _wdsp.CloseChannel(ctypes.c_int(self.channel))
                self._initialized = False
                print(f"🔧 WDSP Processor closed")
            except Exception as e:
                print(f"⚠️ WDSP close error: {e}")
    
    def __del__(self):
        """Destructor - ensure cleanup"""
        self.close()


class WDSPExternalNB:
    """
    External Noise Blanker using WDSP.
    Can be used independently without a full RX channel.
    """
    
    def __init__(self, 
                 sample_rate: int = 48000,
                 buffer_size: int = 256,
                 threshold: float = 0.5,
                 tau: float = 0.01):
        """
        Initialize external noise blanker.
        
        Args:
            sample_rate: Audio sample rate
            buffer_size: Buffer size
            threshold: Detection threshold (0.0-1.0)
            tau: Time constant
        """
        if not WDSP_AVAILABLE:
            raise RuntimeError("WDSP library not available")
        
        self.id = 0
        self.sample_rate = sample_rate
        self.buffer_size = buffer_size
        
        try:
            _wdsp.create_nobEXT(
                ctypes.c_int(self.id),
                ctypes.c_int(1),  # run
                ctypes.c_int(0),  # mode
                ctypes.c_int(buffer_size),
                ctypes.c_double(sample_rate),
                ctypes.c_double(0.001),  # slewtime
                ctypes.c_double(0.005),  # hangtime
                ctypes.c_double(0.0005), # advtime
                ctypes.c_double(0.01),   # backtau
                ctypes.c_double(threshold)
            )
            print(f"🔧 WDSP External NB initialized")
        except Exception as e:
            print(f"❌ External NB init error: {e}")
            raise
    
    def process(self, audio_data: np.ndarray) -> np.ndarray:
        """Process audio through noise blanker"""
        try:
            # Convert to float64
            if audio_data.dtype == np.int16:
                float_data = audio_data.astype(np.float64) / 32768.0
            else:
                float_data = audio_data.astype(np.float64)
            
            # Ensure correct size
            if len(float_data) < self.buffer_size:
                padded = np.zeros(self.buffer_size, dtype=np.float64)
                padded[:len(float_data)] = float_data
                float_data = padded
            else:
                float_data = float_data[:self.buffer_size]
            
            # Output buffer
            out_buffer = np.zeros(self.buffer_size, dtype=np.float64)
            
            # Process
            _wdsp.xnobEXT(
                ctypes.c_int(self.id),
                float_data.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
                out_buffer.ctypes.data_as(ctypes.POINTER(ctypes.c_double))
            )
            
            # Convert back
            if audio_data.dtype == np.int16:
                result = np.clip(out_buffer[:len(audio_data)] * 32767, -32768, 32767).astype(np.int16)
            else:
                result = out_buffer[:len(audio_data)].astype(audio_data.dtype)
            
            return result
            
        except Exception as e:
            print(f"⚠️ NB process error: {e}")
            return audio_data
    
    def close(self):
        """Close noise blanker"""
        try:
            _wdsp.destroy_nobEXT(ctypes.c_int(self.id))
        except Exception as e:
            # L34: 清理失败不应完全静默，留 debug 痕迹
            print(f"⚠️ WDSPExternalNB close error: {e}")


def get_wdsp_version() -> int:
    """Get WDSP library version"""
    if not WDSP_AVAILABLE:
        return 0
    try:
        return _wdsp.GetWDSPVersion()
    except Exception:
        return 0


# Convenience function for quick processing
def process_with_wdsp(audio_data: np.ndarray,
                      sample_rate: int = 48000,
                      enable_nr2: bool = True,
                      enable_nb: bool = False) -> np.ndarray:
    """
    One-shot WDSP processing function.
    
    Args:
        audio_data: Input audio (int16 or float32)
        sample_rate: Sample rate
        enable_nr2: Enable spectral noise reduction
        enable_nb: Enable noise blanker
        
    Returns:
        Processed audio
    """
    if not WDSP_AVAILABLE:
        return audio_data
    
    processor = None
    try:
        processor = WDSPProcessor(
            sample_rate=sample_rate,
            buffer_size=len(audio_data),
            enable_nr2=enable_nr2,
            enable_nb=enable_nb
        )
        return processor.process(audio_data)
    except Exception as e:
        print(f"⚠️ WDSP processing error: {e}")
        return audio_data
    finally:
        if processor:
            processor.close()


# Test function
if __name__ == "__main__":
    print("=" * 60)
    print("WDSP Wrapper Test")
    print("=" * 60)
    
    if not WDSP_AVAILABLE:
        print("❌ WDSP library not available. Please build it first:")
        print("   cd /tmp && git clone https://github.com/g0orx/wdsp.git")
        print("   cd wdsp && make")
        exit(1)
    
    version = get_wdsp_version()
    print(f"WDSP Version: {version}")
    print()
    
    # Test processor
    print("Testing WDSP Processor...")
    try:
        proc = WDSPProcessor(
            sample_rate=48000,
            buffer_size=256,
            mode=WDSPMode.USB,
            enable_nr2=True,
            enable_nb=True,
            agc_mode=WDSPAGCMode.MED
        )
        
        # Generate test signal (noise + sine wave)
        t = np.linspace(0, 1, 48000)
        test_signal = (np.random.randn(48000) * 0.3 + 
                       np.sin(2 * np.pi * 1000 * t) * 0.5).astype(np.float32)
        
        # Process in chunks
        chunk_size = 256
        processed = []
        for i in range(0, len(test_signal), chunk_size):
            chunk = test_signal[i:i+chunk_size]
            if len(chunk) < chunk_size:
                chunk = np.pad(chunk, (0, chunk_size - len(chunk)))
            result = proc.process(chunk)
            processed.append(result[:len(test_signal[i:i+chunk_size])])
        
        processed = np.concatenate(processed)
        
        print(f"✅ Processing test passed")
        print(f"   Input shape: {test_signal.shape}")
        print(f"   Output shape: {processed.shape}")
        print(f"   Input power: {np.mean(test_signal**2):.4f}")
        print(f"   Output power: {np.mean(processed**2):.4f}")
        
        # Get meter reading
        meter = proc.get_meter(WDSPMeterType.S_PK)
        print(f"   S-meter: {meter:.1f} dB")
        
        proc.close()
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
    
    print()
    print("=" * 60)
    print("WDSP Wrapper test complete")
    print("=" * 60)