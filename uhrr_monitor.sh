#!/bin/bash

# UHRR 服务监控脚本
# 通过 SSH 远程监控 UHRR 服务状态和性能

UHRR_DIR="/Users/cheenle/UHRR/UHRR_mac"
SERVICE_NAME="com.user.uhrr"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

# 检查基本状态
check_basic_status() {
    echo "=== UHRR 服务基本状态 ==="
    
    # 检查进程
    PID=$(pgrep -f "UHRR")
    if [ -n "$PID" ]; then
        log_success "UHRR 进程运行中 (PID: $PID)"
        
        # 获取进程详细信息
        echo "进程信息:"
        ps -p $PID -o pid,user,pcpu,pmem,etime,command --no-headers
        
        # 检查内存使用
        MEM_USAGE=$(ps -p $PID -o pmem --no-headers | awk '{print $1}')
        echo "内存使用: ${MEM_USAGE}%"
        
        # 检查运行时间
        UPTIME=$(ps -p $PID -o etime --no-headers)
        echo "运行时间: $UPTIME"
    else
        log_error "UHRR 进程未运行"
    fi
    
    # 检查端口
    PORT=8899
    if lsof -i :$PORT > /dev/null 2>&1; then
        log_success "Web 服务器监听端口 $PORT"
        
        # 获取端口连接信息
        CONNECTIONS=$(lsof -i :$PORT | grep -c "LISTEN")
        echo "监听连接数: $CONNECTIONS"
    else
        log_error "Web 服务器未在端口 $PORT 上监听"
    fi
    
    echo ""
}

# 检查系统资源
check_system_resources() {
    echo "=== 系统资源使用情况 ==="
    
    # CPU 使用率
    CPU_USAGE=$(top -l 1 | grep "CPU usage" | awk '{print $3}' | sed 's/%//')
    echo "CPU 使用率: ${CPU_USAGE}%"
    
    # 内存使用
    MEMORY_INFO=$(vm_stat | grep "Pages active" | awk '{print $3}' | sed 's/\.//')
    TOTAL_MEMORY=$(( $(sysctl -n hw.memsize) / 1024 / 1024 ))
    ACTIVE_MEMORY=$(( MEMORY_INFO * 4096 / 1024 / 1024 ))
    MEMORY_PERCENT=$(( ACTIVE_MEMORY * 100 / TOTAL_MEMORY ))
    echo "内存使用: ${ACTIVE_MEMORY}MB / ${TOTAL_MEMORY}MB (${MEMORY_PERCENT}%)"
    
    # 磁盘空间
    DISK_USAGE=$(df -h "$UHRR_DIR" | tail -1 | awk '{print $5}')
    echo "磁盘使用率: $DISK_USAGE"
    
    echo ""
}

# 检查网络连接
check_network_status() {
    echo "=== 网络连接状态 ==="
    
    # 检查本地连接
    if netstat -an | grep ".8899" | grep "LISTEN" > /dev/null; then
        log_success "本地端口 8899 监听正常"
    else
        log_error "本地端口 8899 未监听"
    fi
    
    # 检查 rigctld 连接
    if netstat -an | grep ".4532" | grep "LISTEN" > /dev/null; then
        log_success "rigctld 端口 4532 监听正常"
    else
        log_warning "rigctld 端口 4532 未监听 (可能正常)"
    fi
    
    echo ""
}

# 检查日志状态
check_logs_status() {
    echo "=== 日志文件状态 ==="
    
    LOG_FILES=(
        "$UHRR_DIR/uhrr_service.log"
        "$UHRR_DIR/uhrr_service_error.log"
        "$UHRR_DIR/uhrr_debug.log"
        "$UHRR_DIR/uhrr.log"
    )
    
    for LOG_FILE in "${LOG_FILES[@]}"; do
        if [ -f "$LOG_FILE" ]; then
            SIZE=$(ls -lh "$LOG_FILE" | awk '{print $5}')
            LINES=$(wc -l < "$LOG_FILE")
            LAST_MODIFIED=$(stat -f "%Sm" "$LOG_FILE")
            echo "✓ $(basename "$LOG_FILE"): ${SIZE}, ${LINES} 行, 最后修改: $LAST_MODIFIED"
        else
            echo "✗ $(basename "$LOG_FILE"): 文件不存在"
        fi
    done
    
    echo ""
}

# 检查错误和警告
check_errors_warnings() {
    echo "=== 错误和警告检查 ==="
    
    ERROR_COUNT=0
    WARNING_COUNT=0
    
    # 检查服务错误日志
    if [ -f "$UHRR_DIR/uhrr_service_error.log" ]; then
        ERRORS=$(grep -i -e "error" -e "failed" -e "exception" "$UHRR_DIR/uhrr_service_error.log" | tail -5)
        if [ -n "$ERRORS" ]; then
            log_error "服务错误日志中发现错误:"
            echo "$ERRORS"
            ERROR_COUNT=$((ERROR_COUNT + $(echo "$ERRORS" | wc -l)))
        else
            log_success "服务错误日志中未发现错误"
        fi
    fi
    
    # 检查调试日志
    if [ -f "$UHRR_DIR/uhrr_debug.log" ]; then
        WARNINGS=$(grep -i "warning" "$UHRR_DIR/uhrr_debug.log" | tail -5)
        if [ -n "$WARNINGS" ]; then
            log_warning "调试日志中发现警告:"
            echo "$WARNINGS"
            WARNING_COUNT=$((WARNING_COUNT + $(echo "$WARNINGS" | wc -l)))
        fi
        
        RECENT_ERRORS=$(grep -i -e "error" -e "failed" "$UHRR_DIR/uhrr_debug.log" | tail -5)
        if [ -n "$RECENT_ERRORS" ]; then
            log_error "调试日志中发现错误:"
            echo "$RECENT_ERRORS"
            ERROR_COUNT=$((ERROR_COUNT + $(echo "$RECENT_ERRORS" | wc -l)))
        fi
    fi
    
    echo "错误总数: $ERROR_COUNT"
    echo "警告总数: $WARNING_COUNT"
    echo ""
}

# 检查音频设备状态
check_audio_status() {
    echo "=== 音频设备状态 ==="
    
    # 检查 PyAudio 设备
    if python3 -c "import pyaudio; p = pyaudio.PyAudio(); print('PyAudio 可用'); p.terminate()" 2>/dev/null; then
        log_success "PyAudio 库可用"
        
        # 获取音频设备信息
        AUDIO_INFO=$(python3 -c "
import pyaudio
p = pyaudio.PyAudio()
input_devices = [i for i in range(p.get_device_count()) if p.get_device_info_by_index(i)['maxInputChannels'] > 0]
output_devices = [i for i in range(p.get_device_count()) if p.get_device_info_by_index(i)['maxOutputChannels'] > 0]
print(f'输入设备: {len(input_devices)} 个')
print(f'输出设备: {len(output_devices)} 个')
for i in input_devices:
    info = p.get_device_info_by_index(i)
    print(f'  输入: {info[\"name\"]} (通道: {info[\"maxInputChannels\"]})')
for i in output_devices:
    info = p.get_device_info_by_index(i)
    print(f'  输出: {info[\"name\"]} (通道: {info[\"maxOutputChannels\"]})')
p.terminate()
" 2>/dev/null)
        
        if [ -n "$AUDIO_INFO" ]; then
            echo "$AUDIO_INFO"
        fi
    else
        log_error "PyAudio 库不可用"
    fi
    
    echo ""
}

# 生成健康报告
generate_health_report() {
    echo "=== UHRR 服务健康报告 ==="
    echo "生成时间: $(date)"
    echo ""
    
    check_basic_status
    check_system_resources
    check_network_status
    check_logs_status
    check_errors_warnings
    check_audio_status
    
    echo "=== 建议操作 ==="
    
    # 根据状态给出建议
    PID=$(pgrep -f "UHRR")
    if [ -z "$PID" ]; then
        echo "❌ 服务未运行，建议执行: ./uhrr_control.sh start"
    else
        echo "✅ 服务运行正常"
        
        # 检查内存使用
        MEM_USAGE=$(ps -p $PID -o pmem --no-headers | awk '{print $1}' | cut -d. -f1)
        if [ "$MEM_USAGE" -gt 50 ]; then
            echo "⚠️  内存使用较高，建议重启服务: ./uhrr_control.sh restart"
        fi
    fi
    
    # 检查日志文件大小
    if [ -f "$UHRR_DIR/uhrr_service.log" ]; then
        LOG_SIZE=$(stat -f%z "$UHRR_DIR/uhrr_service.log")
        if [ "$LOG_SIZE" -gt 10485760 ]; then # 10MB
            echo "⚠️  服务日志文件较大，建议清理"
        fi
    fi
}

# 实时监控模式
realtime_monitor() {
    echo "启动 UHRR 服务实时监控..."
    echo "按 Ctrl+C 退出监控"
    echo ""
    
    while true; do
        clear
        echo "=== UHRR 实时监控 - $(date '+%Y-%m-%d %H:%M:%S') ==="
        echo ""
        
        # 基本状态
        PID=$(pgrep -f "UHRR")
        if [ -n "$PID" ]; then
            echo "✅ 服务运行中 (PID: $PID)"
            
            # CPU 和内存
            CPU=$(ps -p $PID -o pcpu --no-headers | awk '{print $1}')
            MEM=$(ps -p $PID -o pmem --no-headers | awk '{print $1}')
            echo "📊 CPU: ${CPU}% | 内存: ${MEM}%"
            
            # 运行时间
            UPTIME=$(ps -p $PID -o etime --no-headers)
            echo "⏰ 运行时间: $UPTIME"
        else
            echo "❌ 服务未运行"
        fi
        
        # 端口状态
        if lsof -i :8899 > /dev/null 2>&1; then
            echo "🌐 Web 服务: 正常 (端口 8899)"
        else
            echo "🌐 Web 服务: 异常"
        fi
        
        # 系统资源
        SYS_CPU=$(top -l 1 | grep "CPU usage" | awk '{print $3}' | sed 's/%//')
        echo "💻 系统CPU: ${SYS_CPU}%"
        
        echo ""
        echo "监控刷新中... (5秒间隔)"
        sleep 5
    done
}

# 显示帮助信息
show_help() {
    echo "UHRR 服务监控脚本"
    echo ""
    echo "用法: $0 [命令]"
    echo ""
    echo "命令:"
    echo "  status    - 生成完整健康报告"
    echo "  basic     - 检查基本状态"
    echo "  system    - 检查系统资源"
    echo "  network   - 检查网络状态"
    echo "  logs      - 检查日志状态"
    echo "  errors    - 检查错误和警告"
    echo "  audio     - 检查音频设备"
    echo "  realtime  - 启动实时监控"
    echo "  help      - 显示此帮助信息"
    echo ""
    echo "示例:"
    echo "  $0 status    # 完整健康检查"
    echo "  $0 realtime  # 实时监控"
    echo "  $0 basic     # 快速状态检查"
}

# 主程序
case "${1:-status}" in
    status)
        generate_health_report
        ;;
    basic)
        check_basic_status
        ;;
    system)
        check_system_resources
        ;;
    network)
        check_network_status
        ;;
    logs)
        check_logs_status
        ;;
    errors)
        check_errors_warnings
        ;;
    audio)
        check_audio_status
        ;;
    realtime)
        realtime_monitor
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        log_error "未知命令: $1"
        echo ""
        show_help
        exit 1
        ;;
esac