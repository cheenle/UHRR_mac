#!/bin/bash
# MRRC 远程服务器配置脚本
# 在 www.vlsc.net 上运行此脚本配置 SSH 和防火墙

echo "=== MRRC 远程服务器配置 ==="
echo ""

# 1. 配置 SSH GatewayPorts
echo "[1/3] 配置 SSH GatewayPorts..."
if [ -f /etc/ssh/sshd_config ]; then
    # 检查是否已有 GatewayPorts 配置
    if grep -q "^GatewayPorts" /etc/ssh/sshd_config; then
        # 修改为 yes
        sed -i 's/^GatewayPorts.*/GatewayPorts yes/' /etc/ssh/sshd_config
        echo "  ✓ 已更新 GatewayPorts 配置"
    else
        # 添加配置
        echo "GatewayPorts yes" >> /etc/ssh/sshd_config
        echo "  ✓ 已添加 GatewayPorts 配置"
    fi
else
    echo "  ✗ 未找到 SSH 配置文件"
    exit 1
fi

# 2. 重启 SSH 服务
echo ""
echo "[2/3] 重启 SSH 服务..."
if systemctl restart sshd 2>/dev/null || service ssh restart 2>/dev/null; then
    echo "  ✓ SSH 服务已重启"
else
    echo "  ⚠ 请手动重启 SSH 服务: systemctl restart sshd"
fi

# 3. 配置防火墙
echo ""
echo "[3/3] 配置防火墙..."

# 检查防火墙类型并开放端口
if command -v ufw >/dev/null 2>&1; then
    # Ubuntu/Debian UFW
    ufw allow 8891/tcp
    ufw allow 8892/tcp
    echo "  ✓ UFW 防火墙规则已添加"
    ufw status | grep -E "8891|8892"
elif command -v firewall-cmd >/dev/null 2>&1; then
    # CentOS/RHEL firewalld
    firewall-cmd --permanent --add-port=8891/tcp
    firewall-cmd --permanent --add-port=8892/tcp
    firewall-cmd --reload
    echo "  ✓ firewalld 规则已添加"
elif command -v iptables >/dev/null 2>&1; then
    # iptables
    iptables -I INPUT -p tcp --dport 8891 -j ACCEPT
    iptables -I INPUT -p tcp --dport 8892 -j ACCEPT
    echo "  ✓ iptables 规则已添加"
    # 尝试保存规则
    if command -v netfilter-persistent >/dev/null 2>&1; then
        netfilter-persistent save
    elif [ -f /etc/sysconfig/iptables ]; then
        service iptables save
    fi
else
    echo "  ⚠ 未检测到支持的防火墙，请手动开放 8891/8892 端口"
fi

echo ""
echo "=== 配置完成 ==="
echo ""
echo "请确保："
echo "  1. SSH GatewayPorts 已启用"
echo "  2. 防火墙已开放 8891/8892 端口"
echo ""
echo "验证命令:"
echo "  netstat -tlnp | grep -E '8891|8892'"
echo ""
echo "配置完成后，用户可以通过以下地址访问："
echo "  radio1: https://www.vlsc.net:8891"
echo "  radio2: https://www.vlsc.net:8892"
