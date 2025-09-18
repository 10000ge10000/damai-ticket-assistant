@echo off
title 大麦抢票工具启动器

echo ================================
echo      大麦抢票工具 v2.0
echo ================================
echo.
echo 正在启动GUI界面...
echo 请稍候，界面即将打开...
echo.

cd /d "%~dp0"
python damai_gui.py

if %errorlevel% neq 0 (
    echo.
    echo ================================
    echo      启动失败
    echo ================================
    echo 可能的原因：
    echo 1. Python未安装或未添加到环境变量
    echo 2. 缺少必要的依赖包
    echo 3. 脚本文件损坏
    echo.
    echo 请检查环境或联系技术支持
    echo.
    pause
)