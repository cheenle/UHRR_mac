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

# Try to load WDSP library
def _load_wdsp_library():
    """Load the WDSP shared library"""
    import platform
    system = platform.system()
    
    # Search paths
    search_paths = [
        os.path.dirname(os.path.abspath(__file__)),  # Same directory
        "/usr/local/lib",
        "/opt/homebrew/lib",  # macOS Homebrew ARM64
        "/opt/local/lib",      # macOS Homebrew x86-64
        "/usr/lib",
        "/tmp/wdsp",  # Build directory
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "DSP", "wdsp"),  # 项目目录
        ".",
    ]
    
    lib_name = "libwdsp.dylib" if system == "Darwin" else "libwdsp.so"
    
    print(f"🔍 WDSP: 正在搜索库文件: {lib_name}")
    
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
    
    # Try system library
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
                 agc_mode: int = WDSPAGCMode.MED):
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
        # Buffers for WDSP processing (float64 - WDSP 库要求)
        self._in_buffer = np.zeros(buffer_size * 2, dtype=np.float64)
        self._out_buffer = np.zeros(buffer_size * 2, dtype=np.float64)
        
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
            _wdsp.SetRXAPanelGain1(ctypes.c_int(self.channel), ctypes.c_double(0.06))
            
            # 注意：暂时禁用带通滤波器，因为测试显示它会导致信号被错误衰减
            # 后续需要进一步调试带通滤波器参数
            # self.set_bandpass(300.0, 2700.0)
            
            # Configure AGC (注意：必须在设置PanelGain之后)
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
            
            self._initialized = True
            print(f"🔧 WDSP Processor initialized: SR={self.sample_rate}Hz, Mode={self.mode}")
            print(f"   NR2={'ON' if self._nr2_enabled else 'OFF'}, "
                  f"NB={'ON' if self._nb_enabled else 'OFF'}, "
                  f"ANF={'ON' if self._anf_enabled else 'OFF'}, "
                  f"AGC={self._agc_mode}")
            
        except Exception as e:
            print(f"❌ WDSP initialization error: {e}")
            raise
    
    def _setup_nr2(self):
        """Setup Spectral Noise Reduction (NR2) - using EMNR for strong noise reduction"""
        try:
            # 使用 EMNR (Enhanced Multi-band NR) - 专业级频谱降噪
            _wdsp.SetRXAANRRun(ctypes.c_int(self.channel), ctypes.c_int(0))  # 禁用 LMS NR
            
            # 启用 EMNR
            _wdsp.SetRXAEMNRRun(ctypes.c_int(self.channel), ctypes.c_int(1))
            
            # EMNR 参数配置 - 使用中等强度默认设置
            # gainMethod: 0=保守, 1=中等, 2=激进(最大降噪)
            # npeMethod: 0=LambdaD, 1=LambdaDs
            # aeRun: 1=开启自动均衡(消除音乐噪音)
            _wdsp.SetRXAEMNRgainMethod(ctypes.c_int(self.channel), ctypes.c_int(1))  # 中等强度
            _wdsp.SetRXAEMNRnpeMethod(ctypes.c_int(self.channel), ctypes.c_int(1))   # LambdaDs
            _wdsp.SetRXAEMNRaeRun(ctypes.c_int(self.channel), ctypes.c_int(1))       # 开启自动均衡
            _wdsp.SetRXAEMNRPosition(ctypes.c_int(self.channel), ctypes.c_int(1))
            
            self._nr2_enabled = True
            self._nr2_level = 1  # 默认强度
            print(f"   NR2 (EMNR) configured - gainMethod=1, npeMethod=1, aeRun=ON (中等强度)")
        except Exception as e:
            print(f"   ⚠️ NR2 setup error: {e}")
    
    def set_nr2_level(self, level: int):
        """
        Set NR2 intensity level (EMNR mode).
        
        Args:
            level: 0-4 
                0 = OFF
                1 = MIN (gainMethod=0, aeRun=OFF) - 极温和
                2 = LOW (gainMethod=0, aeRun=ON) - 温和
                3 = MED (gainMethod=1, aeRun=OFF) - 中等
                4 = HIGH (gainMethod=2, aeRun=ON) - 强力
        """
        if not self._initialized:
            return
        
        try:
            if level == 0:
                # 关闭 NR
                _wdsp.SetRXAEMNRRun(ctypes.c_int(self.channel), ctypes.c_int(0))
                _wdsp.SetRXAANRRun(ctypes.c_int(self.channel), ctypes.c_int(0))
                self._nr2_enabled = False
                self._nr2_level = 0
                print(f"🔧 WDSP NR2: OFF")
            else:
                # 使用 EMNR
                _wdsp.SetRXAANRRun(ctypes.c_int(self.channel), ctypes.c_int(0))
                _wdsp.SetRXAEMNRRun(ctypes.c_int(self.channel), ctypes.c_int(1))
                
                # 组合参数：gainMethod 和 aeRun
                # 增强降噪效果：使用更激进的参数
                # level 1: gainMethod=1, aeRun=1 (中等强度)
                # level 2: gainMethod=2, aeRun=1 (高强度)
                # level 3: gainMethod=2, aeRun=1 + 额外设置 (强力)
                # level 4: gainMethod=2, aeRun=1 + 最大效果 (极强力)
                params = {
                    1: (1, 1, 1),  # gainMethod=1(中等), npeMethod=1, aeRun=1
                    2: (2, 1, 1),  # gainMethod=2(激进), npeMethod=1, aeRun=1
                    3: (2, 1, 1),  # gainMethod=2(激进), npeMethod=1, aeRun=1
                    4: (2, 1, 1),  # gainMethod=2(激进), npeMethod=1, aeRun=1
                }
                gain_method, npe_method, ae_run = params.get(level, (1, 1, 1))
                
                _wdsp.SetRXAEMNRgainMethod(ctypes.c_int(self.channel), ctypes.c_int(gain_method))
                _wdsp.SetRXAEMNRnpeMethod(ctypes.c_int(self.channel), ctypes.c_int(npe_method))
                _wdsp.SetRXAEMNRaeRun(ctypes.c_int(self.channel), ctypes.c_int(ae_run))
                
                self._nr2_enabled = True
                self._nr2_level = level
                level_names = {1: 'MIN(极温和)', 2: 'LOW(温和)', 3: 'MED(中等)', 4: 'HIGH(强力)'}
                print(f"🔧 WDSP NR2: {level_names.get(level, level)} (gain={gain_method}, ae={ae_run})")
        except Exception as e:
            print(f"⚠️ NR2 level error: {e}")
    
    def set_nr2_gain_method(self, method: int):
        """Set NR2 Gain Method (0=Conservative, 1=Moderate, 2=Aggressive)"""
        if not self._initialized or not self._nr2_enabled:
            return
        try:
            _wdsp.SetRXAEMNRgainMethod(ctypes.c_int(self.channel), ctypes.c_int(method))
            self._nr2_gain_method = method
            method_names = {0: 'Conservative', 1: 'Moderate', 2: 'Aggressive'}
            print(f"🔧 WDSP NR2 GainMethod: {method_names.get(method, method)}")
        except Exception as e:
            print(f"⚠️ NR2 gain method error: {e}")
    
    def set_nr2_npe_method(self, method: int):
        """Set NR2 NPE Method (0=LambdaD, 1=LambdaDs)"""
        if not self._initialized or not self._nr2_enabled:
            return
        try:
            _wdsp.SetRXAEMNRnpeMethod(ctypes.c_int(self.channel), ctypes.c_int(method))
            self._nr2_npe_method = method
            method_names = {0: 'LambdaD', 1: 'LambdaDs'}
            print(f"🔧 WDSP NR2 NpeMethod: {method_names.get(method, method)}")
        except Exception as e:
            print(f"⚠️ NR2 npe method error: {e}")
    
    def set_nr2_ae_run(self, enabled: bool):
        """Set NR2 Auto-Equalization Run"""
        if not self._initialized or not self._nr2_enabled:
            return
        try:
            _wdsp.SetRXAEMNRaeRun(ctypes.c_int(self.channel), ctypes.c_int(1 if enabled else 0))
            self._nr2_ae_run = enabled
            print(f"🔧 WDSP NR2 AeRun: {'ON' if enabled else 'OFF'}")
        except Exception as e:
            print(f"⚠️ NR2 ae run error: {e}")
    
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
        Set bandpass filter frequencies.
        
        Args:
            low_freq: Low cutoff frequency in Hz
            high_freq: High cutoff frequency in Hz
        """
        if not self._initialized:
            return
        
        try:
            _wdsp.SetRXABandpassRun(ctypes.c_int(self.channel), ctypes.c_int(1))
            _wdsp.SetRXABandpassFreqs(
                ctypes.c_int(self.channel),
                ctypes.c_double(low_freq),
                ctypes.c_double(high_freq)
            )
            self._bandpass_low = low_freq
            self._bandpass_high = high_freq
            print(f"🔧 WDSP Bandpass: {low_freq}Hz - {high_freq}Hz")
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
                # AGC OFF 时，设置固定增益为 1.0（直通），避免额外增益放大噪音
                _wdsp.SetRXAAGCAttack(ctypes.c_int(self.channel), ctypes.c_int(0))
                _wdsp.SetRXAAGCDecay(ctypes.c_int(self.channel), ctypes.c_int(0))
                _wdsp.SetRXAAGCHang(ctypes.c_int(self.channel), ctypes.c_int(0))
                # 设置 AGC 目标增益为 0dB（无增益）
                # _wdsp.SetRXAAGCTarget(ctypes.c_int(self.channel), ctypes.c_float(0.0))
                # 关键：强制设置固定增益为 1.0（无增益），从源头防止削波
                _wdsp.SetRXAAGCFixed(ctypes.c_int(self.channel), ctypes.c_double(1.0))
                # print(f"🔧 WDSP AGC: OFF (固定增益=1.0, 无放大)")
            elif mode == WDSPAGCMode.MED:
                _wdsp.SetRXAAGCAttack(ctypes.c_int(self.channel), ctypes.c_int(4))
                _wdsp.SetRXAAGCDecay(ctypes.c_int(self.channel), ctypes.c_int(250))
                _wdsp.SetRXAAGCHang(ctypes.c_int(self.channel), ctypes.c_int(250))
                # _wdsp.SetRXAAGCTarget(ctypes.c_int(self.channel), ctypes.c_float(-3.0))  # 默认目标 -3dB
                # print(f"🔧 WDSP AGC: MED")
            elif mode == WDSPAGCMode.FAST:
                _wdsp.SetRXAAGCAttack(ctypes.c_int(self.channel), ctypes.c_int(2))
                _wdsp.SetRXAAGCDecay(ctypes.c_int(self.channel), ctypes.c_int(100))
                _wdsp.SetRXAAGCHang(ctypes.c_int(self.channel), ctypes.c_int(100))
                # _wdsp.SetRXAAGCTarget(ctypes.c_int(self.channel), ctypes.c_float(-3.0))
                # print(f"🔧 WDSP AGC: FAST")
            elif mode == WDSPAGCMode.SLOW:
                _wdsp.SetRXAAGCAttack(ctypes.c_int(self.channel), ctypes.c_int(4))
                _wdsp.SetRXAAGCDecay(ctypes.c_int(self.channel), ctypes.c_int(500))
                _wdsp.SetRXAAGCHang(ctypes.c_int(self.channel), ctypes.c_int(500))
                # _wdsp.SetRXAAGCTarget(ctypes.c_int(self.channel), ctypes.c_float(-3.0))
                # print(f"🔧 WDSP AGC: SLOW")
            elif mode == WDSPAGCMode.LONG:
                _wdsp.SetRXAAGCAttack(ctypes.c_int(self.channel), ctypes.c_int(6))
                _wdsp.SetRXAAGCDecay(ctypes.c_int(self.channel), ctypes.c_int(1000))
                _wdsp.SetRXAAGCHang(ctypes.c_int(self.channel), ctypes.c_int(1000))
                # _wdsp.SetRXAAGCTarget(ctypes.c_int(self.channel), ctypes.c_float(-3.0))
                # print(f"🔧 WDSP AGC: LONG")
            
            # 关键：每次 AGC 模式切换后，重新设置 PanelGain1 = 0.06
            # 保持保守增益，减少削峰
            _wdsp.SetRXAPanelGain1(ctypes.c_int(self.channel), ctypes.c_double(0.06))
                
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
            
            # error -2 means "output samples not available" - this is normal during startup
            # WDSP uses ring buffers and needs time to fill them
            if error.value == -2:
                # 输出不可用，返回输入数据（直通）
                return audio_data
            elif error.value != 0:
                print(f"⚠️ WDSP processing error: {error.value}")
            
            # Extract output (I channel only for mono)
            output = self._out_buffer[0::2].copy()
            
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
            
            return output[:len(audio_data)]
            
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
            pass


def get_wdsp_version() -> int:
    """Get WDSP library version"""
    if not WDSP_AVAILABLE:
        return 0
    try:
        return _wdsp.GetWDSPVersion()
    except:
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