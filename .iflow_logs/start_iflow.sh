#!/bin/bash
# 自动记录 iFlow CLI 对话的启动脚本

# 配置 - 使用当前工作目录
PROJECT_DIR="$(pwd)"
LOG_DIR="$PROJECT_DIR/.iflow_logs"
DATE=$(date +%Y-%m-%d)
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="$LOG_DIR/${DATE}_${TIMESTAMP}_iflow_session.log"

# 创建日志目录（如果不存在）
mkdir -p "$LOG_DIR"

echo "========================================="
echo "  iFlow CLI 自动记录模式"
echo "========================================="
echo "日志文件: $LOG_FILE"
echo "开始时间: $(date)"
echo ""
echo "提示:"
echo "  - 所有输入输出都会自动记录"
echo "  - 正常结束后输入 'exit' 或按 Ctrl+D"
echo "  - 日志保存在 .iflow_logs/ 目录"
echo ""
echo "开始记录..."
echo ""

# 使用 script 命令记录会话
# -q: 安静模式，不显示启动/结束消息
# -r: 使用更精确的定时（用于 scriptreplay）
# 或者使用 -F 刷新模式
if command -v script >/dev/null 2>&1; then
    # macOS 的 script 命令格式
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS 版本
        script -q "$LOG_FILE" /bin/bash -c "
            cd '$PROJECT_DIR'
            echo '当前目录: \$(pwd)'
            echo '会话开始于: \$(date)'
            echo ''
            echo '现在你可以正常使用 iFlow CLI...'
            echo ''
            exec /bin/bash
        "
    else
        # Linux 版本
        script -q -f "$LOG_FILE" /bin/bash -c "
            cd '$PROJECT_DIR'
            echo '当前目录: \$(pwd)'
            echo '会话开始于: \$(date)'
            echo ''
            echo '现在你可以正常使用 iFlow CLI...'
            echo ''
            exec /bin/bash
        "
    fi
else
    echo "错误: 未找到 'script' 命令"
    exit 1
fi

echo ""
echo "========================================="
echo "  会话已结束"
echo "========================================="
echo "日志保存于: $LOG_FILE"
echo "结束时间: $(date)"
echo ""

# 创建一个索引文件
INDEX_FILE="$LOG_DIR/.session_index"
echo "[$TIMESTAMP] $LOG_FILE" >> "$INDEX_FILE"

# 显示最近的日志
echo "最近5次会话记录:"
tail -5 "$INDEX_FILE" | while read line; do
    echo "  $line"
done
