#!/bin/bash
# Socat 端口转发监控脚本
# 检查并确保 8800 和 60001 端口转发正常工作

LOG_FILE="/tmp/socat_monitor.log"
SOCAT_PATH="/opt/homebrew/bin/socat"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

check_and_restart() {
    local PORT=$1
    local TARGET=$2
    
    # 检查端口是否在监听
    if ! lsof -i :$PORT -sTCP:LISTEN | grep -q socat; then
        log "端口 $PORT 未监听，正在重启..."
        $SOCAT_PATH -d -d TCP6-LISTEN:$PORT,reuseaddr,fork TCP4:$TARGET >> /tmp/socat_${PORT}.log 2>&1 &
        sleep 2
        if lsof -i :$PORT -sTCP:LISTEN | grep -q socat; then
            log "端口 $PORT 重启成功"
        else
            log "端口 $PORT 重启失败"
        fi
        return 1
    fi
    
    # 检查目标是否可达
    local TARGET_HOST=$(echo $TARGET | cut -d: -f1)
    local TARGET_PORT=$(echo $TARGET | cut -d: -f2)
    
    if ! nc -z -w 3 $TARGET_HOST $TARGET_PORT 2>/dev/null; then
        log "目标 $TARGET 不可达，端口转发可能无法正常工作"
        return 2
    fi
    
    return 0
}

# 主检查流程
log "=== 开始检查端口转发状态 ==="

# 检查 8800 -> 192.168.1.63:80
check_and_restart 8800 "192.168.1.63:80"
RESULT_8800=$?

# 检查 60001 -> 192.168.1.63:60001
check_and_restart 60001 "192.168.1.63:60001"
RESULT_60001=$?

# 输出当前状态
log "状态: 8800端口($([ $RESULT_8800 -eq 0 ] && echo '正常' || echo '异常')), 60001端口($([ $RESULT_60001 -eq 0 ] && echo '正常' || echo '异常'))"
log "=== 检查完成 ==="
