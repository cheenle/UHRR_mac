#!/usr/bin/env bash
# 取安装包要内置的外部二进制（当前只有 frpc），逐个校验 SHA-256。
#
#   ./dev_tools/fetch_payload.sh              # 构建前跑；缺件即取，取不到就失败
#   ./dev_tools/fetch_payload.sh --check      # 只校验现状，不联网（CI / 发版门禁用）
#
# 设计要点：
#   * 权威是 packaging/payload.lock（入库）：<平台/文件名>\t<版本>\t<sha256>。
#     二进制本身不入库（.gitignore 的 packaging/payload/）。
#   * 已在本地且哈希符合 lock ⇒ 直接通过，**不联网**。GitHub 在实例侧/本机经常不可达
#     （2026-10-06 实测 github.com 连接超时），构建不能因此失败。
#   * 缺件时才去取：优先用 mrrc_hub 的取件器（它按 frp 官方 checksums 校验），
#     取回来再按 lock 复算一次 —— 两道校验都要过。
#   * 任何一步哈希不符 ⇒ 删除该文件并报错退出（宁可不打包，也不塞来路不明的二进制）。
#   * 退出码：0 全部就位 / 1 缺件或哈希不符 / 2 用法或 lock 不可读。
#
# 硬门禁的理由见 packaging/payload.lock 头部注释与 windows-installer 技能的实测教训：
# 取件脚本会打印"取件完成"并退出 0，而 frpc 一个都没放（官方 checksums 拉不到时按设计整批跳过）。
# 所以判据是**文件在不在、哈希对不对**，不是脚本的退出码或 ✓ 的条数。
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

LOCK="packaging/payload.lock"
OUT="packaging/payload"
HUB_FETCH="../mrrc_hub/deploy/fetch_installer_payload.sh"
CHECK_ONLY=0

case "${1:-}" in
--check) CHECK_ONLY=1 ;;
"") ;;
*)
	echo "用法: $0 [--check]" >&2
	exit 2
	;;
esac

[[ -r "$LOCK" ]] || {
	echo "❌ lock 不可读: $LOCK" >&2
	exit 2
}

sha256_of() {
	if command -v sha256sum >/dev/null 2>&1; then
		sha256sum "$1" | awk '{print $1}'
	else shasum -a 256 "$1" | awk '{print $1}'; fi
}

fail=0
while IFS=$'\t' read -r name version hash; do
	[[ -n "$name" && "$name" != \#* ]] || continue
	plat="${name%%/*}"
	file="${name##*/}"
	dest="$OUT/$plat/$file"

	if [[ -f "$dest" ]]; then
		got="$(sha256_of "$dest")"
		if [[ "$got" == "$hash" ]]; then
			echo "  ✓ $name  v$version  ($got)"
			continue
		fi
		echo "  ✗ ${name}: 本地文件 SHA-256 与 lock 不符（期望 ${hash} 实得 ${got}）—— 已删除" >&2
		rm -f "$dest"
		fail=1
		[[ $CHECK_ONLY = 1 ]] && continue
	fi

	if [[ $CHECK_ONLY = 1 ]]; then
		echo "  ✗ $name: 缺件（--check 不联网取件）" >&2
		fail=1
		continue
	fi

	echo "  · $name: 本地缺件，尝试取件…" >&2
	if [[ -x "$HUB_FETCH" ]]; then
		# --lock /dev/null：本产品不需要 openssl（ssl_bootstrap.py 用 Python cryptography），
		# 也不随包带 install_instance_tunnel.ps1（那是 mrrc_modern 的流程）。只要 frpc。
		MRRC_FRP_VERSION="$version" "$HUB_FETCH" --out "$OUT" --platforms "$plat" --lock /dev/null || true
		# 取件器会把同平台的脚本/配置也放进去，本产品用不到 —— 只留 lock 里点名的文件。
		find "$OUT/$plat" -type f ! -name "$file" -delete 2>/dev/null || true
	else
		echo "    （未找到 ${HUB_FETCH}；请手工把 ${file} 放到 ${dest}）" >&2
	fi

	if [[ -f "$dest" ]]; then
		got="$(sha256_of "$dest")"
		if [[ "$got" == "$hash" ]]; then
			echo "  ✓ $name  v$version  ($got)"
		else
			echo "  ✗ ${name}: 取回来的文件 SHA-256 与 lock 不符（期望 ${hash} 实得 ${got}）—— 已删除" >&2
			rm -f "$dest"
			fail=1
		fi
	else
		echo "  ✗ $name: 取件失败，$dest 仍不存在" >&2
		fail=1
	fi
done <"$LOCK"

if [[ $fail -ne 0 ]]; then
	echo "❌ 安装包内置件不齐 —— 不要继续构建（装出来的包接不进 Cloud Hub）。" >&2
	echo "   lock: $LOCK" >&2
	exit 1
fi
echo "内置件齐备。"
