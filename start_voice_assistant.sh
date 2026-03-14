#!/bin/bash
#
# 语音助手服务启动脚本
# 启动后端语音识别与合成服务
#

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 配置
PORT=${VOICE_PORT:-8878}
WHISPER_MODEL=${WHISPER_MODEL:-base}
LANGUAGE=${LANGUAGE:-zh}

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  MRRC 语音助手服务${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# 检查Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}错误: 未找到 python3${NC}"
    exit 1
fi

# 检查依赖
echo -e "${YELLOW}检查依赖...${NC}"

# 定义需要检查的包
REQUIRED_PACKAGES="numpy sounddevice soundfile tornado"
OPTIONAL_PACKAGES="openai-whisper pyttsx3"

# 检查必需包
for pkg in $REQUIRED_PACKAGES; do
    if ! python3 -c "import ${pkg}" 2>/dev/null; then
        echo -e "${YELLOW}安装 ${pkg}...${NC}"
        pip3 install -q "$pkg"
    fi
done

# 检查可选包
for pkg in $OPTIONAL_PACKAGES; do
    if python3 -c "import ${pkg}" 2>/dev/null; then
        echo -e "${GREEN}✓ ${pkg} 已安装${NC}"
    else
        echo -e "${YELLOW}○ ${pkg} 未安装 (可选)${NC}"
    fi
done

echo -e "${GREEN}依赖检查完成${NC}"
echo ""

# 检查语音助手服务文件
if [ ! -f "voice_assistant_service.py" ]; then
    echo -e "${RED}错误: 未找到 voice_assistant_service.py${NC}"
    exit 1
fi

# 下载Whisper模型（如果不存在）
MODEL_DIR="$HOME/.cache/whisper"
if [ ! -f "$MODEL_DIR/$WHISPER_MODEL.pt" ]; then
    echo -e "${YELLOW}首次运行: 将自动下载 Whisper $WHISPER_MODEL 模型${NC}"
    echo -e "${YELLOW}这可能需要几分钟时间，请耐心等待...${NC}"
    echo ""
fi

# 检查端口是否被占用
if lsof -Pi :${PORT} -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo -e "${YELLOW}警告: 端口 ${PORT} 已被占用${NC}"
    echo -e "${YELLOW}尝试查找占用进程...${NC}"
    lsof -Pi :${PORT} -sTCP:LISTEN
    echo ""
    echo -e "${YELLOW}请选择:${NC}"
    echo -e "  1) 终止占用进程并继续"
    echo -e "  2) 使用其他端口"
    echo -e "  3) 退出"
    read -p "选择 [1/2/3]: " choice
    
    case $choice in
        1)
            echo -e "${YELLOW}终止占用进程...${NC}"
            lsof -Pi :${PORT} -sTCP:LISTEN -t | xargs kill -9 2>/dev/null
            sleep 1
            ;;
        2)
            read -p "请输入新端口: " new_port
            PORT=$new_port
            ;;
        *)
            exit 1
            ;;
    esac
fi

# 启动服务
echo -e "${GREEN}启动语音助手服务...${NC}"
echo -e "  端口: ${PORT}"
echo -e "  模型: ${WHISPER_MODEL}"
echo -e "  语言: ${LANGUAGE}"
echo ""
echo -e "${BLUE}服务地址:${NC}"
echo -e "  WebSocket: ws://localhost:${PORT}/ws/voice"
echo -e "  HTTP API:  http://localhost:${PORT}/api/status"
echo ""
echo -e "${YELLOW}按 Ctrl+C 停止服务${NC}"
echo ""

# 启动Python服务
trap 'echo -e "\n${RED}服务已停止${NC}"; exit 0' INT

python3 voice_assistant_service.py \
    --port "$PORT" \
    --whisper-model "$WHISPER_MODEL" \
    --language "$LANGUAGE"
