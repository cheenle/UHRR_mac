#!/bin/bash

# UHRR System Control Script
# Start and stop script for Universal HamRadio Remote HTML5 system
ulimit -n 10240

# Configuration
RIGCTL_MODEL="30003"  # IC-R9000
RIGCTL_DEVICE="/dev/cu.usbserial-120"
RIGCTL_SPEED="4800"
RIGCTL_STOP_BITS="2"
RIGCTL_HOST="127.0.0.1"
RIGCTL_PORT="4532"
UHRR_PORT="8877"
ATU_SERVER_PORT="8889"
LOG_DIR="/Users/cheenle/UHRR/UHRR_mac"
RIGCTLD_LOG="$LOG_DIR/rigctld.log"
UHRR_LOG="$LOG_DIR/uhrr.log"
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

# Function to start UHRR
start_uhrr() {
    if is_running "UHRR"; then
        print_warning "UHRR is already running"
        return 1
    fi
    
    print_status "Starting UHRR server..."
    
    # Clear log files
    > "$UHRR_LOG"
    
    # Start UHRR server
    python3 "$LOG_DIR/UHRR" > "$UHRR_LOG" 2>&1 &
    
    local pid=$!
    sleep 3
    
    if is_running "UHRR"; then
        print_success "UHRR started successfully (PID: $pid)"
        echo "UHRR PID: $pid" > "$LOG_DIR/uhrr.pid"
        print_success "UHRR is now accessible at https://localhost:$UHRR_PORT"
        return 0
    else
        print_error "Failed to start UHRR"
        print_error "Check $UHRR_LOG for details"
        return 1
    fi
}

# Function to stop rigctld
stop_rigctld() {
    kill_process "rigctld"
    rm -f "$LOG_DIR/rigctld.pid"
}

# Function to stop UHRR
stop_uhrr() {
    kill_process "UHRR"
    rm -f "$LOG_DIR/uhrr.pid"
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
    echo "=== UHRR System Status ==="
    
    if is_running "rigctld"; then
        local pid=$(get_pid "rigctld")
        print_success "rigctld is running (PID: $pid)"
    else
        print_error "rigctld is not running"
    fi
    
    if is_running "UHRR"; then
        local pid=$(get_pid "UHRR")
        print_success "UHRR is running (PID: $pid)"
        print_success "Accessible at https://localhost:$UHRR_PORT"
    else
        print_error "UHRR is not running"
    fi
    
    echo ""
    echo "=== Log File Sizes ==="
    echo "rigctld log: $(ls -lh "$RIGCTLD_LOG" 2>/dev/null | awk '{print $5}' || echo '0 bytes')"
    echo "UHRR log: $(ls -lh "$UHRR_LOG" 2>/dev/null | awk '{print $5}' || echo '0 bytes')"
}

# Function to show logs
show_logs() {
    local lines=${1:-20}
    
    case "$2" in
        rigctld)
            echo "=== Last $lines lines from rigctld log ==="
            tail -n "$lines" "$RIGCTLD_LOG"
            ;;
        uhrr)
            echo "=== Last $lines lines from UHRR log ==="
            tail -n "$lines" "$UHRR_LOG"
            ;;
        *)
            echo "=== Last $lines lines from rigctld log ==="
            tail -n "$lines" "$RIGCTLD_LOG"
            echo ""
            echo "=== Last $lines lines from UHRR log ==="
            tail -n "$lines" "$UHRR_LOG"
            ;;
    esac
}

# Function to restart the system
restart_system() {
    print_status "Restarting UHRR system..."
    stop
    sleep 3
    start
}

# Function to start all services
start() {
    print_status "Starting UHRR system..."
    
    # Check if device exists
    if [ ! -e "$RIGCTL_DEVICE" ]; then
        print_warning "Radio device $RIGCTL_DEVICE not found, starting anyway..."
    fi
    
        start_rigctld
    sleep 2
    start_uhrr
    
    if is_running "rigctld" && is_running "UHRR"; then
        print_success "UHRR system started successfully!"
        show_status
    else
        print_error "Failed to start UHRR system completely"
    fi
}

# Function to stop all services
stop() {
    print_status "Stopping UHRR system..."
    stop_uhrr
    stop_rigctld
    print_success "UHRR system stopped"
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
    start-uhrr)
        start_uhrr
        ;;
    stop-uhrr)
        stop_uhrr
        ;;
    start-atu)
        start_atu_server
        ;;
    stop-atu)
        stop_atu_server
        ;;
    *)
        echo "UHRR System Control Script"
        echo "Usage: $0 {start|stop|restart|status|logs [lines] [service]|start-rigctld|stop-rigctld|start-uhrr|stop-uhrr|start-atu|stop-atu}"
        echo ""
        echo "Commands:"
        echo "  start          - Start rigctld and UHRR services"
        echo "  stop           - Stop rigctld and UHRR services"
        echo "  restart        - Restart the entire system"
        echo "  status         - Show current status of services"
        echo "  logs [n] [service] - Show last n lines of logs (default 20)"
        echo "                   service can be 'rigctld', 'uhrr' or 'atu'"
        echo "  start-rigctld  - Start only rigctld service"
        echo "  stop-rigctld   - Stop only rigctld service"
        echo "  start-uhrr     - Start only UHRR service"
        echo "  stop-uhrr      - Stop only UHRR service"
        
        echo ""
        echo "Examples:"
        echo "  $0 start"
        echo "  $0 logs 50 rigctld"
        echo "  $0 status"
        echo "  $0 start-atu"
        exit 1
        ;;
esac

exit 0
