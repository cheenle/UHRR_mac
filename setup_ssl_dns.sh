#!/bin/bash
# MRRC SSL 证书 DNS 验证配置脚本
# 支持多种 DNS 提供商

set -e

DOMAIN="radio.vlsc.net"
ACME_SH="$HOME/.acme.sh/acme.sh"
PROXY="socks5://127.0.0.1:3328"

# 颜色
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

export HTTPS_PROXY="$PROXY"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  DNS 验证方式申请 SSL 证书${NC}"
echo -e "${GREEN}  域名: $DOMAIN${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# 检查 acme.sh
if [ ! -f "$ACME_SH" ]; then
    echo -e "${RED}错误: acme.sh 未安装${NC}"
    exit 1
fi

echo "请选择 DNS 提供商:"
echo ""
echo "1) Cloudflare (推荐)"
echo "   - 需要 API Token"
echo "   - 支持自动续期"
echo ""
echo "2) 阿里云 DNS"
echo "   - 需要 AccessKey ID/Secret"
echo "   - 支持自动续期"
echo ""
echo "3) 腾讯云 DNSPod"
echo "   - 需要 API Token"
echo "   - 支持自动续期"
echo ""
echo "4) 手动 DNS (仅用于测试)"
echo "   - 需要手动添加 TXT 记录"
echo "   - 不支持自动续期"
echo ""

read -p "选择 [1-4]: " provider

case "$provider" in
    1)
        echo ""
        echo -e "${YELLOW}Cloudflare 配置${NC}"
        echo "请获取 API Token:"
        echo "1. 访问 https://dash.cloudflare.com/profile/api-tokens"
        echo "2. 创建 Token，权限: Zone:DNS:Edit"
        echo "3. 区域资源: Include: Specific zone: vlsc.net"
        echo ""
        
        read -p "输入 CF_Token: " cf_token
        read -p "输入 CF_Account_ID (可选): " cf_account
        
        export CF_Token="$cf_token"
        [ -n "$cf_account" ] && export CF_Account_ID="$cf_account"
        
        echo ""
        echo -e "${YELLOW}正在申请证书...${NC}"
        "$ACME_SH" --issue -d "$DOMAIN" --dns dns_cf
        ;;
    
    2)
        echo ""
        echo -e "${YELLOW}阿里云 DNS 配置${NC}"
        read -p "输入 Ali_Key (AccessKey ID): " ali_key
        read -p "输入 Ali_Secret (AccessKey Secret): " ali_secret
        
        export Ali_Key="$ali_key"
        export Ali_Secret="$ali_secret"
        
        echo ""
        echo -e "${YELLOW}正在申请证书...${NC}"
        "$ACME_SH" --issue -d "$DOMAIN" --dns dns_ali
        ;;
    
    3)
        echo ""
        echo -e "${YELLOW}腾讯云 DNSPod 配置${NC}"
        read -p "输入 DP_Id (API ID): " dp_id
        read -p "输入 DP_Key (API Token): " dp_key
        
        export DP_Id="$dp_id"
        export DP_Key="$dp_key"
        
        echo ""
        echo -e "${YELLOW}正在申请证书...${NC}"
        "$ACME_SH" --issue -d "$DOMAIN" --dns dns_dp
        ;;
    
    4)
        echo ""
        echo -e "${YELLOW}手动 DNS 验证${NC}"
        echo "注意: 这种方式不支持自动续期"
        echo ""
        
        "$ACME_SH" --issue -d "$DOMAIN" --dns \
            --yes-I-know-dns-manual-mode-enough-go-ahead-please
        
        echo ""
        echo -e "${GREEN}证书申请成功!${NC}"
        echo "手动模式不支持自动续期，到期后请重新申请"
        exit 0
        ;;
    
    *)
        echo -e "${RED}无效选择${NC}"
        exit 1
        ;;
esac

# 安装证书
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
        cp "$CERT_DIR/radio.vlsc.net.pem" "$CERT_DIR/backup/radio.vlsc.net.pem.$(date +%Y%m%d)"
        cp "$CERT_DIR/radio.vlsc.net.key" "$CERT_DIR/backup/radio.vlsc.net.key.$(date +%Y%m%d)"
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
    echo "自动续期: 已启用 (cron 任务)"
    echo "续期检查: 每天 0:00"
    echo ""
    echo "手动测试续期:"
    echo "  ./setup_ssl_acme.sh renew"
else
    echo ""
    echo -e "${RED}✗ 证书申请失败${NC}"
    echo "请检查:"
    echo "1. API Token 是否正确"
    echo "2. 域名 DNS 是否由该提供商管理"
    echo "3. 网络连接是否正常"
    exit 1
fi
