#!/bin/bash
# iFlow CLI 自动记录功能安装脚本

set -e

PROJECT_DIR="/Users/cheenle/UHRR/MRRC"
LOG_DIR="$PROJECT_DIR/.iflow_logs"
SHELL_RC=""

echo "╔════════════════════════════════════════════════╗"
echo "║     iFlow CLI 自动记录功能安装程序             ║"
echo "╚════════════════════════════════════════════════╝"
echo ""

# 检测 shell
if [ -n "$ZSH_VERSION" ]; then
    SHELL_RC="$HOME/.zshrc"
elif [ -n "$BASH_VERSION" ]; then
    SHELL_RC="$HOME/.bashrc"
else
    echo "⚠️  未检测到支持的 shell（需要 bash 或 zsh）"
    exit 1
fi

echo "检测到 shell: $SHELL_RC"
echo ""

# 检查是否已安装
if grep -q "iflow_auto_log.sh" "$SHELL_RC" 2>/dev/null; then
    echo "✅ 自动记录功能已经安装"
    echo ""
    echo "使用方式:"
    echo "  1. 重新加载 shell 配置: source $SHELL_RC"
    echo "  2. 运行: iflow"
    exit 0
fi

# 添加到 shell 配置
echo "正在安装..."
echo ""

# 添加注释和 source 命令
cat >> "$SHELL_RC" << EOF

# iFlow CLI 自动记录功能
# 添加于 $(date)
source "$LOG_DIR/iflow_auto_log.sh"
EOF

echo "✅ 安装完成！"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "请运行以下命令使配置生效:"
echo "  source $SHELL_RC"
echo ""
echo "然后就可以使用:"
echo "  iflow         - 启动带自动记录的 iFlow CLI"
echo "  iflow-logs    - 查看最近的会话列表"
echo "  iflow-today   - 查看今日的会话"
echo ""
echo "日志将保存在: $LOG_DIR"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
