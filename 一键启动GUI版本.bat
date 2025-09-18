@echo off
chcp 65001 >nul
title 大麦抢票工具 - GUI版本启动器

echo ================================
echo      大麦抢票工具 v2.0
echo         GUI图形界面版本
echo ================================
echo.

:: 切换到脚本所在目录
cd /d "%~dp0"

:: 检查Python是否可用
echo [1/4] 检查Python环境...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未找到Python或Python未添加到环境变量
    echo.
    echo 请按照以下步骤安装Python：
    echo 1. 访问 https://www.python.org/downloads/
    echo 2. 下载Python 3.9+版本
    echo 3. 安装时务必勾选 "Add Python to PATH"
    echo.
    pause
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo ✓ Python %PYTHON_VERSION% 已安装

:: 检查必要文件是否存在
echo [2/4] 检查程序文件...
if not exist "damai_gui.py" (
    echo [错误] 找不到主程序文件 damai_gui.py
    echo 请确保您下载了完整的项目文件
    pause
    exit /b 1
)

if not exist "requirements.txt" (
    echo [错误] 找不到依赖列表文件 requirements.txt
    echo 请确保您下载了完整的项目文件
    pause
    exit /b 1
)
echo ✓ 程序文件检查完成

:: 检查并安装依赖
echo [3/4] 检查Python依赖包...
python -c "import selenium" >nul 2>&1
if %errorlevel% neq 0 (
    echo ⚠ 检测到缺少selenium库，正在自动安装...
    echo 请稍候，这可能需要几分钟时间...
    echo.
    pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo.
        echo [错误] 依赖安装失败
        echo 请手动运行以下命令：
        echo    pip install -r requirements.txt
        echo.
        echo 如果仍然失败，请尝试：
        echo    pip install selenium
        echo.
        pause
        exit /b 1
    )
    echo ✓ 依赖包安装完成
) else (
    echo ✓ 依赖包已安装
)

:: 启动程序
echo [4/4] 启动GUI程序...
echo 正在启动图形界面，请稍候...
echo.

python damai_gui.py

:: 检查启动结果
if %errorlevel% neq 0 (
    echo.
    echo ================================
    echo          启动失败
    echo ================================
    echo 可能的原因：
    echo 1. 依赖包安装不完整
    echo 2. Python版本不兼容（需要Python 3.7+）
    echo 3. 系统缺少Chrome浏览器
    echo.
    echo 解决方法：
    echo 1. 手动安装依赖：pip install -r requirements.txt
    echo 2. 安装Chrome浏览器
    echo 3. 检查Python版本：python --version
    echo.
    echo 如需技术支持，请查看项目说明文档
    pause
) else (
    echo.
    echo ✓ GUI程序启动成功！
    echo 请在弹出的图形界面中进行操作
    echo.
)
