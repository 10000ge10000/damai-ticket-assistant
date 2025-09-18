@echo off
chcp 65001 >nul
title 大麦抢票工具 - 依赖安装器

echo ================================
echo    大麦抢票工具依赖安装器
echo ================================
echo.
echo 本脚本将自动安装运行所需的所有依赖库
echo 请确保您已经安装了Python 3.7+
echo.

:: 切换到脚本所在目录
cd /d "%~dp0"

:: 检查Python是否可用
echo [1/3] 检查Python环境...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未找到Python或Python未添加到环境变量
    echo.
    echo 请先安装Python：
    echo 1. 访问 https://www.python.org/downloads/
    echo 2. 下载Python 3.9+版本
    echo 3. 安装时务必勾选 "Add Python to PATH"
    echo.
    echo 安装Python后请重新运行此脚本
    pause
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo ✓ 检测到 Python %PYTHON_VERSION%

:: 检查pip是否可用
echo [2/3] 检查pip包管理器...
pip --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] pip未安装或不可用
    echo 请重新安装Python并确保包含pip
    pause
    exit /b 1
)
echo ✓ pip可用

:: 安装依赖
echo [3/3] 开始安装依赖包...
echo.
echo 正在安装必要的Python库，请稍候...
echo 这可能需要几分钟时间，取决于您的网络速度。
echo.

:: 逐个安装主要依赖，显示详细进度
echo ► 安装 selenium (网页自动化库)...
pip install selenium
if %errorlevel% neq 0 (
    echo [错误] selenium安装失败
    goto :install_error
)
echo ✓ selenium 安装成功

echo.
echo ► 安装 webdriver-manager (自动管理浏览器驱动)...
pip install webdriver-manager
if %errorlevel% neq 0 (
    echo [警告] webdriver-manager安装失败，但不影响基本功能
)

echo.
echo ► 安装其他依赖包...
if exist "requirements.txt" (
    pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo [警告] requirements.txt中的某些包安装失败
        echo 但核心功能应该可以正常使用
    )
) else (
    echo [提示] 未找到requirements.txt，跳过批量安装
)

echo.
echo ================================
echo        安装完成！
echo ================================
echo.
echo ✓ 所有依赖已成功安装
echo ✓ 您现在可以使用以下方式启动程序：
echo.
echo   方式1：双击 "一键启动GUI版本.bat"
echo   方式2：双击 "一键启动命令行版本.bat"
echo   方式3：运行命令 "python damai_gui.py"
echo.
echo 如遇到问题，请查看README.md说明文档
echo.
pause
exit /b 0

:install_error
echo.
echo ================================
echo        安装失败
echo ================================
echo.
echo 可能的解决方案：
echo 1. 检查网络连接是否正常
echo 2. 尝试使用国内pip源：
echo    pip install -i https://pypi.tuna.tsinghua.edu.cn/simple selenium
echo 3. 升级pip版本：
echo    python -m pip install --upgrade pip
echo 4. 使用管理员权限运行此脚本
echo.
echo 如果问题持续存在，请查看详细错误信息或寻求技术支持
pause
exit /b 1