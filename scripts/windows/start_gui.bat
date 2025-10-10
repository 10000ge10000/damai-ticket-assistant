@echo off
setlocal EnableExtensions EnableDelayedExpansion
:: 尝试设置UTF-8编码，忽略错误
chcp 65001 >nul 2>&1

:: 如果UTF-8不支持，尝试设置GBK编码
if %errorlevel% neq 0 (
    chcp 936 >nul 2>&1
)

title Damai Ticket Tool - GUI Version

echo ================================
echo      Damai Ticket Tool v3.0.0
echo         GUI Version
echo ================================
echo.

:: Switch to project root (two levels above scripts\windows)
cd /d "%~dp0..\.."

:: Check Python availability
echo [1/6] Checking Python environment...
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
echo [2/6] Checking program files...
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
echo [3/6] Checking Python dependencies...
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

echo [4/6] Checking Node.js runtime...
call :ensure_node
if %errorlevel% neq 0 (
    pause
    exit /b 1
)
echo ✓ Node.js detected (%NODE_VERSION%)

echo [5/6] Checking Appium CLI...
call :ensure_appium
if %errorlevel% neq 0 (
    pause
    exit /b 1
)
echo ✓ Appium CLI detected (%APPIUM_VERSION%)
:: Start program
echo [6/6] Starting GUI program...
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
    echo Press any key to close this window...
    pause >nul
)

exit /b 0

    :ensure_node
    setlocal EnableExtensions
    set "VERSION="
    for /f "delims=" %%i in ('node --version 2^>nul') do set "VERSION=%%i"
    if defined VERSION (
        endlocal & set "NODE_VERSION=%VERSION%" & exit /b 0
    )
    echo ⚠ Node.js not found. Attempting automatic installation via winget...
    call :install_node
    set "VERSION="
    for /f "delims=" %%i in ('node --version 2^>nul') do set "VERSION=%%i"
    if defined VERSION (
        endlocal & set "NODE_VERSION=%VERSION%" & exit /b 0
    )
    echo [ERROR] Node.js still missing. Please install from https://nodejs.org/ (remember to add to PATH).
    echo.
    endlocal
    exit /b 1

    :ensure_appium
    setlocal EnableExtensions
    set "VERSION="
    for /f "delims=" %%i in ('appium -v 2^>nul') do set "VERSION=%%i"
    if defined VERSION (
        endlocal & set "APPIUM_VERSION=%VERSION%" & exit /b 0
    )
    echo ⚠ Appium CLI not found. Installing via npm (may require administrator permission)...
    call :install_appium
    set "VERSION="
    for /f "delims=" %%i in ('appium -v 2^>nul') do set "VERSION=%%i"
    if defined VERSION (
        endlocal & set "APPIUM_VERSION=%VERSION%" & exit /b 0
    )
    echo [ERROR] Appium CLI still missing. Please run: npm install -g appium
    echo.
    endlocal
    exit /b 1

:install_node
winget -v >nul 2>&1
if %errorlevel% neq 0 (
    echo   Winget 未检测到或当前账户无权限，无法自动安装 Node.js。
    goto :eof
)
echo   调用 winget 安装 Node.js LTS...
winget install --id OpenJS.NodeJS.LTS -e --accept-source-agreements --accept-package-agreements
if %errorlevel% neq 0 (
    echo   winget 安装 Node.js 失败，请确认已授权或稍后手动安装。
) else (
    echo   Node.js 安装流程已完成。
)
goto :eof

:install_appium
npm -v >nul 2>&1
if %errorlevel% neq 0 (
    echo   npm 未检测到，无法自动安装 Appium。请先确认 Node.js 安装成功。
    goto :eof
)
echo   通过 npm 全局安装 Appium CLI...
npm install -g appium@latest --loglevel error
if %errorlevel% neq 0 (
    echo   npm 安装 Appium 失败，可稍后手动执行：npm install -g appium
) else (
    echo   Appium CLI 安装完成。
)
goto :eof

:install_adb
set "TOOLS_ROOT=%~dp0tools"
set "PLATFORM_DIR=%TOOLS_ROOT%\platform-tools"
echo   正在下载 Android Platform Tools...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Try { $dest = '%TOOLS_ROOT%'; $ErrorActionPreference = 'Stop'; if (-not (Test-Path $dest)) { New-Item -ItemType Directory -Path $dest | Out-Null } ; $zip = Join-Path $dest 'platform-tools.zip'; if (Test-Path (Join-Path $dest 'platform-tools')) { Remove-Item -Recurse -Force (Join-Path $dest 'platform-tools') } ; Invoke-WebRequest -Uri 'https://dl.google.com/android/repository/platform-tools-latest-windows.zip' -OutFile $zip -UseBasicParsing ; Expand-Archive -Path $zip -DestinationPath $dest -Force ; Remove-Item $zip ; exit 0 } Catch { Write-Error $_ ; exit 1 }"
if %errorlevel% neq 0 (
    echo   平台工具下载失败，请稍后手动安装。
    goto :eof
)
set "PATH=%PLATFORM_DIR%;%PATH%"
echo   已将 %PLATFORM_DIR% 添加到当前会话 PATH。
echo   如需永久生效，可手动将该目录加入系统环境变量。
goto :eof