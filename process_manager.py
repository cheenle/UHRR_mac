#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
MRRC Process Manager - 音频进程生命周期管理

负责：
1. 管理所有音频子进程的生命周期
2. 自动重启崩溃的进程
3. 进程状态监控和日志
4. 优雅关闭和资源清理

版本: v1.0
日期: 2026-03-06
"""

import multiprocessing as mp
from multiprocessing import Process, Queue, Manager
import threading
import time
import logging
import signal
import sys
import os
import atexit
from typing import Dict, Optional, Callable
from dataclasses import dataclass
from enum import Enum

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - ProcessManager - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('ProcessManager')


class ProcessState(Enum):
    """进程状态枚举"""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    CRASHED = "crashed"
    RESTARTING = "restarting"


@dataclass
class ProcessConfig:
    """进程配置"""
    name: str
    target: Callable
    args: tuple
    kwargs: dict = None
    auto_restart: bool = True
    max_restarts: int = 5
    restart_delay: float = 2.0
    daemon: bool = True
    

@dataclass
class ProcessInfo:
    """进程信息"""
    config: ProcessConfig
    process: Optional[Process] = None
    state: ProcessState = ProcessState.STOPPED
    pid: Optional[int] = None
    start_time: Optional[float] = None
    restart_count: int = 0
    last_crash_time: Optional[float] = None
    last_error: Optional[str] = None


class ProcessManager:
    """
    进程管理器
    
    核心功能：
    - 统一管理所有子进程
    - 自动重启崩溃进程
    - 状态监控和告警
    - 优雅关闭
    """
    
    def __init__(self):
        self.processes: Dict[str, ProcessInfo] = {}
        self.manager = Manager()
        self.shared_queues: Dict[str, Queue] = {}
        self.shared_dicts: Dict[str, dict] = {}
        
        self.running = False
        self.monitor_thread: Optional[threading.Thread] = None
        self.lock = threading.Lock()
        
        # 统计
        self.stats = {
            'total_starts': 0,
            'total_crashes': 0,
            'total_restarts': 0
        }
        
        # 注册退出处理
        atexit.register(self.shutdown)
        
        logger.info("ProcessManager initialized")
        
    def register_process(self, config: ProcessConfig):
        """
        注册一个进程
        
        Args:
            config: 进程配置
        """
        with self.lock:
            if config.name in self.processes:
                logger.warning(f"Process {config.name} already registered, updating config")
                
            self.processes[config.name] = ProcessInfo(config=config)
            logger.info(f"Registered process: {config.name}")
            
    def create_queue(self, name: str, maxsize: int = 100) -> Queue:
        """创建共享队列"""
        if name not in self.shared_queues:
            self.shared_queues[name] = Queue(maxsize=maxsize)
            logger.info(f"Created shared queue: {name}")
        return self.shared_queues[name]
        
    def create_shared_dict(self, name: str) -> dict:
        """创建共享字典"""
        if name not in self.shared_dicts:
            self.shared_dicts[name] = self.manager.dict()
            logger.info(f"Created shared dict: {name}")
        return self.shared_dicts[name]
        
    def start_process(self, name: str) -> bool:
        """
        启动指定进程
        
        Args:
            name: 进程名称
            
        Returns:
            是否启动成功
        """
        with self.lock:
            if name not in self.processes:
                logger.error(f"Process {name} not registered")
                return False
                
            info = self.processes[name]
            
            if info.state == ProcessState.RUNNING:
                logger.warning(f"Process {name} already running")
                return True
                
            try:
                info.state = ProcessState.STARTING
                
                # 准备参数
                args = info.config.args or ()
                kwargs = info.config.kwargs or {}
                
                # 创建进程
                info.process = Process(
                    target=info.config.target,
                    args=args,
                    kwargs=kwargs,
                    daemon=info.config.daemon
                )
                
                # 启动进程
                info.process.start()
                info.pid = info.process.pid
                info.state = ProcessState.RUNNING
                info.start_time = time.time()
                
                self.stats['total_starts'] += 1
                
                logger.info(f"✅ Started process {name} (PID: {info.pid})")
                return True
                
            except Exception as e:
                info.state = ProcessState.CRASHED
                info.last_error = str(e)
                logger.error(f"Failed to start process {name}: {e}")
                return False
                
    def stop_process(self, name: str, timeout: float = 5.0) -> bool:
        """
        停止指定进程
        
        Args:
            name: 进程名称
            timeout: 等待超时时间
            
        Returns:
            是否停止成功
        """
        with self.lock:
            if name not in self.processes:
                logger.error(f"Process {name} not registered")
                return False
                
            info = self.processes[name]
            
            if info.state != ProcessState.RUNNING:
                logger.warning(f"Process {name} not running (state: {info.state})")
                return True
                
            try:
                info.state = ProcessState.STOPPING
                
                # 发送终止信号
                if info.process and info.process.is_alive():
                    info.process.terminate()
                    
                    # 等待进程结束
                    info.process.join(timeout=timeout)
                    
                    # 如果进程还在运行，强制杀死
                    if info.process.is_alive():
                        logger.warning(f"Force killing process {name}")
                        info.process.kill()
                        info.process.join(timeout=1.0)
                        
                info.state = ProcessState.STOPPED
                info.process = None
                info.pid = None
                
                logger.info(f"🛑 Stopped process {name}")
                return True
                
            except Exception as e:
                logger.error(f"Error stopping process {name}: {e}")
                info.state = ProcessState.CRASHED
                info.last_error = str(e)
                return False
                
    def restart_process(self, name: str) -> bool:
        """
        重启指定进程
        
        Args:
            name: 进程名称
            
        Returns:
            是否重启成功
        """
        logger.info(f"Restarting process {name}...")
        
        # 先停止
        if not self.stop_process(name):
            return False
            
        # 等待一段时间
        time.sleep(1.0)
        
        # 重新启动
        return self.start_process(name)
        
    def start_all(self):
        """启动所有已注册的进程"""
        logger.info("Starting all processes...")
        
        # 获取进程名称列表（在锁内）
        with self.lock:
            process_names = list(self.processes.keys())
        
        # 启动进程（在锁外，避免死锁）
        for name in process_names:
            self.start_process(name)
                
        # 启动监控线程
        self.running = True
        self.monitor_thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True
        )
        self.monitor_thread.start()
        
        logger.info("All processes started, monitoring active")
        
    def stop_all(self):
        """停止所有进程"""
        logger.info("Stopping all processes...")
        
        self.running = False
        
        # 获取进程名称列表（在锁内）
        with self.lock:
            process_names = list(self.processes.keys())
        
        # 停止进程（在锁外，避免死锁）
        for name in process_names:
            self.stop_process(name)
                
        logger.info("All processes stopped")
        
    def shutdown(self):
        """关闭进程管理器（优雅关闭）"""
        logger.info("Shutting down ProcessManager...")
        self.stop_all()
        
        # 清理共享资源
        self.shared_queues.clear()
        self.shared_dicts.clear()
        
        logger.info("ProcessManager shutdown complete")
        
    def _monitor_loop(self):
        """进程监控循环"""
        logger.info("Process monitor started")
        
        while self.running:
            try:
                self._check_processes()
                time.sleep(1.0)  # 每秒检查一次
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}")
                time.sleep(5.0)
                
        logger.info("Process monitor stopped")
        
    def _check_processes(self):
        """检查所有进程状态"""
        with self.lock:
            for name, info in self.processes.items():
                if info.state == ProcessState.RUNNING:
                    if info.process and not info.process.is_alive():
                        # 进程意外退出
                        self._handle_process_crash(name, info)
                        
    def _handle_process_crash(self, name: str, info: ProcessInfo):
        """处理进程崩溃"""
        exit_code = info.process.exitcode if info.process else -1
        logger.error(f"❌ Process {name} crashed! Exit code: {exit_code}")
        
        info.state = ProcessState.CRASHED
        info.last_crash_time = time.time()
        info.last_error = f"Exit code: {exit_code}"
        
        self.stats['total_crashes'] += 1
        
        # 检查是否需要自动重启
        if info.config.auto_restart:
            if info.restart_count < info.config.max_restarts:
                # 检查重启间隔
                if info.last_crash_time and info.start_time:
                    uptime = info.last_crash_time - info.start_time
                    if uptime < 5.0:  # 如果进程运行时间太短，可能是配置问题
                        logger.warning(f"Process {name} crashed quickly after start (uptime: {uptime:.1f}s), "
                                      f"may indicate configuration issue")
                        
                # 延迟重启
                logger.info(f"Scheduling restart for {name} in {info.config.restart_delay}s "
                           f"(attempt {info.restart_count + 1}/{info.config.max_restarts})")
                           
                # 在新线程中延迟重启
                threading.Thread(
                    target=self._delayed_restart,
                    args=(name,),
                    daemon=True
                ).start()
            else:
                logger.error(f"Process {name} exceeded max restarts ({info.config.max_restarts}), "
                            f"not restarting")
                            
    def _delayed_restart(self, name: str):
        """延迟重启进程"""
        with self.lock:
            if name not in self.processes:
                return
            info = self.processes[name]
            info.restart_count += 1
            info.state = ProcessState.RESTARTING
            
        delay = info.config.restart_delay
        
        # 等待
        time.sleep(delay)
        
        # 尝试重启
        if self.running:  # 只在管理器运行时重启
            self.start_process(name)
            self.stats['total_restarts'] += 1
            
    def get_process_status(self, name: str) -> Optional[dict]:
        """获取进程状态"""
        with self.lock:
            if name not in self.processes:
                return None
                
            info = self.processes[name]
            
            status = {
                'name': name,
                'state': info.state.value,
                'pid': info.pid,
                'start_time': info.start_time,
                'uptime': time.time() - info.start_time if info.start_time else 0,
                'restart_count': info.restart_count,
                'last_crash_time': info.last_crash_time,
                'last_error': info.last_error,
                'is_alive': info.process.is_alive() if info.process else False
            }
            
            return status
            
    def get_all_status(self) -> dict:
        """获取所有进程状态"""
        with self.lock:
            status = {}
            for name in self.processes:
                status[name] = self.get_process_status(name)
                
            status['_manager'] = {
                'running': self.running,
                'total_starts': self.stats['total_starts'],
                'total_crashes': self.stats['total_crashes'],
                'total_restarts': self.stats['total_restarts']
            }
            
            return status


# 全局进程管理器实例（单例）
_process_manager: Optional[ProcessManager] = None


def get_process_manager() -> ProcessManager:
    """获取全局进程管理器实例"""
    global _process_manager
    if _process_manager is None:
        _process_manager = ProcessManager()
    return _process_manager


if __name__ == '__main__':
    """测试模式"""
    logger.info("Testing ProcessManager...")
    
    # 创建进程管理器
    pm = ProcessManager()
    
    # 定义测试进程函数
    def test_worker(name, duration):
        import time
        print(f"Worker {name} started, running for {duration}s")
        for i in range(duration):
            print(f"Worker {name}: {i+1}/{duration}")
            time.sleep(1)
        print(f"Worker {name} finished")
        
    def test_crash_worker(name, crash_after):
        import time
        print(f"Crash worker {name} started, will crash after {crash_after}s")
        time.sleep(crash_after)
        raise RuntimeError(f"Simulated crash in {name}")
        
    # 注册测试进程
    pm.register_process(ProcessConfig(
        name="test_worker_1",
        target=test_worker,
        args=("Worker-1", 10),
        auto_restart=False
    ))
    
    pm.register_process(ProcessConfig(
        name="test_crash_worker",
        target=test_crash_worker,
        args=("CrashWorker", 3),
        auto_restart=True,
        max_restarts=3,
        restart_delay=2.0
    ))
    
    # 启动所有进程
    pm.start_all()
    
    try:
        # 运行一段时间
        for i in range(15):
            time.sleep(1)
            status = pm.get_all_status()
            print(f"\n--- Status at {i+1}s ---")
            for name, info in status.items():
                print(f"  {name}: {info}")
                
    except KeyboardInterrupt:
        print("\nInterrupted")
    finally:
        pm.shutdown()
        
    logger.info("Test completed")
