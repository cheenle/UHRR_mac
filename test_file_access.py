#!/usr/bin/env python3
import os

# 测试文件是否存在和可读
file_path = "www/index.html"
if os.path.exists(file_path):
    print(f"文件 {file_path} 存在")
    if os.access(file_path, os.R_OK):
        print(f"文件 {file_path} 可读")
        # 尝试读取文件
        try:
            with open(file_path, 'r') as f:
                content = f.read()
                print(f"文件大小: {len(content)} 字符")
                print("文件前 100 个字符:")
                print(content[:100])
        except Exception as e:
            print(f"读取文件时出错: {e}")
    else:
        print(f"文件 {file_path} 不可读")
else:
    print(f"文件 {file_path} 不存在")