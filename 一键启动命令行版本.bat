@echo off
chcp 65001 > nul
title 大麦抢票工具 - 命令行版本

echo.
echo     ╔══════════════════════════════════════╗
echo     ║           大麦抢票工具 v2.0            ║
echo     ║          命令行版本 - 专业用户          ║
echo     ╚══════════════════════════════════════╝
echo.
echo 🚀 正在启动命令行版本...
echo ⚠️  请确保已配置好 damai/config.json 文件
echo.

cd /d "%~dp0"

REM 检查命令行版本文件是否存在
if not exist "damai\damai.py" (
    echo ❌ 错误：未找到命令行版本文件
    echo 📁 请确认 damai\damai.py 文件存在
    echo.
    pause
    exit /b 1
)

if not exist "damai\config.json" (
    echo ❌ 错误：未找到配置文件
    echo 📁 请在 damai 目录下创建 config.json 文件
    echo 💡 参考README.md中的配置说明
    echo.
    pause
    exit /b 1
)

echo ✅ 文件检查通过，正在启动...
echo.

cd damai
python damai.py

if %errorlevel% neq 0 (
    echo.
    echo ================================
    echo      命令行版本启动失败
    echo ================================
    echo 可能的原因：
    echo 1. Python未安装或未添加到环境变量
    echo 2. 缺少selenium等依赖包
    echo 3. config.json配置有误
    echo 4. ChromeDriver未配置
    echo.
    echo 💡 建议：
    echo 1. 运行: pip install selenium
    echo 2. 检查config.json格式
    echo 3. 确保Chrome浏览器已安装
    echo.
    pause
)