@echo off
chcp 65001 >nul
cd /d "%~dp0"

py -3 --version >nul 2>nul
if errorlevel 1 (
    python tools\blog.py publish %*
) else (
    py -3 tools\blog.py publish %*
)
set "EXIT_CODE=%ERRORLEVEL%"

echo.
echo %cmdcmdline% | "%SystemRoot%\System32\find.exe" /i "%~nx0" >nul
if not errorlevel 1 pause
exit /b %EXIT_CODE%
