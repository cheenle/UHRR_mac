# MRRC 一键升级端到端验收（在 VM 上以**管理员** PowerShell 运行）
# 流程：装 6.1.0 → 起启动器（后台）→ 等它下载 6.1.1 → 写哨兵触发升级 → 校验 version.txt
# 结果自动上传到 https://www.vlsc.net/mrrc/support/（维护者列表页可见）
$ErrorActionPreference = 'Continue'
$log = 'C:\tmp\upgrade_e2e_report.txt'
function Note($m) { $m | Tee-Object -FilePath $log -Append -Encoding utf8 | Out-Null; Write-Host $m }
"=== MRRC 升级端到端验收 $(Get-Date -Format 'HH:mm:ss') ===" | Out-File $log -Encoding utf8
Note ("elevated: " + (New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator))
Note ("before: version.txt = " + (Get-Content 'C:\Program Files\MRRC\version.txt' -ErrorAction SilentlyContinue))

# 1) 装 6.1.0（第一个自带升级逻辑的版本）
$setup = 'C:\tmp\MRRC-Setup-6.1.0.exe'
if (-not (Test-Path $setup)) {
  Note "下载 6.1.0 安装包…"
  Invoke-WebRequest -Uri 'https://www.vlsc.net/mrrc/downloads/MRRC-Setup-6.1.0.exe' -OutFile $setup -TimeoutSec 900
}
Note "静默安装 6.1.0 …"
$p = Start-Process -FilePath $setup -ArgumentList '/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART',"/LOG=C:\tmp\install610.log" -PassThru -Wait
Note ("installer exit=" + $p.ExitCode)
Note ("after install: version.txt = " + (Get-Content 'C:\Program Files\MRRC\version.txt' -ErrorAction SilentlyContinue))
Note ("upgrade_core present = " + (Test-Path 'C:\Program Files\MRRC\_internal\app\upgrade_core.py'))
if ((Get-Content 'C:\Program Files\MRRC\version.txt' -ErrorAction SilentlyContinue) -ne '6.1.0') { Note "❌ 6.1.0 安装未成功，终止"; }

# 2) 清掉旧状态，后台起启动器（它会看到 latest.json 的 6.1.1）
Get-Process MRRC-Server,MRRC-Launcher -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Remove-Item "$env:LOCALAPPDATA\MRRC\updates\state.json","$env:LOCALAPPDATA\MRRC\updates\upgrade.request" -Force -ErrorAction SilentlyContinue
Note "启动 MRRC-Launcher（后台，日志 C:\tmp\launcher_test.log）…"
Start-Process -FilePath 'cmd.exe' -ArgumentList '/c','"C:\Program Files\MRRC\MRRC-Launcher.exe" > C:\tmp\launcher_test.log 2>&1' -WindowStyle Hidden

# 3) 等新版本下载并校验完成
$staged = $null
for ($i = 0; $i -lt 40; $i++) {
  Start-Sleep -Seconds 6
  try { $state = Get-Content "$env:LOCALAPPDATA\MRRC\updates\state.json" -Raw -Encoding utf8 | ConvertFrom-Json } catch { $state = $null }
  if ($state -and $state.staged -and $state.staged.version -eq '6.1.1') { $staged = $state.staged; break }
}
if ($staged) { Note ("✅ 已下载并暂存: " + $staged.version + " (" + [Math]::Round($staged.size/1MB,1) + " MB, sha " + $staged.sha256.Substring(0,12) + "…)") }
else { Note "❌ 超时：启动器没有暂存 6.1.1（看 launcher_test.log）" }

# 4) 写哨兵触发升级（等价于页面点【立即升级】或按 U）
if ($staged) {
  Note "触发升级（写 upgrade.request）…"
  '{"version":"6.1.1","at":"e2e"}' | Set-Content "$env:LOCALAPPDATA\MRRC\updates\upgrade.request" -Encoding utf8
  for ($i = 0; $i -lt 50; $i++) {
    Start-Sleep -Seconds 6
    $v = Get-Content 'C:\Program Files\MRRC\version.txt' -ErrorAction SilentlyContinue
    if ($v -eq '6.1.1') { break }
  }
}

# 5) 收尾检查 + 报告
Note ("after upgrade: version.txt = " + (Get-Content 'C:\Program Files\MRRC\version.txt' -ErrorAction SilentlyContinue))
try { $s2 = Get-Content "$env:LOCALAPPDATA\MRRC\updates\state.json" -Raw -Encoding utf8 | ConvertFrom-Json; Note ("lastResult = " + ($s2.lastResult | ConvertTo-Json -Compress)) } catch {}
Note ("MRRC-Server running = " + ((Get-Process MRRC-Server -ErrorAction SilentlyContinue | Measure-Object).Count))
Note "--- launcher 日志尾部 25 行 ---"
Get-Content C:\tmp\launcher_test.log -Encoding UTF8 -ErrorAction SilentlyContinue | Select-Object -Last 25 | ForEach-Object { Note $_ }
Note ("install log 尾部: " + ((Get-Content C:\tmp\install-6.1.1.log -Tail 2 -ErrorAction SilentlyContinue) -join ' | '))
Note "=== DONE ==="

# 6) 自动回传报告
try {
  $body = Get-Content $log -Raw -Encoding utf8
  $meta = '{"problem":"VM 一键升级端到端验收报告","contact":"vm-e2e","version":"6.1.1"}'
  $created = Invoke-RestMethod -Uri 'https://www.vlsc.net/mrrc/support/api/create' -Method Post -Body $meta -ContentType 'application/json' -TimeoutSec 60
  Invoke-WebRequest -Uri ("https://www.vlsc.net/mrrc/support/api/" + $created.id + "/bundle") -Method Put -Body $body -ContentType 'text/plain' -TimeoutSec 180 | Out-Null
  Write-Host "报告已上传到接收端（条目 $($created.id)）"
} catch { Write-Host ("报告上传失败: " + $_.Exception.Message) }
