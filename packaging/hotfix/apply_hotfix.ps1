<#
  apply_hotfix.ps1 —— 把热修补丁包应用到已安装的 MRRC（不必重装）

  适用两种目标：

    1) 覆盖层模式（推荐，6.0.3+ 安装包，无需管理员）
       powershell -ExecutionPolicy Bypass -File apply_hotfix.ps1 -Pack hotfix-6.0.4.zip
       → 解到 %LOCALAPPDATA%\MRRC\patch\（app/、www/、vendor/），重启 MRRC 生效
       （6.0.3+ 的启动器也会自动从 https://www.vlsc.net/mrrc/downloads/patch.json 拉取，
        本模式主要用于离线/手动安装，或把热修包分发给别人）

    2) 就地模式（仅 6.0.2 及更早的安装包，需要管理员）
       powershell -ExecutionPolicy Bypass -File apply_hotfix.ps1 -Pack hotfix-x.zip -InPlace
       → 覆盖 <安装目录>\_internal\www\** 与 vendor\...\*.dll，并备份为 *.bak-<版本>

  重要限制（脚本会检查并拒绝）：
    6.0.2 及更早把应用代码（MRRC、wdsp_wrapper.py …）冻结在 exe 的 PYZ 里，磁盘覆盖无效
    （实测见 patch_overlay.py 头部）。这类补丁必须用 6.0.3+ 安装包或完整重装，
    脚本遇到 app/* 条目会明确报错而不是“假装修好了”。
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Pack,
    [string]$InstallDir = "$env:ProgramFiles\MRRC",
    [switch]$InPlace,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

function Fail($msg) { Write-Host "❌ $msg" -ForegroundColor Red; exit 1 }
function Info($msg) { Write-Host "   $msg" }
function Ok($msg)   { Write-Host "✅ $msg" -ForegroundColor Green }

if (-not (Test-Path $Pack)) { Fail "找不到补丁包: $Pack" }
$Pack = (Resolve-Path $Pack).Path

# ---- 1. 校验补丁包（manifest.json + 每文件 SHA256）----
Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip = [System.IO.Compression.ZipFile]::OpenRead($Pack)
try {
    $manifestEntry = $zip.Entries | Where-Object { $_.FullName -eq 'manifest.json' }
    if (-not $manifestEntry) { Fail "补丁包缺少 manifest.json" }
    $reader = New-Object System.IO.StreamReader($manifestEntry.Open())
    $manifest = $reader.ReadToEnd() | ConvertFrom-Json
    $reader.Close()
    Info "补丁版本: $($manifest.version)   需要安装版本 >= $($manifest.requires)"
    if ($manifest.notes) { Info "说明: $($manifest.notes)" }

    $sha = [System.Security.Cryptography.SHA256]::Create()
    foreach ($entry in $zip.Entries) {
        if ($entry.FullName -eq 'manifest.json' -or $entry.FullName -eq '') { continue }
        $expected = ($manifest.files | Where-Object { $_.path -eq $entry.FullName }).sha256
        if (-not $expected) { Fail "manifest.json 里没有 $($entry.FullName) 的哈希" }
        $stream = $entry.Open()
        $hash = ([BitConverter]::ToString($sha.ComputeHash($stream)) -replace '-', '').ToLower()
        $stream.Close()
        if ($hash -ne $expected.ToLower()) { Fail "$($entry.FullName) SHA256 不符" }
    }
    Ok "补丁包完整性校验通过（$($manifest.files.Count) 个文件）"
}
finally { $zip.Dispose() }

# ---- 2. 选择目标目录 ----
$staging = Join-Path $env:TEMP ("mrrc-hotfix-" + $manifest.version)
if (Test-Path $staging) { Remove-Item $staging -Recurse -Force }
Expand-Archive -Path $Pack -DestinationPath $staging -Force

if ($InPlace) {
    $target = Join-Path $InstallDir "_internal"
    $vendorTarget = Join-Path $InstallDir "vendor"

    $appEntries = $manifest.files | Where-Object { $_.path -like 'app/*' }
    if ($appEntries) {
        Fail ("此补丁包含服务端 Python 代码（app/…），但 $InstallDir 是 6.0.2 或更早的安装：" +
              "应用代码被冻结在 exe 的 PYZ 里，磁盘覆盖无效（实测）。请改用 6.0.3+ 安装包，" +
              "或完整重装。")
    }
    if (-not (Test-Path $target)) { Fail "找不到安装目录: $InstallDir（可用 -InstallDir 指定）" }

    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $elevated = (New-Object Security.Principal.WindowsPrincipal($identity)).IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator)
    if (-not $elevated -and -not $DryRun) {
        Fail "就地模式需要管理员权限（安装目录在 Program Files）。请以管理员身份重开 PowerShell。"
    }

    foreach ($file in $manifest.files) {
        if ($file.path -like 'www/*') {
            $dest = Join-Path $target ("www\" + ($file.path -replace '^www/', '' -replace '/', '\'))
        } elseif ($file.path -like 'vendor/*') {
            $dest = Join-Path $InstallDir ($file.path -replace '/', '\')
        } else { Fail "不支持的路径: $($file.path)" }

        $src = Join-Path $staging ($file.path -replace '/', '\')
        if (-not (Test-Path $src)) { Fail "补丁包内缺少 $($file.path)" }
        $destDir = Split-Path $dest -Parent
        if (-not (Test-Path $destDir)) { New-Item -ItemType Directory -Path $destDir -Force | Out-Null }
        if (Test-Path $dest) {
            $backup = "$dest.bak-$($manifest.version)"
            if (-not $DryRun) { Copy-Item $dest $backup -Force }
            Info "备份 $dest -> $(Split-Path $backup -Leaf)"
        }
        if ($DryRun) { Info "[dry-run] 将写入 $dest" }
        else { Copy-Item $src $dest -Force; Ok "写入 $dest" }
    }
    Info "重启 MRRC（或重启 MRRC-Launcher）后生效。"
    exit 0
}

# ---- 3. 覆盖层模式（默认，无需管理员）----
$patchRoot = Join-Path $env:LOCALAPPDATA "MRRC\patch"
if ($DryRun) { Info "[dry-run] 将解到 $patchRoot"; exit 0 }
New-Item -ItemType Directory -Path $patchRoot -Force | Out-Null
Get-ChildItem -Path $staging | Where-Object { $_.Name -ne 'manifest.json' } | ForEach-Object {
    Copy-Item $_.FullName (Join-Path $patchRoot $_.Name) -Recurse -Force
}
$applied = Join-Path $patchRoot "applied.json"
$record = @{ appliedAt = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss"); version = $manifest.version
             files = @($manifest.files | ForEach-Object { $_.path }) }
if (Test-Path $applied) {
    $history = Get-Content $applied -Raw | ConvertFrom-Json
    if ($history -isnot [array]) { $history = @($history) }
    $history = @($history) + $record
} else { $history = @($record) }
$history | ConvertTo-Json -Depth 6 | Set-Content $applied -Encoding UTF8

Ok "已应用到覆盖层: $patchRoot"
Info "文件: $((@($manifest.files) | ForEach-Object { $_.path }) -join ', ')"
Info "重启 MRRC-Launcher 后生效（服务端 Python 覆盖需重启；www 覆盖刷新浏览器即可）。"
