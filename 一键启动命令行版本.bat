@echo off
chcp 65001 >nul
title 大麦抢票工具 - 命令行版本启动器

echo ================================
echo      大麦抢票工具 v2.0
echo        命令行版本
echo ================================
echo.
echo 正在启动命令行版本...
echo 请稍候...
echo.

:: 切换到脚本所在目录
cd /d "%~dp0"

:: 检查必要文件是否存在
if not exist "damai\damai.py" (
    echo [错误] 找不到主程序文件 damai\damai.py
    echo 请确保以下文件存在：
    echo    - damai\damai.py
    echo    - damai\concert.py
    echo    - damai\config.json
    pause
    exit /b 1
)

:: 切换到damai目录并启动程序
cd damai
echo 正在启动命令行版本...
python damai.py

:: 检查启动结果
if %errorlevel% neq 0 (
    echo.
    echo ================================
    echo          启动失败
    echo ================================
    echo 可能的原因：
    echo 1. Python未安装或未添加到环境变量
    echo 2. 缺少必要的依赖包（运行: pip install -r requirements.txt）
    echo 3. Python版本过低（需要Python 3.7+）
    echo 4. 配置文件config.json配置错误
    echo.
    echo 解决方法：
    echo 1. 安装Python 3.9+并确保添加到PATH
    echo 2. 在项目根目录运行: pip install -r requirements.txt
    echo 3. 检查damai\config.json配置是否正确
    echo.
    pause
)