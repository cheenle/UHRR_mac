#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ATU模拟服务器
用于测试ATU集成功能，提供模拟的功率和驻波比数据
"""

import json
import time
import random
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

class ATUMockHandler(BaseHTTPRequestHandler):
    """ATU模拟API处理器"""

    def do_GET(self):
        """处理GET请求"""
        if self.path == '/status':
            # 模拟ATU状态数据
            power = random.uniform(0, 100)  # 随机功率 0-100W
            swr = random.uniform(1.0, 3.0)  # 随机驻波比 1.0-3.0

            data = {
                'power': round(power, 1),
                'swr': round(swr, 2),
                'timestamp': time.time()
            }

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()

            self.wfile.write(json.dumps(data).encode('utf-8'))

        elif self.path == '/':
            # 根路径返回API信息
            info = {
                'name': 'ATU Mock Server',
                'version': '1.0.0',
                'endpoints': ['/status'],
                'description': 'Mock ATU server for testing'
            }

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()

            self.wfile.write(json.dumps(info).encode('utf-8'))

        else:
            self.send_error(404, 'Not Found')

    def log_message(self, format, *args):
        """覆盖默认日志，减少输出噪音"""
        pass

def run_mock_server(port=80):
    """运行模拟服务器"""
    server_address = ('', port)
    httpd = HTTPServer(server_address, ATUMockHandler)

    print(f"🚀 ATU模拟服务器启动在端口 {port}")
    print("📡 提供模拟的功率和驻波比数据")
    print("🔗 API端点: http://localhost:80/status")
    print("⏹️  使用 Ctrl+C 停止服务器")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n⏹️  ATU模拟服务器已停止")
        httpd.shutdown()

if __name__ == '__main__':
    run_mock_server()

