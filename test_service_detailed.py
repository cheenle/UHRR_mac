#!/usr/bin/env python3
"""
详细测试脚本，用于检查 HamRadio 服务启动过程
"""

import sys
import os
import time
import subprocess
import signal

def test_service_detailed():
    print("启动 HamRadio 服务详细测试...")
    print("=" * 40)
    
    # 启动服务作为子进程
    try:
        process = subprocess.Popen(
            [sys.executable, './UHRR'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        
        print(f"服务进程已启动，PID: {process.pid}")
        print("等待 5 秒钟让服务初始化...")
        
        # 等待几秒钟
        time.sleep(5)
        
        # 检查进程是否仍在运行
        if process.poll() is None:
            print("✓ 服务进程仍在运行")
            
            # 尝试获取一些输出
            try:
                stdout, stderr = process.communicate(timeout=2)
                if stdout:
                    print(f"标准输出:\n{stdout}")
                if stderr:
                    print(f"错误输出:\n{stderr}")
            except subprocess.TimeoutExpired:
                print("服务正在运行，没有立即输出")
                
            # 检查端口
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                result = sock.connect_ex(('localhost', 8888))
                if result == 0:
                    print("✓ 服务正在监听端口 8888")
                else:
                    print("✗ 服务未监听端口 8888")
            finally:
                sock.close()
                
        else:
            print("✗ 服务进程已退出")
            stdout, stderr = process.communicate()
            if stdout:
                print(f"标准输出:\n{stdout}")
            if stderr:
                print(f"错误输出:\n{stderr}")
                
    except Exception as e:
        print(f"启动服务时发生错误: {e}")
        return False
        
    finally:
        # 清理进程
        try:
            process.terminate()
            process.wait(timeout=5)
        except:
            try:
                process.kill()
            except:
                pass
                
    return True

if __name__ == "__main__":
    test_service_detailed()