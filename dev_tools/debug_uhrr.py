#!/usr/bin/env python3
import signal
import sys
import subprocess

def timeout_handler(signum, frame):
    print("服务启动超时")
    sys.exit(0)

# 设置超时信号
signal.signal(signal.SIGALRM, timeout_handler)
signal.alarm(10)  # 10秒超时

try:
    # 启动 UHRR 服务
    result = subprocess.run([sys.executable, './UHRR'], 
                          capture_output=True, text=True, timeout=10)
    print("STDOUT:")
    print(result.stdout)
    print("STDERR:")
    print(result.stderr)
except subprocess.TimeoutExpired:
    print("服务启动超时")
except Exception as e:
    print(f"启动服务时发生错误: {e}")
finally:
    signal.alarm(0)  # 取消超时