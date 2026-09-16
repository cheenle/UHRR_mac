#!/usr/bin/env bash
# 一条命令打 Windows 发行包并发布 —— 在 macOS 仓库根目录执行。
#
#   ./dev_tools/release_windows.sh            # 全流程：上传源码 → VM 构建 → 校验 → 取回 → 提交 → 部署 → 验证
#   ./dev_tools/release_windows.sh --skip-build     # 跳过 VM 构建（用 VM 上已有的产物，仅取回+发布）
#   ./dev_tools/release_windows.sh --no-deploy      # 不部署网站（只出包 + 提交）
#   ./dev_tools/release_windows.sh --dry-run        # 只打印将要做什么
#
# 依赖：本地 ssh 能直连 ham.vlsc.net（再由它跳进 Win11 VM 192.168.122.133）。
# 版本号取自 packaging/windows/MRRC.iss 的 MyAppVersion，构建脚本会自动写进 version.txt。
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

HOST="ham.vlsc.net"
VM_USER="cheenle"
VM_IP="192.168.122.133"
VM_REPO='C:\mrrc'
SRC_ZIP="dist/mrrc_build_src.zip"
LOCAL_EXE="dist/windows/MRRC-Setup.exe"
SITE_EXE="website/downloads/MRRC-Setup.exe"

SKIP_BUILD=0; NO_DEPLOY=0; DRY_RUN=0
for arg in "$@"; do
    case "$arg" in
        --skip-build) SKIP_BUILD=1 ;;
        --no-deploy)  NO_DEPLOY=1 ;;
        --dry-run)    DRY_RUN=1 ;;
        *) echo "未知参数: $arg"; exit 2 ;;
    esac
done

log()  { printf '\033[1;36m==>\033[0m %s\n' "$*"; }
ok()   { printf '\033[1;32m✅ %s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m⚠️  %s\033[0m\n' "$*"; }
run()  { if [ "$DRY_RUN" = 1 ]; then echo "   [dry-run] $*"; else eval "$@"; fi; }

VERSION="$(grep -oE 'MyAppVersion "[^"]+"' packaging/windows/MRRC.iss | head -1 | sed 's/.*"\(.*\)"/\1/')"
[ -n "$VERSION" ] || { echo "无法从 MRRC.iss 读取版本号"; exit 1; }
log "发行版本: V$VERSION"

# ---------- 0. 前置检查 ----------
source_ps1='. "$(dirname "$0")/vm.sh" 2>/dev/null || true'
vm() { ssh -o ConnectTimeout=10 "$HOST" "ssh -o BatchMode=yes -o StrictHostKeyChecking=no ${VM_USER}@${VM_IP} $1"; }
vm_ps() {
    local b64
    b64=$(python3 -c "import base64,sys; print(base64.b64encode(sys.argv[1].encode('utf-16-le')).decode())" \
        "\$ProgressPreference='SilentlyContinue'; [Console]::OutputEncoding=[Text.Encoding]::UTF8; $1")
    ssh -o ConnectTimeout=10 "$HOST" "ssh -o BatchMode=yes -o StrictHostKeyChecking=no ${VM_USER}@${VM_IP} powershell -NoProfile -EncodedCommand $b64"
}

log "检查 $HOST / Win11 VM 可达性"
if [ "$DRY_RUN" = 0 ]; then
    vm 'hostname' >/dev/null 2>&1 || { echo "❌ 无法连接 $HOST（网络/DDNS？）"; exit 1; }
    vm_ps 'hostname' >/dev/null 2>&1 || { echo "❌ 无法连接 Win11 VM ${VM_IP}"; exit 1; }
    ok "构建机可达"
fi

# ---------- 1. 源码包（git 跟踪文件 + DSP/wdsp 源码 + 构建所需运行时文件） ----------
if [ "$SKIP_BUILD" = 0 ]; then
    log "打包源码（含 DSP/wdsp 全部 .c/.h 与补丁）"
    run "venv/bin/python3 - <<'PY'
import os, subprocess, zipfile
tracked=[f for f in subprocess.run(['git','ls-files'],capture_output=True,text=True).stdout.split('\\n') if f and os.path.isfile(f)]
tracked=[f for f in tracked if not f.startswith('website/downloads/')]
dsp=sorted(os.path.join('DSP/wdsp',f) for f in os.listdir('DSP/wdsp')
           if f.endswith(('.c','.h','.md','.sh')) or f.startswith(('Makefile','makefile')))
extra=[f for f in ('win_pack.md','memory_channels.json','MRRC_users.db','windows/MRRC.conf.template') if os.path.isfile(f)]
files=sorted(set(tracked+[f for f in dsp if os.path.isfile(f)]+extra))
out='$SRC_ZIP'
if os.path.exists(out): os.remove(out)
with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    for f in files: z.write(f,f)
print(f'源码包 {len(files)} 文件 / {os.path.getsize(out)/1e6:.1f} MB')
PY"

    log "上传源码到 $HOST → VM"
    run "scp -q $SRC_ZIP $HOST:/tmp/mrrc_build_src.zip"
    run "ssh $HOST 'scp -q -o BatchMode=yes /tmp/mrrc_build_src.zip ${VM_USER}@${VM_IP}:C:/tmp/mrrc_build_src.zip'"

    log "VM 上构建（解压 → PyInstaller → Inno Setup）"
    run "vm_ps \"Set-Location '${VM_REPO}'; Expand-Archive -Path C:\\tmp\\mrrc_build_src.zip -DestinationPath '${VM_REPO}' -Force; \$env:PATH='${VM_REPO}\\venv\\Scripts;'+\$env:PATH; powershell -NoProfile -ExecutionPolicy Bypass -File packaging\\windows\\build.ps1 > C:\\tmp\\build_release.log 2>&1; \\\"build exit=\$LASTEXITCODE\\\"; Get-Content C:\\tmp\\build_release.log -Tail 3\""

    log "VM 上跑热修通道验收（在打包产物上）"
    run "vm_ps \"Set-Location '${VM_REPO}'; & '${VM_REPO}\\venv\\Scripts\\python.exe' packaging\\hotfix\\verify_hotfix.py --app '${VM_REPO}\\dist\\windows\\MRRC' --repo '${VM_REPO}' 2>&1 | Select-Object -Last 12\""
fi

# ---------- 2. 取回产物 ----------
log "取回 MRRC-Setup.exe"
run "ssh $HOST 'scp -q -o BatchMode=yes ${VM_USER}@${VM_IP}:C:/mrrc/dist/windows/MRRC-Setup.exe /tmp/MRRC-Setup-release.exe'"
run "scp -q $HOST:/tmp/MRRC-Setup-release.exe $LOCAL_EXE"
if [ "$DRY_RUN" = 0 ]; then
    SHA="$(shasum -a 256 "$LOCAL_EXE" | awk '{print $1}')"
    SIZE="$(stat -f%z "$LOCAL_EXE")"
    ok "产物 $SIZE bytes  SHA256 $SHA"
    cp "$LOCAL_EXE" "$SITE_EXE"
    ok "已放入 $SITE_EXE"
fi

# ---------- 3. 提交 + 部署 + 线上验证 ----------
if [ "$NO_DEPLOY" = 0 ]; then
    log "产物归档（带版本名）并生成升级清单 latest.json"
    if [ "$DRY_RUN" = 0 ]; then
        PREV="$(python3 -c "import json;print(json.load(open('website/downloads/latest.json')).get('latest',''))" 2>/dev/null || true)"
        # 上一版安装包留档，供 latest.json 的 previous 段（回退入口）
        if [ -n "$PREV" ] && [ -f "website/downloads/MRRC-Setup-${VERSION}.exe" ] = "0" ]; then :; fi
        if [ -n "$PREV" ] && [ "$PREV" != "$VERSION" ] && [ -f website/downloads/MRRC-Setup.exe ]; then
            cp -f website/downloads/MRRC-Setup.exe "website/downloads/MRRC-Setup-${PREV}.exe"
            ok "已把当前线上包归档为 MRRC-Setup-${PREV}.exe（回退用）"
        fi
        venv/bin/python3 dev_tools/make_latest_json.py --version "$VERSION" \
            --installer "$LOCAL_EXE" --previous "${PREV:-}" --notes "${RELEASE_NOTES:-Windows 安装包 $VERSION}" \
            | tail -20
        ok "latest.json 已生成（installer 指向带版本名产物）"
    fi

    log "提交并推送"
    run "git add -A packaging/windows/MRRC.iss www/ README.md CHANGELOG.md website/ dist/RELEASE-${VERSION}.md 2>/dev/null || true"
    run "git add -A website/downloads/MRRC-Setup.exe website/downloads/MRRC-Setup-*.exe website/downloads/latest.json"
    run "git commit -q -m 'release: Windows V${VERSION} 安装包\n\n产物 $(stat -f%z "$LOCAL_EXE" 2>/dev/null || echo ?) bytes\nSHA256 $(shasum -a 256 "$LOCAL_EXE" 2>/dev/null | awk '{print $1}')\nCo-Authored-By: Pi <noreply@pi.dev>' || true"
    run "git push -q origin main"

    log "部署网站"
    run "./deploy_website.sh 2>&1 | tail -5"

    log "线上验证（下载并比对 SHA256）"
    if [ "$DRY_RUN" = 0 ]; then
        curl -s -o /tmp/dl_verify.exe https://www.vlsc.net/mrrc/downloads/MRRC-Setup.exe
        LIVE_SHA="$(shasum -a 256 /tmp/dl_verify.exe | awk '{print $1}')"
        if [ "$LIVE_SHA" = "$SHA" ]; then ok "线上文件与本地逐字节一致（$LIVE_SHA）"; else
            echo "❌ 线上 SHA256 不一致：$LIVE_SHA"; exit 1; fi
        curl -s https://www.vlsc.net/mrrc/ | grep -oE "V${VERSION}[^<]*" | head -3 || true
        curl -s https://www.vlsc.net/mrrc/downloads/latest.json | python3 -c "
import json, sys
m = json.load(sys.stdin)
print('线上 latest.json →', m.get('latest'), '| installer', m.get('installer', {}).get('url', '')[-28:],
      '| previous', (m.get('previous') or {}).get('version'))" || true
    fi
fi

ok "完成：V$VERSION"
echo
echo "热修补丁（以后修 bug 用这个，不重装）："
echo "  python3 packaging/hotfix/make_hotfix.py --version ${VERSION%.*}.$(( ${VERSION##*.} + 1 )) www/controls.js wdsp_wrapper.py"
echo "  cp dist/hotfix/* website/downloads/ && ./deploy_website.sh"
