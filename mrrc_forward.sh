#!/bin/bash
# MRRC 端口转发脚本
# 将 radio1/radio2 端口转发到 www.vlsc.net

SOCAT_PATH="/opt/homebrew/bin/socat"
LOG_DIR="/Users/cheenle/UHRR/MRRC"
PID_DIR="/Users/cheenle/UHRR/MRRC"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

start_forwarding() {
    local LOCAL_PORT=$1
    local TARGET_HOST=$2
    local TARGET_PORT=$3
    local NAME=$4
    
    # 检查 socat 是否存在
    if [ ! -x "$SOCAT_PATH" ]; then
        log "错误: socat 未安装或不可执行"
        return 1
    fi
    
    # 检查端口是否已被占用
    if lsof -i :$LOCAL_PORT -sTCP:LISTEN 2>/dev/null | grep -q socat; then
        log "$NAME ($LOCAL_PORT) 已在运行"
        return 0
    fi
    
    # 启动端口转发
    # TCP-LISTEN: 监听本地端口
    # fork: 支持多个连接
    # reuseaddr: 快速重用地址
    $SOCAT_PATH -d -d TCP-LISTEN:$LOCAL_PORT,reuseaddr,fork TCP:$TARGET_HOST:$TARGET_PORT >> "$LOG_DIR/forward_${NAME}.log" 2>&1 &
    
    sleep 1
    
    if lsof -i :$LOCAL_PORT -sTCP:LISTEN 2>/dev/null | grep -q socat; then
        log "✅ $NAME 端口转发已启动: $LOCAL_PORT -> $TARGET_HOST:$TARGET_PORT"
    else
        log "❌ $NAME 端口转发启动失败"
        return 1
    fi
}

stop_forwarding() {
    local PORT=$1
    local NAME=$2
    
    # 查找并终止 socat 进程
    PIDS=$(lsof -ti :$PORT 2>/dev/null)
    if [ -n "$PIDS" ]; then
        kill $PIDS 2>/dev/null
        sleep 1
        log "🛑 $NAME 端口转发已停止 (端口 $PORT)"
    fi
}

case "$1" in
    start)
        log "=== 启动 MRRC 端口转发 ==="
        start_forwarding 8891 "www.vlsc.net" 8891 "radio1"
        start_forwarding 8892 "www.vlsc.net" 8892 "radio2"
        log "=== 端口转发启动完成 ==="
        ;;
    stop)
        log "=== 停止 MRRC 端口转发 ==="
        stop_forwarding 8891 "radio1"
        stop_forwarding 8892 "radio2"
        log "=== 端口转发停止完成 ==="
        ;;
    restart)
        $0 stop
        sleep 2
        $0 start
        ;;
    status)
        log "=== 端口转发状态 ==="
        for PORT in 8891 8892; do
            if lsof -i :$PORT -sTCP:LISTEN 2>/dev/null | grep -q socat; then
                NAME=$( [ "$PORT" = "8891" ] && echo "radio1" || echo "radio2" )
                log "✅ $NAME ($PORT): 运行中"
            else
                NAME=$( [ "$PORT" = "8891" ] && echo "radio1" || echo "radio2" )
                log "❌ $NAME ($PORT): 已停止"
            fi
        done
        ;;
    *)
        echo "用法: $0 {start|stop|restart|status}"
        exit 1
        ;;
esac
