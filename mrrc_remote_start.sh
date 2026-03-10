#!/bin/bash

# MRRC Remote Start Script with Audio Permissions
# 解决 macOS 通过 SSH 远程启动时没有音频设备权限的问题
#
# 方案说明：
# macOS 中，只有通过 GUI 登录的进程才有访问音频设备的权限。
# 通过 SSH 启动的进程属于不同的安全上下文，无法访问麦克风/扬声器。
#
# 使用方法：
# 1. 在本地登录 Mac（有图形界面）
# 2. 在本地终端运行此脚本启动 MRRC
# 3. 然后可以通过 SSH 远程管理，MRRC 会保持音频权限
#
# 或者：
# 1. 通过 SSH 连接到 Mac
# 2. 运行此脚本（它会尝试使用 launchd 在用户会话中启动）
# 3. 如果 launchd 方法失败，会回退到 screen 方法

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
MRRC_LOG="$SCRIPT_DIR/mrrc.log"

echo "========================================"
echo "MRRC 远程启动脚本（带音频权限）"
echo "========================================"

# 检查 MRRC 是否已在运行
if pgrep -f "MRRC" > /dev/null 2>&1; then
    echo "⚠️  MRRC 已在运行"
    echo "PID: $(pgrep -f 'MRRC')"
    echo ""
    echo "如需重启，请先停止："
    echo "  ./mrrc_control.sh stop-mrrc"
    exit 1
fi

# 方法1：使用 launchd 启动（推荐，有完整 GUI 权限）
echo "📡 尝试使用 launchd 在用户会话中启动..."

PLIST_PATH="$HOME/Library/LaunchAgents/com.user.mrrc.remote.plist"

# 创建专门的远程启动 plist
mkdir -p "$HOME/Library/LaunchAgents"
cat > "$PLIST_PATH" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.user.mrrc.remote</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>$SCRIPT_DIR/MRRC</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$SCRIPT_DIR</string>
    <key>StandardOutPath</key>
    <string>$SCRIPT_DIR/mrrc_service.log</string>
    <key>StandardErrorPath</key>
    <string>$SCRIPT_DIR/mrrc_service_error.log</string>
    <key>ProcessType</key>
    <string>Interactive</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    </dict>
</dict>
</plist>
EOF

# 先卸载旧的（如果存在）
launchctl unload "$PLIST_PATH" 2>/dev/null
sleep 1

# 加载并启动
if launchctl load -w "$PLIST_PATH" 2>/dev/null; then
    sleep 2
    if pgrep -f "MRRC" > /dev/null 2>&1; then
        PID=$(pgrep -f "MRRC")
        echo "✅ MRRC 启动成功！"
        echo "   PID: $PID"
        echo "   访问: https://$(hostname):8877"
        echo "   日志: $SCRIPT_DIR/mrrc_service.log"
        echo ""
        echo "🎵 音频设备权限已获取（通过 launchd）"
        exit 0
    fi
fi

# 方法2：使用 screen 启动（备选）
echo "⚠️  launchd 方法失败，尝试使用 screen..."

if ! command -v screen >/dev/null 2>&1; then
    echo "❌ 未安装 screen，尝试安装..."
    if command -v brew >/dev/null 2>&1; then
        brew install screen
    else
        echo "❌ 请先安装 Homebrew，然后运行: brew install screen"
        exit 1
    fi
fi

# 在 screen 中启动
screen -dmS mrrc bash -c "cd '$SCRIPT_DIR' && python3 MRRC 2>&1 | tee -a '$MRRC_LOG'"
sleep 3

if pgrep -f "MRRC" > /dev/null 2>&1; then
    PID=$(pgrep -f "MRRC")
    echo "✅ MRRC 启动成功！"
    echo "   PID: $PID"
    echo "   访问: https://$(hostname):8877"
    echo "   日志: tail -f $MRRC_LOG"
    echo ""
    echo "💡 使用以下命令附加到会话："
    echo "   screen -r mrrc"
    echo ""
    echo "💡 在 screen 会话中按 Ctrl+A 然后 D 可分离"
    echo ""
    echo "⚠️ 注意：screen 方法可能没有音频权限"
    echo "   建议：在本地 Mac 终端运行此脚本"
else
    echo "❌ 启动失败"
    echo "请检查日志: $MRRC_LOG"
    exit 1
fi
