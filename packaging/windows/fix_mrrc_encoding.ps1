<#
.SYNOPSIS
  MRRC 配置编码修复工具（修复中文 Windows 启动 UnicodeDecodeError）

.DESCRIPTION
  旧版 Windows 安装包（V6.0.0 - V6.0.2）在中文 Windows 上会把 MRRC.conf
  按 GBK(cp936) 写回（设置页保存 / 记事本另存 ANSI）；而服务器启动时固定
  按 UTF-8 读配置，于是启动即报：

      UnicodeDecodeError: 'utf-8' codec can't decode byte 0xd5 in position ...

  服务器起不来，浏览器打不开。

  本工具把 %LOCALAPPDATA%\MRRC\MRRC.conf 转为 UTF-8（无 BOM），原文件保留
  为 MRRC.conf.bak，并可选地启动 MRRC。

  注意：旧版安装包在网页"设置页保存"后仍会写回 GBK。启动失败时重跑本工具
  即可；或改用同目录的 fix_and_start_mrrc.bat 启动（每次先修后启）。

.PARAMETER DataDir
  MRRC 数据目录，默认 %LOCALAPPDATA%\MRRC

.PARAMETER IncludeAux
  同时转换 MRRC_users.db / memory_channels.json / atr1000_tuner.json
  （默认只修 MRRC.conf —— 只有它会在启动时被强制按 UTF-8 读取）

.PARAMETER Launch
  修复完成后启动 MRRC-Launcher.exe

.PARAMETER CreateShortcut
  在桌面创建"MRRC 修复并启动"快捷方式（指向本目录 fix_and_start_mrrc.bat）

.PARAMETER DryRun
  只检查不写文件

.PARAMETER SelfTest
  自检：在临时目录验证 GBK / UTF-16 / UTF-8(BOM) 的识别与转换逻辑

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File fix_mrrc_encoding.ps1
  powershell -NoProfile -ExecutionPolicy Bypass -File fix_mrrc_encoding.ps1 -Launch
  powershell -NoProfile -ExecutionPolicy Bypass -File fix_mrrc_encoding.ps1 -SelfTest
#>
[CmdletBinding()]
param(
    [string]$DataDir = '',
    [switch]$IncludeAux,
    [switch]$Launch,
    [switch]$CreateShortcut,
    [switch]$DryRun,
    [switch]$SelfTest
)

$ErrorActionPreference = 'Stop'

function Write-Head { param([string]$Text) Write-Host ''; Write-Host "== $Text" -ForegroundColor Cyan }
function Write-Ok   { param([string]$Text) Write-Host "  [OK]   $Text" -ForegroundColor Green }
function Write-Fix  { param([string]$Text) Write-Host "  [修复] $Text" -ForegroundColor Yellow }
function Write-Skip { param([string]$Text) Write-Host "  [跳过] $Text" -ForegroundColor DarkGray }
function Write-Warn { param([string]$Text) Write-Host "  [注意] $Text" -ForegroundColor Yellow }
function Write-Err  { param([string]$Text) Write-Host "  [错误] $Text" -ForegroundColor Red }

# 本机 ANSI 代码页（中文 Windows = 936）。PowerShell 7 下 ::Default 是 UTF-8，
# 所以显式用当前区域的 ANSI 代码页，取不到就退回 GBK。
function Get-LegacyEncoding {
    $cp = 0
    try { $cp = [System.Globalization.CultureInfo]::CurrentCulture.TextInfo.ANSICodePage } catch { $cp = 0 }
    if ($cp -eq 0 -or $cp -eq 65001) { $cp = 936 }
    foreach ($candidate in @($cp, 936, 950, 1252, 932, 949)) {
        try { return [System.Text.Encoding]::GetEncoding($candidate) } catch { }
    }
    return $null   # 无可用传统代码页：宁可拒绝转换，也不能用 ASCII/UTF-8 解码损坏数据
}

# 字节 -> (文本, 来源编码)。来源: utf-8 / utf-8-bom / utf-16 / legacy
function Convert-BytesToText {
    param([byte[]]$Bytes, [System.Text.Encoding]$Legacy)

    if ($Bytes.Length -ge 2 -and $Bytes[0] -eq 0xFF -and $Bytes[1] -eq 0xFE) {
        return @{ Text = [System.Text.Encoding]::Unicode.GetString($Bytes, 2, $Bytes.Length - 2); Source = 'utf-16' }
    }
    if ($Bytes.Length -ge 2 -and $Bytes[0] -eq 0xFE -and $Bytes[1] -eq 0xFF) {
        return @{ Text = [System.Text.Encoding]::BigEndianUnicode.GetString($Bytes, 2, $Bytes.Length - 2); Source = 'utf-16' }
    }
    if ($Bytes.Length -ge 3 -and $Bytes[0] -eq 0xEF -and $Bytes[1] -eq 0xBB -and $Bytes[2] -eq 0xBF) {
        # UTF-8 BOM 也会让 configparser 解析失败（首行变成 BOM+[SECTION]），需要去 BOM
        return @{ Text = [System.Text.Encoding]::UTF8.GetString($Bytes, 3, $Bytes.Length - 3); Source = 'utf-8-bom' }
    }
    try {
        $strict = New-Object System.Text.UTF8Encoding -ArgumentList @($false, $true)
        return @{ Text = $strict.GetString($Bytes); Source = 'utf-8' }
    } catch { }
    return @{ Text = $Legacy.GetString($Bytes); Source = 'legacy' }
}

function Repair-File {
    param([string]$Path, [System.Text.Encoding]$Legacy, [bool]$DryRun)

    $name = [System.IO.Path]::GetFileName($Path)
    if (-not (Test-Path -LiteralPath $Path)) { Write-Skip "$name 不存在"; return $false }
    try {
        $bytes = [System.IO.File]::ReadAllBytes($Path)
    } catch {
        Write-Err "$name 读取失败：$($_.Exception.Message)"; return $false
    }
    $result = Convert-BytesToText -Bytes $bytes -Legacy $Legacy
    if ($result.Source -eq 'utf-8') { Write-Skip "$name 已是 UTF-8（$($bytes.Length) 字节）"; return $false }

    $label = switch ($result.Source) {
        'utf-16'    { 'UTF-16' }
        'utf-8-bom' { 'UTF-8(BOM)' }
        default     { "$($Legacy.WebName.ToUpper()) (代码页 $($Legacy.CodePage))" }
    }
    if ($DryRun) { Write-Fix "[预演] $name：$label -> UTF-8"; return $true }

    $backup = $Path + '.bak'
    try {
        if (-not (Test-Path -LiteralPath $backup)) {
            [System.IO.File]::WriteAllBytes($backup, $bytes)
        }
        $utf8NoBom = New-Object System.Text.UTF8Encoding -ArgumentList @($false)
        [System.IO.File]::WriteAllText($Path, $result.Text, $utf8NoBom)
        Write-Fix "$name：$label -> UTF-8（原文件已备份为 $name.bak）"
        return $true
    } catch {
        Write-Err "$name 写入失败：$($_.Exception.Message)"
        return $false
    }
}

function Find-Launcher {
    $candidates = @()
    if (${env:ProgramFiles}) { $candidates += (Join-Path ${env:ProgramFiles} 'MRRC\MRRC-Launcher.exe') }
    if (${env:ProgramFiles(x86)}) { $candidates += (Join-Path ${env:ProgramFiles(x86)} 'MRRC\MRRC-Launcher.exe') }
    if ($env:LOCALAPPDATA) { $candidates += (Join-Path $env:LOCALAPPDATA 'Programs\MRRC\MRRC-Launcher.exe') }
    foreach ($c in $candidates) { if (Test-Path -LiteralPath $c) { return $c } }
    return $null
}

function Start-Mrrc {
    $exe = Find-Launcher
    if (-not $exe) {
        Write-Warn '未找到 MRRC-Launcher.exe，请从开始菜单启动 MRRC。'
        return
    }
    Write-Ok "启动 $exe"
    Start-Process -FilePath $exe -WorkingDirectory (Split-Path -Parent $exe)
}

function New-DesktopShortcut {
    $bat = Join-Path $PSScriptRoot 'fix_and_start_mrrc.bat'
    if (-not (Test-Path -LiteralPath $bat)) {
        Write-Warn "同目录未找到 fix_and_start_mrrc.bat，跳过创建快捷方式。"
        return
    }
    try {
        $desktop = [Environment]::GetFolderPath('Desktop')
        $lnk = Join-Path $desktop 'MRRC 修复并启动.lnk'
        $shell = New-Object -ComObject WScript.Shell
        $sc = $shell.CreateShortcut($lnk)
        $sc.TargetPath = $bat
        $sc.WorkingDirectory = $PSScriptRoot
        $sc.Description = 'MRRC 配置编码修复并启动（旧版安装包 GBK 问题）'
        $sc.Save()
        Write-Ok "桌面快捷方式已创建：$lnk"
    } catch {
        Write-Warn "创建快捷方式失败：$($_.Exception.Message)"
    }
}

function Invoke-SelfTest {
    Write-Head '自检（编码识别与转换）'
    $tmp = Join-Path ([System.IO.Path]::GetTempPath()) ('mrrc_fix_selftest_' + [Guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $tmp | Out-Null
    $legacy = Get-LegacyEncoding
    if ($null -eq $legacy) { Write-Err '本机缺少 GBK 代码页，无法自检 legacy 分支'; return 1 }
    $gbk = $null
    try { $gbk = [System.Text.Encoding]::GetEncoding(936) } catch { }
    $sample = "[SERVER]`r`nlog_file = C:/Users/张伟/MRRC.log`r`nport = 8877`r`n"

    $cases = @(
        @{ Name = 'gbk.conf';   Enc = $gbk;                                    Expect = 'legacy'    },
        @{ Name = 'utf8.conf';  Enc = (New-Object System.Text.UTF8Encoding -ArgumentList @($true));  Expect = 'utf-8-bom' },
        @{ Name = 'plain.conf'; Enc = (New-Object System.Text.UTF8Encoding -ArgumentList @($false)); Expect = 'utf-8'     },
        @{ Name = 'u16.conf';   Enc = [System.Text.Encoding]::Unicode;          Expect = 'utf-16'    }
    )

    $pass = $true
    foreach ($case in $cases) {
        if ($null -eq $case.Enc) { Write-Warn "$($case.Name) 跳过（本机不支持该编码）"; continue }
        $p = Join-Path $tmp $case.Name
        try { [System.IO.File]::WriteAllText($p, $sample, $case.Enc) }
        catch { Write-Warn "$($case.Name) 写入测试文件失败：$($_.Exception.Message)"; continue }
        $r = Convert-BytesToText -Bytes ([System.IO.File]::ReadAllBytes($p)) -Legacy $legacy
        if ($r.Source -eq $case.Expect -and $r.Text -eq $sample) {
            Write-Ok "$($case.Name)：识别为 $($r.Source)，内容无损"
        } else {
            Write-Err "$($case.Name)：期望 $($case.Expect)，实际 $($r.Source)"
            $pass = $false
        }
    }
    Remove-Item -LiteralPath $tmp -Recurse -Force -ErrorAction SilentlyContinue
    if ($pass) { Write-Ok '自检通过'; return 0 }
    Write-Err '自检失败'; return 1
}

function Invoke-Repair {
    if (-not $DataDir) {
        if ($env:LOCALAPPDATA) { $DataDir = Join-Path $env:LOCALAPPDATA 'MRRC' }
        else { $DataDir = Join-Path $HOME 'MRRC' }
    }
    Write-Host ''
    Write-Host '========================================' -ForegroundColor Magenta
    Write-Host '  MRRC 配置编码修复（中文 Windows）' -ForegroundColor Magenta
    Write-Host '========================================' -ForegroundColor Magenta
    Write-Host "数据目录：$DataDir"

    if (-not (Test-Path -LiteralPath $DataDir)) {
        Write-Err "数据目录不存在：$DataDir"
        Write-Host '        MRRC 从未在这台机器上运行过？请先启动一次 MRRC 再运行本工具。' -ForegroundColor DarkGray
        return 1
    }

    $legacy = Get-LegacyEncoding
    if ($null -eq $legacy) {
        Write-Err '本机缺少 GBK/ANSI 代码页支持，无法安全转换（未改动任何文件）。'
        return 1
    }
    Write-Host "本机 ANSI 代码页：$($legacy.CodePage)（$($legacy.WebName)）"

    $running = Get-Process -Name 'MRRC-Server' -ErrorAction SilentlyContinue
    if ($running) {
        Write-Warn '检测到 MRRC-Server 正在运行；修复后需要重启 MRRC 才会生效。'
    }

    Write-Head '转换文件'
    $targets = @('MRRC.conf')
    if ($IncludeAux) { $targets += @('MRRC_users.db', 'memory_channels.json', 'atr1000_tuner.json') }
    $fixed = 0
    foreach ($t in $targets) {
        if (Repair-File -Path (Join-Path $DataDir $t) -Legacy $legacy -DryRun $DryRun.IsPresent) { $fixed++ }
    }

    $confPath = Join-Path $DataDir 'MRRC.conf'
    if ((Test-Path -LiteralPath $confPath) -and -not $DryRun) {
        $text = [System.IO.File]::ReadAllText($confPath, [System.Text.Encoding]::UTF8)
        $nonAscii = 0
        foreach ($ch in $text.ToCharArray()) { if ([int]$ch -gt 127) { $nonAscii++ } }
        if ($nonAscii -gt 0) {
            Write-Head '提示'
            Write-Warn "配置里有 $nonAscii 个非 ASCII 字符（例如中文用户名路径、中文设备名）。"
            Write-Host '        旧版安装包在网页设置页保存后，会再次把它写成 GBK。' -ForegroundColor DarkGray
            Write-Host '        若下次启动失败，重跑本工具；或改用 fix_and_start_mrrc.bat 启动。' -ForegroundColor DarkGray
        }
    }

    Write-Head '结果'
    if ($DryRun) {
        Write-Host "  预演完成：$fixed 个文件需要转换（未改动任何文件）" -ForegroundColor Yellow
    } elseif ($fixed -gt 0) {
        Write-Ok "$fixed 个文件已修复为 UTF-8"
        Write-Host '        请重新启动 MRRC（关闭旧窗口后从开始菜单启动）。' -ForegroundColor DarkGray
    } else {
        Write-Ok '所有文件都已是 UTF-8，无需修复。'
        Write-Host '        如果服务器仍然起不来，请把 MRRC-Server 窗口里的完整报错发我。' -ForegroundColor DarkGray
    }

    if ($CreateShortcut) { Write-Head '桌面快捷方式'; New-DesktopShortcut }
    if ($Launch -and -not $DryRun) { Write-Head '启动'; Start-Mrrc }
    return 0
}

if ($SelfTest) { exit (Invoke-SelfTest) }
exit (Invoke-Repair)
