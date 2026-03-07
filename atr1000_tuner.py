#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ATR-1000 天调存储模块 - V4.5.14 增强版

核心功能：
1. 记录频率对应的天调参数（LC/CL、电感、电容）
2. 自动学习：发射时记录 SWR 1.0-1.5 的参数
3. 快速调谐：根据频率自动设置天调参数
4. 动态更新：持续优化已存储的参数

数据结构：
{
    "freq": 7053000,          # 频率
    "sw": 0,                  # 网络类型: 0=LC, 1=CL
    "ind": 45,                # 电感索引 (0-127)
    "cap": 32,                # 电容索引 (0-127)
    "swr_avg": 1.15,          # 平均驻波比
    "swr_min": 1.10,          # 最小驻波比
    "swr_max": 1.20,          # 最大驻波比
    "sample_count": 5,        # 采样次数
    "last_update": timestamp  # 最后更新时间
}

作者: MRRC Team
版本: 2.0.0
"""

import json
import os
import time
import logging
import threading
from datetime import datetime
from typing import Optional, Dict, List, Tuple

logger = logging.getLogger('ATR1000-Tuner')

# 存储文件路径
STORAGE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'atr1000_tuner.json')

# SWR 学习阈值
SWR_LEARN_MIN = 1.0   # 最小 SWR 阈值
SWR_LEARN_MAX = 1.5   # 最大 SWR 阈值

# 频率匹配容差
FREQ_TOLERANCE = 5000  # ±5kHz


class TunerStorage:
    """天调参数存储管理 - 增强版"""
    
    def __init__(self, storage_file: str = None):
        self.storage_file = storage_file or STORAGE_FILE
        self.data: Dict[str, dict] = {}  # key: freq_key, value: record
        self.lock = threading.Lock()
        self._load()
    
    def _freq_key(self, freq: int) -> str:
        """生成频率键 (精度到 1kHz)"""
        return str(freq // 1000)
    
    def _load(self):
        """加载存储数据"""
        try:
            if os.path.exists(self.storage_file):
                with open(self.storage_file, 'r', encoding='utf-8') as f:
                    raw = json.load(f)
                    # 转换为以频率为 key 的字典
                    for record in raw.get('records', []):
                        freq = record.get('freq', 0)
                        if freq > 0:
                            key = self._freq_key(freq)
                            self.data[key] = record
                logger.info(f"📂 加载 {len(self.data)} 条天调记录")
        except Exception as e:
            logger.error(f"加载天调数据失败: {e}")
            self.data = {}
    
    def _save(self):
        """保存存储数据"""
        try:
            raw = {
                'version': '2.0',
                'updated': datetime.now().isoformat(),
                'records': list(self.data.values())
            }
            with open(self.storage_file, 'w', encoding='utf-8') as f:
                json.dump(raw, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"保存天调数据失败: {e}")
    
    def learn(self, freq: int, sw: int, ind: int, cap: int, swr: float) -> bool:
        """
        学习天调参数 - 当 SWR 在 1.0-1.5 范围内时记录
        
        Args:
            freq: 频率
            sw: 网络类型 (0=LC, 1=CL)
            ind: 电感索引 (0-127)
            cap: 电容索引 (0-127)
            swr: 驻波比
        
        Returns:
            是否成功记录
        """
        # 检查 SWR 范围
        if swr < SWR_LEARN_MIN or swr > SWR_LEARN_MAX:
            return False
        
        with self.lock:
            key = self._freq_key(freq)
            
            if key in self.data:
                # 更新已有记录 - 动态平均
                record = self.data[key]
                old_avg = record['swr_avg']
                old_count = record['sample_count']
                new_count = old_count + 1
                
                # 指数移动平均
                record['swr_avg'] = (old_avg * old_count + swr) / new_count
                record['sample_count'] = new_count
                record['swr_min'] = min(record['swr_min'], swr)
                record['swr_max'] = max(record['swr_max'], swr)
                record['last_update'] = time.time()
                
                # 如果新参数 SWR 更好，更新参数
                if swr < record['swr_avg']:
                    record['sw'] = sw
                    record['ind'] = ind
                    record['cap'] = cap
                    
            else:
                # 新记录
                self.data[key] = {
                    'freq': freq,
                    'sw': sw,
                    'ind': ind,
                    'cap': cap,
                    'swr_avg': swr,
                    'swr_min': swr,
                    'swr_max': swr,
                    'sample_count': 1,
                    'last_update': time.time()
                }
            
            self._save()
            logger.info(f"📝 学习: {freq/1000:.1f}kHz, SWR={swr:.2f}, SW={'CL' if sw else 'LC'}, L={ind}, C={cap}")
            return True
    
    def find_best(self, freq: int) -> Optional[dict]:
        """
        查找频率的最佳天调参数
        
        Args:
            freq: 目标频率
        
        Returns:
            最佳匹配记录，或 None
        """
        with self.lock:
            # 精确匹配
            key = self._freq_key(freq)
            if key in self.data:
                return self.data[key].copy()
            
            # 范围搜索 (±5kHz)
            freq_khz = freq // 1000
            best_record = None
            best_dist = float('inf')
            
            for k, record in self.data.items():
                record_freq_khz = int(k)
                dist = abs(freq_khz - record_freq_khz)
                
                if dist <= (FREQ_TOLERANCE // 1000) and dist < best_dist:
                    best_dist = dist
                    best_record = record
            
            if best_record:
                return best_record.copy()
            
            return None
    
    def get_tune_params(self, freq: int) -> Optional[Tuple[int, int, int]]:
        """
        获取频率对应的调谐参数
        
        Args:
            freq: 目标频率
        
        Returns:
            (sw, ind, cap) 或 None
        """
        record = self.find_best(freq)
        if record:
            return (record['sw'], record['ind'], record['cap'])
        return None
    
    def get_all(self) -> List[dict]:
        """获取所有记录（按频率排序）"""
        with self.lock:
            records = list(self.data.values())
            records.sort(key=lambda x: x.get('freq', 0))
            return records
    
    def delete(self, freq: int) -> bool:
        """删除指定频率的记录"""
        with self.lock:
            key = self._freq_key(freq)
            if key in self.data:
                del self.data[key]
                self._save()
                return True
            return False
    
    def clear(self):
        """清空所有记录"""
        with self.lock:
            self.data = {}
            self._save()
    
    def get_stats(self) -> dict:
        """获取统计信息"""
        with self.lock:
            if not self.data:
                return {'count': 0}
            
            records = list(self.data.values())
            swr_values = [r['swr_avg'] for r in records]
            
            return {
                'count': len(records),
                'swr_avg': sum(swr_values) / len(swr_values),
                'swr_min': min(swr_values),
                'swr_max': max(swr_values)
            }


# 全局单例
_storage = None
_storage_lock = threading.Lock()

def get_storage() -> TunerStorage:
    """获取存储单例"""
    global _storage
    with _storage_lock:
        if _storage is None:
            _storage = TunerStorage()
        return _storage


# ========== 测试代码 ==========
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    storage = TunerStorage()
    
    # 测试学习
    print("=== 测试学习 ===")
    storage.learn(7053000, 0, 45, 32, 1.15)
    storage.learn(7053000, 0, 46, 33, 1.10)  # 更好的参数
    storage.learn(7055000, 1, 50, 40, 1.25)
    
    # 测试查找
    print("\n=== 测试查找 ===")
    result = storage.find_best(7053000)
    print(f"7.053MHz: {result}")
    
    result = storage.find_best(7054000)  # 相近频率
    print(f"7.054MHz: {result}")
    
    result = storage.find_best(14000000)  # 无匹配
    print(f"14.000MHz: {result}")
    
    # 统计
    print("\n=== 统计 ===")
    print(storage.get_stats())