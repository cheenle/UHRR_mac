#!/bin/bash

# ATU Monitor Server Control Script
# Start and stop script for ATU monitor server

# Configuration
ATU_SERVER_PORT="8889"
LOG_DIR="/Users/cheenle/UHRR/UHRR_mac"
ATU_LOG="$LOG_DIR/atu_server.log"

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
    echo "=== ATU Server Status ==="
    
    if is_running "ATU_SERVER_WEBSOCKET"; then
        local pid=$(get_pid "ATU_SERVER_WEBSOCKET")
        print_success "ATU server is running (PID: $pid)"
        print_success "Accessible at https://localhost:$ATU_SERVER_PORT"
    else
        print_error "ATU server is not running"
    fi
    
    echo ""
    echo "=== Log File Size ==="
    echo "ATU log: $(ls -lh "$ATU_LOG" 2>/dev/null | awk '{print $5}' || echo '0 bytes')"
}

# Function to show logs
show_logs() {
    local lines=${1:-20}
    
    echo "=== Last $lines lines from ATU server log ==="
    tail -n "$lines" "$ATU_LOG"
}

# Main script logic
case "$1" in
    start)
        start_atu_server
        ;;
    stop)
        stop_atu_server
        ;;
    restart)
        print_status "Restarting ATU server..."
        stop_atu_server
        sleep 3
        start_atu_server
        ;;
    status)
        show_status
        ;;
    logs)
        show_logs "$2"
        ;;
    *)
        echo "ATU Monitor Server Control Script"
        echo "Usage: $0 {start|stop|restart|status|logs [lines]}"
        echo ""
        echo "Commands:"
        echo "  start    - Start ATU server"
        echo "  stop     - Stop ATU server"
        echo "  restart  - Restart ATU server"
        echo "  status   - Show current status"
        echo "  logs [n] - Show last n lines of logs (default 20)"
        echo ""
        echo "Examples:"
        echo "  $0 start"
        echo "  $0 logs 50"
        echo "  $0 status"
        exit 1
        ;;
esac

exit 0