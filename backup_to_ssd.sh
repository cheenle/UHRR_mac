#!/bin/bash
#
# MRRC 备份脚本
# 将项目目录备份到 SSD 卷
#

# 配置
SOURCE_DIR="/Users/cheenle/UHRR/MRRC"
BACKUP_DIR="/Volumes/SSD/MRRC_backup"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_NAME="MRRC_backup_${TIMESTAMP}"
BACKUP_PATH="${BACKUP_DIR}/${BACKUP_NAME}"
LATEST_LINK="${BACKUP_DIR}/latest"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 检查SSD是否挂载
if [ ! -d "/Volumes/SSD" ]; then
    echo -e "${RED}错误: SSD 卷未挂载，请检查!${NC}"
    exit 1
fi

# 创建备份目录
mkdir -p "${BACKUP_DIR}"

echo -e "${YELLOW}开始备份 MRRC 项目...${NC}"
echo "源目录: ${SOURCE_DIR}"
echo "备份位置: ${BACKUP_PATH}"
echo ""

# 使用 rsync 进行备份，排除不需要的文件
rsync -avh --progress \
    --exclude='.git' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.DS_Store' \
    --exclude='*.log' \
    --exclude='atr1000_proxy.log' \
    --exclude='*.pid' \
    --exclude='cq*.wav' \
    --exclude='cqcqcq*.wav' \
    --exclude='tune.wav' \
    --exclude='DSP/wdsp/*.o' \
    --exclude='DSP/wdsp/*.a' \
    --exclude='DSP/wdsp/*.dylib' \
    --exclude='DSP/wdsp/*.so' \
    --exclude='opus/__pycache__' \
    --exclude='dev_tools/__pycache__' \
    "${SOURCE_DIR}/" \
    "${BACKUP_PATH}/"

# 检查备份是否成功
if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}备份成功完成!${NC}"
    echo "备份位置: ${BACKUP_PATH}"

    # 计算备份大小
    BACKUP_SIZE=$(du -sh "${BACKUP_PATH}" | cut -f1)
    echo "备份大小: ${BACKUP_SIZE}"

    # 更新 latest 软链接
    rm -f "${LATEST_LINK}"
    ln -s "${BACKUP_NAME}" "${LATEST_LINK}"
    echo "最新备份链接: ${LATEST_LINK}"

    # 清理旧备份（保留最近10个）
    cd "${BACKUP_DIR}"
    BACKUP_COUNT=$(ls -1d MRRC_backup_* 2>/dev/null | wc -l)
    if [ $BACKUP_COUNT -gt 10 ]; then
        echo ""
        echo -e "${YELLOW}清理旧备份（保留最近10个）...${NC}"
        ls -1td MRRC_backup_* | tail -n +11 | xargs -I {} rm -rf {}
        echo "清理完成"
    fi

    echo ""
    echo -e "${GREEN}所有备份:${NC}"
    ls -1td MRRC_backup_* 2>/dev/null | head -10 | nl
else
    echo ""
    echo -e "${RED}备份失败!${NC}"
    exit 1
fi
