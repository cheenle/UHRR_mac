#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试 V5.0 音频架构基础组件
"""

import multiprocessing as mp
import time
import numpy as np
import sys

def simple_worker(q):
    """简单工作进程测试"""
    print('工作进程启动')
    count = 0
    while count < 10:
        try:
            data = q.get(timeout=1)
            if data is None:
                break
            print(f'收到数据: {len(data)} bytes')
            count += 1
        except:
            pass
    print('工作进程结束')


def test_basic_multiprocessing():
    """测试基本进程通信"""
    print('=' * 60)
    print('测试 1: 基本进程通信')
    print('=' * 60)
    
    tx_queue = mp.Queue(maxsize=10)
    
    p = mp.Process(target=simple_worker, args=(tx_queue,), daemon=True)
    p.start()
    
    print(f'进程已启动: PID={p.pid}')
    
    # 发送数据
    for i in range(10):
        tx_queue.put(b'test_data_' + str(i).encode())
        time.sleep(0.05)
    
    # 发送结束信号
    tx_queue.put(None)
    
    # 等待结束
    p.join(timeout=5)
    
    if p.is_alive():
        print('强制结束进程')
        p.terminate()
        p.join()
        
    print(f'进程状态: is_alive={p.is_alive()}, exitcode={p.exitcode}')
    print('✅ 测试 1 完成!\n')


def test_process_manager():
    """测试进程管理器"""
    print('=' * 60)
    print('测试 2: 进程管理器')
    print('=' * 60)
    
    from process_manager import ProcessManager, ProcessConfig
    
    pm = ProcessManager()
    
    # 创建队列
    tx_queue = pm.create_queue('test_queue', maxsize=10)
    
    # 注册进程
    pm.register_process(ProcessConfig(
        name='test_worker',
        target=simple_worker,
        args=(tx_queue,),
        auto_restart=True,
        max_restarts=2,
        daemon=True
    ))
    
    # 启动进程
    pm.start_all()
    time.sleep(1)
    
    # 检查状态
    status = pm.get_process_status('test_worker')
    print(f'进程状态: {status}')
    
    # 发送数据
    for i in range(5):
        tx_queue.put(b'pm_test_' + str(i).encode())
        time.sleep(0.1)
    
    # 发送结束信号
    tx_queue.put(None)
    
    # 停止
    pm.shutdown()
    
    print('✅ 测试 2 完成!\n')


def test_ring_buffer():
    """测试环形缓冲区"""
    print('=' * 60)
    print('测试 3: 环形缓冲区')
    print('=' * 60)
    
    from audio_worker import RingBuffer
    
    rb = RingBuffer(size=1000)
    
    # 写入数据
    data = np.random.randint(-1000, 1000, 500, dtype=np.int16)
    written = rb.write(data)
    print(f'写入 {written} 个样本')
    
    # 读取数据
    read_data = rb.read(300)
    print(f'读取 {len(read_data)} 个样本')
    
    # 获取统计
    stats = rb.get_stats()
    print(f'缓冲区统计: {stats}')
    
    print('✅ 测试 3 完成!\n')


if __name__ == '__main__':
    print('V5.0 音频架构 - 基础组件测试')
    print('=' * 60)
    
    # 测试 1: 基本进程通信
    test_basic_multiprocessing()
    
    # 测试 2: 进程管理器
    test_process_manager()
    
    # 测试 3: 环形缓冲区
    test_ring_buffer()
    
    print('=' * 60)
    print('所有测试完成!')
    print('=' * 60)
