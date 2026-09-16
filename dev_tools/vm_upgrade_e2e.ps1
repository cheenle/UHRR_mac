# MRRC 一键升级端到端验收（在 VM 上以管理员 PowerShell 运行）
# 流程：装基线版本 → 起启动器（后台）→ 等它下载目标版本 → 写哨兵触发升级 → 校验 version.txt
# 结果自动上传到 https://www.vlsc.net/mrrc/support/（维护者列表页可见）
# 注意：本文件含中文，必须存 UTF-8 with BOM（PowerShell 5.1 按 GBK 读会语法崩），且只能有一个 BOM。
param([string]$Base = "6.1.2", [string]$Target = "6.1.3")

$ErrorActionPreference = 'Continue'
$log = 'C:\tmp\upgrade_e2e_report.txt'
function Note($m) { Write-Host $m; Add-Content -Path $log -Value $m -Encoding UTF8 }
"=== MRRC升级端到端验收 $(Get-Date -Format 'HH:mm:ss') 基线=$Base 目标=$Target ===" | Out-File $log -Encoding utf8
Note ("elevated: " + (New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator))
Note ("before: version.txt = " + (Get-Content 'C:\Program Files\MRRC\version.txt' -ErrorAction SilentlyContinue))

# 1) 安装基线版本（第一个自带升级逻辑的版本）
$setup = "C:\tmp\MRRC-Setup-$Base.exe"
if (-not (Test-Path $setup)) {
  Note "下载 $Base 安装包…"
  Invoke-WebRequest -Uri "https://www.vlsc.net/mrrc/downloads/MRRC-Setup-$Base.exe" -OutFile $setup -TimeoutSec 900
}
Note "静默安装 $Base …"
$p = Start-Process -FilePath $setup -ArgumentList '/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART',"/LOG=C:\tmp\install-$Base.log" -PassThru -Wait
Note ("installer exit=" + $p.ExitCode)
Note ("after install: version.txt = " + (Get-Content 'C:\Program Files\MRRC\version.txt' -ErrorAction SilentlyContinue))
if ((Get-Content 'C:\Program Files\MRRC\version.txt' -ErrorAction SilentlyContinue) -ne $Base) { Note "❌ $Base 安装未成功，终止" }

# 2) 清旧状态，后台起启动器（它会看到 latest.json 里的 $Target）
Get-Process MRRC-Server,MRRC-Launcher -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep 2
Remove-Item "$env:LOCALAPPDATA\MRRC\updates\state.json","$env:LOCALAPPDATA\MRRC\updates\upgrade.request" -Force -ErrorAction SilentlyContinue
Note "启动 MRRC-Launcher（后台，日志 C:\tmp\launcher_test.log）…"
Start-Process -FilePath 'cmd.exe' -ArgumentList '/c','"C:\Program Files\MRRC\MRRC-Launcher.exe" > C:\tmp\launcher_test.log 2>&1' -WindowStyle Hidden

# 3) 等新版本下载并校验完成
$staged = $null
for ($i = 0; $i -lt 40; $i++) {
  Start-Sleep -Seconds 6
  try { $state = Get-Content "$env:LOCALAPPDATA\MRRC\updates\state.json" -Raw -Encoding utf8 | ConvertFrom-Json } catch { $state = $null }
  if ($state -and $state.staged -and $state.staged.version -eq $Target) { $staged = $state.staged; break }
}
if ($staged) {
  Note ("✅ 已下载并暂存: " + $staged.version + " (" + [Math]::Round($staged.size/1MB,1) + " MB, sha " + $staged.sha256.Substring(0,12) + "…)")
} else {
  Note "❌ 超时：启动器没有暂存 $Target（看 launcher_test.log）"
}

# 4) 用产品自己的写接口触发升级（等同页面点【立即升级】）
if ($staged) {
  Note "触发升级（upgrade_core.write_upgrade_request，等同页面按钮）…"
  $py = 'C:\mrrc\venv\Scripts\python.exe'
  if (-not (Test-Path $py)) { $py = 'python' }
  $code = "import sys; sys.path.insert(0, r'C:\mrrc'); import upgrade_core as up; up.write_upgrade_request(r'$env:LOCALAPPDATA\MRRC', '$Target')"
  & $py -c $code
  for ($i = 0; $i -lt 60; $i++) {
    Start-Sleep -Seconds 6
    $v = Get-Content 'C:\Program Files\MRRC\version.txt' -ErrorAction SilentlyContinue
    if ($v -eq $Target) { break }
  }
}

# 5) 收尾检查 + 报告
Note ("after upgrade: version.txt = " + (Get-Content 'C:\Program Files\MRRC\version.txt' -ErrorAction SilentlyContinue))
try {
  $s2 = Get-Content "$env:LOCALAPPDATA\MRRC\updates\state.json" -Raw -Encoding utf8 | ConvertFrom-Json
  Note ("lastResult = " + ($s2.lastResult | ConvertTo-Json -Compress))
} catch {}
Note ("MRRC-Server running = " + ((Get-Process MRRC-Server -ErrorAction SilentlyContinue | Measure-Object).Count))
Note ("install-$Target.log 存在 = " + (Test-Path "$env:LOCALAPPDATA\MRRC\updates\install-$Target.log"))
Note "--- launcher 日志尾部 30 行 ---"
Get-Content C:\tmp\launcher_test.log -Encoding UTF8 -ErrorAction SilentlyContinue | Select-Object -Last 30 | ForEach-Object { Note $_ }
Note "=== DONE ==="

# 6) 自动回传报告（显式 UTF-8 字节，避免 PowerShell 默认编码把中文写乱）
try {
  $body = Get-Content $log -Raw -Encoding utf8
  $meta = '{"problem":"VM 一键升级端到端验收报告","contact":"vm-e2e","version":"' + $Target + '"}'
  $created = Invoke-RestMethod -Uri 'https://www.vlsc.net/mrrc/support/api/create' -Method Post -Body ([Text.Encoding]::UTF8.GetBytes($meta)) -ContentType 'application/json; charset=utf-8' -TimeoutSec 60
  Invoke-WebRequest -Uri ("https://www.vlsc.net/mrrc/support/api/" + $created.id + "/bundle") -Method Put -Body ([Text.Encoding]::UTF8.GetBytes($body)) -ContentType 'text/plain; charset=utf-8' -TimeoutSec 180 | Out-Null
  Write-Host "报告已上传（条目 $($created.id)）"
} catch { Write-Host ("报告上传失败: " + $_.Exception.Message) }
