#!/bin/bash
# SSL 证书到期检查脚本 (radio.vlsc.net)
# 检查已部署的证书文件, 剩余天数不足时给出提醒
# 退出码: 0=正常 1=即将到期(<=14天) 2=已过期

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOMAIN="radio.vlsc.net"
DAYS_WARNING=14

# 线上实例实际使用的文件: radio1 用 fullchain.pem, 默认实例用 radio.vlsc.net.pem
CERT_FILES=(
    "$SCRIPT_DIR/radio.vlsc.net.pem"
    "$SCRIPT_DIR/fullchain.pem"
)

MIN_DAYS=""
MIN_FILE=""
MIN_EXPIRY=""
MISSING=0

for f in "${CERT_FILES[@]}"; do
    if [ ! -f "$f" ]; then
        echo "[ERROR] 证书文件不存在: $f"
        MISSING=1
        continue
    fi

    INFO=$(python3 - "$f" << 'EOF'
import datetime, subprocess, sys
path = sys.argv[1]
enddate = subprocess.run(
    ['openssl', 'x509', '-in', path, '-noout', '-enddate'],
    capture_output=True, text=True, check=True
).stdout.strip().split('=', 1)[1]
expiry = datetime.datetime.strptime(enddate, '%b %d %H:%M:%S %Y %Z')
days = (int(expiry.timestamp()) - int(datetime.datetime.now().timestamp())) // 86400
print(f"{enddate}|{days}")
EOF
    )
    if [ -z "$INFO" ]; then
        echo "[ERROR] 无法解析证书: $f"
        MISSING=1
        continue
    fi
    EXPIRY="${INFO%|*}"
    DAYS="${INFO#*|}"

    if [ -z "$MIN_DAYS" ] || [ "$DAYS" -lt "$MIN_DAYS" ]; then
        MIN_DAYS="$DAYS"; MIN_FILE="$f"; MIN_EXPIRY="$EXPIRY"
    fi
done

[ "$MISSING" = "1" ] && exit 1
[ -z "$MIN_DAYS" ] && { echo "[ERROR] 未找到可检查的证书"; exit 1; }

echo "[INFO] 域名: $DOMAIN"
echo "[INFO] 最早到期文件: $MIN_FILE"
echo "[INFO] 到期日期: $MIN_EXPIRY"
echo "[INFO] 剩余天数: $MIN_DAYS"

if [ "$MIN_DAYS" -le 0 ]; then
    echo "[CRITICAL] 证书已过期！请立即续期！"
    echo "           运行: cd $SCRIPT_DIR && ./setup_ssl_manual.sh"
    if command -v osascript &> /dev/null; then
        osascript -e "display notification \"证书已过期，请立即续期!\" with title \"SSL证书警告\"" 2>/dev/null
    fi
    exit 2
elif [ "$MIN_DAYS" -le "$DAYS_WARNING" ]; then
    echo "[WARNING] 证书将在 $MIN_DAYS 天后到期，请尽快续期！"
    echo "          运行: cd $SCRIPT_DIR && ./setup_ssl_manual.sh"
    echo "          （或配置好阿里云 DNS API 后运行 ./setup_ssl_auto.sh 实现自动续期）"
    if command -v osascript &> /dev/null; then
        osascript -e "display notification \"证书将在 $MIN_DAYS 天后到期，请尽快续期!\" with title \"SSL证书提醒\"" 2>/dev/null
    fi
    exit 1
else
    echo "[OK] 证书正常，还有 $MIN_DAYS 天到期"
    exit 0
fi
