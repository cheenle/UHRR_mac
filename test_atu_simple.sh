#!/bin/bash

# ATU设备简单连接测试脚本
# 专注于基本连通性测试

ATU_IP="192.168.1.12"

echo "=== ATU设备基础连接测试 ==="
echo "设备IP: $ATU_IP"
echo "测试时间: $(date)"
echo

# 1. 测试基本连通性
echo "1. 测试设备连通性..."
if ping -c 2 -W 2 "$ATU_IP" >/dev/null 2>&1; then
    echo "✅ 设备可达"
    echo "   延迟: $(ping -c 1 -W 1 "$ATU_IP" | grep 'time=' | cut -d'=' -f4)"
else
    echo "❌ 设备不可达"
    echo "💡 请检查:"
    echo "   - 设备是否开机"
    echo "   - 网络连接是否正常"
    echo "   - IP地址是否正确"
    exit 1
fi

echo

# 2. 测试常用端口
echo "2. 测试常用端口..."
PORTS=(80 81 8080 8081)

for port in "${PORTS[@]}"; do
    echo -n "端口 $port: "

    # 使用curl测试HTTP端口
    if timeout 3 curl -s "http://$ATU_IP:$port/" >/dev/null 2>&1; then
        echo "✅ 开放 (HTTP)"

        # 尝试获取页面标题
        if title=$(timeout 2 curl -s "http://$ATU_IP:$port/" | grep -o '<title>[^<]*' | sed 's/<title>//'); then
            echo "   页面标题: $title"
        fi
    else
        echo "❌ 关闭或无响应"
    fi
done

echo

# 3. 提供建议
echo "3. 使用建议:"
echo "• 访问诊断工具: http://localhost:8080/atu_diagnostic.html"
echo "• 点击'扫描端口'按钮进行详细诊断"
echo "• 如果端口81不工作，尝试端口8080或8081"
echo "• 先访问 http://$ATU_IP/ 查看设备Web界面"

echo
echo "=== 测试完成 ==="

# 4. 如果端口80可用，尝试获取更多信息
echo "4. 设备信息检查..."
if timeout 3 curl -s "http://$ATU_IP/" >/dev/null 2>&1; then
    echo "✅ 可以访问设备Web界面"

    # 尝试获取设备型号等信息（如果页面包含相关信息）
    if device_info=$(timeout 3 curl -s "http://$ATU_IP/" | grep -i "atu\|tuner\|model" | head -1); then
        echo "   发现设备信息: $device_info"
    fi
else
    echo "❌ 无法访问设备Web界面"
fi

echo
echo "💡 下一步操作:"
echo "1. 打开浏览器访问: http://localhost:8080/atu_diagnostic.html"
echo "2. 点击'扫描端口'按钮"
echo "3. 根据扫描结果调整端口设置"
echo "4. 查看详细的故障排除指南"
