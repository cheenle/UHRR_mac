#!/bin/bash
# MRRC SSH 反向隧道脚本
# 将本地 radio1/radio2 端口通过 SSH 隧道暴露到 www.vlsc.net

REMOTE_HOST="www.vlsc.net"
REMOTE_USER="cheenle"  # SSH 登录用户名
LOCAL_RADIO1_PORT=8891
LOCAL_RADIO2_PORT=8892
REMOTE_RADIO1_PORT=8891
REMOTE_RADIO2_PORT=8892

LOG_FILE="/tmp/mrrc_tunnel.log"
PID_FILE="/tmp/mrrc_tunnel.pid"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

start_tunnel() {
    # 检查是否已有隧道在运行
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            log "隧道已在运行 (PID: $PID)"
            return 0
        fi
    fi
    
    log "=== 启动 MRRC SSH 反向隧道 ==="
    log "本地: $LOCAL_RADIO1_PORT/$LOCAL_RADIO2_PORT -> 远程: $REMOTE_HOST:$REMOTE_RADIO1_PORT/$REMOTE_RADIO2_PORT"
    
    # 使用 SSH 反向隧道
    # -N: 不执行远程命令
    # -R: 反向端口转发 [远程端口]:[本地地址]:[本地端口]
    # -o ServerAliveInterval=60: 保持连接活跃
    # -o ExitOnForwardFailure=yes: 端口转发失败时退出
    ssh -N \
        -R "$REMOTE_RADIO1_PORT:localhost:$LOCAL_RADIO1_PORT" \
        -R "$REMOTE_RADIO2_PORT:localhost:$LOCAL_RADIO2_PORT" \
        -o ServerAliveInterval=60 \
        -o ServerAliveCountMax=3 \
        -o ExitOnForwardFailure=yes \
        -o StrictHostKeyChecking=no \
        "$REMOTE_USER@$REMOTE_HOST" &
    
    TUNNEL_PID=$!
    echo $TUNNEL_PID > "$PID_FILE"
    
    sleep 3
    
    if ps -p "$TUNNEL_PID" > /dev/null 2>&1; then
        log "✅ SSH 隧道已启动 (PID: $TUNNEL_PID)"
        log "用户可以通过以下地址访问:"
        log "  radio1: https://$REMOTE_HOST:$REMOTE_RADIO1_PORT"
        log "  radio2: https://$REMOTE_HOST:$REMOTE_RADIO2_PORT"
    else
        log "❌ SSH 隧道启动失败"
        rm -f "$PID_FILE"
        return 1
    fi
}

stop_tunnel() {
    log "=== 停止 MRRC SSH 隧道 ==="
    
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            kill "$PID" 2>/dev/null
            sleep 1
            log "🛑 SSH 隧道已停止 (PID: $PID)"
        else
            log "隧道进程已不存在"
        fi
        rm -f "$PID_FILE"
    else
        log "没有找到隧道进程"
        # 尝试查找并终止相关 SSH 进程
        pkill -f "ssh.*$REMOTE_HOST.*$LOCAL_RADIO1_PORT"
    fi
}

status() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            log "✅ SSH 隧道运行中 (PID: $PID)"
            log "访问地址:"
            log "  radio1: https://$REMOTE_HOST:$REMOTE_RADIO1_PORT"
            log "  radio2: https://$REMOTE_HOST:$REMOTE_RADIO2_PORT"
            
            # 检查远程端口是否监听
            if ssh "$REMOTE_USER@$REMOTE_HOST" "lsof -i :$REMOTE_RADIO1_PORT -sTCP:LISTEN" > /dev/null 2>&1; then
                log "✅ 远程端口 $REMOTE_RADIO1_PORT 正在监听"
            else
                log "⚠️ 远程端口 $REMOTE_RADIO1_PORT 未监听"
            fi
            return 0
        else
            log "❌ 隧道进程不存在 (PID: $PID)"
            rm -f "$PID_FILE"
            return 1
        fi
    else
        log "❌ 隧道未运行"
        return 1
    fi
}

restart() {
    stop_tunnel
    sleep 2
    start_tunnel
}

# 监控模式（自动重连）
monitor() {
    log "=== 启动隧道监控模式 ==="
    while true; do
        if ! status > /dev/null 2>&1; then
            log "检测到隧道断开，正在重新连接..."
            start_tunnel
        fi
        sleep 30
    done
}

# 检查 SSH 密钥
check_ssh_key() {
    if [ ! -f "$HOME/.ssh/id_rsa" ] && [ ! -f "$HOME/.ssh/id_ed25519" ]; then
        log "⚠️ 未找到 SSH 密钥，建议配置免密登录:"
        log "  ssh-keygen -t ed25519 -C 'mrrc@radio'"
        log "  ssh-copy-id $REMOTE_USER@$REMOTE_HOST"
        return 1
    fi
    
    # 测试连接
    if ! ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no "$REMOTE_USER@$REMOTE_HOST" "echo OK" > /dev/null 2>&1; then
        log "⚠️ 无法连接到 $REMOTE_USER@$REMOTE_HOST"
        log "请确保:"
        log "  1. 网络连接正常"
        log "  2. SSH 服务已启动"
        log "  3. 配置了免密登录 (ssh-copy-id)"
        return 1
    fi
    
    log "✅ SSH 连接测试通过"
    return 0
}

# 主逻辑
case "$1" in
    start)
        check_ssh_key && start_tunnel
        ;;
    stop)
        stop_tunnel
        ;;
    restart)
        restart
        ;;
    status)
        status
        ;;
    monitor)
        monitor
        ;;
    setup)
        log "=== 配置 SSH 免密登录 ==="
        if [ ! -f "$HOME/.ssh/id_ed25519" ]; then
            ssh-keygen -t ed25519 -C "mrrc@radio" -f "$HOME/.ssh/id_ed25519" -N ""
        fi
        log "请将公钥复制到远程服务器:"
        log "  ssh-copy-id -i ~/.ssh/id_ed25519.pub $REMOTE_USER@$REMOTE_HOST"
        log "或者手动添加 ~/.ssh/id_ed25519.pub 到远程服务器的 ~/.ssh/authorized_keys"
        ;;
    *)
        echo "MRRC SSH 反向隧道管理脚本"
        echo ""
        echo "用法: $0 {start|stop|restart|status|monitor|setup}"
        echo ""
        echo "命令:"
        echo "  start    - 启动 SSH 反向隧道"
        echo "  stop     - 停止 SSH 反向隧道"
        echo "  restart  - 重启 SSH 反向隧道"
        echo "  status   - 查看隧道状态"
        echo "  monitor  - 监控模式（自动重连）"
        echo "  setup    - 配置 SSH 免密登录"
        echo ""
        echo "配置:"
        echo "  远程服务器: $REMOTE_USER@$REMOTE_HOST"
        echo "  radio1: 本地:$LOCAL_RADIO1_PORT -> 远程:$REMOTE_RADIO1_PORT"
        echo "  radio2: 本地:$LOCAL_RADIO2_PORT -> 远程:$REMOTE_RADIO2_PORT"
        echo ""
        echo "使用前请先修改脚本中的 REMOTE_USER 变量"
        exit 1
        ;;
esac