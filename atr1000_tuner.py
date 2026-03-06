#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ATR-1000 天调存储模块

功能：
1. 存储频率对应的天调参数（LC/CL、电感、电容）
2. 根据频率自动匹配最佳天调参数
3. 提供天调参数管理 API

数据结构：
{
    "id": "uuid",
    "freq_min": 7000000,      # 频率下限
    "freq_max": 7200000,      # 频率上限
    "band": "40m",            # 波段名称
    "sw": 0,                  # 网络类型: 0=LC, 1=CL
    "ind": 45,                # 电感值 (索引 0-127)
    "cap": 32,                # 电容值 (索引 0-127)
    "swr": 1.15,              # 最佳驻波比
    "power": 100,             # 测试功率 (W)
    "timestamp": "2026-03-04T12:00:00",
    "notes": "40m波段最佳"
}

作者: MRRC Team
版本: 1.0.0
"""

import json
import os
import time
import uuid
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

# 配置日志
logger = logging.getLogger('ATR1000-Tuner')

# 存储文件路径
STORAGE_FILE = os.path.join(os.path.dirname(__file__), 'atr1000_tuner.json')

# 默认波段定义
DEFAULT_BANDS = [
    {"name": "160m", "freq_min": 1800000, "freq_max": 2000000},
    {"name": "80m", "freq_min": 3500000, "freq_max": 4000000},
    {"name": "60m", "freq_min": 5250000, "freq_max": 5450000},
    {"name": "40m", "freq_min": 7000000, "freq_max": 7300000},
    {"name": "30m", "freq_min": 10100000, "freq_max": 10150000},
    {"name": "20m", "freq_min": 14000000, "freq_max": 14350000},
    {"name": "17m", "freq_min": 18068000, "freq_max": 18168000},
    {"name": "15m", "freq_min": 21000000, "freq_max": 21450000},
    {"name": "12m", "freq_min": 24890000, "freq_max": 24990000},
    {"name": "10m", "freq_min": 28000000, "freq_max": 29700000},
    {"name": "6m", "freq_min": 50000000, "freq_max": 54000000},
]


class ATR1000TunerStorage:
    """ATR-1000 天调参数存储管理"""
    
    def __init__(self, storage_file: str = None):
        self.storage_file = storage_file or STORAGE_FILE
        self.records: List[Dict[str, Any]] = []
        self.load()
    
    def load(self) -> bool:
        """加载存储数据"""
        try:
            if os.path.exists(self.storage_file):
                with open(self.storage_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.records = data.get('records', [])
                    logger.info(f"加载 {len(self.records)} 条天调记录")
                return True
        except Exception as e:
            logger.error(f"加载天调数据失败: {e}")
            self.records = []
        return False
    
    def save(self) -> bool:
        """保存存储数据"""
        try:
            data = {
                'version': '1.0',
                'updated': datetime.now().isoformat(),
                'records': self.records
            }
            with open(self.storage_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.info(f"保存 {len(self.records)} 条天调记录")
            return True
        except Exception as e:
            logger.error(f"保存天调数据失败: {e}")
            return False
    
    def get_band_name(self, freq: int) -> str:
        """根据频率获取波段名称"""
        for band in DEFAULT_BANDS:
            if band['freq_min'] <= freq <= band['freq_max']:
                return band['name']
        return "Unknown"
    
    def find_best_match(self, freq: int, tolerance: int = 100000) -> Optional[Dict[str, Any]]:
        """
        查找频率的最佳天调参数
        
        Args:
            freq: 目标频率
            tolerance: 频率容差, 默认 ±100kHz
        
        Returns:
            最佳匹配记录，或 None
        """
        freq_min = freq - tolerance
        freq_max = freq + tolerance
        
        # 筛选频率范围内的记录
        matches = []
        for record in self.records:
            # 检查记录的频率范围是否与目标频率重叠
            record_min = record.get('freq_min', 0)
            record_max = record.get('freq_max', 0)
            
            # 如果记录的频率范围与目标范围有重叠
            if record_min <= freq_max and record_max >= freq_min:
                matches.append(record)
        
        if not matches:
            return None
        
        # 按 SWR 排序，选择最低的
        matches.sort(key=lambda x: x.get('swr', 999))
        return matches[0]
    
    def find_by_band(self, band_name: str) -> List[Dict[str, Any]]:
        """查找指定波段的所有记录"""
        return [r for r in self.records if r.get('band') == band_name]
    
    def add_record(self, freq: int, sw: int, ind: int, cap: int, 
                   swr: float = 0, power: int = 0, 
                   freq_range: int = 50000, notes: str = "") -> Dict[str, Any]:
        """
        添加天调参数记录
        
        Args:
            freq: 中心频率
            sw: 网络类型 (0=LC, 1=CL)
            ind: 电感索引 (0-127)
            cap: 电容索引 (0-127)
            swr: 驻波比
            power: 测试功率
            freq_range: 频率范围 ±Hz，默认 ±50kHz
            notes: 备注
        
        Returns:
            新创建的记录
        """
        record = {
            'id': str(uuid.uuid4()),
            'freq_min': freq - freq_range,
            'freq_max': freq + freq_range,
            'center_freq': freq,
            'band': self.get_band_name(freq),
            'sw': sw,
            'ind': ind,
            'cap': cap,
            'swr': swr,
            'power': power,
            'timestamp': datetime.now().isoformat(),
            'notes': notes
        }
        
        self.records.append(record)
        self.save()
        logger.info(f"添加天调记录: {record['band']} {freq}Hz, SWR={swr}")
        return record
    
    def update_record(self, record_id: str, **kwargs) -> Optional[Dict[str, Any]]:
        """更新记录"""
        for record in self.records:
            if record['id'] == record_id:
                record.update(kwargs)
                record['timestamp'] = datetime.now().isoformat()
                self.save()
                return record
        return None
    
    def delete_record(self, record_id: str) -> bool:
        """删除记录"""
        for i, record in enumerate(self.records):
            if record['id'] == record_id:
                self.records.pop(i)
                self.save()
                logger.info(f"删除天调记录: {record_id}")
                return True
        return False
    
    def get_all_records(self) -> List[Dict[str, Any]]:
        """获取所有记录"""
        return self.records.copy()
    
    def clear_all(self) -> bool:
        """清空所有记录"""
        self.records = []
        return self.save()
    
    def import_from_atr1000(self, memory_data: Dict[str, Any]) -> int:
        """
        从 ATR-1000 设备存储数据导入
        
        ATR-1000 内存格式:
        {
            "id": 存储位号,
            "sw": 网络类型,
            "ind": 电感索引,
            "cap": 电容索引,
            "freq": 频率
        }
        """
        count = 0
        for key, data in memory_data.items():
            try:
                freq = int(data.get('freq', 0) * 1000)  # kHz -> Hz
                if freq > 0:
                    self.add_record(
                        freq=freq,
                        sw=data.get('sw', 0),
                        ind=data.get('ind', 0),
                        cap=data.get('cap', 0),
                        notes=f"从ATR-1000导入 M{data.get('id', key)}"
                    )
                    count += 1
            except Exception as e:
                logger.error(f"导入记录失败: {e}")
        
        logger.info(f"从 ATR-1000 导入 {count} 条记录")
        return count


# 全局单例
_tuner_storage = None

def get_tuner_storage() -> ATR1000TunerStorage:
    """获取天调存储单例"""
    global _tuner_storage
    if _tuner_storage is None:
        _tuner_storage = ATR1000TunerStorage()
    return _tuner_storage


# 测试代码
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    
    storage = ATR1000TunerStorage()
    
    # 测试添加记录
    record = storage.add_record(
        freq=7100000,
        sw=0,
        ind=45,
        cap=32,
        swr=1.15,
        power=100,
        notes="40m波段测试"
    )
    print(f"添加记录: {record}")
    
    # 测试查找
    match = storage.find_best_match(7120000)
    print(f"查找 7.120MHz: {match}")
    
    # 显示所有记录
    print(f"\n所有记录 ({len(storage.get_all_records())} 条):")
    for r in storage.get_all_records():
        print(f"  {r['band']}: {r['center_freq']/1000:.1f}kHz, SWR={r['swr']}")
