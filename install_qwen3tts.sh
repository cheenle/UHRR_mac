#!/bin/bash
# 安装Qwen3-TTS依赖脚本

echo "=========================================="
echo "安装Qwen3-TTS 1.7B依赖"
echo "=========================================="
echo ""
echo "这将安装:"
echo "- transformers (HuggingFace库)"
echo "- torch (PyTorch)"
echo "- soundfile (音频处理)"
echo ""
echo "首次使用Qwen3-TTS时会自动下载:"
echo "- Qwen3-TTS-1.7B模型 (约4.5GB)"
echo ""
echo "开始安装..."
echo ""

# 安装依赖
pip3 install transformers torch soundfile --break-system-packages

if [ $? -eq 0 ]; then
    echo ""
    echo "=========================================="
    echo "✅ 依赖安装完成!"
    echo "=========================================="
    echo ""
    echo "现在重启MRRC服务即可使用Qwen3-TTS:"
    echo "  ./mrrc_control.sh restart"
    echo ""
    echo "首次使用时会自动下载4.5GB模型文件，"
    echo "下载时间取决于网络速度(通常5-15分钟)"
    echo ""
else
    echo ""
    echo "=========================================="
    echo "❌ 安装失败"
    echo "=========================================="
    echo ""
    echo "请检查网络连接和Python环境"
    echo ""
fi
