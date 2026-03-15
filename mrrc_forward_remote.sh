#!/bin/bash
# MRRC 端口转发脚本 - 在 www.vlsc.net 上运行
# 将 8891/8892 端口转发到本地 MRRC 服务器

LOCAL_MRR_SERVER="183.241.214.232"
SOCAT_PATH="/usr/bin/socat"
LOG_DIR="/var/log/mrrc"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_DIR/forward.log"
}

# 创建日志目录
mkdir -p "$LOG_DIR"

start_forwarding() {
    local LOCAL_PORT=$1
    local TARGET_PORT=$2
    local NAME=$3
    
    # 检查 socat 是否存在
    if [ ! -x "$SOCAT_PATH" ]; then
        log "错误: socat 未安装"
        return 1
    fi
    
    # 停止已有的 socat 进程
    pkill -f "socat.*$LOCAL_PORT.*$LOCAL_MRR_SERVER" 2>/dev/null
    sleep 1
    
    # 启动端口转发
    # TCP-LISTEN: 监听本地端口
    # fork: 支持多个连接
    # reuseaddr: 快速重用地址
    nohup $SOCAT_PATH -d -d TCP-LISTEN:$LOCAL_PORT,reuseaddr,fork TCP:$LOCAL_MRR_SERVER:$TARGET_PORT >> "$LOG_DIR/forward_${NAME}.log" 2>&1 &
    
    sleep 2
    
    if lsof -i :$LOCAL_PORT -sTCP:LISTEN 2>/dev/null | grep -q socat; then
        log "✅ $NAME 端口转发已启动: $LOCAL_PORT -> $LOCAL_MRR_SERVER:$TARGET_PORT"
    else
        log "❌ $NAME 端口转发启动失败"
        return 1
    fi
}

stop_forwarding() {
    local PORT=$1
    local NAME=$2
    
    # 查找并终止 socat 进程
    pkill -f "socat.*$PORT.*TCP-LISTEN" 2>/dev/null
    sleep 1
    log "🛑 $NAME 端口转发已停止 (端口 $PORT)"
}

case "$1" in
    start)
        log "=== 启动 MRRC 端口转发到 $LOCAL_MRR_SERVER ==="
        start_forwarding 8891 8891 "radio1"
        start_forwarding 8892 8892 "radio2"
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
                log "✅ $NAME ($PORT): 运行中 -> $LOCAL_MRR_SERVER:$PORT"
            else
                NAME=$( [ "$PORT" = "8891" ] && echo "radio1" || echo "radio2" )
                log "❌ $NAME ($PORT): 已停止"
            fi
        done
        ;;
    *)
        echo "用法: $0 {start|stop|restart|status}"
        echo ""
        echo "此脚本在 www.vlsc.net 服务器上运行"
        echo "将 8891/8892 端口转发到本地 MRRC 服务器: $LOCAL_MRR_SERVER"
        exit 1
        ;;
esac
