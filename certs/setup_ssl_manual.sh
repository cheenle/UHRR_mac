#!/bin/bash
# ============================================================
#  MRRC SSL 证书续期 - radio.vlsc.net (手动 DNS 验证模式)
#
#  背景: 本域名 DNS 在万网/阿里云 (dns25.hichina.com), 默认走
#  acme.sh 的"手动 DNS"验证, 必须分两步执行:
#    第 1 步: 生成订单和挑战值 -> 去 DNS 面板添加 TXT 记录
#    第 2 步: TXT 生效后重新运行本脚本 -> 真正验证并签发
#  脚本会根据"配置里是否存在待验证挑战"自动判断当前该做哪一步,
#  因此可以放心重复运行。
#
#  签发成功后, acme.sh 会按已保存的部署配置自动安装证书并执行重启
#  命令 (见 ~/.acme.sh/radio.vlsc.net_ecc/radio.vlsc.net.conf 里的
#  Le_Real* / Le_ReloadCmd), 本脚本随后核对结果。
#
#  用法:
#    ./setup_ssl_manual.sh              正常续期(自动判断第 1/2 步)
#    ./setup_ssl_manual.sh --status     只查看状态, 不请求 Let's Encrypt
#    ./setup_ssl_manual.sh --force-manual
#                                       当前是 API 自动模式时, 强制改回
#                                       手动 DNS 模式(会破坏自动续期, 慎用)
#
#  长期方案(推荐): 配置阿里云 DNS API 实现全自动续期:
#    ./setup_ssl_auto.sh <Ali_Key> <Ali_Secret>
# ============================================================

set -u

DOMAIN="radio.vlsc.net"
ACME_SH="$HOME/.acme.sh/acme.sh"
DOMAIN_DIR="$HOME/.acme.sh/${DOMAIN}_ecc"
# 允许测试时用 DOMAIN_CONF_OVERRIDE 指向副本, 避免动真实配置
DOMAIN_CONF="${DOMAIN_CONF_OVERRIDE:-$DOMAIN_DIR/${DOMAIN}.conf}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_PEM="$SCRIPT_DIR/radio.vlsc.net.pem"
DEPLOY_KEY="$SCRIPT_DIR/radio.vlsc.net.key"
DEPLOY_FULLCHAIN="$SCRIPT_DIR/fullchain.pem"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; BLUE='\033[0;34m'; NC='\033[0m'

MODE="run"
FORCE_MANUAL=0
for arg in "$@"; do
    case "$arg" in
        --status)       MODE="status" ;;
        --force-manual) FORCE_MANUAL=1 ;;
        -h|--help)      awk 'NR>1 && /^#/ {print; next} NR>1 {exit}' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "未知参数: $arg (用 --help 查看用法)"; exit 1 ;;
    esac
done

# ---------- 工具函数 ----------

conf_get() {
    [ -f "$DOMAIN_CONF" ] || return 1
    grep "^$1=" "$DOMAIN_CONF" 2>/dev/null | head -1 | cut -d= -f2- | sed "s/^'//; s/'$//"
}

has_pending_challenge() {
    [ -f "$DOMAIN_CONF" ] && grep -q "^Le_Vlist=" "$DOMAIN_CONF"
}

# 从挂起的挑战(Le_Vlist)里算出应添加到 DNS 的 TXT 值
expected_txt() {
    local entry keyauth
    entry="$(conf_get Le_Vlist | cut -d, -f1)"
    keyauth="$(printf '%s' "$entry" | cut -d'#' -f2)"
    [ -n "$keyauth" ] || return 1
    printf '%s' "$keyauth" | openssl dgst -sha256 -binary | openssl base64 -A | tr '+/' '-_' | tr -d '='
}

# 查询 DNS 中 _acme-challenge 的所有 TXT 值(历史续期可能残留多条)
dns_txt_all() {
    local ns out
    for ns in 1.1.1.1 8.8.8.8; do
        out="$(dig +short TXT "_acme-challenge.$DOMAIN" @"$ns" 2>/dev/null | tr -d '"' | grep -v '^$')"
        if [ -n "$out" ]; then printf '%s\n' "$out"; return 0; fi
    done
    return 1
}

# DNS 中是否已包含指定 TXT 值
# 注意: 同名 TXT 可以有多条, 只要包含期望值即可通过 ACME 验证
dns_has_txt() {
    dns_txt_all | grep -Fxq "$1"
}

cert_end_epoch() {
    local enddate
    enddate="$(openssl x509 -in "$1" -noout -enddate 2>/dev/null | cut -d= -f2)"
    [ -n "$enddate" ] || return 1
    python3 -c "import datetime,sys; print(int(datetime.datetime.strptime(sys.argv[1],'%b %d %H:%M:%S %Y %Z').timestamp()))" "$enddate" 2>/dev/null
}

cert_end_human() {
    openssl x509 -in "$1" -noout -enddate 2>/dev/null | cut -d= -f2
}

# 运行 acme.sh 并把输出同时显示和保存, 返回 acme.sh 的退出码
ACME_OUT=""
run_acme() {
    ACME_OUT="$(mktemp)"
    "$ACME_SH" "$@" 2>&1 | tee "$ACME_OUT"
    return "${PIPESTATUS[0]}"
}

show_status() {
    local webroot="" pending="no" exp="" dns=""
    webroot="$(conf_get Le_Webroot || true)"
    has_pending_challenge && pending="yes"

    echo ""
    echo -e "${BLUE}========== radio.vlsc.net 证书状态 ==========${NC}"
    echo "  验证方式:     ${webroot:-（未配置）}$([ "$webroot" = dns ] && echo '（手动 DNS）')$([ "$webroot" = dns_ali ] && echo '（阿里云 API，自动）')"
    echo "  待验证挑战:   $([ "$pending" = yes ] && echo '有（需完成第 2 步）' || echo '无')"

    if [ "$pending" = yes ]; then
        exp="$(expected_txt || true)"
        echo "  期望 TXT 值:  ${exp:-（无法从配置解析）}"
        dns="$(dns_txt_all | tr '\n' ' ' | sed 's/ *$//' || true)"
        if [ -z "$dns" ]; then
            echo -e "  DNS 当前值:   ${YELLOW}（未查询到 TXT 记录）${NC}"
        else
            echo "  DNS 当前值:   $dns"
            if [ -n "$exp" ] && dns_has_txt "$exp"; then
                echo -e "  DNS 校验:     ${GREEN}已包含期望值 ✓${NC}"
            else
                echo -e "  DNS 校验:     ${YELLOW}不包含期望值/尚未生效${NC}"
            fi
        fi
    fi

    [ -f "$DOMAIN_DIR/$DOMAIN.cer" ] && echo "  acme 证书:    有效期至 $(cert_end_human "$DOMAIN_DIR/$DOMAIN.cer" || echo '?')"
    [ -f "$DEPLOY_PEM" ] && echo "  已部署 pem:   有效期至 $(cert_end_human "$DEPLOY_PEM" || echo '?')"
    [ -f "$DEPLOY_FULLCHAIN" ] && echo "  已部署 chain: 有效期至 $(cert_end_human "$DEPLOY_FULLCHAIN" || echo '?')"
    echo -e "${BLUE}============================================${NC}"
    echo ""
    echo "  提示: 定时任务每天 07:48 自动尝试续期; 另见 crontab 中的每日到期检查。"
    echo "        阿里云 DNS API 可用时可运行 ./setup_ssl_auto.sh 实现免手动续期。"
    echo ""
}

verify_deployed() {
    local ok=0
    for f in "$DEPLOY_PEM" "$DEPLOY_FULLCHAIN"; do
        if [ ! -f "$f" ]; then
            echo -e "${RED}✗ 缺少部署文件: $f${NC}"; ok=1; continue
        fi
        echo "  $f -> 有效期至 $(cert_end_human "$f")"
    done
    if [ -f "$DEPLOY_PEM" ] && [ -f "$DEPLOY_KEY" ]; then
        local a b
        a="$(openssl x509 -in "$DEPLOY_PEM" -noout -pubkey | openssl md5)"
        b="$(openssl ec -in "$DEPLOY_KEY" -pubout 2>/dev/null | openssl md5)"
        if [ "$a" != "$b" ]; then
            echo -e "${RED}✗ 部署的证书与私钥不匹配!${NC}"; ok=1
        fi
    fi
    return $ok
}

if [ "$MODE" = "status" ]; then
    show_status
    exit 0
fi

# ---------- 主流程 ----------

WEBROOT="$(conf_get Le_Webroot || true)"

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  MRRC SSL 证书续期  $DOMAIN${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# 当前是 API 自动模式时, 默认不破坏它
if [ -n "$WEBROOT" ] && [ "$WEBROOT" != "dns" ] && [ "$FORCE_MANUAL" != "1" ]; then
    echo -e "${YELLOW}当前验证方式是 '$WEBROOT'（自动模式），本脚本不会改动它。${NC}"
    echo ""
    echo "如需立即强制续期（走现有自动方式）:"
    echo "  $ACME_SH --renew -d $DOMAIN --ecc --force"
    echo ""
    echo "如需强制改回手动 DNS 模式（会关闭自动续期）:"
    echo "  $0 --force-manual"
    echo ""
    exit 0
fi

# ---------- 第 2 步: 有挂起挑战, 检查 DNS 后验证签发 ----------
if has_pending_challenge; then
    echo -e "${BLUE}检测到未完成的验证（第 2 步）。${NC}"
    echo ""

    EXP="$(expected_txt || true)"
    if [ -z "$EXP" ]; then
        echo -e "${RED}无法从配置解析出挑战值（Le_Vlist 异常）。${NC}"
        echo "可执行下面命令清除挂起状态后重新运行本脚本:"
        echo "  sed -i '' '/^Le_Vlist=/d' \"$DOMAIN_CONF\""
        exit 1
    fi

    DNSVAL="$(dns_txt_all | tr '\n' ' ' | sed 's/ *$//' || true)"
    echo "  需要添加到 DNS 的 TXT 记录:"
    echo "    主机记录:  _acme-challenge.$DOMAIN"
    echo "    记录值:    $EXP"
    echo ""
    if dns_has_txt "$EXP"; then
        echo -e "  DNS 校验: ${GREEN}已生效 ✓${NC}"
    else
        echo -e "  DNS 校验: ${YELLOW}尚未生效（当前查询到: ${DNSVAL:-无}）${NC}"
        echo "  （同名旧 TXT 记录可保留，验证时只要求包含期望值）"
        echo ""
        echo -e "${YELLOW}请在 DNS 管理面板添加/更新上面的 TXT 记录。${NC}"
        echo "TXT 记录传播通常需要几分钟，可稍后用以下命令确认，然后重新运行本脚本:"
        echo ""
        echo "  $0 --status"
        echo ""
        echo -e "${YELLOW}如果你确定这次挂起挑战已经作废（例如隔了太久），可选：${NC}"
        echo "  清除挂起状态后重新开始:"
        echo "    read -p '确认清除? (y/n): ' a; [ \"\$a\" = y ] && sed -i '' '/^Le_Vlist=/d' \"$DOMAIN_CONF\""
        echo "  然后重新运行本脚本生成新的挑战值。"
        exit 0
    fi

    echo ""
    echo "正在提交验证并签发（可能需要 1 分钟左右）..."
    echo ""
    OLD_END="$(cert_end_epoch "$DOMAIN_DIR/$DOMAIN.cer" || true)"
    run_acme --renew -d "$DOMAIN" --ecc --yes-I-know-dns-manual-mode-enough-go-ahead-please
    rc=$?
    echo ""

    if [ "$rc" != "0" ]; then
        echo -e "${RED}验证/签发失败（退出码 $rc）。${NC}"
        echo "常见原因: TXT 记录未生效、DNS 未传播、或在别处已消费该挑战。"
        echo "可查看完整日志或重试:"
        echo "  tail -50 /tmp/acme_*.log 2>/dev/null"
        echo "  $0 --status"
        exit 1
    fi
else
    # ---------- 第 1 步: 生成订单并输出 TXT 记录 ----------
    echo -e "${BLUE}没有待验证的挑战，执行第 1 步：生成订单和 TXT 记录。${NC}"
    echo ""

    run_acme --issue -d "$DOMAIN" --ecc --dns --yes-I-know-dns-manual-mode-enough-go-ahead-please
    rc=$?

    if [ "$rc" = "2" ]; then
        # RENEW_SKIP: 未到续期时间
        echo ""
        echo -e "${GREEN}证书仍在有效期内，未到续期时间。${NC}"
        echo "  下次自动检查时间: $(conf_get Le_NextRenewTimeStr || echo '未知')"
        echo "  当前部署证书:     $(cert_end_human "$DEPLOY_PEM" 2>/dev/null || echo '未知')"
        echo ""
        echo "如需强制立即续期, 加 --force 重新运行:"
        echo "  $ACME_SH --issue -d $DOMAIN --ecc --dns --yes-I-know-dns-manual-mode-enough-go-ahead-please --force"
        exit 0
    fi

    if [ "$rc" = "3" ]; then
        # 手动模式正常路径: 等待 TXT 记录
        TXT_LINE="$(grep -E "TXT value:" "$ACME_OUT" | tail -1 | sed "s/.*TXT value: *'//; s/'.*//")"
        echo ""
        echo -e "${GREEN}========================================${NC}"
        echo -e "${GREEN}  第 1 步完成，请在 DNS 面板添加 TXT 记录${NC}"
        echo -e "${GREEN}========================================${NC}"
        echo ""
        echo "  主机记录:  _acme-challenge.$DOMAIN"
        echo "  记录类型:  TXT"
        echo "  记录值:    ${TXT_LINE:-（请查看上面的 acme.sh 输出）}"
        echo "  说明:      同名旧 TXT 记录不影响验证（含期望值即可），可顺手删除以免累积。"
        echo ""
        echo -e "${YELLOW}添加后等几分钟（可用 '$0 --status' 确认已生效），${NC}"
        echo -e "${YELLOW}然后重新运行本脚本完成签发与部署。${NC}"
        echo ""
        exit 0
    fi

    if [ "$rc" != "0" ]; then
        echo -e "${RED}acme.sh 执行失败（退出码 $rc）。完整日志: $ACME_OUT${NC}"
        exit 1
    fi
fi

# ---------- 成功后的核对 ----------
NEW_END="$(cert_end_epoch "$DOMAIN_DIR/$DOMAIN.cer" || true)"
NOW="$(date +%s)"
if [ -z "$NEW_END" ] || [ "$NEW_END" -le "$NOW" ]; then
    echo -e "${RED}签发流程结束, 但证书文件仍无效或已过期, 请检查上面输出。${NC}"
    exit 1
fi
if [ -n "${OLD_END:-}" ] && [ "$NEW_END" = "$OLD_END" ]; then
    echo -e "${YELLOW}警告: 证书有效期没有变化（可能使用了旧证书文件）。${NC}"
fi

echo -e "${GREEN}✓ 续期成功: 新证书有效期至 $(cert_end_human "$DOMAIN_DIR/$DOMAIN.cer")${NC}"
echo ""
echo "已部署文件:"
if ! verify_deployed; then
    echo ""
    echo -e "${RED}部署核对未通过。可手动重新部署:${NC}"
    echo "  $ACME_SH --install-cert -d $DOMAIN --ecc \\"
    echo "    --cert-file $DEPLOY_PEM \\"
    echo "    --key-file $DEPLOY_KEY \\"
    echo "    --fullchain-file $DEPLOY_FULLCHAIN"
    exit 1
fi

echo ""
if grep -q "Reload error" "$ACME_OUT" 2>/dev/null; then
    echo -e "${RED}✗ 证书已更新, 但服务重启失败（Reload error）。${NC}"
    echo "  请查看 $SCRIPT_DIR/renew_deploy.log 并手动重启:"
    echo "  cd $(dirname "$SCRIPT_DIR") && ./mrrc_multi.sh restart radio1"
    exit 1
elif grep -q "Reload successful" "$ACME_OUT" 2>/dev/null; then
    echo -e "${GREEN}✓ MRRC 已自动重启并加载新证书。${NC}"
else
    echo -e "${YELLOW}注意: 本次未见自动重启记录，请确认服务已加载新证书:${NC}"
    echo "  cd $(dirname "$SCRIPT_DIR") && ./mrrc_multi.sh restart radio1"
fi
echo ""
