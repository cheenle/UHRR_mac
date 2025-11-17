#!/usr/bin/env python3
"""
ATU PTT状态监控API
提供PTT状态查询接口，从rigctld.log文件中读取最新的PTT状态
"""

import os
import json
import time
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler

class PttStatusHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/api/ptt-status':
            self.handle_ptt_status()
        elif self.path == '/api/rigctld-log':
            self.handle_rigctld_log()
        else:
            self.send_error(404)
    
    def handle_ptt_status(self):
        """处理PTT状态查询"""
        try:
            ptt_status = self.get_latest_ptt_status()
            response = {
                'ptt': ptt_status,
                'timestamp': datetime.now().isoformat(),
                'status': 'success'
            }
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode('utf-8'))
        except Exception as e:
            self.send_error(500, f"Error getting PTT status: {str(e)}")
    
    def handle_rigctld_log(self):
        """提供rigctld.log文件内容"""
        try:
            log_path = '/Users/cheenle/UHRR/UHRR_mac/rigctld.log'
            if os.path.exists(log_path):
                with open(log_path, 'r', encoding='utf-8') as f:
                    log_content = f.read()
                self.send_response(200)
                self.send_header('Content-Type', 'text/plain')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(log_content.encode('utf-8'))
            else:
                self.send_error(404, "rigctld.log not found")
        except Exception as e:
            self.send_error(500, f"Error reading log file: {str(e)}")
    
    def get_latest_ptt_status(self):
        """从rigctld.log文件中获取最新的PTT状态"""
        log_path = '/Users/cheenle/UHRR/UHRR_mac/rigctld.log'
        
        if not os.path.exists(log_path):
            return False
        
        try:
            with open(log_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # 从文件末尾开始查找最新的PTT状态
            for line in reversed(lines):
                if 'rigctl_set_ptt:' in line:
                    if 'ptt=1' in line:
                        return True
                    elif 'ptt=0' in line:
                        return False
            
            # 如果没有找到PTT记录，返回默认状态
            return False
            
        except Exception as e:
            print(f"Error reading PTT status: {e}")
            return False
    
    def log_message(self, format, *args):
        """自定义日志格式"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"[{timestamp}] {format % args}")

def run_server(port=8890):
    """启动HTTP服务器"""
    server_address = ('', port)
    httpd = HTTPServer(server_address, PttStatusHandler)
    print(f"PTT状态监控API服务器启动在端口 {port}")
    print(f"API端点:")
    print(f"  GET /api/ptt-status - 获取当前PTT状态")
    print(f"  GET /api/rigctld-log - 获取rigctld.log文件内容")
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n服务器关闭")

if __name__ == '__main__':
    run_server()