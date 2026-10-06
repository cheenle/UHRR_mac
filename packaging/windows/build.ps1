$ErrorActionPreference = "Stop"

# $ErrorActionPreference does NOT apply to native commands (python, pyinstaller,
# iscc) — check $LASTEXITCODE explicitly so a failing test or build aborts the
# packaging instead of silently shipping a broken installer.
function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true, Position = 0)][string]$Command,
        [Parameter(ValueFromRemainingArguments = $true)]$Remaining
    )
    $flat = @()
    foreach ($a in $Remaining) { $flat += $a }
    & $Command @flat
    if ($LASTEXITCODE -ne 0) {
        throw "$Command $($flat -join ' ') failed with exit code $LASTEXITCODE"
    }
}

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$DistRoot = Join-Path $RepoRoot "dist\windows"
$AppRoot = Join-Path $DistRoot "MRRC"
$PyInstallerRoot = Join-Path $DistRoot "_pyinstaller"

Set-Location $RepoRoot

# 中文 Windows 控制台是 cp936：测试/工具会打印 emoji，必须让子进程用 UTF-8 输出，
# 否则 unittest 会因为 UnicodeEncodeError 变成假失败。
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"

# Compile every .py at the repo root as a quick syntax gate.
$pyFiles = Get-ChildItem -Name *.py
if ($pyFiles) {
    Invoke-Checked python -m py_compile @pyFiles
}

# Run the test suite if one exists.
if (Test-Path (Join-Path $RepoRoot "tests")) {
    Invoke-Checked python -m unittest discover -s tests -v
}

# Windows-specific regression gate: config/text encoding robustness.
# History: GBK-written MRRC.conf (locale write path / Notepad ANSI) crashed
# startup with UnicodeDecodeError when the reader was pinned to UTF-8.
# Never ship an installer that fails this test.
Invoke-Checked python dev_tools\test_config_encoding.py

# Warn about missing native libraries.  The installer will still build, but the
# app needs these DLLs at runtime on Windows.
$vendorChecks = @(
    @{ Paths = @("vendor\opus\windows\bin\x64\opus.dll"); Description = "Opus audio (RX/TX)" },
    @{ Paths = @("vendor\hamlib\windows\bin\x64\libhamlib.dll", "vendor\hamlib\windows\bin\x64\hamlib.dll"); Description = "Hamlib radio control" },
    @{ Paths = @("vendor\wdsp\windows\bin\x64\libwdsp.dll", "vendor\wdsp\windows\bin\x64\wdsp.dll"); Description = "WDSP DSP" }
)
foreach ($check in $vendorChecks) {
    $present = $false
    foreach ($rel in $check.Paths) {
        $full = Join-Path $RepoRoot $rel
        if (Test-Path $full) {
            $present = $true
            break
        }
    }
    if (!$present) {
        Write-Warning "Missing $($check.Description) runtime library: $($check.Paths -join ' or ')"
    }
}

Invoke-Checked pyinstaller packaging\pyinstaller\mrrc_server.spec --noconfirm --distpath "$PyInstallerRoot" --workpath "build\pyinstaller"
Invoke-Checked pyinstaller packaging\pyinstaller\mrrc_launcher.spec --noconfirm --distpath "$PyInstallerRoot" --workpath "build\pyinstaller"
Invoke-Checked pyinstaller packaging\pyinstaller\atr1000_proxy.spec --noconfirm --distpath "$PyInstallerRoot" --workpath "build\pyinstaller"

if (Test-Path $AppRoot) {
    Remove-Item $AppRoot -Recurse -Force
}
New-Item -ItemType Directory -Path $AppRoot | Out-Null

# 版本标记：启动器读它来判断是否需要应用热补丁（package-hotfix 通道）
$appVersion = (Select-String -Path (Join-Path $PSScriptRoot "MRRC.iss") -Pattern 'MyAppVersion "([^"]+)"' `
    | ForEach-Object { $_.Matches[0].Groups[1].Value } | Select-Object -First 1)
if ($appVersion) {
    Set-Content -Path (Join-Path $AppRoot "version.txt") -Value $appVersion -Encoding ASCII -NoNewline
    Write-Host "Version marker: version.txt = $appVersion"
} else {
    Write-Warning "Could not read MyAppVersion from MRRC.iss; version.txt not written"
}

Copy-Item (Join-Path $PyInstallerRoot "MRRC-Server\*") $AppRoot -Recurse -Force
Copy-Item (Join-Path $PyInstallerRoot "MRRC-Launcher.exe") $AppRoot -Force
Copy-Item (Join-Path $PyInstallerRoot "ATR1000-Proxy.exe") $AppRoot -Force
Copy-Item (Join-Path $RepoRoot "windows") $AppRoot -Recurse -Force
# Do not ship stale bytecode caches in the installer.
Remove-Item (Join-Path $AppRoot "windows\__pycache__") -Recurse -Force -ErrorAction SilentlyContinue

# Copy any vendor trees that are present.
$VendorRoot = Join-Path $RepoRoot "vendor"
if (Test-Path $VendorRoot) {
    Copy-Item $VendorRoot (Join-Path $AppRoot "vendor") -Recurse -Force
}

# Cloud Hub（内网穿透）的内置件：frpc 隧道客户端。权威是 packaging/payload.lock（入库），
# 二进制本身不入库，构建前由 dev_tools/fetch_payload.sh 取到 packaging/payload/ 并校验哈希。
#
# 为什么是硬要求而不是像上面 vendor 那样只告警：冻结包里 _cloud_fleet_dir() =
# _runtime_dir()/fleet = **安装目录**\fleet，那里不会有任何 frpc；Windows 用户的 PATH 上一般
# 也没有（~/bin 与 ~/.local/share/mrrc-fleet 是 POSIX 习惯）。缺了它，用户申请/批准全走通了，
# 最后一步起不了隧道（/api/cloud/state 报 frpc_available:false）—— 而这正是本次发版的功能。
# 实例侧网络也未必能访问 GitHub（2026-10-06 实测超时），所以不能让用户自己下载。
# 只给临时试验用：MRRC_ALLOW_MISSING_PAYLOAD=1 显式放行。
#
# 不需要 modern 那套 openssl.exe + 9 个 DLL：本产品的实例证书由 ssl_bootstrap.py 用 Python
# cryptography 签，不调 openssl CLI；也不随包带 install_instance_tunnel.ps1（那是 modern 的流程）。
$PayloadSource = Join-Path $RepoRoot "packaging\payload\windows-amd64"
$FleetDest = Join-Path $AppRoot "fleet"
$AllowMissingPayload = ($env:MRRC_ALLOW_MISSING_PAYLOAD -eq "1")
if (Test-Path (Join-Path $PayloadSource "frpc.exe")) {
    # 先建目录再拷，拷完硬校：目录建不出来 / 文件没到位，都不能让它“看起来成了”。
    if (-not (Test-Path $FleetDest)) { New-Item -ItemType Directory -Path $FleetDest -Force | Out-Null }
    Copy-Item (Join-Path $PayloadSource "frpc.exe") (Join-Path $FleetDest "frpc.exe") -Force
    if (-not (Test-Path (Join-Path $FleetDest "frpc.exe"))) { throw "frpc.exe was not copied into $FleetDest" }
    $frpcSize = (Get-Item (Join-Path $FleetDest "frpc.exe")).Length
    $frpcHash = (Get-FileHash (Join-Path $FleetDest "frpc.exe") -Algorithm SHA256).Hash.ToLower()
    Write-Host "Fleet payload: frpc.exe ($frpcSize bytes, sha256 $frpcHash)"
} elseif ($AllowMissingPayload) {
    Write-Warning "frpc.exe missing ($PayloadSource) - building anyway because MRRC_ALLOW_MISSING_PAYLOAD=1; the installer will NOT be able to set up a Cloud Hub tunnel"
} else {
    throw "fleet payload missing: $PayloadSource\frpc.exe - run dev_tools/fetch_payload.sh first (or set MRRC_ALLOW_MISSING_PAYLOAD=1 to build a test package without it)"
}

# NR3: RNNoise (Xiph 新代, BSD-3) —— MinGW 构建 rnnoise.dll 放进应用模块目录
# （audio_interface.py 同目录查找；构建失败只告警，NR3 在该包内自动降级关闭）
$RnSrc = Join-Path $RepoRoot "DSP\rnnoise"
if (Test-Path (Join-Path $RnSrc "src\denoise.c")) {
    $RnDir = Join-Path $AppRoot "_internal\app"
    $RnOut = Join-Path $RnDir "rnnoise.dll"
    New-Item -ItemType Directory -Force -Path $RnDir | Out-Null
    $gccCmd = Get-Command gcc -ErrorAction SilentlyContinue
    if ($gccCmd) {
        # 注意：不要走 Invoke-Checked —— gcc 的 -I/-O 参数会被 PowerShell 函数参数绑定误解析
        $gccArgs = @('-O3','-shared','-static','-DHAVE_CONFIG_H',"-I$RnSrc","-I$RnSrc\include","-I$RnSrc\src",'-DNDEBUG',
            "$RnSrc\src\rnnoise_data.c","$RnSrc\src\rnnoise_tables.c","$RnSrc\src\rnn.c","$RnSrc\src\pitch.c",
            "$RnSrc\src\nnet.c","$RnSrc\src\nnet_default.c","$RnSrc\src\parse_lpcnet_weights.c",
            "$RnSrc\src\kiss_fft.c","$RnSrc\src\denoise.c","$RnSrc\src\celt_lpc.c",'-o',$RnOut)
        & gcc @gccArgs
        if ($LASTEXITCODE -ne 0) { throw "gcc rnnoise.dll failed with exit code $LASTEXITCODE" }
        Copy-Item $RnOut (Join-Path $DistRoot "rnnoise.dll") -Force
        Write-Host "NR3: rnnoise.dll built -> $RnOut"
    } else {
        Write-Warning "gcc not found: skip rnnoise.dll (NR3 degrades to off in this package)"
    }
}

if (Get-Command iscc -ErrorAction SilentlyContinue) {
    # Build into a scratch directory and copy the result into place. Measured on the build VM
    # (mrrc_modern, 2026-10-02): iscc aborts with "The output file appears to be in use (32)"
    # because real-time antivirus keeps the freshly written exe open, and it cannot recover from
    # that - while a plain copy of the finished file succeeds every time. Worse, the stale
    # MRRC-Setup.exe from the previous build is still sitting in dist\windows, so a failed iscc
    # leaves a *plausible-looking old artifact* behind.
    $scratch = Join-Path $env:TEMP ("mrrc-iscc-" + [guid]::NewGuid().ToString("N").Substring(0, 8))
    New-Item -ItemType Directory -Path $scratch -Force | Out-Null
    # Remove the previous artifact first: if iscc fails, a stale MRRC-Setup.exe left in
    # dist\windows still looks like a successful build (this burned three rounds on
    # mrrc_modern v1.24.6). After this line, "the file exists" can only mean "this build made it".
    Remove-Item (Join-Path $DistRoot "MRRC-Setup.exe") -Force -ErrorAction SilentlyContinue
    Invoke-Checked iscc "/O$scratch" packaging\windows\MRRC.iss
    Copy-Item (Join-Path $scratch "MRRC-Setup.exe") (Join-Path $DistRoot "MRRC-Setup.exe") -Force
    Remove-Item $scratch -Recurse -Force -ErrorAction SilentlyContinue
} else {
    Write-Warning "Inno Setup Compiler 'iscc' was not found. Install Inno Setup and rerun this script to create the setup EXE."
}

Write-Host "Assembled app: $AppRoot"
Write-Host "Installer output: $(Join-Path $DistRoot 'MRRC-Setup.exe')"
