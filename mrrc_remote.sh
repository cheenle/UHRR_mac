#!/bin/bash
# MRRC 远程控制脚本
# 用法: ./mrrc_remote.sh start|stop|restart|status
# S9: 部署目录与解释器不再硬编码——目录基于脚本位置自动解析，解释器自动探测
set -euo pipefail

MRRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 探测可用的 python3 解释器
detect_python() {
    for cand in python3 /opt/local/bin/python3 /usr/bin/python3 /opt/homebrew/bin/python3; do
        if command -v "$cand" >/dev/null 2>&1; then
            command -v "$cand"
            return 0
        fi
    done
    echo "python3"
}
PYTHON_PATH="$(detect_python)"
# 用户级 site-packages（按解释器版本探测，找不到则置空）
_pyver="$("$PYTHON_PATH" -c 'import sys;print("%d.%d"%sys.version_info[:2])' 2>/dev/null || true)"
PYTHONPATH="${HOME}/Library/Python/${_pyver:-3}/lib/python/site-packages"

case "$1" in
    start)
        echo "启动 MRRC..."
        cd "$MRRC_DIR"
        PYTHONPATH="$PYTHONPATH" nohup "$PYTHON_PATH" -u ./MRRC > mrrc_service.log 2>&1 &
        sleep 3
        if lsof -iTCP:8877 -sTCP:LISTEN -n -P >/dev/null 2>&1; then
            echo "✅ MRRC 已启动"
        else
            echo "❌ MRRC 启动失败，查看日志:"
            tail -20 "$MRRC_DIR/mrrc_service.log"
        fi
        ;;
    stop)
        echo "停止 MRRC..."
        pkill -f "MRRC" || true
        sleep 1
        echo "✅ MRRC 已停止"
        ;;
    restart)
        echo "重启 MRRC..."
        pkill -f "MRRC" || true
        sleep 2
        cd "$MRRC_DIR"
        PYTHONPATH="$PYTHONPATH" nohup "$PYTHON_PATH" -u ./MRRC > mrrc_service.log 2>&1 &
        sleep 5
        if lsof -iTCP:8877 -sTCP:LISTEN -n -P >/dev/null 2>&1; then
            echo "✅ MRRC 已重启"
        else
            echo "❌ MRRC 重启失败"
        fi
        ;;
    status)
        if lsof -iTCP:8877 -sTCP:LISTEN -n -P >/dev/null 2>&1; then
            echo "✅ MRRC 运行中"
            ps aux | grep "[M]RRC" || true
        else
            echo "❌ MRRC 未运行"
        fi
        ;;
    log)
        tail -30 "$MRRC_DIR/mrrc_service.log"
        ;;
    *)
        echo "用法: $0 {start|stop|restart|status|log}"
        exit 1
        ;;
esac
