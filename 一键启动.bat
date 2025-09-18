@echo off
chcp 65001 > nul
title 大麦抢票工具

echo.
echo     ╔══════════════════════════════════════╗
echo     ║           大麦抢票工具 v2.0            ║
echo     ║        GUI图形界面版 - 小白友好         ║
echo     ╚══════════════════════════════════════╝
echo.
echo 🚀 正在启动图形界面...
echo.

cd /d "%~dp0"

REM 尝试使用pythonw启动（无CMD窗口）
if exist start_gui.pyw (
    start "" pythonw start_gui.pyw
    echo ✅ 图形界面已启动（无CMD窗口模式）
    echo 📌 如未看到界面窗口，请检查任务栏或稍等片刻
    timeout /t 3 > nul
    exit
)

REM 备用：使用python启动
if exist damai_gui.py (
    python damai_gui.py
) else (
    echo ❌ 未找到GUI程序文件
    echo 📁 请确认以下文件存在：
    echo    - damai_gui.py
    echo    - start_gui.pyw
    pause
)