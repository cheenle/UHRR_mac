#!/bin/bash
# MRRC SSL 证书 - 阿里云 DNS 验证
# 域名: radio.vlsc.net

set -e

DOMAIN="radio.vlsc.net"
ACME_SH="$HOME/.acme.sh/acme.sh"
PROXY="socks5://127.0.0.1:3328"

# 颜色
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# 设置代理
export HTTPS_PROXY="$PROXY"
export ACME_USE_WGET=1

# 加载阿里云配置
CONFIG_FILE="$(cd "$(dirname "$0")" && pwd)/certs/aliyun_dns.conf"
if [ -f "$CONFIG_FILE" ]; then
    source "$CONFIG_FILE"
    echo -e "${GREEN}✓ 已加载阿里云配置${NC}"
else
    echo -e "${RED}✗ 配置文件不存在: $CONFIG_FILE${NC}"
    exit 1
fi

# 检查 acme.sh
if [ ! -f "$ACME_SH" ]; then
    echo -e "${RED}错误: acme.sh 未安装${NC}"
    echo "请先安装: curl https://get.acme.sh | sh"
    exit 1
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  阿里云 DNS 验证申请 SSL 证书${NC}"
echo -e "${GREEN}  域名: $DOMAIN${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# 申请证书
echo -e "${YELLOW}正在申请证书...${NC}"
"$ACME_SH" --issue -d "$DOMAIN" --dns dns_ali

if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}✓ 证书申请成功!${NC}"
    echo ""
    echo -e "${YELLOW}正在部署证书到 MRRC...${NC}"
    
    MRRC_DIR="$(cd "$(dirname "$0")" && pwd)"
    CERT_DIR="$MRRC_DIR/certs"
    
    # 备份旧证书
    if [ -f "$CERT_DIR/radio.vlsc.net.pem" ]; then
        mkdir -p "$CERT_DIR/backup"
        BACKUP_DATE=$(date +%Y%m%d_%H%M%S)
        cp "$CERT_DIR/radio.vlsc.net.pem" "$CERT_DIR/backup/radio.vlsc.net.pem.$BACKUP_DATE"
        cp "$CERT_DIR/radio.vlsc.net.key" "$CERT_DIR/backup/radio.vlsc.net.key.$BACKUP_DATE"
        echo -e "${YELLOW}已备份旧证书到 backup/ 目录${NC}"
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
    echo "  - $CERT_DIR/fullchain.pem"
    echo ""
    echo -e "${GREEN}MRRC 服务已重启，新证书已生效${NC}"
    echo ""
    echo "证书信息:"
    openssl x509 -in "$CERT_DIR/radio.vlsc.net.pem" -noout -subject -dates 2>/dev/null || true
    echo ""
    echo "自动续期: 已启用 (acme.sh cron 任务)"
    echo "续期检查: 每天自动检查"
    echo ""
    echo "手动续期命令:"
    echo "  ./setup_ssl_aliyun.sh renew"
    
else
    echo ""
    echo -e "${RED}✗ 证书申请失败${NC}"
    echo ""
    echo "请检查:"
    echo "1. AccessKey ID/Secret 是否正确"
    echo "2. 该 AccessKey 是否有 DNS 管理权限"
    echo "3. 域名 radio.vlsc.net 的 DNS 是否在阿里云管理"
    echo "4. 网络连接是否正常 (已配置代理 $PROXY)"
    echo ""
    echo "调试命令:"
    echo "  export HTTPS_PROXY=$PROXY"
    echo "  $ACME_SH --issue -d $DOMAIN --dns dns_ali --debug"
    exit 1
fi