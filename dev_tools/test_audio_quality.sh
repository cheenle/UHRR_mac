#!/bin/bash

# Audio Quality Test Script for Mobile Interface
echo "=== 移动端音频质量测试 ==="

# Check if server is running
echo "1. 检查服务器状态..."
if ps aux | grep UHRR | grep -v grep > /dev/null; then
    echo "✅ 服务器运行正常"
else
    echo "❌ 服务器未运行"
    exit 1
fi

# Check mobile interface files
echo "2. 检查移动端文件..."
if [ -f "www/mobile.js" ] && [ -f "www/mobile.html" ] && [ -f "www/mobile.css" ]; then
    echo "✅ 移动端文件存在"
else
    echo "❌ 移动端文件缺失"
    exit 1
fi

# Check audio processing implementation
echo "3. 检查音频处理实现..."
if grep -q "audioRXSourceNode\|audioRXGainNode\|audioRXBiquadFilterNode" www/mobile.js; then
    echo "✅ 高级音频处理节点已实现"
else
    echo "❌ 高级音频处理节点未实现"
fi

# Check Web Audio API usage
echo "4. 检查Web Audio API使用..."
if grep -q "createScriptProcessor\|createGain\|createBiquadFilter" www/mobile.js; then
    echo "✅ Web Audio API处理链已实现"
else
    echo "❌ Web Audio API处理链未完全实现"
fi

# Check audio buffer management
echo "5. 检查音频缓冲区管理..."
if grep -q "audioRXAudioBuffer\|onaudioprocess" www/mobile.js; then
    echo "✅ 音频缓冲区管理已实现"
else
    echo "❌ 音频缓冲区管理未实现"
fi

# Check volume control
echo "6. 检查音量控制..."
if grep -q "updateAFGain\|audioRXGainNode.gain" www/mobile.js; then
    echo "✅ 音量控制已实现"
else
    echo "❌ 音量控制未实现"
fi

# Check filter controls
echo "7. 检查滤波器控制..."
if grep -q "setAudioFilter\|audioRXBiquadFilterNode" www/mobile.js; then
    echo "✅ 滤波器控制已实现"
else
    echo "❌ 滤波器控制未实现"
fi

# Check monitoring functions
echo "8. 检查音频监控功能..."
if grep -q "monitorAudioBuffer\|startAudioMonitoring" www/mobile.js; then
    echo "✅ 音频监控功能已实现"
else
    echo "❌ 音频监控功能未实现"
fi

echo "=== 音频质量测试完成 ==="
echo ""
echo "请执行以下手动测试步骤："
echo "1. 在移动设备上访问 https://localhost:8888/mobile"
echo "2. 打开浏览器开发者工具"
echo "3. 检查Console输出，确认没有音频相关错误"
echo "4. 调整AF增益滑块，观察音量变化"
echo "5. 检查音频是否清晰，无杂音"
echo "6. 观察音频缓冲区状态报告"