#!/bin/bash
# SSL 证书到期检查脚本
# 用于手动 DNS 模式的证书到期提醒

CERT_FILE="/Users/cheenle/UHRR/MRRC/certs/radio.vlsc.net.pem"
DOMAIN="radio.vlsc.net"
DAYS_WARNING=14

# 检查证书是否存在
if [ ! -f "$CERT_FILE" ]; then
    echo "[ERROR] 证书文件不存在: $CERT_FILE"
    exit 1
fi

# 获取到期日期并使用Python计算剩余天数
EXPIRY_INFO=$(python3 << 'EOF'
import datetime
import sys

# 从openssl输出解析日期
import subprocess
result = subprocess.run(['openssl', 'x509', '-in', '/Users/cheenle/UHRR/MRRC/certs/radio.vlsc.net.pem', '-noout', '-enddate'], capture_output=True, text=True)
expiry_str = result.stdout.strip().split('=')[1]

# 解析日期
expiry_dt = datetime.datetime.strptime(expiry_str, '%b %d %H:%M:%S %Y %Z')
expiry_timestamp = int(expiry_dt.timestamp())

# 当前时间
now_timestamp = int(datetime.datetime.now().timestamp())

# 计算剩余天数
days_remaining = (expiry_timestamp - now_timestamp) // 86400

print(f"EXPIRY_DATE={expiry_str}")
print(f"DAYS_REMAINING={days_remaining}")
EOF
)

# 解析Python输出
EXPIRY_DATE=$(echo "$EXPIRY_INFO" | grep "EXPIRY_DATE=" | cut -d= -f2)
DAYS_REMAINING=$(echo "$EXPIRY_INFO" | grep "DAYS_REMAINING=" | cut -d= -f2)

echo "[INFO] 域名: $DOMAIN"
echo "[INFO] 到期日期: $EXPIRY_DATE"
echo "[INFO] 剩余天数: $DAYS_REMAINING"

# 检查是否需要续期
if [ "$DAYS_REMAINING" -le 0 ]; then
    echo "[CRITICAL] 证书已过期！请立即续期！"
    echo "           运行: cd /Users/cheenle/UHRR/MRRC && ./setup_ssl_manual.sh"
    
    # 发送系统通知（macOS）
    if command -v osascript &> /dev/null; then
        osascript -e "display notification \"证书已过期，请立即续期!\" with title \"SSL证书警告\""
    fi
    exit 2
elif [ "$DAYS_REMAINING" -le $DAYS_WARNING ]; then
    echo "[WARNING] 证书将在 $DAYS_REMAINING 天后到期，请尽快续期！"
    echo "          运行: cd /Users/cheenle/UHRR/MRRC && ./setup_ssl_manual.sh"
    
    # 发送系统通知（macOS）
    if command -v osascript &> /dev/null; then
        osascript -e "display notification \"证书将在 $DAYS_REMAINING 天后到期，请尽快续期!\" with title \"SSL证书提醒\""
    fi
    exit 1
else
    echo "[OK] 证书正常，还有 $DAYS_REMAINING 天到期"
    exit 0
fi