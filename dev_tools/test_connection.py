#!/usr/bin/env python3
import requests
import urllib3
import time

# 禁用 SSL 警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

try:
    print("正在测试连接到 https://localhost:8888/...")
    response = requests.get('https://localhost:8888/', verify=False, timeout=10)
    print(f"状态码: {response.status_code}")
    print(f"响应长度: {len(response.text)} 字符")
    if len(response.text) > 0:
        print("服务器返回了内容")
        print(f"前 200 个字符: {response.text[:200]}")
    else:
        print("服务器返回了空内容")
except requests.exceptions.ConnectionError as e:
    print(f"连接错误: {e}")
except requests.exceptions.Timeout as e:
    print(f"连接超时: {e}")
except Exception as e:
    print(f"其他错误: {e}")