#!/bin/bash
# ============================================================
#  MRRC SSL 证书 - 配置阿里云 DNS API (dns_ali) 全自动续期
#
#  用法:
#    ./setup_ssl_auto.sh <Ali_Key> <Ali_Secret>
#
#  前置条件:
#    1. 域名 radio.vlsc.net 的 DNS 托管在阿里云/万网
#    2. 阿里云控制台 -> RAM 访问控制 -> 用户 创建(建议专用)用户,
#       授予 AliyunDNSFullAccess 权限, 然后创建 AccessKey
#
#  脚本做的事:
#    1. 先在临时环境用 Let's Encrypt staging 完整测试凭据
#       (不会碰生产证书; staging 证书无效, 仅用于验证 API)
#    2. 通过后在生产环境强制签发一次, 验证方式永久切换为 dns_ali
#    3. 之后 crontab 里 acme.sh 的每日任务(07:48)会自动续期,
#       续期成功会按 Le_ReloadCmd 自动部署并重启 MRRC
#
#  说明: 使用 --dnssleep 30 跳过公共 DoH 传播检查(本机网络访问
#        Cloudflare/Google DoH 不通, 检查会卡满 20 分钟); 睡 30 秒
#        后由 Let's Encrypt 自己验证。该值会存入域名配置, 后续
#        cron 续期同样生效。
#
#  注意: 已禁用的 AccessKey 会返回 InvalidAccessKeyId.Inactive,
#        需要在阿里云控制台重新启用或新建 AccessKey。
# ============================================================

set -u

DOMAIN="radio.vlsc.net"
ACME_SH="$HOME/.acme.sh/acme.sh"
DOMAIN_DIR="$HOME/.acme.sh/${DOMAIN}_ecc"
DOMAIN_CONF="$DOMAIN_DIR/${DOMAIN}.conf"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MRRC_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
CERT_DIR="$SCRIPT_DIR"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; BLUE='\033[0;34m'; NC='\033[0m'

RELOAD_CMD="cd $MRRC_DIR && PATH=/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:\$PATH ./mrrc_multi.sh restart radio1 >> certs/renew_deploy.log 2>&1"

if [ $# -ne 2 ]; then
    awk 'NR>1 && /^#/ {print; next} NR>1 {exit}' "$0" | sed 's/^# \{0,1\}//'
    exit 1
fi

Ali_Key="$1"
Ali_Secret="$2"
export Ali_Key Ali_Secret

if [ ! -x "$ACME_SH" ]; then
    echo -e "${RED}错误: 未找到 acme.sh ($ACME_SH)${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  配置阿里云 DNS 自动续期 - $DOMAIN${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# ---------- 第 1 步: 临时环境 + staging 测试凭据 ----------
echo -e "${BLUE}[1/3] 用 staging 环境测试凭据（不影响生产证书）...${NC}"
TMPHOME="$(mktemp -d /tmp/acme_ali_test.XXXXXX)"
cp "$HOME/.acme.sh/account.conf" "$TMPHOME/account.conf" 2>/dev/null || true

if "$ACME_SH" --home "$TMPHOME" --issue -d "$DOMAIN" --dns dns_ali --server letsencrypt_test --dnssleep 30 > "$TMPHOME/test.log" 2>&1; then
    echo -e "${GREEN}✓ 凭据有效，可以调用阿里云 DNS API${NC}"
else
    rm -rf "$TMPHOME"
    echo -e "${RED}✗ 凭据测试失败，未对生产环境做任何修改。${NC}"
    echo ""
    echo "可能原因:"
    echo "  - AccessKey 已禁用/删除（错误码 InvalidAccessKeyId.Inactive）"
    echo "  - RAM 用户缺少 AliyunDNSFullAccess 权限"
    echo "  - Key/Secret 复制有误或含多余空格"
    echo ""
    echo "完整日志请重新运行并观察，或调试:"
    echo "  Ali_Key=<key> Ali_Secret=<secret> $ACME_SH --issue -d $DOMAIN --dns dns_ali --server letsencrypt_test --debug"
    echo "  （登录阿里云控制台检查 AccessKey 状态与权限）"
    exit 1
fi
rm -rf "$TMPHOME"

# ---------- 第 2 步: 清除可能残留的手动挑战, 生产签发 ----------
echo ""
echo -e "${BLUE}[2/3] 生产环境强制签发（自动部署 + 重启 MRRC）...${NC}"
if [ -f "$DOMAIN_CONF" ] && grep -q "^Le_Vlist=" "$DOMAIN_CONF"; then
    echo -e "${YELLOW}检测到残留的手动 DNS 挑战，先清除以便切换到 API 模式${NC}"
    sed -i '' '/^Le_Vlist=/d' "$DOMAIN_CONF"
fi

"$ACME_SH" --issue -d "$DOMAIN" --ecc --dns dns_ali --force --dnssleep 30 \
    --cert-file "$CERT_DIR/radio.vlsc.net.pem" \
    --key-file "$CERT_DIR/radio.vlsc.net.key" \
    --fullchain-file "$CERT_DIR/fullchain.pem" \
    --reloadcmd "$RELOAD_CMD"
rc=$?

if [ "$rc" != "0" ]; then
    echo ""
    echo -e "${RED}生产签发失败（退出码 $rc）。当前证书未被破坏，可继续用手动模式:${NC}"
    echo "  $SCRIPT_DIR/setup_ssl_manual.sh"
    exit 1
fi

# ---------- 第 3 步: 核对 ----------
echo ""
echo -e "${BLUE}[3/3] 核对结果...${NC}"

WEBROOT="$(grep "^Le_Webroot=" "$DOMAIN_CONF" 2>/dev/null | head -1 | cut -d= -f2- | tr -d "'")"
echo "  验证方式:   ${WEBROOT:-未知} （应为 dns_ali）"
if [ -f "$CERT_DIR/radio.vlsc.net.pem" ]; then
    echo "  已部署证书: 有效期至 $(openssl x509 -in "$CERT_DIR/radio.vlsc.net.pem" -noout -enddate | cut -d= -f2)"
fi
NEXT="$(grep "^Le_NextRenewTimeStr=" "$DOMAIN_CONF" 2>/dev/null | head -1 | cut -d= -f2- | tr -d "'")"
echo "  下次自动续期: ${NEXT:-未知}"
echo ""

if [ "$WEBROOT" != "dns_ali" ]; then
    echo -e "${YELLOW}警告: 验证方式未保存为 dns_ali，自动续期可能不生效。${NC}"
    exit 1
fi

if ! crontab -l 2>/dev/null | grep -q "acme.sh.*--cron"; then
    echo -e "${YELLOW}提示: crontab 里没有 acme.sh 定时任务，自动续期不会触发。${NC}"
    echo "  可执行: $ACME_SH --install-cronjob"
fi

echo -e "${GREEN}✓ 自动续期已配置完成。之后每天由 cron 自动检查，无需手动操作。${NC}"
echo ""
echo -e "${YELLOW}小提示: DNS 里遗留的 _acme-challenge.$DOMAIN TXT 记录可以删除了（不影响续期）。${NC}"
echo ""
