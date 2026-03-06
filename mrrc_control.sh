#!/bin/bash

# MRRC System Control Script
# Start and stop script for Mobile Remote Radio Control system
ulimit -n 10240

# 获取脚本所在目录（支持相对路径部署）
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Configuration
RIGCTL_MODEL="30003"  # IC-R9000
RIGCTL_DEVICE="/dev/cu.usbserial-120"
RIGCTL_SPEED="4800"
RIGCTL_STOP_BITS="2"
RIGCTL_HOST="127.0.0.1"
RIGCTL_PORT="4532"
MRRC_PORT="8877"
LOG_DIR="$SCRIPT_DIR"
RIGCTLD_LOG="$LOG_DIR/rigctld.log"
MRRC_LOG="$LOG_DIR/mrrc.log"
ATR1000_LOG="$LOG_DIR/atr1000_proxy.log"

# ATR-1000 Configuration
ATR1000_DEVICE="192.168.1.63"
ATR1000_PORT="60001"
ATR1000_INTERVAL="1.0"  # 数据请求间隔（秒）

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print status messages
print_status() {
    echo -e "${BLUE}[STATUS]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if a process is running
is_running() {
    pgrep -f "$1" > /dev/null 2>&1
}

# Function to get PID of a process
get_pid() {
    pgrep -f "$1" 2>/dev/null
}

# Function to kill a process
kill_process() {
    local process_name="$1"
    local pid=$(get_pid "$process_name")
    
    if [ -n "$pid" ]; then
        print_status "Killing $process_name (PID: $pid)..."
        kill "$pid" 2>/dev/null
        sleep 2
        
        # Force kill if still running
        if is_running "$process_name"; then
            print_warning "$process_name still running, force killing..."
            kill -9 "$pid" 2>/dev/null
            sleep 1
        fi
        
        if ! is_running "$process_name"; then
            print_success "$process_name stopped successfully"
        else
            print_error "Failed to stop $process_name"
        fi
    else
        print_status "$process_name is not running"
    fi
}

# Function to start rigctld
start_rigctld() {
    if is_running "rigctld"; then
        print_warning "rigctld is already running"
        return 1
    fi
    
    print_status "Starting rigctld..."
    
    # Clear log files
    > "$RIGCTLD_LOG"
    
    # Start rigctld with verbose logging
    rigctld -m "$RIGCTL_MODEL" \
            -r "$RIGCTL_DEVICE" \
            -s "$RIGCTL_SPEED" \
            -C stop_bits="$RIGCTL_STOP_BITS" \
            -T "$RIGCTL_HOST" \
            -t "$RIGCTL_PORT" \
            -vvv > "$RIGCTLD_LOG" 2>&1 &
    
    local pid=$!
    sleep 3
    
    if is_running "rigctld"; then
        print_success "rigctld started successfully (PID: $pid)"
        echo "rigctld PID: $pid" > "$LOG_DIR/rigctld.pid"
        return 0
    else
        print_error "Failed to start rigctld"
        return 1
    fi
}

# Function to start MRRC
start_mrrc() {
    if is_running "MRRC"; then
        print_warning "MRRC is already running"
        return 1
    fi
    
    print_status "Starting MRRC server..."
    
    # Clear log files
    > "$MRRC_LOG"
    
    # Start MRRC server
    python3 "$LOG_DIR/MRRC" > "$MRRC_LOG" 2>&1 &
    
    local pid=$!
    sleep 3
    
    if is_running "MRRC"; then
        print_success "MRRC started successfully (PID: $pid)"
        echo "MRRC PID: $pid" > "$LOG_DIR/mrrc.pid"
        print_success "MRRC is now accessible at https://localhost:$MRRC_PORT"
        return 0
    else
        print_error "Failed to start MRRC"
        print_error "Check $MRRC_LOG for details"
        return 1
    fi
}

# Function to stop rigctld
stop_rigctld() {
    kill_process "rigctld"
    rm -f "$LOG_DIR/rigctld.pid"
}

# Function to stop MRRC
stop_mrrc() {
    kill_process "MRRC"
    rm -f "$LOG_DIR/mrrc.pid"
}

# Function to start ATR-1000 proxy
start_atr1000() {
    if is_running "atr1000_proxy.py"; then
        print_warning "ATR-1000 proxy is already running"
        return 1
    fi
    
    print_status "Starting ATR-1000 proxy..."
    
    # Clear log files
    > "$ATR1000_LOG"
    
    # Start ATR-1000 proxy
    python3 "$LOG_DIR/atr1000_proxy.py" \
        --device "$ATR1000_DEVICE" \
        --port "$ATR1000_PORT" \
        --interval "$ATR1000_INTERVAL" \
        > "$ATR1000_LOG" 2>&1 &
    
    local pid=$!
    sleep 2
    
    if is_running "atr1000_proxy.py"; then
        print_success "ATR-1000 proxy started successfully (PID: $pid)"
        echo "ATR-1000 proxy PID: $pid" > "$LOG_DIR/atr1000.pid"
        print_success "ATR-1000 device: $ATR1000_DEVICE:$ATR1000_PORT"
        return 0
    else
        print_error "Failed to start ATR-1000 proxy"
        print_error "Check $ATR1000_LOG for details"
        return 1
    fi
}

# Function to stop ATR-1000 proxy
stop_atr1000() {
    kill_process "atr1000_proxy.py"
    rm -f "$LOG_DIR/atr1000.pid"
    # Clean up Unix Socket
    rm -f /tmp/atr1000_proxy.sock
}

# Function to start ATU server
start_atu_server() {
    if is_running "ATU_SERVER_WEBSOCKET"; then
        print_warning "ATU server is already running"
        return 1
    fi
    
    print_status "Starting ATU server..."
    
    # Clear log files
    > "$ATU_LOG"
    
    # Start ATU server
    python3 "$LOG_DIR/ATU_SERVER_WEBSOCKET.py" > "$ATU_LOG" 2>&1 &
    
    local pid=$!
    sleep 3
    
    if is_running "ATU_SERVER_WEBSOCKET"; then
        print_success "ATU server started successfully (PID: $pid)"
        echo "ATU server PID: $pid" > "$LOG_DIR/atu_server.pid"
        print_success "ATU server is now accessible at https://localhost:$ATU_SERVER_PORT"
        return 0
    else
        print_error "Failed to start ATU server"
        print_error "Check $ATU_LOG for details"
        return 1
    fi
}

# Function to stop ATU server
stop_atu_server() {
    kill_process "ATU_SERVER_WEBSOCKET"
    rm -f "$LOG_DIR/atu_server.pid"
}

# Function to show status
show_status() {
    echo "=== MRRC System Status ==="
    
    if is_running "rigctld"; then
        local pid=$(get_pid "rigctld")
        print_success "rigctld is running (PID: $pid)"
    else
        print_error "rigctld is not running"
    fi
    
    if is_running "MRRC"; then
        local pid=$(get_pid "MRRC")
        print_success "MRRC is running (PID: $pid)"
        print_success "Accessible at https://localhost:$MRRC_PORT"
        
        # V5.0: 检查音频进程模式
        if [ -f "$LOG_DIR/MRRC.conf" ]; then
            if grep -q "enabled = true" "$LOG_DIR/MRRC.conf" 2>/dev/null; then
                print_success "Audio Architecture: V5.0 (Independent Process Mode)"
            else
                print_status "Audio Architecture: V4.x (Legacy Thread Mode)"
            fi
        fi
    else
        print_error "MRRC is not running"
    fi
    
    if is_running "atr1000_proxy.py"; then
        local pid=$(get_pid "atr1000_proxy.py")
        print_success "ATR-1000 proxy is running (PID: $pid)"
    else
        print_warning "ATR-1000 proxy is not running"
    fi
    
    echo ""
    echo "=== Log File Sizes ==="
    echo "rigctld log: $(ls -lh "$RIGCTLD_LOG" 2>/dev/null | awk '{print $5}' || echo '0 bytes')"
    echo "MRRC log: $(ls -lh "$MRRC_LOG" 2>/dev/null | awk '{print $5}' || echo '0 bytes')"
    echo "ATR-1000 log: $(ls -lh "$ATR1000_LOG" 2>/dev/null | awk '{print $5}' || echo '0 bytes')"
}

# Function to show logs
show_logs() {
    local lines=${1:-20}
    
    case "$2" in
        rigctld)
            echo "=== Last $lines lines from rigctld log ==="
            tail -n "$lines" "$RIGCTLD_LOG"
            ;;
        mrrc)
            echo "=== Last $lines lines from MRRC log ==="
            tail -n "$lines" "$MRRC_LOG"
            ;;
        atr1000)
            echo "=== Last $lines lines from ATR-1000 log ==="
            tail -n "$lines" "$ATR1000_LOG"
            ;;
        *)
            echo "=== Last $lines lines from rigctld log ==="
            tail -n "$lines" "$RIGCTLD_LOG"
            echo ""
            echo "=== Last $lines lines from MRRC log ==="
            tail -n "$lines" "$MRRC_LOG"
            echo ""
            echo "=== Last $lines lines from ATR-1000 log ==="
            tail -n "$lines" "$ATR1000_LOG"
            ;;
    esac
}

# Function to restart the system
restart_system() {
    print_status "Restarting MRRC system..."
    stop
    sleep 3
    start
}

# Function to start all services
start() {
    print_status "Starting MRRC system..."
    
    # Check if device exists
    if [ ! -e "$RIGCTL_DEVICE" ]; then
        print_warning "Radio device $RIGCTL_DEVICE not found, starting anyway..."
    fi
    
    start_rigctld
    sleep 2
    start_mrrc
    sleep 1
    start_atr1000
    
    if is_running "rigctld" && is_running "MRRC"; then
        print_success "MRRC system started successfully!"
        show_status
    else
        print_error "Failed to start MRRC system completely"
    fi
}

# Function to stop all services
stop() {
    print_status "Stopping MRRC system..."
    stop_atr1000
    stop_mrrc
    stop_rigctld
    print_success "MRRC system stopped"
}

# Main script logic
case "$1" in
    start)
        start
        ;;
    stop)
        stop
        ;;
    restart)
        restart_system
        ;;
    status)
        show_status
        ;;
    logs)
        show_logs "$2" "$3"
        ;;
    start-rigctld)
        start_rigctld
        ;;
    stop-rigctld)
        stop_rigctld
        ;;
    start-mrrc)
        start_mrrc
        ;;
    stop-mrrc)
        stop_mrrc
        ;;
    start-atr1000)
        start_atr1000
        ;;
    stop-atr1000)
        stop_atr1000
        ;;
    start-atu)
        start_atu_server
        ;;
    stop-atu)
        stop_atu_server
        ;;
    *)
        echo "MRRC System Control Script"
        echo "Usage: $0 {start|stop|restart|status|logs [lines] [service]|start-rigctld|stop-rigctld|start-mrrc|stop-mrrc|start-atr1000|stop-atr1000}"
        echo ""
        echo "Commands:"
        echo "  start           - Start rigctld, MRRC and ATR-1000 proxy services"
        echo "  stop            - Stop all services"
        echo "  restart         - Restart the entire system"
        echo "  status          - Show current status of services"
        echo "  logs [n] [service] - Show last n lines of logs (default 20)"
        echo "                    service can be 'rigctld', 'mrrc', 'atr1000' or 'all'"
        echo "  start-rigctld   - Start only rigctld service"
        echo "  stop-rigctld    - Stop only rigctld service"
        echo "  start-mrrc      - Start only MRRC service"
        echo "  stop-mrrc       - Stop only MRRC service"
        echo "  start-atr1000   - Start only ATR-1000 proxy service"
        echo "  stop-atr1000    - Stop only ATR-1000 proxy service"
        echo ""
        echo "Examples:"
        echo "  $0 start"
        echo "  $0 logs 50 atr1000"
        echo "  $0 status"
        echo "  $0 start-atr1000"
        exit 1
        ;;
esac

exit 0
