@echo off
setlocal
rem ---------------------------------------------------------------------------
rem MRRC config encoding repair (Chinese Windows UTF-8 decode fix).
rem Repairs %LOCALAPPDATA%\MRRC\MRRC.conf from GBK/ANSI/UTF-16 to UTF-8.
rem Requires fix_mrrc_encoding.ps1 in the same folder.
rem Usage:  double-click this file
rem         or: fix_mrrc_encoding.bat -DryRun
rem         or: fix_mrrc_encoding.bat -IncludeAux
rem ---------------------------------------------------------------------------
set "PS1=%~dp0fix_mrrc_encoding.ps1"
if not exist "%PS1%" (
    echo [ERROR] fix_mrrc_encoding.ps1 not found next to this file.
    echo         Keep both files in the same folder.
    echo.
    pause
    exit /b 1
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%PS1%" %*
set "RC=%ERRORLEVEL%"
echo.
if not "%RC%"=="0" echo [ERROR] exit code %RC%
pause
exit /b %RC%
