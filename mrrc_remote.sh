#!/bin/bash
# MRRC 远程控制脚本
# 用法: ./mrrc_remote.sh start|stop|restart|status

MRRC_DIR="/Users/cheenle/UHRR/MRRC"
PYTHON_PATH="/opt/local/bin/python3"
PYTHONPATH="/Users/cheenle/Library/Python/3.12/lib/python/site-packages"

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
        pkill -f "MRRC"
        sleep 1
        echo "✅ MRRC 已停止"
        ;;
    restart)
        echo "重启 MRRC..."
        pkill -f "MRRC"
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
            ps aux | grep "MRRC" | grep -v grep
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
