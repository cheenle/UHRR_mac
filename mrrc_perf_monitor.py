#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MRRC 性能监控脚本
实时监控 MRRC、ATR-1000代理、rigctld 的 CPU、内存、网络、IO

用法:
    python3 mrrc_perf_monitor.py          # 实时监控
    python3 mrrc_perf_monitor.py --record # 记录到文件
    python3 mrrc_perf_monitor.py --analyze perf_data.json # 分析数据
"""

import os
import sys
import json
import time
import argparse
import subprocess
import threading
from datetime import datetime
from collections import deque

# 配置
MONITOR_INTERVAL = 1.0  # 监控间隔（秒）
HISTORY_SIZE = 300      # 保留历史记录数（5分钟@1s间隔）

class ProcessMonitor:
    """进程监控器"""
    
    def __init__(self, name, pattern):
        self.name = name
        self.pattern = pattern
        self.pid = None
        self.history = deque(maxlen=HISTORY_SIZE)
        self.find_pid()
    
    def find_pid(self):
        """查找进程 PID"""
        try:
            result = subprocess.run(
                ['pgrep', '-f', self.pattern],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                pids = result.stdout.strip().split('\n')
                if pids and pids[0]:
                    self.pid = int(pids[0])
                    return True
        except:
            pass
        self.pid = None
        return False
    
    def get_stats(self):
        """获取进程统计"""
        if not self.pid:
            if not self.find_pid():
                return None
        
        try:
            # CPU 和内存 (macOS 兼容格式)
            result = subprocess.run(
                ['ps', '-p', str(self.pid), '-o', 'pcpu,pmem,rss,vsz,state'],
                capture_output=True, text=True
            )
            if result.returncode != 0:
                self.pid = None
                return None
            
            lines = result.stdout.strip().split('\n')
            if len(lines) < 2:
                return None
            
            parts = lines[1].split()
            stats = {
                'time': datetime.now().isoformat(),
                'pid': self.pid,
                'cpu_percent': float(parts[0]),
                'mem_percent': float(parts[1]),
                'rss_mb': int(parts[2]) / 1024,  # KB -> MB
                'vsz_mb': int(parts[3]) / 1024,
                'threads': 0,  # macOS ps 不支持线程数
                'state': parts[4]
            }
            
            # 网络 IO (通过 lsof)
            try:
                result = subprocess.run(
                    ['lsof', '-p', str(self.pid), '-i'],
                    capture_output=True, text=True
                )
                connections = len([l for l in result.stdout.split('\n') if 'TCP' in l or 'UDP' in l])
                stats['network_connections'] = connections
            except:
                stats['network_connections'] = 0
            
            # 磁盘 IO (macOS 没有 /proc，用粗略估计)
            stats['disk_read_mb'] = 0
            stats['disk_write_mb'] = 0
            
            self.history.append(stats)
            return stats
            
        except Exception as e:
            return None


class NetworkMonitor:
    """网络监控器"""
    
    def __init__(self):
        self.last_stats = None
        self.history = deque(maxlen=HISTORY_SIZE)
    
    def get_stats(self):
        """获取网络统计"""
        try:
            # macOS 使用 netstat
            result = subprocess.run(
                ['netstat', '-ib'],
                capture_output=True, text=True
            )
            
            lines = result.stdout.strip().split('\n')
            total_in = 0
            total_out = 0
            
            for line in lines[1:]:  # 跳过标题
                parts = line.split()
                if len(parts) >= 10:
                    try:
                        # Ibytes, Obytes
                        total_in += int(parts[6])
                        total_out += int(parts[9])
                    except:
                        pass
            
            current_stats = {
                'time': datetime.now().isoformat(),
                'total_in_mb': total_in / 1024 / 1024,
                'total_out_mb': total_out / 1024 / 1024
            }
            
            if self.last_stats:
                current_stats['rate_in_kbps'] = (current_stats['total_in_mb'] - self.last_stats['total_in_mb']) * 1024 / MONITOR_INTERVAL
                current_stats['rate_out_kbps'] = (current_stats['total_out_mb'] - self.last_stats['total_out_mb']) * 1024 / MONITOR_INTERVAL
            else:
                current_stats['rate_in_kbps'] = 0
                current_stats['rate_out_kbps'] = 0
            
            self.last_stats = current_stats.copy()
            self.history.append(current_stats)
            return current_stats
            
        except Exception as e:
            return None


class LogMonitor:
    """日志监控器"""
    
    def __init__(self, log_path):
        self.log_path = log_path
        self.last_size = 0
        self.last_time = time.time()
        self.history = deque(maxlen=HISTORY_SIZE)
    
    def get_stats(self):
        """获取日志统计"""
        try:
            if not os.path.exists(self.log_path):
                return None
            
            current_size = os.path.getsize(self.log_path)
            current_time = time.time()
            
            stats = {
                'time': datetime.now().isoformat(),
                'size_mb': current_size / 1024 / 1024,
            }
            
            if self.last_size > 0:
                stats['growth_rate_kbps'] = (current_size - self.last_size) / 1024 / (current_time - self.last_time)
            else:
                stats['growth_rate_kbps'] = 0
            
            self.last_size = current_size
            self.last_time = current_time
            self.history.append(stats)
            return stats
            
        except:
            return None


class ATR1000DeviceMonitor:
    """ATR-1000 设备监控器 - 监控设备压力和通讯状态"""
    
    def __init__(self, device_ip='192.168.1.63', device_port=60001):
        self.device_ip = device_ip
        self.device_port = device_port
        self.history = deque(maxlen=HISTORY_SIZE)
        
        # 统计计数器
        self.request_count = 0          # 请求次数
        self.response_count = 0         # 响应次数
        self.timeout_count = 0          # 超时次数
        self.reconnect_count = 0        # 重连次数
        self.last_response_time = None  # 最后响应时间
        self.last_ping_ms = None        # 最后 ping 延迟
        self.connected = False          # 连接状态
        
        # 从日志解析统计
        self.log_path = '/Users/cheenle/UHRR/MRRC/atr1000_proxy.log'
        self.last_log_pos = 0
        self.last_log_check = time.time()
        
        # 时间窗口统计（最近60秒）
        self.window_start = time.time()
        self.window_requests = 0
        self.window_responses = 0
        self.window_timeouts = 0
        self.window_reconnects = 0
    
    def check_network(self):
        """检查网络连通性"""
        try:
            # ping 测试 (发送 1 个包，超时 1 秒)
            result = subprocess.run(
                ['ping', '-c', '1', '-W', '1000', self.device_ip],
                capture_output=True, text=True, timeout=2
            )
            if result.returncode == 0:
                # 解析 ping 延迟
                import re
                match = re.search(r'time=([\d.]+)\s*ms', result.stdout)
                if match:
                    self.last_ping_ms = float(match.group(1))
                    return True
            self.last_ping_ms = None
            return False
        except:
            self.last_ping_ms = None
            return False
    
    def check_port(self):
        """检查端口可达性"""
        try:
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex((self.device_ip, self.device_port))
            sock.close()
            return result == 0
        except:
            return False
    
    def parse_log_stats(self, scan_all=False):
        """从代理日志解析统计信息"""
        try:
            if not os.path.exists(self.log_path):
                return
            
            # 读取新增的日志内容（或全部扫描）
            current_size = os.path.getsize(self.log_path)
            
            if scan_all:
                # 全量扫描模式：只读取最近的日志（约 60 秒的数据）
                # 假设每行平均 100 字节，读取最近 1000 行
                read_size = min(100000, current_size)  # 最多读取 100KB
                with open(self.log_path, 'r') as f:
                    f.seek(max(0, current_size - read_size))
                    new_lines = f.readlines()
                self.last_log_pos = current_size
            else:
                # 增量模式：只读取新增内容
                if current_size <= self.last_log_pos:
                    return
                with open(self.log_path, 'r') as f:
                    f.seek(self.last_log_pos)
                    new_lines = f.readlines()
                self.last_log_pos = current_size
            
            # 解析日志
            import re
            for line in new_lines:
                # 请求计数 (📊 或 SYNC)
                if '📊' in line or 'SYNC' in line:
                    self.request_count += 1
                    self.window_requests += 1
                # 响应计数 (📤 广播)
                if '📤' in line or '广播' in line:
                    self.response_count += 1
                    self.window_responses += 1
                # 超时计数
                if '无响应' in line or 'timeout' in line.lower():
                    self.timeout_count += 1
                    self.window_timeouts += 1
                # 重连计数
                if '重连' in line or 'reconnect' in line.lower():
                    self.reconnect_count += 1
                    self.window_reconnects += 1
                # 连接状态（设备连接）
                if '✅ ATR-1000 已连接' in line:
                    self.connected = True
                    self.last_response_time = time.time()
                # 设备连接关闭（仅当设备断开时）
                if 'ATR-1000 连接关闭' in line or 'Connection reset by peer' in line:
                    self.connected = False
                # 如果连续无响应超过 60 秒，认为断开
                if '最后数据:' in line:
                    import re as re2
                    match = re2.search(r'最后数据:\s*([\d.]+)秒前', line)
                    if match and float(match.group(1)) > 60:
                        self.connected = False
                    
        except Exception as e:
            pass
    
    def get_stats(self):
        """获取 ATR-1000 设备统计"""
        # 每隔一段时间检查网络
        now = time.time()
        
        # 首次调用时扫描整个日志文件
        if not hasattr(self, '_initialized'):
            self._initialized = True
            self.parse_log_stats(scan_all=True)
        else:
            # 解析日志统计（增量）
            self.parse_log_stats()
        
        # 检查网络连通性 (每 5 秒检查一次)
        if not hasattr(self, '_last_network_check') or now - self._last_network_check > 5:
            self._last_network_check = now
            network_ok = self.check_network()
            port_ok = self.check_port()
        else:
            network_ok = self.last_ping_ms is not None
            port_ok = True  # 假设端口状态未变
        
        # 计算响应率（使用窗口数据）
        response_rate = 0
        if self.window_requests > 0:
            response_rate = (self.window_responses / self.window_requests) * 100
        
        # 计算设备压力指标（使用窗口数据）
        # 压力 = (超时次数 * 10 + 重连次数 * 50) / (响应次数 + 1)
        pressure_score = 0
        if self.window_responses > 0:
            pressure_score = (self.window_timeouts * 10 + self.window_reconnects * 50) / (self.window_responses + 1)
        
        # 每 60 秒重置窗口
        if now - self.window_start > 60:
            self.window_start = now
            self.window_requests = 0
            self.window_responses = 0
            self.window_timeouts = 0
            self.window_reconnects = 0
        
        stats = {
            'time': datetime.now().isoformat(),
            'device_ip': self.device_ip,
            'device_port': self.device_port,
            'connected': self.connected,
            'ping_ms': self.last_ping_ms,
            'network_ok': network_ok,
            'port_ok': port_ok,
            'request_count': self.window_requests,  # 使用窗口数据
            'response_count': self.window_responses,
            'timeout_count': self.window_timeouts,
            'reconnect_count': self.window_reconnects,
            'response_rate': response_rate,
            'pressure_score': pressure_score,
        }
        
        self.history.append(stats)
        return stats
    
    def reset_counters(self):
        """重置计数器"""
        self.request_count = 0
        self.response_count = 0
        self.timeout_count = 0
        self.reconnect_count = 0


class PerformanceAnalyzer:
    """性能分析器"""
    
    def __init__(self):
        # 进程匹配 pattern：
        # - MRRC: 匹配 "Python .../MRRC" 但排除 atr1000_proxy
        # - 使用负向前瞻排除包含 atr1000 的进程
        self.mrrc = ProcessMonitor('MRRC', 'Python.*/MRRC$')
        self.atr1000 = ProcessMonitor('ATR-1000', 'atr1000_proxy')
        self.rigctld = ProcessMonitor('rigctld', 'rigctld')
        self.network = NetworkMonitor()
        self.mrrc_log = LogMonitor('/Users/cheenle/UHRR/MRRC/mrrc.log')
        self.atr1000_log = LogMonitor('/Users/cheenle/UHRR/MRRC/atr1000_proxy.log')
        self.debug_log = LogMonitor('/Users/cheenle/UHRR/MRRC/mrrc_debug.log')
        
        # ATR-1000 设备监控（网络、通讯、压力）
        self.atr1000_device = ATR1000DeviceMonitor('192.168.1.63', 60001)
        
        self.recording = False
        self.record_data = []
    
    def collect(self):
        """收集所有监控数据"""
        return {
            'time': datetime.now().isoformat(),
            'mrrc': self.mrrc.get_stats(),
            'atr1000': self.atr1000.get_stats(),
            'rigctld': self.rigctld.get_stats(),
            'network': self.network.get_stats(),
            'logs': {
                'mrrc': self.mrrc_log.get_stats(),
                'atr1000': self.atr1000_log.get_stats(),
                'debug': self.debug_log.get_stats()
            },
            'atr1000_device': self.atr1000_device.get_stats()
        }
    
    def analyze_bottlenecks(self):
        """分析性能瓶颈"""
        issues = []
        
        # 分析 MRRC
        if self.mrrc.history:
            recent = list(self.mrrc.history)[-30:]  # 最近 30 秒
            avg_cpu = sum(s['cpu_percent'] for s in recent) / len(recent)
            max_cpu = max(s['cpu_percent'] for s in recent)
            avg_mem = sum(s['mem_percent'] for s in recent) / len(recent)
            
            if avg_cpu > 10:
                issues.append(f"⚠️  MRRC CPU 平均使用率 {avg_cpu:.1f}% 偏高")
            if max_cpu > 30:
                issues.append(f"🔴 MRRC CPU 峰值 {max_cpu:.1f}% 过高")
            if avg_mem > 2:
                issues.append(f"⚠️  MRRC 内存使用率 {avg_mem:.1f}%")
        
        # 分析 ATR-1000 代理
        if self.atr1000.history:
            recent = list(self.atr1000.history)[-30:]
            avg_cpu = sum(s['cpu_percent'] for s in recent if s) / len([s for s in recent if s])
            if avg_cpu > 5:
                issues.append(f"⚠️  ATR-1000 CPU 使用率 {avg_cpu:.1f}%")
        
        # 分析 ATR-1000 设备压力
        if self.atr1000_device.history:
            device_stats = list(self.atr1000_device.history)[-1] if self.atr1000_device.history else None
            if device_stats:
                if not device_stats.get('connected'):
                    issues.append(f"🔴 ATR-1000 设备未连接")
                if device_stats.get('timeout_count', 0) > 3:
                    issues.append(f"⚠️  ATR-1000 设备超时 {device_stats['timeout_count']} 次")
                if device_stats.get('reconnect_count', 0) > 1:
                    issues.append(f"🔴 ATR-1000 设备重连 {device_stats['reconnect_count']} 次")
                if device_stats.get('pressure_score', 0) > 10:
                    issues.append(f"🔴 ATR-1000 设备压力过高: {device_stats['pressure_score']:.1f}")
                if device_stats.get('response_rate', 100) < 80:
                    issues.append(f"⚠️  ATR-1000 响应率低: {device_stats['response_rate']:.1f}%")
        
        # 分析日志增长
        if self.debug_log.history:
            recent = list(self.debug_log.history)[-30:]
            avg_growth = sum(s['growth_rate_kbps'] for s in recent if s) / len([s for s in recent if s])
            if avg_growth > 10:
                issues.append(f"🔴 Debug 日志增长过快: {avg_growth:.1f} KB/s")
        
        return issues
    
    def print_status(self, data):
        """打印状态"""
        # os.system('clear')  # 禁用清屏，保留调试输出
        print("\n" + "=" * 70)
        print(f"MRRC 性能监控 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70)
        
        # 进程状态
        print("\n📊 进程状态:")
        print("-" * 70)
        print(f"{'进程':<15} {'PID':<8} {'CPU%':<8} {'MEM%':<8} {'RSS(MB)':<10} {'线程':<6} {'状态':<6}")
        print("-" * 70)
        
        for name, proc in [('MRRC', data['mrrc']), ('ATR-1000', data['atr1000']), ('rigctld', data['rigctld'])]:
            if proc:
                print(f"{name:<15} {proc['pid']:<8} {proc['cpu_percent']:<8.1f} {proc['mem_percent']:<8.1f} {proc['rss_mb']:<10.1f} {proc['threads']:<6} {proc['state']:<6}")
            else:
                print(f"{name:<15} {'N/A':<8} {'未运行':<40}")
        
        # 网络状态
        print("\n🌐 网络状态:")
        print("-" * 70)
        if data['network']:
            net = data['network']
            print(f"入站流量: {net['total_in_mb']:.1f} MB ({net['rate_in_kbps']:.1f} KB/s)")
            print(f"出站流量: {net['total_out_mb']:.1f} MB ({net['rate_out_kbps']:.1f} KB/s)")
        
        # 日志状态
        print("\n📝 日志状态:")
        print("-" * 70)
        if data['logs']['mrrc']:
            print(f"mrrc.log:      {data['logs']['mrrc']['size_mb']:.2f} MB (增长: {data['logs']['mrrc']['growth_rate_kbps']:.1f} KB/s)")
        if data['logs']['atr1000']:
            print(f"atr1000.log:   {data['logs']['atr1000']['size_mb']:.2f} MB (增长: {data['logs']['atr1000']['growth_rate_kbps']:.1f} KB/s)")
        if data['logs']['debug']:
            print(f"debug.log:     {data['logs']['debug']['size_mb']:.2f} MB (增长: {data['logs']['debug']['growth_rate_kbps']:.1f} KB/s)")
        
        # ATR-1000 设备状态
        if 'atr1000_device' in data and data['atr1000_device']:
            dev = data['atr1000_device']
            print("\n📡 ATR-1000 设备状态:")
            print("-" * 70)
            status = "🟢 已连接" if dev.get('connected') else "🔴 未连接"
            print(f"设备: {dev.get('device_ip', 'N/A')}:{dev.get('device_port', 'N/A')} {status}")
            
            # 网络状态
            net_status = "🟢 正常" if dev.get('network_ok') else "🔴 不可达"
            port_status = "🟢 开放" if dev.get('port_ok') else "🔴 关闭"
            ping = f"{dev.get('ping_ms', 0):.1f}ms" if dev.get('ping_ms') else "超时"
            print(f"网络: {net_status} | 端口: {port_status} | Ping: {ping}")
            
            # 通讯统计
            print(f"请求: {dev.get('request_count', 0)} | 响应: {dev.get('response_count', 0)} | 超时: {dev.get('timeout_count', 0)} | 重连: {dev.get('reconnect_count', 0)}")
            
            # 压力指标
            response_rate = dev.get('response_rate', 0)
            pressure = dev.get('pressure_score', 0)
            pressure_level = "🟢 正常" if pressure < 5 else ("🟡 中等" if pressure < 15 else "🔴 过高")
            print(f"响应率: {response_rate:.1f}% | 设备压力: {pressure:.1f} ({pressure_level})")
            
            # 数据流统计
            if 'data_rate' in dev:
                print(f"数据流: {dev['data_rate']:.1f} 条/秒 | 最后数据: {dev.get('last_data_age', 0):.1f}秒前")
        
        # 性能瓶颈分析
        issues = self.analyze_bottlenecks()
        if issues:
            print("\n⚠️  性能问题:")
            print("-" * 70)
            for issue in issues:
                print(issue)
        
        print("\n" + "=" * 70)
        print("按 Ctrl+C 退出 | 正在记录: {}".format("是" if self.recording else "否"))
    
    def run(self, record=False, duration=0):
        """运行监控"""
        self.recording = record
        
        print("启动性能监控...")
        print(f"监控间隔: {MONITOR_INTERVAL} 秒")
        print(f"历史记录: {HISTORY_SIZE} 条")
        if duration > 0:
            print(f"运行时长: {duration} 秒")
        print()
        
        start_time = time.time()
        try:
            while True:
                data = self.collect()
                self.print_status(data)
                
                if record:
                    self.record_data.append(data)
                
                # 检查是否达到运行时长
                if duration > 0 and (time.time() - start_time) >= duration:
                    print(f"\n\n已运行 {duration} 秒，监控结束")
                    break
                
                time.sleep(MONITOR_INTERVAL)
        except KeyboardInterrupt:
            print("\n\n监控已停止")
        
        # 保存数据（无论是正常结束还是 Ctrl+C）
        if record and self.record_data:
            filename = f"perf_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(filename, 'w') as f:
                json.dump(self.record_data, f, indent=2)
            print(f"数据已保存到: {filename}")


def analyze_file(filename):
    """分析记录的数据文件"""
    with open(filename, 'r') as f:
        data = json.load(f)
    
    print(f"\n分析文件: {filename}")
    print(f"记录数量: {len(data)}")
    print("=" * 70)
    
    # 计算统计
    mrrc_cpus = [d['mrrc']['cpu_percent'] for d in data if d.get('mrrc')]
    mrrc_mems = [d['mrrc']['mem_percent'] for d in data if d.get('mrrc')]
    
    if mrrc_cpus:
        print(f"\nMRRC CPU:")
        print(f"  平均: {sum(mrrc_cpus)/len(mrrc_cpus):.2f}%")
        print(f"  最大: {max(mrrc_cpus):.2f}%")
        print(f"  最小: {min(mrrc_cpus):.2f}%")
    
    if mrrc_mems:
        print(f"\nMRRC 内存:")
        print(f"  平均: {sum(mrrc_mems)/len(mrrc_mems):.2f}%")
        print(f"  最大: {max(mrrc_mems):.2f}%")
    
    # 日志增长
    if len(data) > 1:
        first = data[0]['logs'].get('debug', {})
        last = data[-1]['logs'].get('debug', {})
        if first and last:
            growth = last.get('size_mb', 0) - first.get('size_mb', 0)
            duration = len(data) * MONITOR_INTERVAL
            print(f"\nDebug 日志增长: {growth:.2f} MB ({growth*1024/duration:.1f} KB/s)")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='MRRC 性能监控')
    parser.add_argument('--record', action='store_true', help='记录数据到文件')
    parser.add_argument('--duration', type=int, default=0, help='运行时长(秒)，0表示持续运行')
    parser.add_argument('--analyze', type=str, help='分析指定的数据文件')
    args = parser.parse_args()
    
    if args.analyze:
        analyze_file(args.analyze)
    else:
        analyzer = PerformanceAnalyzer()
        analyzer.run(record=args.record, duration=args.duration)
