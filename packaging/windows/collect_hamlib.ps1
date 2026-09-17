# 从本机已安装的 Hamlib 收集 rigctld.exe 与运行所需 DLL 到 vendor（Windows 打包前运行一次即可）
# 用法: powershell -ExecutionPolicy Bypass -File packaging\windows\collect_hamlib.ps1
#       powershell ... -HamlibBin "C:\Program Files\hamlib-w64-4.7.2\bin"
param([string]$HamlibBin = "")
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path))
$vd = Join-Path $root 'vendor\hamlib\windows\bin\x64'

if (-not $HamlibBin) {
    $cand = @()
    $cand += (Get-Command rigctld -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty Source)
    $cand += (Get-ChildItem 'C:\Program Files\hamlib*\bin\rigctld.exe', 'C:\Program Files (x86)\hamlib*\bin\rigctld.exe',
              'C:\hamlib*\bin\rigctld.exe', 'C:\msys64\*\bin\rigctld.exe' -ErrorAction SilentlyContinue |
              Sort-Object LastWriteTime -Descending | Select-Object -First 1 -ExpandProperty FullName)
    $hit = $cand | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
    if (-not $hit) { Write-Error "找不到 rigctld.exe：请先安装 Hamlib（或用 -HamlibBin 指定 bin 目录）"; exit 1 }
    $HamlibBin = Split-Path -Parent $hit
}
Write-Host "Hamlib bin: $HamlibBin"
New-Item -ItemType Directory -Force -Path $vd | Out-Null
# rigctld.exe 的依赖（真机实测 objdump -p）：libhamlib-4.dll、libwinpthread-1.dll；
# libgcc_s_seh-1.dll / libusb-1.0.dll 为传递依赖；全部按原名放入（MRRC 自己的 ctypes 仍用 libhamlib.dll）
foreach ($f in 'rigctld.exe', 'libhamlib-4.dll', 'libgcc_s_seh-1.dll', 'libwinpthread-1.dll', 'libusb-1.0.dll') {
    $src = Join-Path $HamlibBin $f
    if (Test-Path $src) {
        Copy-Item $src $vd -Force
        Write-Host ("  → {0}  {1} KB" -f $f, [int]((Get-Item $src).Length / 1024))
    } else {
        Write-Warning "  缺少 $f（Hamlib 安装可能不完整）"
    }
}
Write-Host "完成。vendor 目录内容："
Get-ChildItem $vd | Sort-Object Name | ForEach-Object { Write-Host ("  {0,8} KB  {1}" -f [int]($_.Length / 1024), $_.Name) }
