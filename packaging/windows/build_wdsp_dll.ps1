<#
  build_wdsp_dll.ps1 — 在 Windows 上用 MSYS2/MinGW-w64 构建 libwdsp.dll

  背景：WDSP 的 macOS/Linux 构建走 Makefile，Windows 侧只有 MSVC 工程且跑不通
  （MSVC 专有写法 + MSVCRT 符号冲突），所以 Windows 安装包长期没有 WDSP 库。
  本脚本用 mingw-w64 直接编出可用的 libwdsp.dll，并校验导出符号与运行时依赖。

  用法（Windows 构建机）：
      powershell -NoProfile -ExecutionPolicy Bypass -File packaging\windows\build_wdsp_dll.ps1

  前置：
      - MSYS2 装在 C:\msys64（含 mingw-w64-x86_64-gcc、mingw-w64-x86_64-fftw）
      - DSP/wdsp 源码已打上 DSP/patches/ 下的两个 patch（源码包里已是打好的状态）

  产物：DSP/wdsp/libwdsp.dll，并复制到 vendor\wdsp\windows\bin\x64\libwdsp.dll
#>
param(
    [string]$Msys = "C:\msys64\mingw64",
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path,
    [switch]$SkipCopy
)

$ErrorActionPreference = "Stop"

$gcc     = Join-Path $Msys "bin\gcc.exe"
$objdump = Join-Path $Msys "bin\objdump.exe"
foreach ($tool in @($gcc, $objdump)) {
    if (-not (Test-Path $tool)) { throw "找不到 $tool —— 请先安装 MSYS2 mingw-w64 工具链" }
}

$wdspDir = Join-Path $RepoRoot "DSP\wdsp"
$fftw    = Join-Path $Msys "lib\libfftw3.a"        # 静态链接，避免再带 libfftw3-3.dll
if (-not (Test-Path $wdspDir)) { throw "找不到 WDSP 源码目录: $wdspDir" }
if (-not (Test-Path $fftw))    { throw "找不到静态 FFTW: $fftw （pacman -S mingw-w64-x86_64-fftw）" }

Push-Location $wdspDir
try {
    # macOS/Linux 构建残留的 .o 会在 mingw 链接时混进来，先清掉
    Remove-Item *.o -Force -ErrorAction SilentlyContinue

    # 排除 Java/JNI 桥（需要 jni.h），其余全部参与构建
    $sources = Get-ChildItem -Filter *.c |
        Where-Object { $_.Name -ne "org_openhpsdr_dsp_Wdsp.c" } |
        ForEach-Object { $_.Name }
    Write-Host "编译 $($sources.Count) 个 .c …"

    # -static: 不吃 libwinpthread-1.dll / libgcc_s 等运行时依赖
    & $gcc -O2 -w -D _GNU_SOURCE -shared -static -o libwdsp.dll $sources $fftw -lpthread -lm
    if ($LASTEXITCODE -ne 0) { throw "gcc 编译失败 (exit $LASTEXITCODE)" }

    $info = & $objdump -p libwdsp.dll

    # 1) 必须存在的导出符号
    $required = @(
        "OpenChannel", "CloseChannel",
        "SetRXAEMNRRun", "SetRXAEMNRnpeMethod", "SetRXAEMNRgainMethod", "SetRXAEMNRPosition",
        "SetRXAEMNRmaxAttenDb", "SetRXAEMNRdry",          # MRRC NR2 语音保护
        "SetRXANBPFreqs",                                  # MRRC SSB 带通走 nbp0
        "SetRXAAGCMode", "SetRXAAGCTop", "SetRXAPanelGain1", "SetRXABandpassFreqs"
    )
    $missing = $required | Where-Object { -not ($info -match [regex]::Escape($_)) }
    if ($missing) { throw "导出符号缺失: $($missing -join ', ')" }

    # 2) 运行时依赖只允许系统 DLL
    $deps = @($info | Select-String "DLL Name" | ForEach-Object { ($_.Line -replace ".*DLL Name:\s*", "").Trim() })
    $bad = $deps | Where-Object { $_ -notmatch "^(KERNEL32|msvcrt|USER32|ADVAPI32|WS2_32|SHELL32|ole32)\.dll$" }
    if ($bad) { throw "出现非系统运行时依赖: $($bad -join ', ')（应为 -static 链接）" }

    $dll = Get-Item libwdsp.dll
    Write-Host ("✅ libwdsp.dll: {0:N0} bytes" -f $dll.Length)
    Write-Host ("   依赖: {0}" -f ($deps -join ", "))
    Write-Host ("   SHA256: {0}" -f (Get-FileHash libwdsp.dll -Algorithm SHA256).Hash)

    if (-not $SkipCopy) {
        $dest = Join-Path $RepoRoot "vendor\wdsp\windows\bin\x64"
        New-Item -ItemType Directory -Force -Path $dest | Out-Null
        Copy-Item libwdsp.dll (Join-Path $dest "libwdsp.dll") -Force
        Write-Host "   已复制到 vendor\wdsp\windows\bin\x64\libwdsp.dll"
    }
}
finally {
    Pop-Location
}
