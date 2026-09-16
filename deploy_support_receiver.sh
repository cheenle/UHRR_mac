#!/usr/bin/env bash
# 部署/更新 MRRC 支持包接收端到 www.vlsc.net（幂等，可重复执行）。
#
#   ./deploy_support_receiver.sh [user@host]
#
# 口令来源（按顺序）：环境变量 SUPPORT_PASSWORD → ~/.mrrc-support-credentials.txt → 随机生成
# 口令只写到服务器 /etc/mrrc-support.env（0600 root），不入库、不打印。
set -euo pipefail

REMOTE="${1:-cheenle@www.vlsc.net}"
HERE="$(cd "$(dirname "$0")" && pwd)"

PW="${SUPPORT_PASSWORD:-}"
if [ -z "$PW" ] && [ -f "$HOME/.mrrc-support-credentials.txt" ]; then
    PW="$(tr -d '\n' < "$HOME/.mrrc-support-credentials.txt")"
fi
if [ -z "$PW" ]; then
    PW="$(python3 -c 'import secrets,string;print("".join(secrets.choice(string.ascii_letters+string.digits) for _ in range(24)))')"
    printf '%s' "$PW" > "$HOME/.mrrc-support-credentials.txt"
    chmod 600 "$HOME/.mrrc-support-credentials.txt"
    echo "已生成新口令 → ~/.mrrc-support-credentials.txt"
fi

echo "==> 准备目录（存储目录归 www-data，且不在站点 docroot 内）"
ssh "$REMOTE" 'sudo mkdir -p /opt/mrrc-support && sudo mkdir -p /var/www/support && sudo chown www-data:www-data /var/www/support && sudo chmod 750 /var/www/support'

echo "==> 上传 server.py / unit / README"
rsync -az "$HERE/tools/support_receiver/server.py" "$REMOTE:/tmp/support-server.py"
rsync -az "$HERE/tools/support_receiver/support-receiver.service" "$REMOTE:/tmp/support-receiver.service"
ssh "$REMOTE" 'sudo install -m 644 /tmp/support-server.py /opt/mrrc-support/server.py && sudo install -m 644 /tmp/support-receiver.service /etc/systemd/system/support-receiver.service'

echo "==> 写入口令（0600，仅 root 可读）"
ssh "$REMOTE" "sudo bash -c 'umask 077; printf \"SUPPORT_PASSWORD=%s\n\" \"$PW\" > /etc/mrrc-support.env'"

echo "==> 启动/重启服务"
ssh "$REMOTE" 'sudo systemctl daemon-reload && sudo systemctl enable --now support-receiver >/dev/null 2>&1; sudo systemctl restart support-receiver; sleep 1; sudo systemctl is-active support-receiver'
ssh "$REMOTE" 'curl -s -o /dev/null -w "  本地探测 /api/list 无口令 → HTTP %{http_code}（应 401）\n" http://127.0.0.1:8099/api/list'

echo "==> 完成。若尚未配置 nginx 反代，见仓库 docs/current/operations/support-bundle.md"
