@echo off
setlocal EnableExtensions
chcp 65001 >nul 2>&1

:: 切换到项目根目录（脚本位于 scripts\windows）
cd /d "%~dp0..\.."

title Damai Ticket Assistant - 一键安装与启动

echo ===============================================
echo   Damai Ticket Assistant 一键安装 + 启动入口
echo ===============================================
echo.

:: 优先使用 PowerShell 7 (pwsh)
where pwsh >nul 2>&1
if %errorlevel%==0 (
    echo [INFO] 检测到 PowerShell 7 (pwsh)，正在执行安装脚本...
    pwsh -NoProfile -ExecutionPolicy Bypass -File ".\scripts\windows\install_all.ps1"
    goto :end
)

:: 回退到 Windows PowerShell
where powershell >nul 2>&1
if %errorlevel%==0 (
    echo [INFO] 检测到 Windows PowerShell，正在执行安装脚本...
    powershell -NoProfile -ExecutionPolicy Bypass -File ".\scripts\windows\install_all.ps1"
    goto :end
)

echo [ERROR] 未检测到 PowerShell，无法执行一键安装脚本。
echo         请手动安装 PowerShell 或在终端运行:
echo         python start_gui.pyw
echo.
pause

:end
exit /b 0