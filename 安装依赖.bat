@echo off
chcp 65001 >nul
title Damai Ticket Tool - Dependency Installer

echo ================================
echo  Damai Ticket Tool Dependencies
echo         Installer v2.0
echo ================================
echo.
echo This script will automatically install all required dependencies
echo Please ensure you have Python 3.7+ installed
echo.

:: Switch to script directory
cd /d "%~dp0"

:: Check Python availability
echo [1/3] Checking Python environment...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found or not added to PATH
    echo.
    echo Please install Python first:
    echo 1. Visit https://www.python.org/downloads/
    echo 2. Download Python 3.9+ version
    echo 3. Make sure to check "Add Python to PATH" during installation
    echo.
    echo After installing Python, please run this script again
    pause
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo ✓ Detected Python %PYTHON_VERSION%

:: Check pip availability
echo [2/3] Checking pip package manager...
pip --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] pip not installed or unavailable
    echo Please reinstall Python and ensure pip is included
    pause
    exit /b 1
)
echo ✓ pip is available

:: Install dependencies
echo [3/3] Starting dependency installation...
echo.
echo Installing required Python libraries, please wait...
echo This may take a few minutes depending on your network speed.
echo.

:: Install main dependencies individually with detailed progress
echo ► Installing selenium (web automation library)...
pip install selenium
if %errorlevel% neq 0 (
    echo [ERROR] selenium installation failed
    goto :install_error
)
echo ✓ selenium installed successfully

echo.
echo ► Installing webdriver-manager (automatic browser driver management)...
pip install webdriver-manager
if %errorlevel% neq 0 (
    echo [WARNING] webdriver-manager installation failed, but basic functionality should work
)

echo.
echo ► Installing other dependencies...
if exist "requirements.txt" (
    pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo [WARNING] Some packages in requirements.txt failed to install
        echo But core functionality should work normally
    )
) else (
    echo [INFO] requirements.txt not found, skipping batch installation
)

echo.
echo ================================
echo     Installation Complete!
echo ================================
echo.
echo ✓ All dependencies have been successfully installed
echo ✓ You can now start the program using:
echo.
echo   Method 1: Double-click "一键启动GUI版本.bat"
echo   Method 2: Double-click "一键启动命令行版本.bat"
echo   Method 3: Run command "python damai_gui.py"
echo.
echo If you encounter any issues, please check README.md documentation
echo.
pause
exit /b 0

:install_error
echo.
echo ================================
echo    Installation Failed
echo ================================
echo.
echo Possible solutions:
echo 1. Check your network connection
echo 2. Try using Chinese pip mirror:
echo    pip install -i https://pypi.tuna.tsinghua.edu.cn/simple selenium
echo 3. Upgrade pip version:
echo    python -m pip install --upgrade pip
echo 4. Run this script as administrator
echo.
echo If the problem persists, please check detailed error messages or seek technical support
pause
exit /b 1