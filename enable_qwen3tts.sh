#!/bin/bash
# 后台安装Qwen3-TTS并在完成后启用

echo "=========================================="
echo "后台安装Qwen3-TTS 1.7B"
echo "=========================================="
echo ""
echo "安装日志: ~/qwen3tts_install.log"
echo ""

# 使用socks5代理安装
export ALL_PROXY=socks5h://localhost:3328

# 安装依赖并记录日志
pip3 install transformers torch soundfile --break-system-packages > ~/qwen3tts_install.log 2>&1

if [ $? -eq 0 ]; then
    echo "✅ 依赖安装完成!" | tee -a ~/qwen3tts_install.log
    echo "" | tee -a ~/qwen3tts_install.log
    echo "现在需要重启MRRC服务以启用Qwen3-TTS:" | tee -a ~/qwen3tts_install.log
    echo "  cd /Users/cheenle/UHRR/MRRC && ./mrrc_control.sh restart" | tee -a ~/qwen3tts_install.log
    echo "" | tee -a ~/qwen3tts_install.log
    echo "首次使用时会自动下载4.5GB模型文件到 ~/.cache/qwen3-tts/" | tee -a ~/qwen3tts_install.log
else
    echo "❌ 安装失败，请检查日志: ~/qwen3tts_install.log" | tee -a ~/qwen3tts_install.log
fi
