#!/bin/bash
# MRRC SSL 证书 - 手动 DNS 验证
# 域名: radio.vlsc.net

set -e

DOMAIN="radio.vlsc.net"
ACME_SH="$HOME/.acme.sh/acme.sh"
PROXY="socks5://127.0.0.1:3328"

# 颜色
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

# 设置代理
export HTTPS_PROXY="$PROXY"
export ACME_USE_WGET=1

# 检查 acme.sh
if [ ! -f "$ACME_SH" ]; then
    echo -e "${RED}错误: acme.sh 未安装${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  手动 DNS 验证申请 SSL 证书${NC}"
echo -e "${GREEN}  域名: $DOMAIN${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${YELLOW}注意: 此方式不支持自动续期${NC}"
echo -e "${YELLOW}证书到期前需要手动重新申请${NC}"
echo ""

# 申请证书 (手动模式)
echo -e "${YELLOW}正在申请证书...${NC}"
echo ""

# 创建临时脚本用于交互
TEMP_SCRIPT=$(mktemp)
cat > "$TEMP_SCRIPT" << 'EOF'
#!/usr/bin/env expect
set timeout -1

spawn ~/.acme.sh/acme.sh --issue -d radio.vlsc.net --dns --yes-I-know-dns-manual-mode-enough-go-ahead-please

expect {
    "Add the following TXT record" {
        puts "\n========================================"
        puts "请在 DNS 管理面板添加以下 TXT 记录:"
        puts "========================================"
    }
    timeout {
        puts "超时"
        exit 1
    }
}

interact
EOF

# 如果没有 expect，使用普通方式
if command -v expect &> /dev/null; then
    chmod +x "$TEMP_SCRIPT"
    expect "$TEMP_SCRIPT"
    rm -f "$TEMP_SCRIPT"
else
    # 使用普通方式，需要用户手动操作
    echo -e "${BLUE}请运行以下命令:${NC}"
    echo ""
    echo "export HTTPS_PROXY=socks5://127.0.0.1:3328"
    echo "export ACME_USE_WGET=1"
    echo "~/.acme.sh/acme.sh --issue -d radio.vlsc.net --dns --yes-I-know-dns-manual-mode-enough-go-ahead-please"
    echo ""
    echo "按提示添加 TXT 记录后，再运行本脚本完成部署"
    echo ""
    
    read -p "是否继续申请? (y/n): " confirm
    if [ "$confirm" != "y" ]; then
        echo "已取消"
        exit 0
    fi
    
    # 开始申请
    ~/.acme.sh/acme.sh --issue -d "$DOMAIN" --dns \
        --yes-I-know-dns-manual-mode-enough-go-ahead-please || true
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  证书申请完成!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# 部署证书
echo -e "${YELLOW}正在部署证书到 MRRC...${NC}"

MRRC_DIR="$(cd "$(dirname "$0")" && pwd)"
CERT_DIR="$MRRC_DIR/certs"

# 备份旧证书
if [ -f "$CERT_DIR/radio.vlsc.net.pem" ]; then
    mkdir -p "$CERT_DIR/backup"
    BACKUP_DATE=$(date +%Y%m%d_%H%M%S)
    cp "$CERT_DIR/radio.vlsc.net.pem" "$CERT_DIR/backup/radio.vlsc.net.pem.$BACKUP_DATE"
    cp "$CERT_DIR/radio.vlsc.net.key" "$CERT_DIR/backup/radio.vlsc.net.key.$BACKUP_DATE"
    echo -e "${YELLOW}已备份旧证书${NC}"
fi

# 安装证书
"$ACME_SH" --install-cert -d "$DOMAIN" \
    --cert-file "$CERT_DIR/radio.vlsc.net.pem" \
    --key-file "$CERT_DIR/radio.vlsc.net.key" \
    --fullchain-file "$CERT_DIR/fullchain.pem" \
    --reloadcmd "cd $MRRC_DIR && ./mrrc_control.sh restart"

echo ""
echo -e "${GREEN}✓ 证书部署完成!${NC}"
echo ""
echo "证书位置:"
echo "  - $CERT_DIR/radio.vlsc.net.pem"
echo "  - $CERT_DIR/radio.vlsc.net.key"
echo ""
echo -e "${YELLOW}注意: 手动模式不支持自动续期${NC}"
echo "证书到期前请手动重新申请"
echo ""
echo "查看证书信息:"
openssl x509 -in "$CERT_DIR/radio.vlsc.net.pem" -noout -dates 2>/dev/null || true
