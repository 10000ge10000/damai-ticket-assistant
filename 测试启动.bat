@echo off
echo 测试GUI启动脚本
echo 当前目录: %CD%
echo.

:: 切换到脚本所在目录
cd /d "%~dp0"
echo 切换后目录: %CD%
echo.

:: 检查文件是否存在
if exist "damai_gui.py" (
    echo ✓ 找到damai_gui.py文件
) else (
    echo ✗ 未找到damai_gui.py文件
    pause
    exit /b 1
)

echo.
echo 正在启动Python程序...
python damai_gui.py

echo.
echo 程序执行完毕
pause