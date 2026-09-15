@echo off
setlocal
rem ---------------------------------------------------------------------------
rem MRRC: repair config encoding, then start MRRC.
rem Use this instead of the normal shortcut if the server fails to start with
rem "UnicodeDecodeError: 'utf-8' codec can't decode byte ...".
rem Requires fix_mrrc_encoding.ps1 in the same folder.
rem ---------------------------------------------------------------------------
set "PS1=%~dp0fix_mrrc_encoding.ps1"
if not exist "%PS1%" (
    echo [ERROR] fix_mrrc_encoding.ps1 not found next to this file.
    echo         Keep both files in the same folder.
    echo.
    pause
    exit /b 1
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%PS1%" -Launch %*
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" (
    echo.
    echo [ERROR] repair failed with exit code %RC%
    pause
)
exit /b %RC%
