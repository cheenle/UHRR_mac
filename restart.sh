#!/bin/bash

# MRRC 单实例重启脚本
# 以 radio1 的配置为准，重启 rigctld + MRRC + ATR-1000 代理
# 用法: ./restart.sh

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)

# 单实例固定使用 radio1 配置
INSTANCE="radio1"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m'

echo -e "${MAGENTA}======================================${NC}"
echo -e "${MAGENTA}  MRRC 单实例重启 (${INSTANCE})        ${NC}"
echo -e "${MAGENTA}======================================${NC}"
echo ""

if [ ! -f "$SCRIPT_DIR/MRRC.$INSTANCE.conf" ]; then
    echo -e "${RED}错误: 配置文件不存在 MRRC.$INSTANCE.conf${NC}"
    exit 1
fi

echo -e "${BLUE}[$INSTANCE]${NC} 正在重启实例: $INSTANCE"
echo ""

# 先停止再启动，失败即中止
if ! "$SCRIPT_DIR/mrrc_multi.sh" stop "$INSTANCE"; then
    echo -e "${RED}[$INSTANCE]${NC} 停止实例失败"
    exit 1
fi

echo ""
sleep 2

if ! "$SCRIPT_DIR/mrrc_multi.sh" start "$INSTANCE"; then
    echo -e "${RED}[$INSTANCE]${NC} 启动实例失败"
    exit 1
fi

echo ""
"$SCRIPT_DIR/mrrc_multi.sh" status "$INSTANCE"

echo -e "${GREEN}======================================${NC}"
echo -e "${GREEN}  实例 ${INSTANCE} 重启完成              ${NC}"
echo -e "${GREEN}======================================${NC}"
