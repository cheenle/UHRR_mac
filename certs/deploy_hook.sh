#!/bin/bash
# acme.sh 证书部署钩子
# 证书更新后自动重启 MRRC

set -e

MRRC_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG_FILE="$MRRC_DIR/certs/deploy.log"

echo "[$(date)] 证书已更新，正在部署到 MRRC..." >> "$LOG_FILE"

# 停止 MRRC
"$MRRC_DIR/mrrc_control.sh" stop >> "$LOG_FILE" 2>&1 || true

# 等待进程停止
sleep 2

# 启动 MRRC
"$MRRC_DIR/mrrc_control.sh" start >> "$LOG_FILE" 2>&1

if [ $? -eq 0 ]; then
    echo "[$(date)] ✓ MRRC 重启成功" >> "$LOG_FILE"
else
    echo "[$(date)] ✗ MRRC 重启失败" >> "$LOG_FILE"
    exit 1
fi

echo "[$(date)] 部署完成" >> "$LOG_FILE"
