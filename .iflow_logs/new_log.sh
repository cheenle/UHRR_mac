#!/bin/bash
# iFlow CLI 对话记录快速创建脚本

# 获取当前日期
DATE=$(date +%Y-%m-%d)
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# 检查是否提供了描述
if [ -z "$1" ]; then
    echo "用法: ./new_log.sh '简短描述'"
    echo "例如: ./new_log.sh '修复PTT延迟问题'"
    exit 1
fi

DESCRIPTION=$1
FILENAME="${DATE}_${DESCRIPTION}.md"

# 创建文件
cat > "$FILENAME" << EOF
# 对话记录 - ${DATE}

## 主题
${DESCRIPTION}

## 背景

## 讨论内容

### 问题/需求

### 解决方案

### 实现细节

## 关键决策
- [ ]

## 修改的文件

## 代码片段

\`\`\`python

\`\`\`

## 后续行动
- [ ]

## 备注
EOF

echo "已创建对话记录文件: $FILENAME"
echo "请编辑该文件记录对话内容"
