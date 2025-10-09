# 离线一键安装与内置依赖打包指南（Windows 优先）

目标：将运行时需要手动下载的关键外部组件（Node.js、Appium CLI、Android Platform Tools、Python 依赖等）预先打包进仓库（或发布产物），实现“完全离线的一键安装 + 启动”。本指南提供目录规范、打包方法、校验建议与 CI 流程建议。

适用范围
- 首选平台：Windows（PowerShell 脚本已就绪）
- 侧重 App 模式依赖（Node/Appium/adb），Web 模式依赖仅需 Python + Selenium（已通过 Selenium Manager 自动管理驱动）

不建议内置的内容
- Chrome/Edge 等浏览器（体积大、更新频繁、许可证限制）
- 完整 Python 解释器（可选“嵌入式”Python，但复杂度高，建议保留系统级 Python）

---

## 目录规范（vendor-first）

在项目根目录新增 vendor/ 目录，用于存放离线包与镜像缓存。推荐结构如下：

```
vendor/
  wheels/                                # Python 依赖离线轮子集合（wheelhouse）
    selenium-*.whl
    pydantic-*.whl
    Appium_Python_Client-*.whl
    ...
  node/
    node-v20.x.y-win-x64.zip             # Node.js LTS Windows Zip 发行包（包含 npm）
  appium/
    appium-2.x.y.tgz                     # 通过 npm pack 生成的离线 tgz 包
    appium-doctor-1.x.y.tgz              # 可选：appium-doctor 离线 tgz
  platform-tools/
    platform-tools-latest-windows.zip    # Android SDK Platform Tools 原包（adb）
  SHA256SUMS.txt                         # 可选：校验文件（建议）
```

说明
- wheels/：pip 离线安装源，会启用 `pip install --no-index --find-links vendor/wheels -r requirements.txt`
- node-v*.zip：解压后包含 node.exe 与 npm，避免 MSI/winget 依赖与管理员权限
- appium-*.tgz：`npm pack appium` 的输出，离线安装 `npm -g <本地tgz>`
- platform-tools：无需联网下载，直接解压添加到 PATH

---

## 准备离线包（一次性）

1）Python 依赖 wheelhouse
```powershell
# 建议在本机或 CI 上一次性生成 wheelhouse
python -m pip install -U pip wheel
python -m pip download -r requirements.txt -d ./vendor/wheels
```
- 需要附加平台相关额外包时，可按需追加 `-r extra-requirements.txt`

2）Node.js LTS Zip
- 打开 https://nodejs.org/dist/latest-v20.x/ （或最新 LTS）
- 下载 `node-v20.x.y-win-x64.zip` 到 `vendor/node/`

3）Appium & appium-doctor 离线 tgz
```powershell
# 需本机已安装 Node 与 npm
npm pack appium@latest
npm pack appium-doctor@latest
# 将生成的 appium-*.tgz / appium-doctor-*.tgz 移动到 vendor/appium/
```

4）Android Platform Tools
- 下载 https://developer.android.com/tools/releases/platform-tools
- 保存 `platform-tools-latest-windows.zip` 到 `vendor/platform-tools/`

5）生成校验（可选，但强烈建议）
```powershell
Get-FileHash -Algorithm SHA256 vendor\**\* | ForEach-Object {
  "$($_.Hash)  $($_.Path)" 
} | Set-Content -Path vendor\SHA256SUMS.txt -Encoding UTF8
```

---

## 一键脚本改造（思路）

现有安装脚本 [install_all.ps1](scripts/windows/install_all.ps1) 已实现在线优先（含 winget/npm/Invoke-WebRequest）逻辑。为了“离线一键”，可以将其改为“vendor 优先，在线回退”的策略：

推荐改造要点（我们会按需提交补丁）：
- 在 Ensure-Node 前尝试使用 `vendor/node/node-v*.zip`：
  - Expand-Archive 到 `scripts/windows/tools/node/`
  - 将该目录追加到 `$env:Path`
  - 验证 `node --version`/`npm --version`
- 在 Ensure-Appium 前，如果检测到 `vendor/appium/appium-*.tgz`：
  - 执行：`npm install -g "<tgz路径>"`（使用 vendor node 中的 npm）
  - 如存在 appium-doctor tgz，一并安装：`npm -g "<tgz路径>"`
- 在 Ensure-Adb 前，如果存在 `vendor/platform-tools/platform-tools-*.zip`：
  - Expand-Archive 到 `scripts/windows/tools/platform-tools/`
  - 将该目录追加到 `$env:Path`
- 在 Install-Requirements 内，优先离线安装：
  - 若存在 `vendor/wheels`：`pip install --no-index --find-links vendor/wheels -r requirements.txt`
  - 否则回退在线安装（含清华镜像）

注：我们将以 PR 形式把上述“vendor 优先”逻辑直接内置到 [install_all.ps1](scripts/windows/install_all.ps1) 中，避免使用者手动调整脚本。

---

## 使用指令（完全离线）

将 vendor/ 填好后：
```powershell
# 推荐方式
pwsh -NoProfile -ExecutionPolicy Bypass -File .\scripts\windows\install_all.ps1
# 或双击 .\scripts\windows\oneclick_start.bat
```

脚本将：
- 离线安装 Python 依赖（wheelhouse）
- 离线解压 Node + npm
- 离线安装 Appium（tgz）
- 离线解压 platform-tools（adb）
- 启动 GUI（pythonw）

---

## 体积与更新建议

大致体积（仅供参考）：
- Node LTS Zip： ~30~40 MB
- Appium tgz： ~10 MB（含依赖由 npm 解决，首次安装会展开到全局目录）
- Platform Tools： ~10 MB
- Python wheels：按依赖数量与平台 ABI 变化而定（通常 30~60 MB）

更新节奏：
- 定期（或按版本发布）更新 vendor/ 内的四类文件
- 使用 SHA256SUMS.txt 做校验（脚本可选实现校验逻辑）

---

## 许可证与合规

- Node.js（https://nodejs.org/）：依据其 License（MIT）维护
- Appium CLI：遵循其开源许可证
- Android Platform Tools：来自 Google 的条款，分发需留意许可与镜像政策
- Python 第三方依赖：各自的 License，建议在发行包中附带 `THIRD_PARTY_NOTICES.txt`（可用 `pip-licenses` 生成）

---

## CI/CD 与发布产物

建议：
- 在 CI 中构建 `vendor-bundle.zip`（包含 `vendor/`）
- 将 `vendor-bundle.zip` 作为 Releases 附件或私有制品
- 在 README 提供“双轨安装”：
  - 在线轻量一键（现有）
  - 离线完全一键（下载 vendor-bundle.zip 解压后运行）

示例：在 Actions 中增加构建 wheelhouse 步骤（Windows Runner）：
```yaml
- name: Build wheelhouse
  shell: pwsh
  run: |
    python -m pip install -U pip wheel
    python -m pip download -r requirements.txt -d vendor/wheels
- name: Archive vendor
  uses: actions/upload-artifact@v4
  with:
    name: vendor-bundle
    path: vendor
```

---

## 常见问题

- Q：node-v*.zip 中是否包含 npm？
  - A：官方 Windows Zip 版包含 npm 与 node_modules/npm，解压后可直接 `npm -v`
- Q：离线安装 Appium 需要哪些前置？
  - A：只需可用的 node/npm。从 node Zip 解压后 npm 即可用，执行 `npm -g "<appium.tgz>"`
- Q：pip 离线安装缺包？
  - A：为保证覆盖，建议在与目标环境相同的 Python 版本、Windows 平台上执行 `pip download` 创建 wheelhouse；跨平台 wheel 需单独准备

---

## 下一步

- 我们将把“vendor 优先、在线回退”的逻辑合并进 [install_all.ps1](scripts/windows/install_all.ps1)（无需用户再手改）
- 可附带一个 `scripts\windows\make_offline_vendor.ps1` 辅助脚本，自动下载并填充 vendor（供“在线预打包”使用）
- 若需要，我们也可提供 macOS/Linux 的离线指引与 Bash 脚本版本
