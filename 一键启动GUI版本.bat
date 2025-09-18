@echo off
chcp 65001 >nul
title 大麦抢票工具 - GUI版本启动器

echo ================================
echo      大麦抢票工具 v2.0
echo         GUI图形界面版本
echo ================================
echo.
echo 正在启动GUI界面...
echo 请稍候，界面即将打开...
echo.

:: 切换到脚本所在目录
cd /d "%~dp0"

:: 检查必要文件是否存在
if not exist "damai_gui.py" (
    echo [错误] 找不到主程序文件 damai_gui.py
    echo 请确保以下文件存在：
    echo    - damai_gui.py
    echo    - gui_concert.py
    pause
    exit /b 1
)

if not exist "start_gui.pyw" (
    echo [错误] 找不到启动文件 start_gui.pyw
    echo 请确保以下文件存在：
    echo    - start_gui.pyw
    pause
    exit /b 1
)

:: 尝试启动GUI程序
echo 正在启动...
python start_gui.pyw

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
    echo.
    echo 解决方法：
    echo 1. 安装Python 3.9+并确保添加到PATH
    echo 2. 在此目录打开命令行运行: pip install -r requirements.txt
    echo 3. 或者尝试直接运行: python damai_gui.py
    echo.
    pause
) else (
    echo.
    echo GUI程序已启动，请查看弹出的窗口
    echo.
)
