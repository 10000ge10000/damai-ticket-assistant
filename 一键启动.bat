@echo off
:: 尝试设置UTF-8编码，忽略错误
chcp 65001 >nul 2>&1

:: 如果UTF-8不支持，尝试设置GBK编码
if %errorlevel% neq 0 (
    chcp 936 >nul 2>&1
)

title Damai Ticket Tool - GUI Version

echo ================================
echo      Damai Ticket Tool v2.0
echo         GUI Version
echo ================================
echo.

:: Switch to script directory
cd /d "%~dp0"

:: Check Python availability
echo [1/4] Checking Python environment...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found or not added to PATH
    echo.
    echo Please install Python following these steps:
    echo 1. Visit https://www.python.org/downloads/
    echo 2. Download Python 3.9+ version
    echo 3. Make sure to check "Add Python to PATH" during installation
    echo.
    pause
    exit /b 1
)

echo ✓ Python installed

:: Check required files
echo [2/4] Checking program files...
if not exist "damai_gui.py" (
    echo [ERROR] Main program file damai_gui.py not found
    echo Please ensure you downloaded the complete project files
    pause
    exit /b 1
)

if not exist "requirements.txt" (
    echo [ERROR] Requirements file requirements.txt not found
    echo Please ensure you downloaded the complete project files
    pause
    exit /b 1
)
echo ✓ Program files check completed

:: Check and install dependencies
echo [3/4] Checking Python dependencies...
python -c "import selenium" >nul 2>&1
if %errorlevel% neq 0 (
    echo ⚠ Missing selenium library, installing automatically...
    echo Please wait, this may take a few minutes...
    echo.
    pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo.
        echo [ERROR] Dependency installation failed
        echo Please run manually:
        echo    pip install -r requirements.txt
        echo.
        echo If still fails, try:
        echo    pip install selenium
        echo.
        pause
        exit /b 1
    )
    echo ✓ Dependencies installed
) else (
    echo ✓ Dependencies already installed
)

:: Start program
echo [4/4] Starting GUI program...
echo Starting graphical interface, please wait...
echo.

:: Use pythonw to start GUI program (avoids extra command window)
pythonw damai_gui.py

:: Check startup result
if %errorlevel% neq 0 (
    echo.
    echo ================================
    echo        Startup Failed
    echo ================================
    echo Possible causes:
    echo 1. Dependencies not completely installed
    echo 2. Python version incompatible (requires Python 3.7+)
    echo 3. Chrome browser not installed
    echo.
    echo Solutions:
    echo 1. Install dependencies manually: pip install -r requirements.txt
    echo 2. Install Chrome browser
    echo 3. Check Python version: python --version
    echo.
    echo For technical support, please check project README
    pause
) else (
    echo.
    echo ✓ GUI program started successfully!
    echo Please use the graphical interface that appeared
    echo.
    timeout /t 3 >nul
)