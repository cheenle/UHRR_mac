#!/usr/bin/env python3
"""
ATR-1000 API Server - 独立API服务模块 V2

通过 Unix Socket 调用 ATR-1000 Proxy，避免直接连接设备。
与 proxy 共享设备连接，减少设备压力。

启动方式:
    python3 atr1000_api_server.py --port 8080

API 接口:
    GET  /health              - 健康检查
    GET  /api/v1/status       - 获取当前状态
    GET  /api/v1/relay        - 获取继电器参数
    POST /api/v1/relay        - 设置继电器参数
    GET  /api/v1/tuner        - 获取学习记录列表
    POST /api/v1/tuner        - 手动添加学习记录
    DELETE /api/v1/tuner      - 删除学习记录
    GET  /api/v1/tuner/lookup - 根据频率查找参数
    POST /api/v1/tune         - 执行快速调谐
"""

import json
import logging
import argparse
import asyncio
import socket
import os
from datetime import datetime
from typing import Optional, Dict, Any

import tornado.web
import tornado.ioloop

# 本地模块
from atr1000_tuner import get_storage

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - ATR1000-API - %(levelname)s - %(message)s'
)
logger = logging.getLogger("ATR1000-API")

# Unix Socket 路径
PROXY_SOCKET_PATH = "/tmp/atr1000_proxy.sock"

# 全局缓存（从 proxy 获取）
cache = {
    "power": 0.0,
    "swr": 1.0,
    "vforward": 0.0,
    "vreflected": 0.0,
    "sw": 0,
    "ind": 0,
    "cap": 0,
    "connected": False,
    "last_update": None
}


class ProxyClient:
    """ATR-1000 Proxy 客户端 - 通过 Unix Socket 通信"""
    
    def __init__(self, socket_path: str = PROXY_SOCKET_PATH):
        self.socket_path = socket_path
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self.connected = False
        
    async def connect(self) -> bool:
        """连接 proxy"""
        try:
            # 检查 socket 文件是否存在
            if not os.path.exists(self.socket_path):
                logger.error(f"Proxy socket 不存在: {self.socket_path}")
                logger.error("请确保 atr1000_proxy.py 正在运行")
                return False
            
            # 连接 Unix Socket
            self.reader, self.writer = await asyncio.open_unix_connection(self.socket_path)
            self.connected = True
            cache["connected"] = True
            logger.info(f"已连接 ATR-1000 Proxy: {self.socket_path}")
            
            # 启动接收循环
            asyncio.create_task(self._receive_loop())
            return True
            
        except Exception as e:
            logger.error(f"连接 proxy 失败: {e}")
            self.connected = False
            cache["connected"] = False
            return False
    
    async def _receive_loop(self):
        """接收 proxy 广播的数据"""
        while self.connected and self.reader:
            try:
                line = await self.reader.readline()
                if not line:
                    logger.warning("Proxy 连接已关闭")
                    self.connected = False
                    cache["connected"] = False
                    break
                
                # 解析 JSON 数据
                data = json.loads(line.decode().strip())
                self._handle_data(data)
                
            except json.JSONDecodeError as e:
                logger.warning(f"JSON 解析错误: {e}")
            except Exception as e:
                logger.error(f"接收错误: {e}")
                self.connected = False
                cache["connected"] = False
                break
    
    def _handle_data(self, data: dict):
        """处理 proxy 发来的数据"""
        msg_type = data.get("type")
        
        if msg_type == "atr1000_meter":
            # 功率/SWR 数据
            cache["power"] = data.get("power", 0)
            cache["swr"] = data.get("swr", 1.0)
            cache["vforward"] = data.get("vforward", 0)
            cache["vreflected"] = data.get("vreflected", 0)
            cache["last_update"] = datetime.now().isoformat()
            
        elif msg_type == "atr1000_relay":
            # 继电器状态
            relay = data.get("relay_status", {})
            cache["sw"] = 1 if relay.get("lc") == "CL" else 0
            cache["ind"] = relay.get("inductance", 0)
            cache["cap"] = relay.get("capacitance", 0)
            cache["last_update"] = datetime.now().isoformat()
    
    async def send_command(self, command: dict) -> bool:
        """发送命令到 proxy"""
        if not self.connected or not self.writer:
            return False
        
        try:
            msg = json.dumps(command) + "\n"
            self.writer.write(msg.encode())
            await self.writer.drain()
            return True
        except Exception as e:
            logger.error(f"发送命令失败: {e}")
            return False
    
    async def set_relay(self, sw: int, ind: int, cap: int) -> bool:
        """设置继电器参数"""
        return await self.send_command({
            "action": "set_relay",
            "sw": sw,
            "ind": ind,
            "cap": cap
        })
    
    async def set_freq(self, freq_hz: int) -> bool:
        """设置频率"""
        return await self.send_command({
            "action": "set_freq",
            "freq": freq_hz
        })
    
    async def close(self):
        """关闭连接"""
        if self.writer:
            self.writer.close()
            await self.writer.wait_closed()


# 全局客户端实例
proxy_client: Optional[ProxyClient] = None


class BaseHandler(tornado.web.RequestHandler):
    """基础处理器"""
    
    def set_default_headers(self):
        self.set_header("Access-Control-Allow-Origin", "*")
        self.set_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.set_header("Access-Control-Allow-Headers", "Content-Type")
    
    def options(self):
        self.set_status(204)
        self.finish()
    
    def write_json(self, data: dict, status: int = 200):
        self.set_status(status)
        self.set_header("Content-Type", "application/json")
        self.write(json.dumps(data, ensure_ascii=False))


class HealthHandler(BaseHandler):
    """健康检查"""
    
    def get(self):
        self.write_json({
            "status": "ok",
            "service": "ATR-1000 API Server",
            "version": "2.0.0",
            "proxy_connected": cache["connected"],
            "proxy_socket": PROXY_SOCKET_PATH
        })


class StatusHandler(BaseHandler):
    """获取当前状态"""
    
    def get(self):
        self.write_json({
            "success": True,
            "data": {
                "connected": cache["connected"],
                "power": round(cache["power"], 1),
                "swr": round(cache["swr"], 2),
                "vforward": round(cache["vforward"], 2),
                "vreflected": round(cache["vreflected"], 2),
                "relay": {
                    "sw": cache["sw"],
                    "sw_name": "CL" if cache["sw"] else "LC",
                    "ind": cache["ind"],
                    "ind_display": cache["ind"] / 10.0,
                    "cap": cache["cap"]
                },
                "last_update": cache["last_update"]
            }
        })


class RelayHandler(BaseHandler):
    """继电器控制"""
    
    def get(self):
        """获取继电器参数"""
        self.write_json({
            "success": True,
            "data": {
                "sw": cache["sw"],
                "sw_name": "CL" if cache["sw"] else "LC",
                "ind": cache["ind"],
                "cap": cache["cap"]
            }
        })
    
    async def post(self):
        """设置继电器参数
        
        POST body:
        {
            "sw": 0,      // 0=LC, 1=CL
            "ind": 3,     // 电感索引
            "cap": 27     // 电容索引
        }
        """
        try:
            data = json.loads(self.request.body.decode())
            sw = data.get("sw", 0)
            ind = data.get("ind", 0)
            cap = data.get("cap", 0)
            
            # 验证参数
            if sw not in [0, 1]:
                self.write_json({"success": False, "error": "sw 必须是 0(LC) 或 1(CL)"}, 400)
                return
            if not (0 <= ind <= 127):
                self.write_json({"success": False, "error": "ind 必须在 0-127 范围内"}, 400)
                return
            if not (0 <= cap <= 127):
                self.write_json({"success": False, "error": "cap 必须在 0-127 范围内"}, 400)
                return
            
            if proxy_client and proxy_client.connected:
                success = await proxy_client.set_relay(sw, ind, cap)
                self.write_json({
                    "success": success,
                    "message": "设置成功" if success else "设置失败",
                    "data": {"sw": sw, "ind": ind, "cap": cap}
                })
            else:
                self.write_json({"success": False, "error": "ATR-1000 Proxy 未连接"}, 503)
                
        except json.JSONDecodeError:
            self.write_json({"success": False, "error": "无效的 JSON 格式"}, 400)


class TunerHandler(BaseHandler):
    """学习记录管理"""
    
    def get(self):
        """获取学习记录列表"""
        tuner = get_storage()
        freq_filter = self.get_argument("freq", None)
        limit = int(self.get_argument("limit", 100))
        
        records = tuner.get_all()
        
        if freq_filter:
            freq_hz = int(freq_filter) * 1000
            records = [r for r in records if abs(r["freq"] - freq_hz) < 10000]
        
        records = records[:limit]
        
        result = []
        for r in records:
            result.append({
                "freq_hz": r["freq"],
                "freq_khz": r["freq"] / 1000,
                "sw": r["sw"],
                "sw_name": "CL" if r["sw"] else "LC",
                "ind": r["ind"],
                "ind_display": r["ind"] / 10.0,
                "cap": r["cap"],
                "swr_avg": round(r.get("swr_avg", 1.0), 2),
                "swr_min": r.get("swr_min", 1.0),
                "swr_max": r.get("swr_max", 1.0),
                "sample_count": r.get("sample_count", 0),
                "last_update": r.get("last_update")
            })
        
        self.write_json({
            "success": True,
            "count": len(result),
            "data": result
        })
    
    def post(self):
        """手动添加学习记录"""
        try:
            data = json.loads(self.request.body.decode())
            freq_khz = data.get("freq_khz")
            sw = data.get("sw")
            ind = data.get("ind")
            cap = data.get("cap")
            swr = data.get("swr", 1.0)
            
            if freq_khz is None or sw is None or ind is None or cap is None:
                self.write_json({
                    "success": False,
                    "error": "缺少必要参数: freq_khz, sw, ind, cap"
                }, 400)
                return
            
            tuner = get_storage()
            freq_hz = int(freq_khz) * 1000
            tuner.learn(freq_hz, sw, ind, cap, swr)
            
            self.write_json({
                "success": True,
                "message": "学习记录已添加",
                "data": {
                    "freq_khz": freq_khz,
                    "sw": sw,
                    "sw_name": "CL" if sw else "LC",
                    "ind": ind,
                    "cap": cap,
                    "swr": swr
                }
            })
            
        except json.JSONDecodeError:
            self.write_json({"success": False, "error": "无效的 JSON 格式"}, 400)
    
    def delete(self):
        """删除学习记录"""
        freq_khz = self.get_argument("freq", None)
        
        if not freq_khz:
            self.write_json({"success": False, "error": "缺少参数: freq (kHz)"}, 400)
            return
        
        tuner = get_storage()
        freq_hz = int(freq_khz) * 1000
        deleted = tuner.delete(freq_hz)
        
        self.write_json({
            "success": deleted,
            "message": f"已删除 {freq_khz} kHz 的记录" if deleted else "未找到该记录"
        })


class TunerLookupHandler(BaseHandler):
    """查找天调参数"""
    
    def get(self):
        """根据频率查找天调参数"""
        freq_khz = self.get_argument("freq", None)
        
        if not freq_khz:
            self.write_json({"success": False, "error": "缺少参数: freq (kHz)"}, 400)
            return
        
        tuner = get_storage()
        freq_hz = int(freq_khz) * 1000
        params = tuner.get_tune_params(freq_hz)
        
        # get_tune_params 返回 (sw, ind, cap) 元组或 None
        if params:
            sw, ind, cap = params
            self.write_json({
                "success": True,
                "found": True,
                "data": {
                    "freq_khz": freq_khz,
                    "sw": sw,
                    "sw_name": "CL" if sw else "LC",
                    "ind": ind,
                    "ind_display": ind / 10.0,
                    "cap": cap
                }
            })
        else:
            self.write_json({
                "success": True,
                "found": False,
                "message": f"未找到 {freq_khz} kHz 附近的学习记录"
            })


class QuickTuneHandler(BaseHandler):
    """快速调谐"""
    
    async def post(self):
        """执行快速调谐"""
        try:
            data = json.loads(self.request.body.decode())
            freq_khz = data.get("freq_khz")
            
            if not freq_khz:
                self.write_json({"success": False, "error": "缺少参数: freq_khz"}, 400)
                return
            
            tuner = get_storage()
            freq_hz = int(freq_khz) * 1000
            params = tuner.get_tune_params(freq_hz)
            
            # get_tune_params 返回 (sw, ind, cap) 元组或 None
            if not params:
                self.write_json({
                    "success": False,
                    "found": False,
                    "error": f"未找到 {freq_khz} kHz 的学习记录"
                })
                return
            
            sw, ind, cap = params
            
            # 通过 proxy 应用到设备
            if proxy_client and proxy_client.connected:
                success = await proxy_client.set_relay(sw, ind, cap)
                self.write_json({
                    "success": success,
                    "found": True,
                    "applied": success,
                    "data": {
                        "freq_khz": freq_khz,
                        "sw": sw,
                        "sw_name": "CL" if sw else "LC",
                        "ind": ind,
                        "cap": cap
                    }
                })
            else:
                self.write_json({
                    "success": False,
                    "found": True,
                    "applied": False,
                    "error": "ATR-1000 Proxy 未连接"
                }, 503)
                
        except json.JSONDecodeError:
            self.write_json({"success": False, "error": "无效的 JSON 格式"}, 400)


class SetFreqHandler(BaseHandler):
    """设置频率"""
    
    async def post(self):
        try:
            data = json.loads(self.request.body.decode())
            freq_khz = data.get("freq_khz")
            
            if not freq_khz:
                self.write_json({"success": False, "error": "缺少参数: freq_khz"}, 400)
                return
            
            freq_hz = int(freq_khz) * 1000
            
            if proxy_client and proxy_client.connected:
                success = await proxy_client.set_freq(freq_hz)
                self.write_json({
                    "success": success,
                    "message": "频率已设置" if success else "设置失败",
                    "data": {"freq_khz": freq_khz, "freq_hz": freq_hz}
                })
            else:
                self.write_json({"success": False, "error": "ATR-1000 Proxy 未连接"}, 503)
                
        except json.JSONDecodeError:
            self.write_json({"success": False, "error": "无效的 JSON 格式"}, 400)


def make_app():
    """创建应用"""
    return tornado.web.Application([
        (r"/health", HealthHandler),
        (r"/api/v1/status", StatusHandler),
        (r"/api/v1/relay", RelayHandler),
        (r"/api/v1/tuner", TunerHandler),
        (r"/api/v1/tuner/lookup", TunerLookupHandler),
        (r"/api/v1/tune", QuickTuneHandler),
        (r"/api/v1/freq", SetFreqHandler),
    ])


def main():
    global proxy_client
    
    parser = argparse.ArgumentParser(description="ATR-1000 API Server V2 - 通过 Proxy 通信")
    parser.add_argument("--host", default="0.0.0.0", help="API 服务监听地址")
    parser.add_argument("--port", type=int, default=8080, help="API 服务端口")
    parser.add_argument("--proxy-socket", default=PROXY_SOCKET_PATH, help="Proxy Unix Socket 路径")
    
    args = parser.parse_args()
    
    # 打印启动信息
    print("\n" + "=" * 60)
    print("ATR-1000 API Server V2 (通过 Proxy)")
    print("=" * 60)
    print(f"\nAPI 服务: http://{args.host}:{args.port}")
    print(f"Proxy Socket: {args.proxy_socket}")
    print("\nAPI 端点:")
    print("  GET  /health                - 健康检查")
    print("  GET  /api/v1/status         - 获取当前状态")
    print("  GET  /api/v1/relay          - 获取继电器参数")
    print("  POST /api/v1/relay          - 设置继电器参数")
    print("  GET  /api/v1/tuner          - 获取学习记录")
    print("  POST /api/v1/tuner          - 添加学习记录")
    print("  DELETE /api/v1/tuner        - 删除学习记录")
    print("  GET  /api/v1/tuner/lookup   - 查找天调参数")
    print("  POST /api/v1/tune           - 快速调谐")
    print("  POST /api/v1/freq           - 设置频率")
    print("\n示例:")
    print(f"  curl http://localhost:{args.port}/api/v1/status")
    print(f"  curl 'http://localhost:{args.port}/api/v1/tuner/lookup?freq=7050'")
    print(f"  curl -X POST -H 'Content-Type: application/json' \\")
    print(f"       -d '{{\"freq_khz\":7050}}' http://localhost:{args.port}/api/v1/tune")
    print("=" * 60 + "\n")
    
    # 创建应用
    app = make_app()
    app.listen(args.port)
    
    # 连接 Proxy
    async def init():
        global proxy_client
        proxy_client = ProxyClient(args.proxy_socket)
        connected = await proxy_client.connect()
        if not connected:
            logger.warning(f"无法连接 Proxy ({args.proxy_socket})，API 服务将以离线模式运行")
    
    asyncio.get_event_loop().run_until_complete(init())
    
    logger.info(f"ATR-1000 API Server 启动于 http://{args.host}:{args.port}")
    
    # 运行事件循环
    tornado.ioloop.IOLoop.current().start()


if __name__ == "__main__":
    main()
