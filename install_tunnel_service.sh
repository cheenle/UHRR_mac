#!/bin/bash
# MRRC SSH 隧道服务安装脚本
# 将 SSH 隧道设置为系统服务，开机自动启动

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLIST_NAME="com.user.mrrc.tunnel.plist"
PLIST_SOURCE="$SCRIPT_DIR/$PLIST_NAME"
PLIST_DEST="$HOME/Library/LaunchAgents/$PLIST_NAME"

echo "=== MRRC SSH 隧道服务安装 ==="
echo ""

# 检查源文件是否存在
if [ ! -f "$PLIST_SOURCE" ]; then
    echo "错误: 未找到 $PLIST_SOURCE"
    exit 1
fi

# 创建 LaunchAgents 目录（如果不存在）
mkdir -p "$HOME/Library/LaunchAgents"

# 停止现有服务（如果存在）
if launchctl list | grep -q "com.user.mrrc.tunnel"; then
    echo "停止现有服务..."
    launchctl unload "$PLIST_DEST" 2>/dev/null
fi

# 复制 plist 文件
cp "$PLIST_SOURCE" "$PLIST_DEST"
echo "✓ 服务配置已复制到: $PLIST_DEST"

# 加载服务
launchctl load "$PLIST_DEST"
if [ $? -eq 0 ]; then
    echo "✓ 服务已加载"
else
    echo "✗ 服务加载失败"
    exit 1
fi

# 启动服务
launchctl start "com.user.mrrc.tunnel"
sleep 2

# 检查服务状态
if launchctl list | grep -q "com.user.mrrc.tunnel"; then
    PID=$(launchctl list | grep "com.user.mrrc.tunnel" | awk '{print $1}')
    echo "✓ 服务运行中 (PID: $PID)"
else
    echo "⚠ 服务可能未正常启动，请检查日志"
fi

echo ""
echo "=== 安装完成 ==="
echo ""
echo "管理命令:"
echo "  查看状态: launchctl list | grep mrrc.tunnel"
echo "  停止服务: launchctl stop com.user.mrrc.tunnel"
echo "  启动服务: launchctl start com.user.mrrc.tunnel"
echo "  重启服务: launchctl kickstart -k com.user.mrrc.tunnel"
echo "  查看日志: tail -f $SCRIPT_DIR/tunnel_service.log"
echo "  卸载服务: launchctl unload $PLIST_DEST"
echo ""
echo "日志文件:"
echo "  输出日志: $SCRIPT_DIR/tunnel_service.log"
echo "  错误日志: $SCRIPT_DIR/tunnel_service_error.log"
