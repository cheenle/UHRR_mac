#!/bin/bash

# ATU设备端口测试脚本
# 用于诊断ATU设备的网络连接问题

ATU_IP="192.168.1.12"
TEST_PORTS=(80 81 8080 8081 23 2323)

echo "=== ATU设备端口诊断工具 ==="
echo "目标设备: $ATU_IP"
echo "测试时间: $(date)"
echo

# 测试设备是否可达
echo "1. 测试设备可达性..."
if ping -c 2 -W 3 "$ATU_IP" > /dev/null 2>&1; then
    echo "✅ 设备可达"
else
    echo "❌ 设备不可达"
    exit 1
fi

echo
echo "2. 测试常用端口..."
for port in "${TEST_PORTS[@]}"; do
    echo -n "端口 $port: "

    # 测试TCP连接
    if timeout 3 bash -c "</dev/tcp/$ATU_IP/$port" 2>/dev/null; then
        echo "✅ 开放"

        # 如果是HTTP端口，尝试获取响应
        if [ "$port" -eq 80 ] || [ "$port" -eq 8080 ] || [ "$port" -eq 8081 ]; then
            echo -n "  HTTP响应: "
            if curl -s --max-time 3 "http://$ATU_IP:$port/" | head -c 50 | grep -q "HTML\|html"; then
                echo "✅ Web界面"
            else
                echo "⚠️ 响应异常"
            fi
        fi

        # 如果是WebSocket端口，测试握手
        if [ "$port" -eq 81 ] || [ "$port" -eq 8081 ] || [ "$port" -eq 2323 ]; then
            echo -n "  WebSocket: "
            # 这里简化测试，实际需要更复杂的握手测试
            echo "⚠️ 需要浏览器测试"
        fi
    else
        echo "❌ 关闭"
    fi
done

echo
echo "3. 推荐操作："
echo "• 访问 http://$ATU_IP/ 查看设备Web界面"
echo "• 使用诊断工具: http://localhost:8080/atu_diagnostic.html"
echo "• 点击'扫描端口'按钮自动检测可用端口"
echo "• 查看设备手册确认正确的WebSocket端口"

echo
echo "=== 诊断完成 ==="
