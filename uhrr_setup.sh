#!/bin/bash

# UHRR 服务安装和配置脚本
# 一键安装、配置和启动 UHRR 服务

UHRR_DIR="/Users/cheenle/UHRR/UHRR_mac"
SERVICE_NAME="com.user.uhrr"
LAUNCHD_DIR="$HOME/Library/LaunchAgents"

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

# 检查依赖
check_dependencies() {
    log_info "检查系统依赖..."
    
    # 检查 Python3
    if command -v python3 >/dev/null 2>&1; then
        PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
        log_success "Python3 已安装 ($PYTHON_VERSION)"
    else
        log_error "Python3 未安装，请先安装 Python3"
        return 1
    fi
    
    # 检查 pip3
    if command -v pip3 >/dev/null 2>&1; then
        log_success "pip3 已安装"
    else
        log_error "pip3 未安装，请先安装 pip3"
        return 1
    fi
    
    # 检查必要的命令
    REQUIRED_COMMANDS=("launchctl" "lsof" "netstat" "pgrep")
    for cmd in "${REQUIRED_COMMANDS[@]}"; do
        if command -v "$cmd" >/dev/null 2>&1; then
            log_success "$cmd 命令可用"
        else
            log_error "$cmd 命令不可用"
            return 1
        fi
    done
    
    return 0
}

# 检查 Python 包依赖
check_python_dependencies() {
    log_info "检查 Python 包依赖..."
    
    REQUIRED_PACKAGES=(
        "tornado"
        "numpy"
        "pyaudio"
        "pyrtlsdr"
        "opuslib"
        "pyserial"
    )
    
    MISSING_PACKAGES=()
    
    for package in "${REQUIRED_PACKAGES[@]}"; do
        if python3 -c "import $package" 2>/dev/null; then
            log_success "$package 已安装"
        else
            log_warning "$package 未安装"
            MISSING_PACKAGES+=("$package")
        fi
    done
    
    if [ ${#MISSING_PACKAGES[@]} -eq 0 ]; then
        log_success "所有 Python 包依赖已满足"
        return 0
    else
        log_warning "以下包未安装: ${MISSING_PACKAGES[*]}"
        return 1
    fi
}

# 安装 Python 包依赖
install_python_dependencies() {
    log_info "安装 Python 包依赖..."
    
    PACKAGES_TO_INSTALL=(
        "tornado"
        "numpy"
        "pyaudio"
        "pyrtlsdr"
        "opuslib"
        "pyserial"
    )
    
    for package in "${PACKAGES_TO_INSTALL[@]}"; do
        log_info "安装 $package..."
        if pip3 install "$package" > /dev/null 2>&1; then
            log_success "$package 安装成功"
        else
            log_error "$package 安装失败"
            return 1
        fi
    done
    
    log_success "所有 Python 包依赖安装完成"
    return 0
}

# 验证 UHRR 程序
verify_uhrr_program() {
    log_info "验证 UHRR 程序..."
    
    if [ ! -f "$UHRR_DIR/UHRR" ]; then
        log_error "UHRR 主程序不存在: $UHRR_DIR/UHRR"
        return 1
    fi
    
    if [ ! -x "$UHRR_DIR/UHRR" ]; then
        log_warning "UHRR 程序不可执行，设置执行权限..."
        chmod +x "$UHRR_DIR/UHRR"
    fi
    
    # 检查配置文件
    if [ ! -f "$UHRR_DIR/UHRR.conf" ]; then
        log_warning "UHRR 配置文件不存在，将使用默认配置"
    else
        log_success "UHRR 配置文件存在"
    fi
    
    # 检查 SSL 证书
    if [ ! -f "$UHRR_DIR/certs/fullchain.pem" ] || [ ! -f "$UHRR_DIR/certs/radio.vlsc.net.key" ]; then
        log_warning "SSL 证书文件不存在，HTTPS 可能无法正常工作"
    else
        log_success "SSL 证书文件存在"
    fi
    
    log_success "UHRR 程序验证通过"
    return 0
}

# 安装 launchd 服务
install_launchd_service() {
    log_info "安装 launchd 服务..."
    
    # 检查服务文件
    if [ ! -f "$UHRR_DIR/com.user.uhrr.plist" ]; then
        log_error "服务配置文件不存在: $UHRR_DIR/com.user.uhrr.plist"
        return 1
    fi
    
    # 创建 LaunchAgents 目录
    if [ ! -d "$LAUNCHD_DIR" ]; then
        log_info "创建 LaunchAgents 目录: $LAUNCHD_DIR"
        mkdir -p "$LAUNCHD_DIR"
    fi
    
    # 复制服务文件
    if cp "$UHRR_DIR/com.user.uhrr.plist" "$LAUNCHD_DIR/"; then
        log_success "服务配置文件已复制到: $LAUNCHD_DIR/$SERVICE_NAME.plist"
    else
        log_error "复制服务配置文件失败"
        return 1
    fi
    
    # 设置正确的权限
    chmod 644 "$LAUNCHD_DIR/$SERVICE_NAME.plist"
    
    log_success "launchd 服务安装完成"
    return 0
}

# 配置开机自启动
configure_autostart() {
    log_info "配置开机自启动..."
    
    if launchctl enable "gui/$(id -u)/$SERVICE_NAME" 2>/dev/null; then
        log_success "开机自启动已启用"
    else
        log_error "启用开机自启动失败"
        return 1
    fi
    
    return 0
}

# 启动服务
start_service() {
    log_info "启动 UHRR 服务..."
    
    if launchctl load "$LAUNCHD_DIR/$SERVICE_NAME.plist" 2>/dev/null; then
        log_success "服务启动命令已发送"
        
        # 等待服务启动
        log_info "等待服务启动..."
        sleep 5
        
        # 检查启动状态
        if pgrep -f "UHRR" > /dev/null; then
            log_success "UHRR 服务启动成功"
        else
            log_warning "UHRR 进程未检测到，请检查日志"
        fi
    else
        log_error "启动服务失败"
        return 1
    fi
    
    return 0
}

# 完整安装流程
full_install() {
    log_info "开始 UHRR 服务完整安装..."
    
    echo "=== 安装步骤 ==="
    echo "1. 检查系统依赖"
    echo "2. 检查 Python 包依赖"
    echo "3. 安装缺失的 Python 包"
    echo "4. 验证 UHRR 程序"
    echo "5. 安装 launchd 服务"
    echo "6. 配置开机自启动"
    echo "7. 启动服务"
    echo ""
    
    # 步骤 1: 检查系统依赖
    if ! check_dependencies; then
        log_error "系统依赖检查失败，安装中止"
        return 1
    fi
    
    # 步骤 2: 检查 Python 包依赖
    if ! check_python_dependencies; then
        log_warning "部分 Python 包未安装，将自动安装"
        
        # 步骤 3: 安装缺失的包
        if ! install_python_dependencies; then
            log_error "Python 包安装失败，安装中止"
            return 1
        fi
    fi
    
    # 步骤 4: 验证 UHRR 程序
    if ! verify_uhrr_program; then
        log_error "UHRR 程序验证失败，安装中止"
        return 1
    fi
    
    # 步骤 5: 安装 launchd 服务
    if ! install_launchd_service; then
        log_error "launchd 服务安装失败，安装中止"
        return 1
    fi
    
    # 步骤 6: 配置开机自启动
    if ! configure_autostart; then
        log_warning "开机自启动配置失败，但服务仍可手动启动"
    fi
    
    # 步骤 7: 启动服务
    if ! start_service; then
        log_error "服务启动失败"
        return 1
    fi
    
    log_success "UHRR 服务完整安装完成!"
    
    echo ""
    echo "=== 安装完成 ==="
    echo "✅ UHRR 服务已安装并启动"
    echo "✅ 开机自启动已启用"
    echo "✅ 服务日志: $UHRR_DIR/uhrr_service.log"
    echo ""
    echo "=== 后续操作 ==="
    echo "📊 检查状态: ./uhrr_control.sh status"
    echo "📋 查看日志: ./uhrr_control.sh logs"
    echo "🔄 重启服务: ./uhrr_control.sh restart"
    echo "🛑 停止服务: ./uhrr_control.sh stop"
    echo ""
    echo "🌐 访问地址: https://localhost:8899"
    
    return 0
}

# 卸载服务
uninstall_service() {
    log_info "开始卸载 UHRR 服务..."
    
    # 停止服务
    if launchctl unload "$LAUNCHD_DIR/$SERVICE_NAME.plist" 2>/dev/null; then
        log_success "服务已停止"
    else
        log_warning "停止服务失败（可能未运行）"
    fi
    
    # 强制杀死可能残留的进程
    pkill -f "UHRR" 2>/dev/null
    
    # 禁用开机自启动
    if launchctl disable "gui/$(id -u)/$SERVICE_NAME" 2>/dev/null; then
        log_success "开机自启动已禁用"
    fi
    
    # 删除服务文件
    if [ -f "$LAUNCHD_DIR/$SERVICE_NAME.plist" ]; then
        if rm "$LAUNCHD_DIR/$SERVICE_NAME.plist"; then
            log_success "服务配置文件已删除"
        else
            log_error "删除服务配置文件失败"
            return 1
        fi
    else
        log_warning "服务配置文件不存在"
    fi
    
    log_success "UHRR 服务卸载完成"
    
    echo ""
    echo "=== 卸载完成 ==="
    echo "✅ UHRR 服务已完全卸载"
    echo "✅ 开机自启动已禁用"
    echo "✅ 服务配置文件已删除"
    echo ""
    echo "注意: Python 包和程序文件仍然保留"
    
    return 0
}

# 快速安装（仅安装服务）
quick_install() {
    log_info "开始 UHRR 服务快速安装..."
    
    # 仅安装服务，不检查依赖
    if ! install_launchd_service; then
        log_error "服务安装失败"
        return 1
    fi
    
    if ! configure_autostart; then
        log_warning "开机自启动配置失败"
    fi
    
    log_success "UHRR 服务快速安装完成"
    
    echo ""
    echo "=== 快速安装完成 ==="
    echo "✅ launchd 服务已安装"
    echo "✅ 开机自启动已配置"
    echo ""
    echo "现在可以手动启动服务:"
    echo "  ./uhrr_control.sh start"
    
    return 0
}

# 显示系统信息
show_system_info() {
    echo "=== 系统信息 ==="
    echo "主机名: $(hostname)"
    echo "系统版本: $(sw_vers -productName) $(sw_vers -productVersion)"
    echo "Python 版本: $(python3 --version 2>&1)"
    echo "当前用户: $(whoami)"
    echo "UHRR 目录: $UHRR_DIR"
    echo ""
}

# 显示帮助信息
show_help() {
    echo "UHRR 服务安装和配置脚本"
    echo ""
    echo "用法: $0 [命令]"
    echo ""
    echo "命令:"
    echo "  install    - 完整安装（检查依赖并安装服务）"
    echo "  quick      - 快速安装（仅安装服务）"
    echo "  uninstall  - 卸载服务"
    echo "  info       - 显示系统信息"
    echo "  deps       - 检查依赖"
    echo "  help       - 显示此帮助信息"
    echo ""
    echo "示例:"
    echo "  $0 install    # 首次完整安装"
    echo "  $0 quick      # 快速安装（已安装依赖）"
    echo "  $0 uninstall  # 卸载服务"
    echo "  $0 info       # 显示系统信息"
    echo ""
    echo "安装完成后，使用 uhrr_control.sh 进行日常管理"
}

# 主程序
case "${1:-help}" in
    install)
        show_system_info
        full_install
        ;;
    quick)
        show_system_info
        quick_install
        ;;
    uninstall)
        uninstall_service
        ;;
    info)
        show_system_info
        ;;
    deps)
        check_dependencies
        check_python_dependencies
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