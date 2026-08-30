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

# Compile every .py at the repo root as a quick syntax gate.
$pyFiles = Get-ChildItem -Name *.py
if ($pyFiles) {
    Invoke-Checked python -m py_compile @pyFiles
}

# Run the test suite if one exists.
if (Test-Path (Join-Path $RepoRoot "tests")) {
    Invoke-Checked python -m unittest discover -s tests -v
}

# Warn about missing native libraries.  The installer will still build, but the
# app needs these DLLs at runtime on Windows.
$vendorChecks = @(
    @("vendor\opus\windows\bin\x64\opus.dll",    "Opus audio (RX/TX)"),
    @("vendor\hamlib\windows\bin\x64\libhamlib.dll", "Hamlib radio control"),
    @("vendor\hamlib\windows\bin\x64\hamlib.dll",   "Hamlib radio control"),
    @("vendor\wdsp\windows\bin\x64\libwdsp.dll",   "WDSP DSP"),
    @("vendor\wdsp\windows\bin\x64\wdsp.dll",      "WDSP DSP")
)
foreach ($pair in $vendorChecks) {
    $rel = $pair[0]
    $desc = $pair[1]
    $full = Join-Path $RepoRoot $rel
    if (!(Test-Path $full)) {
        Write-Warning "Missing $desc runtime library: $rel"
    }
}

Invoke-Checked pyinstaller packaging\pyinstaller\mrrc_server.spec --noconfirm --distpath "$PyInstallerRoot" --workpath "build\pyinstaller"
Invoke-Checked pyinstaller packaging\pyinstaller\mrrc_launcher.spec --noconfirm --distpath "$PyInstallerRoot" --workpath "build\pyinstaller"
Invoke-Checked pyinstaller packaging\pyinstaller\atr1000_proxy.spec --noconfirm --distpath "$PyInstallerRoot" --workpath "build\pyinstaller"

if (Test-Path $AppRoot) {
    Remove-Item $AppRoot -Recurse -Force
}
New-Item -ItemType Directory -Path $AppRoot | Out-Null

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

if (Get-Command iscc -ErrorAction SilentlyContinue) {
    Invoke-Checked iscc packaging\windows\MRRC.iss
} else {
    Write-Warning "Inno Setup Compiler 'iscc' was not found. Install Inno Setup and rerun this script to create the setup EXE."
}

Write-Host "Assembled app: $AppRoot"
Write-Host "Installer output: $(Join-Path $DistRoot 'MRRC-Setup.exe')"
