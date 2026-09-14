#!/bin/bash
# acme.sh 部署钩子: 证书更新后重启正在运行的 MRRC 实例
# 可作为 acme.sh 的 --reloadcmd 使用
# 说明: 原实现固定调用 mrrc_control.sh(默认实例), 在多实例场景
#       (如 radio1 使用 MRRC.radio1.conf) 会重启错误的对象。
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MRRC_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_FILE="$SCRIPT_DIR/deploy.log"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG_FILE"; }

log "证书已更新，开始重启 MRRC 实例..."

# 逐个重启正在运行的实例 (MRRC.<name>.conf)
restarted=0
for cfg in "$MRRC_DIR"/MRRC.*.conf; do
    [ -e "$cfg" ] || continue
    inst="${cfg##*/}"; inst="${inst#MRRC.}"; inst="${inst%.conf}"
    case "$inst" in
        *bak*|*orig*|*9000*) continue ;;
    esac
    # 实例名限制, 与 mrrc_multi.sh 的校验保持一致
    printf '%s' "$inst" | grep -qE '^[A-Za-z0-9_-]+$' || continue

    if pgrep -f "MRRC\.$inst\.conf" >/dev/null 2>&1; then
        log "重启实例: $inst"
        if "$MRRC_DIR/mrrc_multi.sh" restart "$inst" >> "$LOG_FILE" 2>&1; then
            log "✓ $inst 重启成功"
        else
            log "✗ $inst 重启失败"
        fi
        restarted=1
    fi
done

# 没有任何多实例在运行时, 回退到默认单实例方式
if [ "$restarted" = "0" ]; then
    log "未发现运行中的多实例，按默认实例重启 (mrrc_control.sh)"
    if "$MRRC_DIR/mrrc_control.sh" restart >> "$LOG_FILE" 2>&1; then
        log "✓ MRRC 重启成功"
    else
        log "✗ MRRC 重启失败"
        exit 1
    fi
fi

log "部署完成"
