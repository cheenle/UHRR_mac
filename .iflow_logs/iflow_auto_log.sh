#!/bin/bash
# iFlow CLI 自动记录函数
# 使用方法: source ~/.iflow_logs/iflow_auto_log.sh
# 然后运行: iflow

iflow() {
    local PROJECT_DIR="$(pwd)"
    local LOG_DIR="$PROJECT_DIR/.iflow_logs"
    local DATE=$(date +%Y-%m-%d)
    local TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    local LOG_FILE="$LOG_DIR/${DATE}_${TIMESTAMP}_iflow.log"
    
    mkdir -p "$LOG_DIR"
    
    echo "╔═══════════════════════════════════════╗"
    echo "║     iFlow CLI 自动记录模式已启动       ║"
    echo "╚═══════════════════════════════════════╝"
    echo ""
    echo "📁 日志文件: $LOG_FILE"
    echo "🕐 开始时间: $(date '+%Y-%m-%d %H:%M:%S')"
    echo ""
    
    # 创建会话信息头
    {
        echo "========================================"
        echo "iFlow CLI 对话记录"
        echo "========================================"
        echo "日期: $(date)"
        echo "项目: $PROJECT_DIR"
        echo "用户: $(whoami)"
        echo "主机: $(hostname)"
        echo "========================================"
        echo ""
    } > "$LOG_FILE"
    
    # 记录索引
    echo "[$TIMESTAMP] $LOG_FILE - $(date '+%H:%M:%S')" >> "$LOG_DIR/.session_index"
    
    # 使用 script 启动记录会话，并运行真正的 iFlow CLI
    cd "$PROJECT_DIR"
    
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS: 启动 script 记录，然后运行 iFlow CLI
        script -q "$LOG_FILE" /opt/homebrew/bin/iflow
    else
        # Linux
        script -q -f "$LOG_FILE" /opt/homebrew/bin/iflow
    fi
    
    echo ""
    echo "✅ 会话已结束，日志保存于:"
    echo "   $LOG_FILE"
}

# 别名
alias iflow-log=iflow

# 查看最近的日志
iflow-logs() {
    local LOG_DIR="$(pwd)/.iflow_logs"
    
    echo "最近10次 iFlow CLI 会话记录:"
    echo "========================================"
    
    if [ -f "$LOG_DIR/.session_index" ]; then
        tail -10 "$LOG_DIR/.session_index" | nl
    else
        echo "暂无记录"
    fi
}

# 查看今日日志
iflow-today() {
    local LOG_DIR="$(pwd)/.iflow_logs"
    local TODAY=$(date +%Y-%m-%d)
    
    echo "今日 ($TODAY) 的 iFlow CLI 会话:"
    echo "========================================"
    
    ls -1t "$LOG_DIR/${TODAY}"*.log 2>/dev/null | while read f; do
        echo "  📄 $(basename $f)"
        echo "     大小: $(ls -lh $f | awk '{print $5}')"
        echo "     行数: $(wc -l < $f)"
        echo ""
    done
}

echo "iFlow CLI 自动记录功能已加载"
echo ""
echo "可用命令:"
echo "  iflow        - 启动带自动记录的 iFlow CLI 会话"
echo "  iflow-log    - iflow 的别名"
echo "  iflow-logs   - 查看最近的会话记录列表"
echo "  iflow-today  - 查看今日的所有会话"
echo ""
echo "提示: 将此文件添加到 ~/.zshrc 或 ~/.bashrc 中以永久启用:"
echo "  echo 'source /Users/cheenle/UHRR/MRRC/.iflow_logs/iflow_auto_log.sh' >> ~/.zshrc"
