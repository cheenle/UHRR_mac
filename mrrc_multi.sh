#!/bin/bash

# MRRC Multi-Instance Control Script
# 支持在一台电脑上运行多个MRRC实例，每个实例连接不同的设备/声卡
ulimit -n 10240

# 获取脚本所在目录
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)

# 默认实例配置
DEFAULT_INSTANCE="default"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m'

# 打印状态消息
print_status() {
    echo -e "${BLUE}[${INSTANCE:-default}]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[${INSTANCE:-default}]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[${INSTANCE:-default}]${NC} $1"
}

print_error() {
    echo -e "${RED}[${INSTANCE:-default}]${NC} $1"
}

print_info() {
    echo -e "${CYAN}[${INSTANCE:-default}]${NC} $1"
}

# 检查进程是否运行
is_running() {
    pgrep -f "$1" > /dev/null 2>&1
}

# 获取进程PID
get_pid() {
    pgrep -f "$1" 2>/dev/null
}

# 杀掉进程
kill_process() {
    local process_pattern="$1"
    local pid=$(get_pid "$process_pattern")
    
    if [ -n "$pid" ]; then
        print_status "Stopping $process_pattern (PID: $pid)..."
        kill "$pid" 2>/dev/null
        sleep 2
        
        if is_running "$process_pattern"; then
            print_warning "Force killing..."
            kill -9 "$pid" 2>/dev/null
            sleep 1
        fi
        
        if ! is_running "$process_pattern"; then
            print_success "Stopped"
        else
            print_error "Failed to stop"
        fi
    else
        print_status "Not running"
    fi
}

# 加载实例配置
load_instance_config() {
    local instance_name="$1"
    local config_file="$SCRIPT_DIR/MRRC.$instance_name.conf"
    
    if [ ! -f "$config_file" ]; then
        print_error "Config file not found: $config_file"
        return 1
    fi
    
    # 使用 Python 解析配置文件获取实例参数
    local python_script=$(cat << 'PYEOF'
import sys
import configparser

config = configparser.ConfigParser()
config.read(sys.argv[1])

# 获取实例配置值
instance = sys.argv[2]

# 尝试从配置文件中读取 INSTANCE_* 变量，如果没有则使用默认值
try:
    # 从配置文件中获取 INSTANCE 相关的值
    section = 'INSTANCE_' + instance.upper()
    
    # 检查是否有专门的实例配置节
    if config.has_section('INSTANCE_SETTINGS'):
        print(config.get('INSTANCE_SETTINGS', 'INSTANCE_PORT', fallback=''))
        print(config.get('INSTANCE_SETTINGS', 'INSTANCE_RIGCTL_DEVICE', fallback=''))
        print(config.get('INSTANCE_SETTINGS', 'INSTANCE_RIGCTL_MODEL', fallback=''))
        print(config.get('INSTANCE_SETTINGS', 'INSTANCE_RIGCTL_SPEED', fallback=''))
        print(config.get('INSTANCE_SETTINGS', 'INSTANCE_RIGCTL_STOP_BITS', fallback=''))
        print(config.get('INSTANCE_SETTINGS', 'INSTANCE_RIGCTL_HOST', fallback=''))
        print(config.get('INSTANCE_SETTINGS', 'INSTANCE_RIGCTL_PORT', fallback=''))
        print(config.get('INSTANCE_SETTINGS', 'INSTANCE_AUDIO_INPUT', fallback=''))
        print(config.get('INSTANCE_SETTINGS', 'INSTANCE_AUDIO_OUTPUT', fallback=''))
        print(config.get('INSTANCE_SETTINGS', 'INSTANCE_ATR1000_DEVICE', fallback=''))
        print(config.get('INSTANCE_SETTINGS', 'INSTANCE_ATR1000_PORT', fallback=''))
        print(config.get('INSTANCE_SETTINGS', 'INSTANCE_LOG_DIR', fallback=''))
        print(config.get('INSTANCE_SETTINGS', 'INSTANCE_UNIX_SOCKET', fallback=''))
    else:
        # 使用默认值
        print('')  # PORT
        print('')  # RIGCTL_DEVICE
        print('30003')  # RIGCTL_MODEL
        print('4800')  # RIGCTL_SPEED
        print('2')  # RIGCTL_STOP_BITS
        print('127.0.0.1')  # RIGCTL_HOST
        print('')  # RIGCTL_PORT
        print('')  # AUDIO_INPUT
        print('')  # AUDIO_OUTPUT
        print('')  # ATR1000_DEVICE
        print('')  # ATR1000_PORT
        print('')  # LOG_DIR
        print('')  # UNIX_SOCKET
except Exception as e:
    print(f"Error: {e}", file=sys.stderr)
    sys.exit(1)
PYEOF
)
    
    # 调用 Python 解析配置
    local config_values=($(python3 -c "$python_script" "$config_file" "$instance_name"))
    
    # 设置实例变量
    INSTANCE="$instance_name"
    
    # 从配置文件中读取标准配置
    INSTANCE_PORT=$(python3 -c "import configparser; c=configparser.ConfigParser(); c.read('$config_file'); print(c.get('SERVER', 'port', fallback='8877'))" 2>/dev/null)
    INSTANCE_AUDIO_INPUT=$(python3 -c "import configparser; c=configparser.ConfigParser(); c.read('$config_file'); print(c.get('AUDIO', 'inputdevice', fallback=''))" 2>/dev/null)
    INSTANCE_AUDIO_OUTPUT=$(python3 -c "import configparser; c=configparser.ConfigParser(); c.read('$config_file'); print(c.get('AUDIO', 'outputdevice', fallback=''))" 2>/dev/null)
    INSTANCE_RIGCTL_DEVICE=$(python3 -c "import configparser; c=configparser.ConfigParser(); c.read('$config_file'); print(c.get('HAMLIB', 'rig_pathname', fallback=''))" 2>/dev/null)
    
    # 从 INSTANCE_SETTINGS 节读取额外的实例配置
    INSTANCE_RIGCTL_MODEL=$(python3 -c "import configparser; c=configparser.ConfigParser(); c.read('$config_file'); print(c.get('INSTANCE_SETTINGS', 'INSTANCE_RIGCTL_MODEL', fallback='30003'))" 2>/dev/null)
    INSTANCE_RIGCTL_SPEED=$(python3 -c "import configparser; c=configparser.ConfigParser(); c.read('$config_file'); print(c.get('INSTANCE_SETTINGS', 'INSTANCE_RIGCTL_SPEED', fallback='4800'))" 2>/dev/null)
    INSTANCE_RIGCTL_STOP_BITS=$(python3 -c "import configparser; c=configparser.ConfigParser(); c.read('$config_file'); print(c.get('INSTANCE_SETTINGS', 'INSTANCE_RIGCTL_STOP_BITS', fallback='2'))" 2>/dev/null)
    INSTANCE_RIGCTL_HOST=$(python3 -c "import configparser; c=configparser.ConfigParser(); c.read('$config_file'); print(c.get('INSTANCE_SETTINGS', 'INSTANCE_RIGCTL_HOST', fallback='127.0.0.1'))" 2>/dev/null)
    INSTANCE_RIGCTL_PORT=$(python3 -c "import configparser; c=configparser.ConfigParser(); c.read('$config_file'); print(c.get('INSTANCE_SETTINGS', 'INSTANCE_RIGCTL_PORT', fallback=''))" 2>/dev/null)
    INSTANCE_ATR1000_DEVICE=$(python3 -c "import configparser; c=configparser.ConfigParser(); c.read('$config_file'); print(c.get('INSTANCE_SETTINGS', 'INSTANCE_ATR1000_DEVICE', fallback=''))" 2>/dev/null)
    INSTANCE_ATR1000_PORT=$(python3 -c "import configparser; c=configparser.ConfigParser(); c.read('$config_file'); print(c.get('INSTANCE_SETTINGS', 'INSTANCE_ATR1000_PORT', fallback='60001'))" 2>/dev/null)
    INSTANCE_LOG_DIR=$(python3 -c "import configparser; c=configparser.ConfigParser(); c.read('$config_file'); print(c.get('INSTANCE_SETTINGS', 'INSTANCE_LOG_DIR', fallback='$SCRIPT_DIR'))" 2>/dev/null)
    INSTANCE_UNIX_SOCKET=$(python3 -c "import configparser; c=configparser.ConfigParser(); c.read('$config_file'); print(c.get('INSTANCE_SETTINGS', 'INSTANCE_UNIX_SOCKET', fallback='/tmp/mrrc_${instance_name}.sock'))" 2>/dev/null)
    
    # 设置默认值
    : ${INSTANCE_PORT:=8877}
    : ${INSTANCE_RIGCTL_MODEL:=30003}
    : ${INSTANCE_RIGCTL_SPEED:=4800}
    : ${INSTANCE_RIGCTL_STOP_BITS:=2}
    : ${INSTANCE_RIGCTL_HOST:=127.0.0.1}
    : ${INSTANCE_ATR1000_PORT:=60001}
    : ${INSTANCE_LOG_DIR:=$SCRIPT_DIR}
    : ${INSTANCE_UNIX_SOCKET:="/tmp/mrrc_${instance_name}.sock"}
    
    # 设置日志文件路径
    RIGCTLD_LOG="${INSTANCE_LOG_DIR}/rigctld_${instance_name}.log"
    MRRC_LOG="${INSTANCE_LOG_DIR}/mrrc_${instance_name}.log"
    ATR1000_LOG="${INSTANCE_LOG_DIR}/atr1000_${instance_name}.log"
    PID_DIR="${INSTANCE_LOG_DIR}"
    
    print_info "Loaded config: $config_file"
    print_info "Port: $INSTANCE_PORT"
    print_info "Rig: $INSTANCE_RIGCTL_DEVICE"
    print_info "Audio In: $INSTANCE_AUDIO_INPUT"
    print_info "Audio Out: $INSTANCE_AUDIO_OUTPUT"
    
    return 0
}

# 启动 rigctld
start_rigctld() {
    # 检查是否需要启动 rigctld（如果未配置设备则跳过）
    if [ -z "$INSTANCE_RIGCTL_DEVICE" ]; then
        print_info "No rigctl device configured, skipping rigctld..."
        return 0
    fi
    
    # 使用端口号作为 rigctld 标识（更可靠）
    : ${INSTANCE_RIGCTL_PORT:=4532}
    local rigctld_pattern="rigctld.*-t.*${INSTANCE_RIGCTL_PORT}"
    
    if is_running "$rigctld_pattern"; then
        print_warning "rigctld already running on port $INSTANCE_RIGCTL_PORT"
        return 1
    fi
    
    # 如果没有指定 rigctl 端口，使用默认值
    : ${INSTANCE_RIGCTL_PORT:=4532}
    
    print_status "Starting rigctld..."
    print_status "  Device: $INSTANCE_RIGCTL_DEVICE"
    print_status "  Model: $INSTANCE_RIGCTL_MODEL"
    print_status "  Speed: $INSTANCE_RIGCTL_SPEED"
    print_status "  Port: $INSTANCE_RIGCTL_PORT"
    
    # 清空日志
    > "$RIGCTLD_LOG"
    
    # 启动 rigctld，使用实例名称作为标识
    rigctld -m "$INSTANCE_RIGCTL_MODEL" \
            -r "$INSTANCE_RIGCTL_DEVICE" \
            -s "$INSTANCE_RIGCTL_SPEED" \
            -C stop_bits="$INSTANCE_RIGCTL_STOP_BITS" \
            -T "$INSTANCE_RIGCTL_HOST" \
            -t "$INSTANCE_RIGCTL_PORT" \
            -vvv > "$RIGCTLD_LOG" 2>&1 &
    
    local pid=$!
    sleep 3
    
    if is_running "$rigctld_pattern"; then
        print_success "rigctld started (PID: $pid)"
        echo "$pid" > "$PID_DIR/rigctld_${INSTANCE}.pid"
        return 0
    else
        print_error "Failed to start rigctld"
        tail -20 "$RIGCTLD_LOG"
        return 1
    fi
}

# 停止 rigctld
stop_rigctld() {
    : ${INSTANCE_RIGCTL_PORT:=4532}
    local rigctld_pattern="rigctld.*-t.*${INSTANCE_RIGCTL_PORT}"
    kill_process "$rigctld_pattern"
    rm -f "$PID_DIR/rigctld_${INSTANCE}.pid"
}

# 启动 MRRC
start_mrrc() {
    if is_running "MRRC.*$INSTANCE"; then
        print_warning "MRRC already running"
        return 1
    fi
    
    print_status "Starting MRRC server..."
    
    # 清空日志
    > "$MRRC_LOG"
    
    # 启动 MRRC，传递配置文件路径
    python3 "$SCRIPT_DIR/MRRC" "$SCRIPT_DIR/MRRC.$INSTANCE.conf" > "$MRRC_LOG" 2>&1 &
    
    local pid=$!
    sleep 3
    
    if is_running "MRRC.*$INSTANCE"; then
        print_success "MRRC started (PID: $pid)"
        echo "$pid" > "$PID_DIR/mrrc_${INSTANCE}.pid"
        print_success "Access at: https://localhost:$INSTANCE_PORT"
        return 0
    else
        print_error "Failed to start MRRC"
        tail -20 "$MRRC_LOG"
        return 1
    fi
}

# 停止 MRRC
stop_mrrc() {
    kill_process "MRRC.*$INSTANCE"
    rm -f "$PID_DIR/mrrc_${INSTANCE}.pid"
}

# 启动 ATR-1000 代理
start_atr1000() {
    if [ -z "$INSTANCE_ATR1000_DEVICE" ]; then
        print_info "ATR-1000 not configured, skipping..."
        return 0
    fi
    
    if is_running "atr1000_proxy.*$INSTANCE"; then
        print_warning "ATR-1000 proxy already running"
        return 1
    fi
    
    print_status "Starting ATR-1000 proxy..."
    
    > "$ATR1000_LOG"
    
    python3 "$SCRIPT_DIR/atr1000_proxy.py" \
        --device "$INSTANCE_ATR1000_DEVICE" \
        --port "$INSTANCE_ATR1000_PORT" \
        --unix-socket "$INSTANCE_UNIX_SOCKET" \
        > "$ATR1000_LOG" 2>&1 &
    
    local pid=$!
    sleep 2
    
    if is_running "atr1000_proxy"; then
        print_success "ATR-1000 proxy started (PID: $pid)"
        echo "$pid" > "$PID_DIR/atr1000_${INSTANCE}.pid"
        return 0
    else
        print_error "Failed to start ATR-1000 proxy"
        return 1
    fi
}

# 停止 ATR-1000 代理
stop_atr1000() {
    kill_process "atr1000_proxy"
    rm -f "$PID_DIR/atr1000_${INSTANCE}.pid"
    rm -f "$INSTANCE_UNIX_SOCKET"
}

# 显示实例状态
show_status() {
    echo ""
    echo -e "${MAGENTA}========== Instance: $INSTANCE ==========${NC}"
    echo ""
    
    if is_running "rigctld"; then
        local pid=$(get_pid "rigctld")
        print_success "rigctld: running (PID: $pid)"
    else
        print_error "rigctld: not running"
    fi
    
    if is_running "MRRC.*$INSTANCE"; then
        local pid=$(get_pid "MRRC.*$INSTANCE")
        print_success "MRRC: running (PID: $pid)"
        print_success "  URL: https://localhost:$INSTANCE_PORT"
    else
        print_error "MRRC: not running"
    fi
    
    if is_running "atr1000_proxy"; then
        local pid=$(get_pid "atr1000_proxy")
        print_success "ATR-1000: running (PID: $pid)"
    else
        print_warning "ATR-1000: not running"
    fi
    
    echo ""
    echo "Log files:"
    echo "  rigctld: $RIGCTLD_LOG"
    echo "  MRRC:    $MRRC_LOG"
    echo "  ATR-1000: $ATR1000_LOG"
    echo ""
}

# 显示所有实例状态
show_all_status() {
    echo ""
    echo -e "${MAGENTA}======================================${NC}"
    echo -e "${MAGENTA}     MRRC Multi-Instance Status       ${NC}"
    echo -e "${MAGENTA}======================================${NC}"
    echo ""
    
    # 查找所有实例配置文件
    local instances=$(ls -1 "$SCRIPT_DIR"/MRRC.*.conf 2>/dev/null | sed 's/.*MRRC\.\(.*\)\.conf/\1/' | grep -v "bak\|orig\|9000")
    
    if [ -z "$instances" ]; then
        print_warning "No instance config files found (MRRC.*.conf)"
        echo ""
        echo "Create config file: MRRC.<instance_name>.conf"
        return
    fi
    
    for inst in $instances; do
        if load_instance_config "$inst" 2>/dev/null; then
            show_status
        fi
    done
}

# 启动所有服务
start_instance() {
    local instance_name="$1"
    
    if [ -z "$instance_name" ]; then
        print_error "Instance name required"
        echo "Usage: $0 start <instance_name>"
        exit 1
    fi
    
    if ! load_instance_config "$instance_name"; then
        exit 1
    fi
    
    print_status "Starting instance: $instance_name"
    
    start_rigctld
    sleep 2
    start_mrrc
    sleep 1
    start_atr1000
    
    if is_running "MRRC.*$INSTANCE"; then
        print_success "Instance '$instance_name' started successfully!"
        show_status
    else
        print_error "Failed to start instance '$instance_name'"
    fi
}

# 停止实例
stop_instance() {
    local instance_name="$1"
    
    if [ -z "$instance_name" ]; then
        print_error "Instance name required"
        echo "Usage: $0 stop <instance_name>"
        exit 1
    fi
    
    if ! load_instance_config "$instance_name"; then
        exit 1
    fi
    
    print_status "Stopping instance: $instance_name"
    stop_atr1000
    stop_mrrc
    stop_rigctld
    
    print_success "Instance '$instance_name' stopped"
}

# 重启实例
restart_instance() {
    local instance_name="$1"
    
    if [ -z "$instance_name" ]; then
        print_error "Instance name required"
        echo "Usage: $0 restart <instance_name>"
        exit 1
    fi
    
    print_status "Restarting instance: $instance_name"
    stop_instance "$instance_name"
    sleep 2
    start_instance "$instance_name"
}

# 创建新实例配置文件
create_instance() {
    local instance_name="$1"
    
    if [ -z "$instance_name" ]; then
        print_error "Instance name required"
        echo "Usage: $0 create <instance_name>"
        exit 1
    fi
    
    local config_file="$SCRIPT_DIR/MRRC.$instance_name.conf"
    
    if [ -f "$config_file" ]; then
        print_error "Config file already exists: $config_file"
        exit 1
    fi
    
    # 计算端口号 - 从实例名称提取数字或使用递增数字
    local instance_num=$(echo "$instance_name" | sed 's/[^0-9]//g')
    if [ -z "$instance_num" ]; then
        # 如果没有数字，使用时间戳末位
        instance_num=$(date +%s | tail -c 2)
    fi
    # 取最后1位作为实例编号，最多支持9个实例
    local instance_digit="${instance_num: -1}"
    local mrrc_port="889$instance_digit"  # 例如 radio1 -> 8891, radio2 -> 8892
    local rigctl_port="453$instance_digit"   # 例如 radio1 -> 4531, radio2 -> 4532
    
    # 复制默认配置并修改端口
    cp "$SCRIPT_DIR/MRRC.conf" "$config_file"
    
    # 使用 Python 修改端口
    python3 -c "
import configparser
config = configparser.ConfigParser()
config.read('$config_file')

# 修改 SERVER 节
if 'SERVER' in config:
    config['SERVER']['port'] = '$mrrc_port'

# 添加 INSTANCE_SETTINGS 节
config['INSTANCE_SETTINGS'] = {
    'INSTANCE_NAME': '$instance_name',
    'INSTANCE_PORT': '$mrrc_port',
    'INSTANCE_RIGCTL_DEVICE': '/dev/cu.usbserial-NEW',
    'INSTANCE_RIGCTL_MODEL': '30003',
    'INSTANCE_RIGCTL_SPEED': '4800',
    'INSTANCE_RIGCTL_STOP_BITS': '2',
    'INSTANCE_RIGCTL_HOST': '127.0.0.1',
    'INSTANCE_RIGCTL_PORT': '$rigctl_port',
    'INSTANCE_AUDIO_INPUT': 'USB Audio CODEC',
    'INSTANCE_AUDIO_OUTPUT': 'USB Audio CODEC',
    'INSTANCE_ATR1000_DEVICE': '',
    'INSTANCE_ATR1000_PORT': '60001',
    'INSTANCE_LOG_DIR': '$SCRIPT_DIR',
    'INSTANCE_UNIX_SOCKET': '/tmp/mrrc_${instance_name}.sock'
}

with open('$config_file', 'w') as f:
    config.write(f)
"
    
    print_success "Created config: $config_file"
    print_info "  MRRC Port: $mrrc_port"
    print_info "  Rigctl Port: $rigctl_port"
    print_info ""
    print_info "Please edit the config file to set correct devices:"
    print_info "  - Audio input/output device names"
    print_info "  - Radio serial device path"
    print_info "  - ATR-1000 device IP (if using)"
}

# 删除实例配置
delete_instance() {
    local instance_name="$1"
    
    if [ -z "$instance_name" ]; then
        print_error "Instance name required"
        echo "Usage: $0 delete <instance_name>"
        exit 1
    fi
    
    local config_file="$SCRIPT_DIR/MRRC.$instance_name.conf"
    
    if [ ! -f "$config_file" ]; then
        print_error "Config file not found: $config_file"
        exit 1
    fi
    
    # 先停止实例
    if load_instance_config "$instance_name" 2>/dev/null; then
        if is_running "MRRC.*$INSTANCE"; then
            print_warning "Instance is running, stopping first..."
            stop_instance "$instance_name"
        fi
    fi
    
    # 删除配置文件
    rm -f "$config_file"
    rm -f "$SCRIPT_DIR/rigctld_${instance_name}.log"
    rm -f "$SCRIPT_DIR/mrrc_${instance_name}.log"
    rm -f "$SCRIPT_DIR/atr1000_${instance_name}.log"
    
    print_success "Deleted instance: $instance_name"
}

# 显示实例列表
list_instances() {
    echo ""
    echo -e "${MAGENTA}======= Available Instances =======${NC}"
    echo ""
    
    local instances=$(ls -1 "$SCRIPT_DIR"/MRRC.*.conf 2>/dev/null | sed 's/.*MRRC\.\(.*\)\.conf/\1/' | grep -v "bak\|orig\|9000\|default")
    
    if [ -z "$instances" ]; then
        print_warning "No instances found"
        echo ""
        echo "Create a new instance:"
        echo "  $0 create <instance_name>"
        return
    fi
    
    for inst in $instances; do
        if load_instance_config "$inst" 2>/dev/null; then
            if is_running "MRRC.*$INSTANCE"; then
                echo -e "  ${GREEN}●${NC} $inst (running) - Port $INSTANCE_PORT"
            else
                echo -e "  ${YELLOW}○${NC} $inst (stopped) - Port $INSTANCE_PORT"
            fi
        fi
    done
    
    echo ""
}

# 显示帮助
show_help() {
    echo "MRRC Multi-Instance Control Script"
    echo ""
    echo "Usage: $0 <command> [instance_name]"
    echo ""
    echo "Commands:"
    echo "  start <name>      Start a specific instance"
    echo "  stop <name>       Stop a specific instance"
    echo "  restart <name>    Restart a specific instance"
    echo "  status [name]     Show status of instance(s)"
    echo "  logs <name> [n]   Show logs (last n lines, default 20)"
    echo "  create <name>     Create new instance config"
    echo "  delete <name>     Delete an instance (stops first)"
    echo "  list              List all instances"
    echo ""
    echo "Examples:"
    echo "  $0 create radio1          # Create instance 'radio1'"
    echo "  $0 start radio1           # Start instance 'radio1'"
    echo "  $0 status radio1          # Show status of 'radio1'"
    echo "  $0 logs radio1 50         # Show last 50 lines of logs"
    echo "  $0 list                   # List all instances"
    echo "  $0 stop radio1            # Stop instance 'radio1'"
    echo ""
}

# 主逻辑
case "$1" in
    start)
        start_instance "$2"
        ;;
    stop)
        stop_instance "$2"
        ;;
    restart)
        restart_instance "$2"
        ;;
    status)
        if [ -n "$2" ]; then
            load_instance_config "$2"
            show_status
        else
            show_all_status
        fi
        ;;
    logs)
        if [ -n "$2" ]; then
            load_instance_config "$2"
            local lines=${3:-20}
            echo "=== rigctld logs ==="
            tail -n "$lines" "$RIGCTLD_LOG"
            echo ""
            echo "=== MRRC logs ==="
            tail -n "$lines" "$MRRC_LOG"
            echo ""
            echo "=== ATR-1000 logs ==="
            tail -n "$lines" "$ATR1000_LOG"
        else
            print_error "Instance name required"
            echo "Usage: $0 logs <instance_name> [lines]"
        fi
        ;;
    create)
        create_instance "$2"
        ;;
    delete)
        delete_instance "$2"
        ;;
    list)
        list_instances
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        show_help
        ;;
esac
