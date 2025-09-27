 # App 模式（Android）环境配置（永久生效）

本文档说明如何在 Windows 上为 App 模式（Appium + uiautomator2）永久配置 Android SDK，并强调在将 `platform-tools` 路径加入系统 `PATH` 后需要重启电脑以确保生效。

## 一句话结论

- 将系统变量 `ANDROID_SDK_ROOT`（或 `ANDROID_HOME`）设置为 Android SDK 根目录（例如 `C:\Android`）。
- 将 `C:\Android\platform-tools` 添加到系统 `PATH`。
- 将路径加入系统 `PATH` 后，务必重启电脑：Windows 上大多数服务/程序在启动时读取环境变量，重启能确保所有服务读取到新变量。

## 永久设置（图形界面）

1. 打开“系统属性” → “高级” → “环境变量”。
2. 在“系统变量（System variables）”中点击“新建（New）”，添加：
   - 变量名：`ANDROID_SDK_ROOT`
   - 变量值：`C:\Android`（根据实际路径替换）
3. 同样再添加：
   - 变量名：`ANDROID_HOME`
   - 变量值：`C:\Android`
4. 选中系统变量中的 `Path` → 编辑 → 新建，添加：`C:\Android\platform-tools`，保存并退出。

> 建议同时设置 `ANDROID_HOME` 与 `ANDROID_SDK_ROOT`，以兼容不同工具链。

## 永久设置（命令行写入当前用户环境）

在非管理员的 PowerShell 中执行（写入当前用户环境变量，需重新打开终端或重启生效）：

```powershell
setx ANDROID_SDK_ROOT "C:\Android"
setx ANDROID_HOME "C:\Android"
```

注意：`setx` 写入后需要打开新终端窗口或重启以使系统级应用读取到新值；不要用 `setx` 直接覆盖 `PATH`，建议通过图形界面或系统设置追加 `C:\Android\platform-tools`。

## 安装 Android Platform Tools

- 推荐：使用 Android Studio 的 SDK Manager 安装 "Android SDK Platform-Tools"。
- 或者手动下载并解压（示例）：<https://developer.android.com/studio/releases/platform-tools>

将 `platform-tools` 父目录（例如 `C:\Android\platform-tools`）添加到系统 `PATH`。

## 为什么需要重启？

Windows 中的大多数系统服务和桌面应用在启动时会读取环境变量。修改系统环境变量后，已运行的程序（包括系统服务）不会自动更新其环境。因此，为确保 Appium（如果作为服务或由某些启动器运行）以及其他所有应用都看到新变量，请重启电脑。

## 验证（重启后）

1. 打开新的 PowerShell 窗口并运行：

   ```powershell
   echo $env:ANDROID_SDK_ROOT
   echo $env:ANDROID_HOME
   adb version
   adb devices
   ```

2. 若 `adb version` 与 `adb devices` 正常，则 Appium 有较高概率成功创建 session。

3. 启动 Appium 并在另一个终端检查：

   ```powershell
   appium
   # 或者使用 appium-doctor --android
   appium-doctor --android
   ```

## 常见 SDK 路径（参考）

- Android Studio 默认：`%LOCALAPPDATA%\\Android\\Sdk`（即 `C:\Users\\<用户名>\\AppData\\Local\\Android\\Sdk`）
- 手动安装示例：`C:\Android`

## 针对 Appium Desktop / Windows 服务 的注意事项

如果 Appium 作为服务或由其他启动器运行，请在配置完成并重启后再启动这些服务，以便它们读取到新的系统环境变量。

---

更新记录：

- 2025-09-27：添加永久变量设置步骤、安装 platform-tools 指南与“重启电脑”说明。
3. 在系统变量中找到 `Path`，点击“编辑（Edit）”，然后添加：

   - `C:\Android\platform-tools`

   （不要覆盖已有 Path；用“新建”按钮追加一行）

4. 点击“确定”保存所有设置，然后关闭所有打开的终端或程序，并重启电脑以确保所有系统服务和 GUI 应用读取到新的系统环境变量。

### 为什么需要重启？

Windows 中的大多数系统服务和桌面应用在启动时会读取环境变量。修改系统环境变量后，已运行的程序（包括系统服务）不会自动更新其环境。因此，为确保 Appium（如果作为服务或由某些启动器运行）以及其他所有应用都看到新变量，请重启电脑。

## 安装 Android Platform Tools

如果你还没有 `platform-tools`，可以通过以下方式安装：

1. 使用 Android Studio 的 SDK Manager 安装 "Android SDK Platform-Tools"。
2. 或者从官方压缩包手动下载并解压到你希望的目录，例如 `C:\Android`：

   - 官方下载（示例）：https://developer.android.com/studio/releases/platform-tools

3. 将 `platform-tools` 的父目录添加到系统 `PATH`（例如添加 `C:\Android\platform-tools`）。

重要提示：将路径加入系统环境变量 `PATH` 后，Windows 中的已运行程序（包括 Appium 服务、桌面应用或已打开的终端）不会自动读取更新的变量。要确保所有服务与程序使用到新变量，请关闭相关程序并重启电脑。

## 验证步骤（重启后）

1. 打开新的 PowerShell 窗口，运行：

   ```powershell
   echo $env:ANDROID_SDK_ROOT
   echo $env:ANDROID_HOME
   adb version
   adb devices
   ```

2. 如果 `adb version` 正常显示且 `adb devices` 能列出你的设备，则 Appium 在大概率上能正常使用 ADB。

3. 启动 Appium，并在另一个终端检查状态：

   ```powershell
   appium
   # 或者使用 appium-doctor（如果安装）
   appium-doctor --android
   ```

## 常见 SDK 路径参考

- Android Studio 默认：`%LOCALAPPDATA%\Android\Sdk`（即 `C:\Users\<用户名>\AppData\Local\Android\Sdk`）
- 手动安装/解压示例：`C:\Android`

## 附：若使用 Appium Desktop / 服务

如果你使用 Appium Desktop 或者把 Appium 注册为 Windows 服务，请确保这些服务/程序在系统变量设置完成并重启后再启动，这样它们能读取到新的环境变量。

---
更新记录：

- 2025-09-27：添加永久变量设置步骤、安装 platform-tools 指南与“重启电脑”说明。
