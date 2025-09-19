@echo off
:: 设置编码（优先UTF-8，失败则用GBK）
chcp 65001 >nul 2>&1
if %errorlevel% neq 0 (
    chcp 936 >nul 2>&1
)

title Damai Ticket Tool - GUI Version

echo ================================
echo      Damai Ticket Tool v2.0
echo         GUI Version
echo ================================
echo.

:: 切换到当前脚本所在目录
cd /d "%~dp0"

:: 检查 Python 环境
echo [1/4] Checking Python environment...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found or not added to PATH
    echo Please install Python 3.9+ and check "Add Python to PATH"
    pause
    exit /b 1
)
echo ✓ Python installed

:: 检查必要文件
echo [2/4] Checking program files...
if not exist "damai_gui.py" (
    echo [ERROR] damai_gui.py not found
    pause
    exit /b 1
)
if not exist "requirements.txt" (
    echo [ERROR] requirements.txt not found
    pause
    exit /b 1
)
echo ✓ Program files found

:: 检查并安装依赖
echo [3/4] Checking Python dependencies...
python -c "import selenium" >nul 2>&1
if %errorlevel% neq 0 (
    echo ⚠ Missing selenium, installing automatically...
    pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to install dependencies
        echo Please run manually: pip install -r requirements.txt
        pause
        exit /b 1
    )
    echo ✓ Dependencies installed
) else (
    echo ✓ Dependencies already installed
)

:: 启动 GUI 程序（发布版用 pythonw 避免多余黑窗）
echo [4/4] Starting GUI program...
pythonw damai_gui.py

if %errorlevel% neq 0 (
    echo ================================
    echo        Startup Failed
    echo ================================
    echo Possible causes:
    echo 1. Dependencies not completely installed
    echo 2. Python version incompatible (requires 3.7+)
    echo 3. Chrome browser or ChromeDriver missing
    echo.
    pause
    exit /b 1
) else (
    echo ✓ GUI program started successfully!
    echo Please use the interface that appeared.
)