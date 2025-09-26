@echo off
:: 尝试设置UTF-8编码，忽略错误
chcp 65001 >nul 2>&1
if %errorlevel% neq 0 (
    chcp 936 >nul 2>&1
)

title Damai Ticket Tool - GUI Version (Debug Mode)

echo ================================
echo      Damai Ticket Tool v3.0.0
echo         GUI Version DEBUG
echo ================================
echo.

:: 切换到项目根目录（脚本位于 scripts\windows）
cd /d "%~dp0..\.."

:: 创建/清空日志文件
echo ====== Damai Ticket Tool Debug Log ====== > log.txt
echo [%date% %time%] Starting debug run... >> log.txt

:: 检查 Python
echo [1/4] Checking Python environment...
python --version >> log.txt 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found or not added to PATH
    echo Please install Python 3.9+ and check "Add to PATH"
    echo See log.txt for details
    pause
    exit /b 1
)
echo ✓ Python installed

:: 检查程序文件
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
python -c "import selenium" >> log.txt 2>&1
if %errorlevel% neq 0 (
    echo ⚠ Missing selenium library, installing automatically...
    pip install -r requirements.txt >> log.txt 2>&1
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

:: 启动程序（用 python 而不是 pythonw，输出到 log.txt）
echo [4/4] Starting GUI program...
echo Output is being written to log.txt
echo.
python damai_gui.py >> log.txt 2>&1

:: 检查启动结果
if %errorlevel% neq 0 (
    echo ================================
    echo        Startup Failed
    echo ================================
    echo See log.txt for detailed error
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

pause