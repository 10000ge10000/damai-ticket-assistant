# Windows 安装依赖指南

> 建议使用 PowerShell 7+ 或 Windows Terminal 执行以下命令。

## 0. 推荐：一键安装与启动

- 方式一：双击脚本
  - 双击 `scripts/windows/oneclick_start.bat`（自动调用 PowerShell 脚本完成依赖安装并启动 GUI）
- 方式二：命令行执行
  - 在项目根目录执行：
    ```powershell
    pwsh ./scripts/windows/install_all.ps1
    ```
- 脚本将自动执行：
  - 检测/创建虚拟环境（venv），安装 `requirements.txt`
  - 检测 Node.js 并安装 Appium CLI（npm -g appium）
  - 检测 adb；必要时自动下载 Android Platform Tools 并加入当前会话 PATH
  - 启动 `start_gui.pyw`（优先使用 pythonw）
- 网络受限场景下，脚本会自动回退至清华镜像源安装依赖。

> ChromeDriver 无需手动安装，Selenium Manager 会自动管理驱动（随 Selenium 4.18+）。

## 1. 准备 Python 环境（手动路径）

1. 确保已安装 Python 3.8 及以上版本，可以在终端执行 `python --version` 检查。
2. 勾选 “Add Python to PATH”，或手动将 Python 安装目录加入系统 PATH。

## 2. 手动安装项目依赖

在项目根目录执行以下命令：

```powershell
cd "C:\path\to\damai-ticket-assistant"
python -m pip install --upgrade pip
pip install -r requirements.txt
```

> 如使用 Poetry，可运行 `poetry install` 自动创建虚拟环境。

## 3. 可选依赖

- **App 模式**：需要 Node.js、Appium CLI 以及 adb，详见 `docs/guides/APP_MODE_README.md`
- **开发工具**：若使用 Poetry，可执行 `poetry install --with dev` 安装测试与 lint 工具（可选）。

## 4. 常见问题

- 如果提示没有权限，请在 PowerShell 中使用管理员身份运行。
- 如果 `pip` 执行失败，可尝试使用 `python -m pip install ...`。
- 如果网络受限，可配置国内镜像源，如 `pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt`。
