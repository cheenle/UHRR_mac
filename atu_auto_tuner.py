#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ATU 自动调谐模块 - V2.0 联动版

功能：
1. 与 MRRC 主程序联动（设置频率、启动 TUNE）
2. 与 ATR-1000 代理通信（设置天调参数、读取 SWR）
3. 与天调存储模块交互（保存最佳参数）

联动机制：
- 设置频率：通过 rigctld (127.0.0.1:4532) 直接与电台通信
- 启动 TUNE：调用 MRRC 的 start_tune()/stop_tune() 函数
- 读取 SWR：通过 ATR-1000 代理 Unix Socket

作者: MRRC Team
版本: 2.0.0
"""

import json
import logging
import threading
import time
import socket
import struct
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass, asdict
from enum import Enum

logger = logging.getLogger('ATU-AutoTuner')

# 业余无线电短波波段定义
HAM_BANDS = {
    '160m': {'start': 1800000, 'end': 2000000, 'name': '160m (1.8-2.0 MHz)'},
    '80m':  {'start': 3500000, 'end': 3900000, 'name': '80m (3.5-3.9 MHz)'},
    '60m':  {'start': 5351500, 'end': 5366500, 'name': '60m (5.35-5.37 MHz)'},
    '40m':  {'start': 7000000, 'end': 7200000, 'name': '40m (7.0-7.2 MHz)'},
    '30m':  {'start': 10100000, 'end': 10150000, 'name': '30m (10.1-10.15 MHz)'},
    '20m':  {'start': 14000000, 'end': 14350000, 'name': '20m (14.0-14.35 MHz)'},
    '17m':  {'start': 18068000, 'end': 18168000, 'name': '17m (18.07-18.17 MHz)'},
    '15m':  {'start': 21000000, 'end': 21450000, 'name': '15m (21.0-21.45 MHz)'},
    '12m':  {'start': 24890000, 'end': 24990000, 'name': '12m (24.89-24.99 MHz)'},
    '10m':  {'start': 28000000, 'end': 29700000, 'name': '10m (28.0-29.7 MHz)'},
}

# Unix Socket 路径
ATR1000_SOCKET_PATH = "/tmp/atr1000_proxy.sock"
MRRC_CONTROL_SOCKET = None  # MRRC 主程序内部调用

# rigctld 配置
RIGCTLD_HOST = "127.0.0.1"
RIGCTLD_PORT = 4532


class TunerState(Enum):
    """调谐状态"""
    IDLE = 'idle'
    TUNING = 'tuning'
    PAUSED = 'paused'
    COMPLETED = 'completed'
    ERROR = 'error'


@dataclass
class TuneResult:
    """单次调谐结果"""
    freq: int           # 频率
    swr: float          # 最佳 SWR
    sw: int             # 网络类型 (0=LC, 1=CL)
    ind: int            # 电感索引
    cap: int            # 电容索引
    success: bool       # 是否成功
    message: str = ""   # 消息


@dataclass
class TuneProgress:
    """调谐进度"""
    state: str                  # 状态
    current_freq: int           # 当前频率
    total_points: int           # 总点数
    completed_points: int       # 已完成点数
    current_swr: float          # 当前 SWR
    best_swr: float             # 最佳 SWR
    best_freq: int              # 最佳频率
    best_ind: int               # 最佳电感
    best_cap: int               # 最佳电容
    best_sw: int                # 最佳网络类型
    elapsed_time: float         # 已用时间 (秒)
    estimated_remaining: float  # 预计剩余时间 (秒)
    curve_data: List[Dict]      # 曲线数据


class RigctldClient:
    """rigctld 客户端 - 直接控制电台"""
    
    def __init__(self, host: str = RIGCTLD_HOST, port: int = RIGCTLD_PORT):
        self.host = host
        self.port = port
        self.lock = threading.Lock()
    
    def _send_command(self, command: str, timeout: float = 2.0) -> str:
        """发送命令到 rigctld"""
        with self.lock:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(timeout)
                sock.connect((self.host, self.port))
                sock.send((command + "\n").encode())
                response = sock.recv(1024).decode().strip()
                sock.close()
                return response
            except Exception as e:
                logger.error(f"rigctld 通信错误: {e}")
                return ""
    
    def set_freq(self, freq: int) -> bool:
        """设置频率"""
        response = self._send_command(f"F {freq}")
        return "RPRT 0" in response or response == ""
    
    def get_freq(self) -> int:
        """获取当前频率"""
        response = self._send_command("f")
        try:
            return int(response)
        except:
            return 0
    
    def set_ptt(self, on: bool) -> bool:
        """设置 PTT"""
        response = self._send_command(f"T {'1' if on else '0'}")
        return True
    
    def get_ptt(self) -> bool:
        """获取 PTT 状态"""
        response = self._send_command("t")
        return response == "1"


class ATR1000Client:
    """ATR-1000 代理客户端（带缓存）"""
    
    def __init__(self, socket_path: str = ATR1000_SOCKET_PATH):
        self.socket_path = socket_path
        self._cache = {}  # 缓存数据
        self._cache_time = {}  # 缓存时间
        self._cache_ttl = 0.5  # 缓存有效期（秒）
    
    def clear_cache(self):
        """清除缓存"""
        self._cache = {}
        self._cache_time = {}
    
    def _send_command(self, command: dict, timeout: float = 3.0, use_cache: bool = False) -> Optional[dict]:
        """发送命令到 ATR-1000 代理并等待响应"""
        action = command.get("action", "")
        
        # 检查缓存
        if use_cache and action in self._cache:
            if time.time() - self._cache_time.get(action, 0) < self._cache_ttl:
                return self._cache[action]
        
        sock = None
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            sock.connect(self.socket_path)
            
            # 发送命令
            msg = json.dumps(command) + "\n"
            sock.sendall(msg.encode())
            
            # 快速接收响应
            response_data = b""
            while True:
                try:
                    chunk = sock.recv(16384)
                    if not chunk:
                        break
                    response_data += chunk
                    if response_data.endswith(b"\n"):
                        break
                    if len(response_data) > 100000:
                        break
                except socket.timeout:
                    break
            
            if response_data:
                response_str = response_data.decode().strip()
                if response_str:
                    result = json.loads(response_str)
                    # 更新缓存
                    if use_cache:
                        self._cache[action] = result
                        self._cache_time[action] = time.time()
                    return result
            return None
            
        except socket.timeout:
            action = command.get('action', 'unknown')
            if action != "get_data":  # get_data 超时不记录
                logger.warning(f"ATR-1000 超时: {action}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"JSON 解析错误: {e}")
            return None
        except Exception as e:
            logger.error(f"ATR-1000 通信错误: {e}")
            return None
        finally:
            if sock:
                try:
                    sock.close()
                except:
                    pass
    
    def get_meter_data(self) -> Optional[dict]:
        """获取功率/SWR 数据（使用缓存）"""
        return self._send_command({"action": "get_data"}, use_cache=True)
    
    def set_relay(self, sw: int, ind: int, cap: int) -> bool:
        """设置继电器参数"""
        result = self._send_command({
            "action": "set_relay",
            "sw": sw,
            "ind": ind,
            "cap": cap
        })
        return result is not None
    
    def set_tune_status(self, is_tune: bool) -> bool:
        """设置 TUNE 状态（True=调谐状态，False=信号直通）"""
        result = self._send_command({
            "action": "set_tune_status",
            "is_tune": is_tune
        })
        return result is not None
    
    def start_tx(self) -> bool:
        """启动 TX 模式（加快代理轮询频率）"""
        result = self._send_command({"action": "start"})
        return result is not None
    
    def stop_tx(self) -> bool:
        """停止 TX 模式（恢复正常轮询频率）"""
        result = self._send_command({"action": "stop"})
        return result is not None
    
    def start_atu_tune(self, mode: int = 2) -> bool:
        """
        启动 ATU 自动调谐
        
        mode: 1=内存调谐, 2=完整调谐, 3=微调调谐
        """
        result = self._send_command({
            "action": "tune",
            "mode": mode
        })
        return result is not None
    
    def quick_tune(self, freq: int) -> Optional[Tuple[int, int, int]]:
        """快速调谐到指定频率（查找映射表）"""
        result = self._send_command({
            "action": "quick_tune",
            "freq": freq
        })
        if result and result.get("success"):
            return (result["sw"], result["ind"], result["cap"])
        return None
    
    def get_best_in_band(self, band_start: int, band_end: int) -> Optional[Tuple[int, int, int, float]]:
        """
        获取波段内 SWR 最低的记录
        
        返回: (sw, ind, cap, swr) 或 None
        """
        result = self._send_command({
            "action": "get_best_in_band",
            "band_start": band_start,
            "band_end": band_end
        })
        
        if result and result.get("found"):
            return (
                result.get("sw", 0),
                result.get("ind", 64),
                result.get("cap", 64),
                result.get("swr", 99.0)
            )
        return None
    
    def get_tune_records(self) -> List[dict]:
        """获取所有天调记录"""
        result = self._send_command({"action": "get_tune_records"}, timeout=5.0)
        if result:
            records = result.get("records", [])
            logger.debug(f"获取到 {len(records)} 条天调记录")
            return records
        logger.warning("获取天调记录失败")
        return []


class ATUAutoTuner:
    """ATU 自动调谐器 - V2.0 联动版"""
    
    def __init__(self):
        self.rig = RigctldClient()
        self.atr = ATR1000Client()
        self.state = TunerState.IDLE
        self.progress = TuneProgress(
            state='idle',
            current_freq=0,
            total_points=0,
            completed_points=0,
            current_swr=0,
            best_swr=99.0,
            best_freq=0,
            best_ind=0,
            best_cap=0,
            best_sw=0,
            elapsed_time=0,
            estimated_remaining=0,
            curve_data=[]
        )
        self.results: List[TuneResult] = []
        self.stop_flag = False
        self.tune_thread: Optional[threading.Thread] = None
        self.start_time = 0
        self.lock = threading.Lock()
        
        # 回调函数（用于通知 MRRC 主程序）
        self.on_progress_callback = None
        
        # MRRC 回调函数（用于发射控制）
        self.mrrc_start_tune = None   # 启动 TUNE 发射（播放 tune.wav + PTT）
        self.mrrc_stop_tune = None    # 停止 TUNE 发射
        self.mrrc_set_freq = None     # 设置电台频率
        
        # 调谐参数
        self.tune_delay = 0.1          # 每点调谐后延迟 (秒) - 优化：0.5→0.1
        self.swr_threshold = 3.0       # SWR 阈值
        self.fine_tune_range = 0.1     # 微调范围 (10%)
        self.fine_tune_step = 0.01     # 微调步进 (1%)
        self.tune_timeout = 3.0        # 单点调谐超时 (秒)
        self.swr_stable_count = 3      # SWR 稳定计数
        
        # 当前调谐波段最佳初始参数（从映射表获取）
        self.current_band_start = 0
        self.current_band_end = 0
        self.initial_sw = 0            # 网络类型
        self.initial_ind = 64          # 电感
        self.initial_cap = 64          # 电容
        self.initial_swr = 99.0        # 波段内最佳 SWR
    
    def get_bands(self) -> Dict:
        """获取可用波段列表"""
        return HAM_BANDS
    
    def get_progress(self) -> Dict:
        """获取调谐进度"""
        with self.lock:
            return asdict(self.progress)
    
    def get_results(self) -> List[Dict]:
        """获取调谐结果"""
        with self.lock:
            return [asdict(r) for r in self.results]
    
    def set_progress_callback(self, callback):
        """设置进度回调函数"""
        self.on_progress_callback = callback
    
    def _update_progress(self, **kwargs):
        """更新进度并通知"""
        with self.lock:
            for key, value in kwargs.items():
                if hasattr(self.progress, key):
                    setattr(self.progress, key, value)
        
        # 通知回调
        if self.on_progress_callback:
            try:
                self.on_progress_callback(self.get_progress())
            except:
                pass
    
    def _set_radio_freq(self, freq: int) -> bool:
        """设置电台频率"""
        logger.info(f"📻 设置电台频率: {freq/1000:.1f} kHz")
        
        # 优先使用 MRRC 回调
        if self.mrrc_set_freq:
            try:
                return self.mrrc_set_freq(freq)
            except Exception as e:
                logger.error(f"MRRC 设置频率失败: {e}")
        
        # 回退到 rigctld
        return self.rig.set_freq(freq)
    
    def _start_tune_transmission(self) -> bool:
        """
        启动 TUNE 发射（播放 tune.wav + PTT）
        
        发射将持续进行，直到 _stop_tune_transmission 被调用
        """
        logger.info("🎵 启动 TUNE 发射（持续模式）")
        
        # 1. 启动 MRRC 的 tune 播放（会循环播放 tune.wav）
        logger.info(f"🔧 mrrc_start_tune 回调: {self.mrrc_start_tune is not None}")
        if self.mrrc_start_tune:
            try:
                self.mrrc_start_tune()
                logger.info("  ✅ MRRC start_tune() 已调用，tune.wav 开始循环播放")
            except Exception as e:
                logger.error(f"  ❌ MRRC 启动 TUNE 失败: {e}")
                raise
        else:
            logger.warning("  ⚠️ mrrc_start_tune 回调未设置")
        
        # 2. 启动 ATR-1000 TX 模式（加快轮询频率）
        logger.info("🔧 启动 ATR-1000 TX 模式")
        self.atr.start_tx()
        
        # 3. 设置 ATR-1000 TUNE 状态
        logger.info("🔧 设置 ATR-1000 TUNE 状态")
        self.atr.set_tune_status(True)
        
        # 4. 确保频率已设置，PTT 已启动
        time.sleep(0.3)
        
        # 5. 额外确保 PTT 状态
        logger.info("🔧 设置 PTT ON")
        self.rig.set_ptt(True)
        
        logger.info("  ✅ 发射已启动，开始调谐...")
        return True
    
    def _stop_tune_transmission(self):
        """停止 TUNE 发射"""
        logger.info("🛑 停止 TUNE 发射")
        
        # 1. 停止 MRRC 的 tune 播放
        if self.mrrc_stop_tune:
            try:
                self.mrrc_stop_tune()
                logger.info("  ✅ MRRC stop_tune() 已调用")
            except Exception as e:
                logger.error(f"  ❌ MRRC 停止 TUNE 失败: {e}")
        
        # 2. 确保 PTT 关闭
        self.rig.set_ptt(False)
        
        # 3. 停止 ATR-1000 TUNE 状态
        self.atr.set_tune_status(False)
        
        # 4. 停止 ATR-1000 TX 模式（恢复正常轮询频率）
        self.atr.stop_tx()
        
        logger.info("  ✅ 发射已停止")
    
    def _read_swr(self, debug: bool = False) -> float:
        """读取 SWR（过滤无效值）"""
        data = self.atr.get_meter_data()
        if data:
            swr = data.get("swr", 0)
            power = data.get("power", 0)
            if debug:
                logger.info(f"  📊 读取: 功率={power}W, SWR={swr:.2f}")
            # 有效条件：功率 > 0，SWR 在 1.0-10.0 范围
            if power > 0 and swr >= 1.0 and swr < 10.0:
                return swr
            elif debug:
                logger.warning(f"  ⚠️ 无效数据: 功率={power}W, SWR={swr:.2f}")
        elif debug:
            logger.warning("  ⚠️ 无法获取数据")
        return 99.0
    
    def _find_best_in_band(self, band_start: int, band_end: int) -> Optional[Tuple[int, int, int, float]]:
        """
        在指定波段内查找 SWR 最低的记录
        
        返回: (sw, ind, cap, swr) 或 None
        """
        records = self.atr.get_tune_records()
        if not records:
            logger.info(f"  波段 {band_start/1000:.0f}-{band_end/1000:.0f}kHz 无历史记录")
            return None
        
        best_record = None
        best_swr = 99.0
        
        for record in records:
            freq = record.get("freq", 0)
            # 兼容 swr 和 swr_avg 字段
            swr = record.get("swr_avg") or record.get("swr", 99.0)
            
            # 只在该波段内查找
            if band_start <= freq <= band_end:
                if swr < best_swr:
                    best_swr = swr
                    best_record = record
        
        if best_record:
            result = (
                best_record.get("sw", 0),
                best_record.get("ind", 64),
                best_record.get("cap", 64),
                best_swr
            )
            logger.info(f"  波段内最佳记录: {best_record.get('freq')/1000:.0f}kHz SWR={best_swr:.2f}")
            return result
        
        logger.info(f"  波段 {band_start/1000:.0f}-{band_end/1000:.0f}kHz 无匹配记录")
        return None
    
    def _find_initial_params(self, freq: int) -> Optional[Tuple[int, int, int]]:
        """查找初始参数（优先使用波段内最佳记录）"""
        # 先尝试在当前波段内查找最佳记录
        if self.current_band_start > 0 and self.current_band_end > 0:
            band_best = self._find_best_in_band(self.current_band_start, self.current_band_end)
            if band_best:
                sw, ind, cap, swr = band_best
                logger.info(f"  波段内最佳初始参数: SWR={swr:.2f} SW={'CL' if sw else 'LC'} L={ind} C={cap}")
                return (sw, ind, cap)
        
        # 回退到快速调谐（查找最近频率）
        return self.atr.quick_tune(freq)
    
    def _fine_tune(self, freq: int, initial_sw: int, initial_ind: int, initial_cap: int) -> TuneResult:
        """
        微调优化 - 分步优化策略（快速版）
        
        策略：
        1. 固定L，扫描C（±10%，步进1%，约21个值）
        2. 固定最佳C，扫描L（±10%，步进1%，约21个值）
        3. 固定最佳L，再扫描C（±10%，步进1%，约21个值）
        
        总计约63次测试
        """
        best_swr = 99.0
        best_sw = initial_sw
        best_ind = initial_ind
        best_cap = initial_cap
        test_count = 0
        
        # 计算调整范围
        cap_range = max(3, int(initial_cap * self.fine_tune_range))
        ind_range = max(3, int(initial_ind * self.fine_tune_range))
        
        logger.info(f"  初始: SW={'CL' if initial_sw else 'LC'} L={initial_ind} C={initial_cap} 范围: L±{ind_range} C±{cap_range}")
        
        # 先测试初始参数
        self.atr.set_relay(initial_sw, initial_ind, initial_cap)
        time.sleep(0.05)
        best_swr = self._read_swr()
        test_count += 1
        
        if best_swr < 1.3:
            logger.info(f"  ✅ 初始SWR={best_swr:.2f} 已达标")
            return TuneResult(freq, best_swr, best_sw, best_ind, best_cap, True, f"SWR={best_swr:.2f}")
        
        # ========== 第一步：固定L，扫描C ==========
        for c_offset in range(-cap_range, cap_range + 1):
            if self.stop_flag:
                return TuneResult(freq, best_swr, best_sw, best_ind, best_cap, False, "用户中断")
            
            cap = initial_cap + c_offset
            cap = max(0, min(127, cap))
            
            self.atr.set_relay(best_sw, best_ind, cap)
            time.sleep(0.02)  # 快速等待
            
            current_swr = self._read_swr()
            test_count += 1
            
            if current_swr < best_swr:
                best_swr = current_swr
                best_cap = cap
        
        # ========== 第二步：固定C，扫描L ==========
        for l_offset in range(-ind_range, ind_range + 1):
            if self.stop_flag:
                return TuneResult(freq, best_swr, best_sw, best_ind, best_cap, False, "用户中断")
            
            ind = best_ind + l_offset
            ind = max(0, min(127, ind))
            
            self.atr.set_relay(best_sw, ind, best_cap)
            time.sleep(0.02)
            
            current_swr = self._read_swr()
            test_count += 1
            
            if current_swr < best_swr:
                best_swr = current_swr
                best_ind = ind
        
        # ========== 第三步：固定L，再扫描C ==========
        for c_offset in range(-cap_range, cap_range + 1):
            if self.stop_flag:
                return TuneResult(freq, best_swr, best_sw, best_ind, best_cap, False, "用户中断")
            
            cap = best_cap + c_offset
            cap = max(0, min(127, cap))
            
            self.atr.set_relay(best_sw, best_ind, cap)
            time.sleep(0.02)
            
            current_swr = self._read_swr()
            test_count += 1
            
            if current_swr < best_swr:
                best_swr = current_swr
                best_cap = cap
        
        # ========== 尝试另一种网络类型（仅当SWR>2.0时）==========
        if best_swr > 2.0:
            other_sw = 1 - best_sw
            self.atr.set_relay(other_sw, best_ind, best_cap)
            time.sleep(0.03)
            current_swr = self._read_swr()
            test_count += 1
            
            if current_swr < best_swr:
                best_swr = current_swr
                best_sw = other_sw
        
        success = best_swr < self.swr_threshold and best_swr < 99.0
        message = f"SWR={best_swr:.2f}" if success else f"SWR无效"
        
        logger.info(f"  ✅ {'CL' if best_sw else 'LC'} L={best_ind} C={best_cap} SWR={best_swr:.2f} ({test_count}次)")
        
        return TuneResult(freq, best_swr, best_sw, best_ind, best_cap, success, message)
    
    def _save_result(self, result: TuneResult):
        """保存结果到映射表"""
        if result.success and result.swr < 3.0:
            # 通过 ATR-1000 代理保存
            self.atr._send_command({
                "action": "learn",
                "freq": result.freq,
                "sw": result.sw,
                "ind": result.ind,
                "cap": result.cap,
                "swr": result.swr
            })
            logger.info(f"💾 保存: {result.freq/1000:.1f}kHz SWR={result.swr:.2f} {'CL' if result.sw else 'LC'} L={result.ind} C={result.cap}")
    
    def _tune_single_freq(self, freq: int) -> TuneResult:
        """
        调谐单个频率 - 用波段最佳参数作为起点，然后启动 ATU 调谐优化
        
        有历史参数时使用微调模式（mode=3，更快）
        无历史参数时使用完整调谐（mode=2）
        """
        logger.info(f"🔊 {freq/1000:.1f} kHz")
        
        # 清除缓存
        self.atr.clear_cache()
        
        # 1. 设置电台频率
        self._set_radio_freq(freq)
        
        # 2. 先设置波段内最佳初始参数（作为起点）
        self.atr.set_relay(self.initial_sw, self.initial_ind, self.initial_cap)
        time.sleep(0.1)  # 优化：0.2→0.1，继电器响应快
        
        # 3. 启动 ATU 自动调谐
        # 有历史参数用微调模式（mode=3），无历史参数用完整调谐（mode=2）
        tune_mode = 3 if self.initial_swr < 99.0 else 2
        mode_name = "微调" if tune_mode == 3 else "完整调谐"
        logger.info(f"  🔧 ATU {mode_name} (mode={tune_mode})")
        self.atr.start_atu_tune(mode=tune_mode)
        
        # 4. 等待调谐完成（优化：更快速检测）
        # 微调模式通常0.5-1秒完成，完整调谐1-2秒
        max_wait = 2.0 if tune_mode == 2 else 1.0  # 微调最多等1秒，完整调谐最多2秒
        check_interval = 0.1  # 检测间隔100ms
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            if self.stop_flag:
                return TuneResult(freq, 99.0, 0, 64, 64, False, "用户中断")
            time.sleep(check_interval)
            swr = self._read_swr()
            if swr < 3.0 and swr >= 1.0:
                break
        
        # 5. 读取最终参数
        data = self.atr.get_meter_data()
        if data:
            final_swr = data.get("swr", 99.0)
            final_sw = data.get("sw", 0)
            final_ind = data.get("ind", 64)
            final_cap = data.get("cap", 64)
            
            success = final_swr < self.swr_threshold
            logger.info(f"  ✅ SWR={final_swr:.2f} {'CL' if final_sw else 'LC'} L={final_ind} C={final_cap}")
            
            return TuneResult(freq, final_swr, final_sw, final_ind, final_cap, success, f"SWR={final_swr:.2f}")
        
        return TuneResult(freq, 99.0, 0, 64, 64, False, "调谐失败")
    
    def _tune_loop(self, freq_start: int, freq_end: int, step: int):
        """
        调谐循环
        
        发射在整个过程中持续进行，直到所有频率点调谐完成
        """
        logger.info(f"🔧 _tune_loop 开始: {freq_start/1000:.0f}-{freq_end/1000:.0f} kHz, step={step}")
        
        self.start_time = time.time()
        
        # 计算总点数
        freq_list = list(range(freq_start, freq_end + 1, step))
        total_points = len(freq_list)
        logger.info(f"🔧 总共 {total_points} 个频率点")
        
        self._update_progress(
            state='tuning',
            total_points=total_points,
            completed_points=0,
            best_swr=99.0,
            best_freq=0,
            curve_data=[]
        )
        
        # ========== 启动发射（整个调谐过程中持续） ==========
        logger.info("🎵 启动持续发射（TUNE 模式）")
        try:
            self._start_tune_transmission()
            logger.info("🔧 _start_tune_transmission 完成")
        except Exception as e:
            logger.error(f"❌ _start_tune_transmission 异常: {e}")
            return
        
        try:
            for i, freq in enumerate(freq_list):
                if self.stop_flag:
                    self._update_progress(state='paused')
                    break
                
                # 更新当前频率
                self._update_progress(current_freq=freq)
                
                # 调谐（发射已经在运行）
                result = self._tune_single_freq(freq)
                self.results.append(result)
                
                # 保存结果到映射表
                if result.success:
                    self._save_result(result)
                
                # 更新进度
                elapsed = time.time() - self.start_time
                remaining = (elapsed / (i + 1)) * (total_points - i - 1) if i > 0 else 0
                
                curve_point = {
                    "freq": freq,
                    "swr": result.swr,
                    "success": result.success
                }
                
                with self.lock:
                    self.progress.curve_data.append(curve_point)
                    self.progress.completed_points = i + 1
                    self.progress.current_swr = result.swr
                    self.progress.elapsed_time = elapsed
                    self.progress.estimated_remaining = remaining
                    
                    if result.swr < self.progress.best_swr:
                        self.progress.best_swr = result.swr
                        self.progress.best_freq = freq
                        self.progress.best_ind = result.ind
                        self.progress.best_cap = result.cap
                        self.progress.best_sw = result.sw
                
                # 频率点之间的短暂间隔（发射继续保持）
                time.sleep(self.tune_delay)
            
            # 完成
            if not self.stop_flag:
                self._update_progress(state='completed')
                self.state = TunerState.COMPLETED
                logger.info("🎉 自动调谐完成！")
            else:
                self.state = TunerState.PAUSED
                logger.info("⏸ 自动调谐已暂停")
            
        except Exception as e:
            logger.error(f"调谐错误: {e}")
            self._update_progress(state='error')
            self.state = TunerState.ERROR
        
        finally:
            # ========== 停止发射 ==========
            self._stop_tune_transmission()
    
    def start_tune(self, band: str = None, freq_start: int = None, freq_end: int = None, step: int = 1000) -> bool:
        """开始自动调谐"""
        if self.state == TunerState.TUNING:
            logger.warning("调谐正在进行中")
            return False
        
        # 确定频率范围
        if band and band in HAM_BANDS:
            freq_start = HAM_BANDS[band]['start']
            freq_end = HAM_BANDS[band]['end']
        elif freq_start and freq_end:
            pass
        else:
            logger.error("请指定波段或频率范围")
            return False
        
        # 验证频率范围
        if freq_start >= freq_end:
            logger.error("起始频率必须小于结束频率")
            return False
        
        if freq_start < 1800000 or freq_end > 30000000:
            logger.error("频率范围必须在 1.8-30 MHz 之间")
            return False
        
        # 保存波段范围
        self.current_band_start = freq_start
        self.current_band_end = freq_end
        
        # 获取波段内最佳初始参数
        best = self.atr.get_best_in_band(freq_start, freq_end)
        if best:
            self.initial_sw, self.initial_ind, self.initial_cap, self.initial_swr = best
            logger.info(f"📌 波段最佳: {'CL' if self.initial_sw else 'LC'} L={self.initial_ind} C={self.initial_cap} SWR={self.initial_swr:.2f}")
        else:
            self.initial_sw, self.initial_ind, self.initial_cap, self.initial_swr = 0, 64, 64, 99.0
            logger.info(f"📌 波段无记录，使用默认参数")
        
        # 重置状态
        self.stop_flag = False
        self.results = []
        self.state = TunerState.TUNING
        
        # 启动调谐线程
        self.tune_thread = threading.Thread(
            target=self._tune_loop,
            args=(freq_start, freq_end, step),
            daemon=True
        )
        self.tune_thread.start()
        
        logger.info(f"🚀 开始自动调谐: {freq_start/1000:.0f}-{freq_end/1000:.0f} kHz")
        return True
    
    def stop_tune(self):
        """停止调谐"""
        self.stop_flag = True
        self.state = TunerState.PAUSED
        logger.info("⏹ 停止调谐")
        
        # 立即停止发射
        self._stop_tune_transmission()
    
    def resume_tune(self) -> bool:
        """恢复调谐"""
        if self.state != TunerState.PAUSED:
            return False
        
        self.stop_flag = False
        self.state = TunerState.TUNING
        logger.info("▶ 恢复调谐")
        return True
    
    # ========== SWR 扫描模式（不调谐） ==========
    
    def start_swr_scan(self, band: str = None, freq_start: int = None, freq_end: int = None, step: int = 5000) -> bool:
        """
        开始 SWR 扫描（不调谐，只测量）
        
        用于分析天线的自然谐振特性
        """
        if self.state == TunerState.TUNING:
            logger.warning("调谐/扫描正在进行中")
            return False
        
        # 确定频率范围
        if band and band in HAM_BANDS:
            freq_start = HAM_BANDS[band]['start']
            freq_end = HAM_BANDS[band]['end']
        elif freq_start and freq_end:
            pass
        else:
            logger.error("请指定波段或频率范围")
            return False
        
        # 验证频率范围
        if freq_start >= freq_end:
            logger.error("起始频率必须小于结束频率")
            return False
        
        # SWR 扫描支持更宽的频率范围（1-60 MHz）
        if freq_start < 1000000 or freq_end > 60000000:
            logger.error("SWR 扫描频率范围必须在 1-60 MHz 之间")
            return False
        
        # 重置状态
        self.stop_flag = False
        self.results = []
        self.state = TunerState.TUNING
        
        # 启动扫描线程
        self.tune_thread = threading.Thread(
            target=self._swr_scan_loop,
            args=(freq_start, freq_end, step),
            daemon=True
        )
        self.tune_thread.start()
        
        logger.info(f"📊 开始 SWR 扫描: {freq_start/1000:.0f}-{freq_end/1000:.0f} kHz, 步进 {step/1000:.0f} kHz")
        return True
    
    def _swr_scan_loop(self, freq_start: int, freq_end: int, step: int):
        """
        SWR 扫描循环（不调谐，只测量）
        """
        self.start_time = time.time()
        
        # 计算总点数
        freq_list = list(range(freq_start, freq_end + 1, step))
        total_points = len(freq_list)
        
        logger.info(f"📊 扫描 {total_points} 个频率点")
        
        self._update_progress(
            state='tuning',
            total_points=total_points,
            completed_points=0,
            best_swr=99.0,
            best_freq=0,
            curve_data=[]
        )
        
        # ========== 启动发射 ==========
        logger.info("🎵 启动发射（SWR 扫描模式）")
        self._start_tune_transmission()
        
        # SWR 扫描：使用直通模式（不设置天调参数）
        # 这样才能测试天线的自然谐振特性
        self.atr.set_relay(0, 0, 0)
        logger.info("📌 直通模式（测试天线自然特性）")
        
        try:
            last_swr = 99.0  # 上一个频率的 SWR 值
            for i, freq in enumerate(freq_list):
                if self.stop_flag:
                    self._update_progress(state='paused')
                    break
                
                # 更新当前频率
                self._update_progress(current_freq=freq)
                
                # 测量 SWR（传入上一个值，返回当前值）
                result, last_swr = self._measure_swr(freq, last_swr)
                self.results.append(result)
                
                # 更新进度
                elapsed = time.time() - self.start_time
                remaining = (elapsed / (i + 1)) * (total_points - i - 1) if i > 0 else 0
                
                curve_point = {
                    "freq": freq,
                    "swr": result.swr,
                    "success": result.swr < 3.0
                }
                
                with self.lock:
                    self.progress.curve_data.append(curve_point)
                    self.progress.completed_points = i + 1
                    self.progress.current_swr = result.swr
                    self.progress.elapsed_time = elapsed
                    self.progress.estimated_remaining = remaining
                    
                    if result.swr < self.progress.best_swr:
                        self.progress.best_swr = result.swr
                        self.progress.best_freq = freq
                
                # 快速步进（只测不调谐，速度更快）
                # 注意：_measure_swr 已经有 0.3s 等待时间
                time.sleep(0.1)
            
            # 完成
            if not self.stop_flag:
                self._update_progress(state='completed')
                self.state = TunerState.COMPLETED
                logger.info("🎉 SWR 扫描完成！")
            else:
                self.state = TunerState.PAUSED
                logger.info("⏸ SWR 扫描已暂停")
            
        except Exception as e:
            logger.error(f"扫描错误: {e}")
            self._update_progress(state='error')
            self.state = TunerState.ERROR
        
        finally:
            # 停止发射
            self._stop_tune_transmission()
    
    def _measure_swr(self, freq: int, last_swr: float = 99.0) -> Tuple[TuneResult, float]:
        """
        测量单个频率的 SWR（不调谐）
        
        返回: (TuneResult, 当前SWR值) - 供下一个频率使用
        """
        logger.info(f"📊 {freq/1000:.1f} kHz")
        
        # 清除缓存
        self.atr.clear_cache()
        
        # 设置电台频率
        self._set_radio_freq(freq)
        
        # 等待稳定
        time.sleep(0.3)
        
        # 读取 SWR
        swr = self._read_swr(debug=True)
        
        # SWR=1.00 时使用上一个频率的值（可能是数据异常）
        if abs(swr - 1.0) < 0.01 and last_swr < 99.0:
            logger.info(f"  ⚠️ SWR=1.00，使用上一个值 {last_swr:.2f}")
            swr = last_swr
        
        # 获取当前天调参数
        data = self.atr.get_meter_data()
        sw = data.get("sw", 0) if data else 0
        ind = data.get("ind", 0) if data else 0
        cap = data.get("cap", 0) if data else 0
        
        success = swr < 3.0
        logger.info(f"  SWR={swr:.2f}")
        
        return TuneResult(freq, swr, sw, ind, cap, success, f"SWR={swr:.2f}"), swr


# 全局单例
_auto_tuner = None
_tuner_lock = threading.Lock()

def get_auto_tuner() -> ATUAutoTuner:
    """获取自动调谐器单例"""
    global _auto_tuner
    with _tuner_lock:
        if _auto_tuner is None:
            _auto_tuner = ATUAutoTuner()
        return _auto_tuner


# ========== API 处理函数 ==========

def handle_auto_tune_command(command: dict) -> dict:
    """处理自动调谐命令"""
    tuner = get_auto_tuner()
    action = command.get("action", "")
    
    if action == "auto_tune_get_bands":
        return {
            "type": "bands",
            "bands": tuner.get_bands()
        }
    
    elif action == "auto_tune_start":
        band = command.get("band")
        freq_start = command.get("freq_start")
        freq_end = command.get("freq_end")
        step = command.get("step", 1000)
        
        success = tuner.start_tune(band, freq_start, freq_end, step)
        return {
            "type": "auto_tune_start",
            "success": success,
            "message": "调谐已启动" if success else "启动失败"
        }
    
    elif action == "swr_scan_start":
        # SWR 扫描模式（不调谐，只测SWR）
        band = command.get("band")
        freq_start = command.get("freq_start")
        freq_end = command.get("freq_end")
        step = command.get("step", 5000)  # 默认 5kHz
        
        success = tuner.start_swr_scan(band, freq_start, freq_end, step)
        return {
            "type": "swr_scan_start",
            "success": success,
            "message": "SWR扫描已启动" if success else "启动失败"
        }
    
    elif action == "auto_tune_stop":
        tuner.stop_tune()
        return {
            "type": "auto_tune_stop",
            "success": True
        }
    
    elif action == "auto_tune_resume":
        success = tuner.resume_tune()
        return {
            "type": "auto_tune_resume",
            "success": success
        }
    
    elif action == "auto_tune_status":
        return {
            "type": "auto_tune_status",
            **tuner.get_progress()
        }
    
    elif action == "auto_tune_results":
        return {
            "type": "auto_tune_results",
            "results": tuner.get_results()
        }
    
    else:
        return {
            "type": "error",
            "message": f"未知命令: {action}"
        }


# ========== 测试代码 ==========
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    tuner = ATUAutoTuner()
    
    # 打印可用波段
    print("=== 可用波段 ===")
    for band, info in tuner.get_bands().items():
        print(f"  {band}: {info['name']}")
    
    # 测试 rigctld 连接
    print("\n=== 测试 rigctld 连接 ===")
    freq = tuner.rig.get_freq()
    print(f"当前频率: {freq/1000:.1f} kHz" if freq else "无法获取频率")
    
    # 测试 ATR-1000 连接
    print("\n=== 测试 ATR-1000 连接 ===")
    data = tuner.atr.get_meter_data()
    if data:
        print(f"功率: {data.get('power', 0)}W, SWR: {data.get('swr', 0):.2f}")
    else:
        print("无法连接 ATR-1000")
