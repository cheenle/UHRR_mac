#!/bin/bash
# MRRC SSL 证书自动管理脚本 (acme.sh)
# 域名: radio.vlsc.net

set -e

# 配置
DOMAIN="radio.vlsc.net"
ACME_SH="$HOME/.acme.sh/acme.sh"
MRRC_DIR="$(cd "$(dirname "$0")" && pwd)"
CERT_DIR="$MRRC_DIR/certs"
PROXY="socks5://127.0.0.1:3328"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  MRRC SSL 证书管理 (acme.sh)${NC}"
echo -e "${GREEN}  域名: $DOMAIN${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# 检查 acme.sh
if [ ! -f "$ACME_SH" ]; then
    echo -e "${RED}错误: acme.sh 未安装${NC}"
    echo "请先安装: curl https://get.acme.sh | sh"
    exit 1
fi

# 设置代理
export HTTPS_PROXY="$PROXY"
export ACME_USE_WGET=1

case "$1" in
    "issue")
        echo -e "${YELLOW}正在申请证书...${NC}"
        echo "请选择验证方式:"
        echo "1) HTTP 验证 (需要 80 端口可访问)"
        echo "2) DNS 手动验证"
        echo "3) Cloudflare DNS API (需设置 CF_Token)"
        read -p "选择 [1-3]: " method
        
        case "$method" in
            1)
                echo -e "${YELLOW}使用 HTTP 验证...${NC}"
                # 先停止 MRRC 释放 80 端口
                echo "临时停止 MRRC 服务..."
                "$MRRC_DIR/mrrc_control.sh" stop 2>/dev/null || true
                
                # 申请证书
                "$ACME_SH" --issue -d "$DOMAIN" --standalone --httpport 80
                
                # 安装证书
                "$ACME_SH" --install-cert -d "$DOMAIN" \
                    --cert-file "$CERT_DIR/radio.vlsc.net.pem" \
                    --key-file "$CERT_DIR/radio.vlsc.net.key" \
                    --fullchain-file "$CERT_DIR/fullchain.pem" \
                    --reloadcmd "\"$MRRC_DIR/mrrc_control.sh\" restart"
                
                echo -e "${GREEN}✓ 证书申请成功!${NC}"
                ;;
            2)
                echo -e "${YELLOW}使用 DNS 手动验证...${NC}"
                "$ACME_SH" --issue -d "$DOMAIN" --dns --yes-I-know-dns-manual-mode-enough-go-ahead-please
                echo -e "${YELLOW}请按上述提示添加 DNS 记录，然后运行:${NC}"
                echo "  $0 renew"
                ;;
            3)
                if [ -z "$CF_Token" ]; then
                    echo -e "${RED}错误: 未设置 CF_Token 环境变量${NC}"
                    echo "请先设置: export CF_Token='your-cloudflare-api-token'"
                    exit 1
                fi
                echo -e "${YELLOW}使用 Cloudflare DNS API...${NC}"
                "$ACME_SH" --issue -d "$DOMAIN" --dns dns_cf
                
                # 安装证书
                "$ACME_SH" --install-cert -d "$DOMAIN" \
                    --cert-file "$CERT_DIR/radio.vlsc.net.pem" \
                    --key-file "$CERT_DIR/radio.vlsc.net.key" \
                    --fullchain-file "$CERT_DIR/fullchain.pem" \
                    --reloadcmd "\"$MRRC_DIR/mrrc_control.sh\" restart"
                
                echo -e "${GREEN}✓ 证书申请成功!${NC}"
                ;;
            *)
                echo -e "${RED}无效选择${NC}"
                exit 1
                ;;
        esac
        ;;
    
    "renew")
        echo -e "${YELLOW}正在续期证书...${NC}"
        "$ACME_SH" --renew -d "$DOMAIN" --force
        echo -e "${GREEN}✓ 证书续期完成!${NC}"
        ;;
    
    "deploy")
        echo -e "${YELLOW}部署证书到 MRRC...${NC}"
        "$ACME_SH" --install-cert -d "$DOMAIN" \
            --cert-file "$CERT_DIR/radio.vlsc.net.pem" \
            --key-file "$CERT_DIR/radio.vlsc.net.key" \
            --fullchain-file "$CERT_DIR/fullchain.pem" \
            --reloadcmd "\"$MRRC_DIR/mrrc_control.sh\" restart"
        echo -e "${GREEN}✓ 证书部署完成!${NC}"
        ;;
    
    "info")
        echo -e "${YELLOW}证书信息:${NC}"
        "$ACME_SH" --info -d "$DOMAIN"
        ;;
    
    "cron")
        echo -e "${YELLOW}安装自动续期任务...${NC}"
        "$ACME_SH" --install-cronjob
        echo -e "${GREEN}✓ 自动续期已启用${NC}"
        ;;
    
    *)
        echo "用法: $0 {issue|renew|deploy|info|cron}"
        echo ""
        echo "命令:"
        echo "  issue  - 申请新证书"
        echo "  renew  - 手动续期证书"
        echo "  deploy - 部署证书到 MRRC"
        echo "  info   - 查看证书信息"
        echo "  cron   - 启用自动续期"
        echo ""
        echo "环境变量:"
        echo "  CF_Token - Cloudflare API Token (用于 DNS 验证)"
        echo ""
        echo "示例:"
        echo "  $0 issue    # 申请证书"
        echo "  $0 renew    # 续期证书"
        exit 1
        ;;
esac

echo ""
echo -e "${GREEN}完成!${NC}"
