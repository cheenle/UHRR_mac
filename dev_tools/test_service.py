#!/usr/bin/env python3
"""
简单的测试脚本，用于验证 HamRadio 服务是否正常运行
"""

import requests
import urllib3
import sys

# 禁用 SSL 警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def test_service():
    try:
        # 尝试连接到服务
        response = requests.get('https://localhost:8888/', verify=False, timeout=5)
        print(f"服务响应状态码: {response.status_code}")
        print(f"服务响应内容长度: {len(response.text)} 字符")
        if response.status_code == 200:
            print("✓ 服务正常运行")
            return True
        else:
            print(f"✗ 服务返回错误状态码: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("✗ 无法连接到服务 - 请确保服务正在运行")
        return False
    except requests.exceptions.Timeout:
        print("✗ 连接超时 - 服务可能没有响应")
        return False
    except Exception as e:
        print(f"✗ 测试过程中发生错误: {e}")
        return False

if __name__ == "__main__":
    print("测试 HamRadio 服务...")
    print("=" * 30)
    success = test_service()
    print("=" * 30)
    if success:
        print("🎉 服务测试通过!")
        sys.exit(0)
    else:
        print("❌ 服务测试失败!")
        sys.exit(1)