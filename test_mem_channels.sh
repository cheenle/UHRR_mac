#!/bin/bash
# 频道记忆功能诊断脚本
echo "========== 频道记忆诊断 =========="

# 1. 文件是否存在
echo ""
echo "1️⃣ memory_channels.json 文件状态:"
if [ -f memory_channels.json ]; then
    echo "   ✅ 文件存在"
    cat memory_channels.json 2>/dev/null | head -5
else
    echo "   ❌ 文件不存在！"
    echo "   → MRRC 可能没有执行到 load_memory_channels()"
fi

# 2. 检查 MRRC 中关键代码是否存在
echo ""
echo "2️⃣ MRRC 关键代码检查:"
grep -c "MemChannelsHandler" MRRC && echo "   ✅ MemChannelsHandler 类存在" || echo "   ❌ MemChannelsHandler 类缺失"
grep -c "load_memory_channels" MRRC && echo "   ✅ load_memory_channels 函数存在" || echo "   ❌ load_memory_channels 缺失"
grep -c "api/mem_channels" MRRC && echo "   ✅ /api/mem_channels 路由已注册" || echo "   ❌ 路由缺失"

# 3. 检查 pyc 缓存（可能运行旧代码）
echo ""
echo "3️⃣ Python 缓存文件:"
find . -name "*.pyc" -o -name "__pycache__" | head -10
echo "   → 如果有缓存，运行: find . -name '*.pyc' -delete && find . -name '__pycache__' -type d -exec rm -rf {} +"

# 4. 检查服务端日志
echo ""
echo "4️⃣ 检查 MRRC 日志中的频道记忆相关输出:"
grep -i "频道记忆\|memory_channel\|memChannels" mrrc_debug.log 2>/dev/null | tail -5 || echo "   (无 mrrc_debug.log 或无关记录)"

# 5. 尝试直接访问 API
echo ""
echo "5️⃣ 测试 HTTP API (需要服务器在运行):"
curl -sk https://localhost:8877/api/mem_channels 2>/dev/null && echo "" || echo "   ❌ API 不可达（服务器未运行或端口不对）"

echo ""
echo "========== 诊断完成 =========="
