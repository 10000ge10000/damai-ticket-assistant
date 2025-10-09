Param(

    [Parameter(Mandatory = $false)]
    [string]$VenvPath = ".\.venv",

    [Parameter(Mandatory = $false)]
    [switch]$StartGui = $true,

    [Parameter(Mandatory = $false)]
    [switch]$SkipNode,

    [Parameter(Mandatory = $false)]
    [switch]$SkipAppium,

    [Parameter(Mandatory = $false)]
    [switch]$SkipAdb
)

# 输出编码统一为 UTF-8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "  Damai Ticket Assistant 一键安装 + 启动  " -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan

# 定位到项目根目录（脚本位于 scripts\windows）
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location $Root
Write-Host "[INFO] 项目根目录: $Root" -ForegroundColor Cyan

function Ensure-Command {
    param(
        [Parameter(Mandatory = $true)][string]$Name
    )
    try {
        $cmd = (Get-Command $Name -ErrorAction Stop).Source
        return $cmd
    } catch {
        return $null
    }
}

function Ensure-Python {
    $pythonExe = Ensure-Command "python"
    if (-not $pythonExe) {
        $pythonExe = Ensure-Command "py"
    }
    if (-not $pythonExe) {
        Write-Host "[ERROR] 未检测到 Python，请安装 3.9+ 并勾选 Add to PATH" -ForegroundColor Red
        Write-Host "        下载地址: https://www.python.org/downloads/" -ForegroundColor Yellow
        exit 2
    }
    Write-Host "[INFO] 使用 Python: $pythonExe" -ForegroundColor Green
    return $pythonExe
}

function Ensure-Venv {
    param([string]$PythonExe, [string]$Path)
    if (-not (Test-Path $Path)) {
        Write-Host "[INFO] 创建虚拟环境: $Path" -ForegroundColor Cyan
        & $PythonExe -m venv $Path
        if ($LASTEXITCODE -ne 0) {
            Write-Host "[ERROR] 创建虚拟环境失败" -ForegroundColor Red
            exit 2
        }
    } else {
        Write-Host "[INFO] 虚拟环境已存在: $Path" -ForegroundColor Green
    }

    $activate = Join-Path $Path "Scripts\Activate.ps1"
    if (-not (Test-Path $activate)) {
        Write-Host "[ERROR] 未找到激活脚本: $activate" -ForegroundColor Red
        exit 2
    }

    Write-Host "[INFO] 激活虚拟环境..." -ForegroundColor Cyan
    . $activate
    if ($null -eq $env:VIRTUAL_ENV) {
        Write-Host "[WARN] 虚拟环境环境变量未设置，但继续尝试使用 venv 解释器" -ForegroundColor Yellow
    }
}

function Install-Requirements {
    Write-Host "[INFO] 升级 pip..." -ForegroundColor Cyan
    python -m pip install -U pip
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[WARN] 升级 pip 失败，继续安装依赖" -ForegroundColor Yellow
    }

    # vendor 优先：使用离线 wheelhouse 安装
    $vendorWheels = Join-Path $Root "vendor\wheels"
    if (Test-Path $vendorWheels) {
        Write-Host "[INFO] 检测到离线 wheelhouse，使用离线依赖安装..." -ForegroundColor Cyan
        pip install --no-index --find-links "$vendorWheels" -r requirements.txt
        if ($LASTEXITCODE -ne 0) {
            Write-Host "[WARN] 离线安装失败，回退在线安装..." -ForegroundColor Yellow
        } else {
            Write-Host "[SUCCESS] 离线依赖安装完成" -ForegroundColor Green
            return
        }
    }

    Write-Host "[INFO] 安装项目依赖（requirements.txt）..." -ForegroundColor Cyan
    pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[WARN] 直接安装失败，尝试使用清华镜像源..." -ForegroundColor Yellow
        pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt
        if ($LASTEXITCODE -ne 0) {
            Write-Host "[ERROR] 依赖安装失败，请检查网络或稍后重试" -ForegroundColor Red
            exit 2
        }
    }
    Write-Host "[SUCCESS] 依赖安装完成" -ForegroundColor Green
}

function Ensure-Node {
    if ($SkipNode) {
        Write-Host "[INFO] 跳过 Node.js 检测" -ForegroundColor Yellow
        return
    }

    # 1) PATH 上已存在
    $nodeExe = Ensure-Command "node"
    if ($nodeExe) {
        $ver = (& $nodeExe --version)
        Write-Host "[INFO] 检测到 Node.js: $ver" -ForegroundColor Green
        return
    }

    # 2) vendor 优先：解压离线 Node 压缩包并添加到 PATH
    $toolsRoot = Join-Path $PSScriptRoot "tools"
    if (-not (Test-Path $toolsRoot)) { New-Item -ItemType Directory -Force -Path $toolsRoot | Out-Null }
    $vendorNodeDir = Join-Path $Root "vendor\node"
    if (Test-Path $vendorNodeDir) {
        $zip = Get-ChildItem -Path $vendorNodeDir -Filter "node-*.zip" -File -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1
        if ($null -ne $zip) {
            $dest = Join-Path $toolsRoot "node"
            if (Test-Path $dest) { Remove-Item -Recurse -Force $dest }
            New-Item -ItemType Directory -Force -Path $dest | Out-Null
            Write-Host "[INFO] 正在解压离线 Node 包: $($zip.Name)" -ForegroundColor Cyan
            Expand-Archive -Path $zip.FullName -DestinationPath $dest -Force
            # 查找 node.exe 所在目录并加入 PATH
            $nodeExePath = Get-ChildItem -Path $dest -Recurse -Filter "node.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
            if ($null -ne $nodeExePath) {
                $nodeDir = Split-Path $nodeExePath.FullName -Parent
                $env:Path = "$nodeDir;$env:Path"
                $ver = (& "$nodeDir\node.exe" --version)
                Write-Host "[SUCCESS] 已使用离线 Node：$ver" -ForegroundColor Green
                return
            } else {
                Write-Host "[WARN] 离线 Node 解压后未找到 node.exe" -ForegroundColor Yellow
            }
        }
    }

    # 3) 在线安装（winget）
    Write-Host "[WARN] 未检测到 Node.js，尝试通过 winget 安装 LTS 版本..." -ForegroundColor Yellow
    $wingetExe = Ensure-Command "winget"
    if (-not $wingetExe) {
        Write-Host "[ERROR] 未检测到 winget，无法自动安装 Node.js" -ForegroundColor Red
        Write-Host "        请手动安装: https://nodejs.org/ (勾选添加到 PATH)" -ForegroundColor Yellow
        return
    }
    & $wingetExe install --id OpenJS.NodeJS.LTS -e --accept-source-agreements --accept-package-agreements
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[WARN] winget 安装 Node.js 失败，请稍后手动安装" -ForegroundColor Yellow
        return
    }
    Write-Host "[SUCCESS] Node.js 安装流程已完成" -ForegroundColor Green
}

function Ensure-Appium {
    if ($SkipAppium) {
        Write-Host "[INFO] 跳过 Appium CLI 检测" -ForegroundColor Yellow
        return
    }
    $appiumExe = Ensure-Command "appium"
    if ($appiumExe) {
        $ver = (& $appiumExe -v)
        Write-Host "[INFO] 检测到 Appium CLI: $ver" -ForegroundColor Green
        return
    }

    $npmExe = Ensure-Command "npm"
    if (-not $npmExe) {
        Write-Host "[ERROR] 未检测到 npm，无法安装 Appium CLI。请先安装 Node.js" -ForegroundColor Red
        return
    }

    # vendor 优先：离线 appium/appium-doctor 安装
    $vendorAppiumDir = Join-Path $Root "vendor\appium"
    $installedOffline = $false
    if (Test-Path $vendorAppiumDir) {
        $tgz = Get-ChildItem -Path $vendorAppiumDir -Filter "appium-*.tgz" -File -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1
        if ($null -ne $tgz) {
            Write-Host "[INFO] 使用离线 appium tgz 安装..." -ForegroundColor Cyan
            & $npmExe install -g "$($tgz.FullName)" --loglevel error
            if ($LASTEXITCODE -eq 0) {
                $installedOffline = $true
                $doctor = Get-ChildItem -Path $vendorAppiumDir -Filter "appium-doctor-*.tgz" -File -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1
                if ($null -ne $doctor) {
                    & $npmExe install -g "$($doctor.FullName)" --loglevel error
                }
            } else {
                Write-Host "[WARN] 离线 appium 安装失败，回退在线安装..." -ForegroundColor Yellow
            }
        }
    }

    if (-not $installedOffline) {
        Write-Host "[INFO] 安装 Appium CLI（npm -g appium）..." -ForegroundColor Cyan
        & $npmExe install -g appium@latest --loglevel error
        if ($LASTEXITCODE -ne 0) {
            Write-Host "[WARN] Appium 安装失败，可稍后手动执行: npm install -g appium" -ForegroundColor Yellow
            return
        }
    }

    $appiumExe = Ensure-Command "appium"
    if ($appiumExe) {
        $ver = (& $appiumExe -v)
        Write-Host "[SUCCESS] Appium CLI 可用: $ver" -ForegroundColor Green
    } else {
        Write-Host "[WARN] Appium CLI 未检测到，请检查 npm 全局目录权限或稍后重试" -ForegroundColor Yellow
    }
}

function Ensure-Adb {
    if ($SkipAdb) {
        Write-Host "[INFO] 跳过 adb 检测" -ForegroundColor Yellow
        return
    }
    $adbExe = Ensure-Command "adb"
    if ($adbExe) {
        $ver = (& $adbExe version)
        Write-Host "[INFO] 检测到 adb: $ver" -ForegroundColor Green
        return
    }

    $toolsRoot = Join-Path $PSScriptRoot "tools"
    if (-not (Test-Path $toolsRoot)) { New-Item -ItemType Directory -Force -Path $toolsRoot | Out-Null }
    $platformDir = Join-Path $toolsRoot "platform-tools"

    # 1) vendor 优先：离线 platform-tools
    $vendorPtDir = Join-Path $Root "vendor\platform-tools"
    $offlineReady = $false
    if (Test-Path $vendorPtDir) {
        $zip = Get-ChildItem -Path $vendorPtDir -Filter "platform-tools*.zip" -File -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1
        if ($null -ne $zip) {
            try {
                Write-Host "[INFO] 使用离线 Platform Tools..." -ForegroundColor Cyan
                if (Test-Path $platformDir) { Remove-Item -Recurse -Force $platformDir }
                Expand-Archive -Path $zip.FullName -DestinationPath $toolsRoot -Force
                $offlineReady = $true
            } catch {
                Write-Host "[WARN] 离线 Platform Tools 解压失败：$($_.Exception.Message)" -ForegroundColor Yellow
            }
        }
    }

    # 2) 在线下载回退
    if (-not $offlineReady) {
        Write-Host "[WARN] 未检测到离线 Platform Tools，尝试在线下载..." -ForegroundColor Yellow
        $zipPath = Join-Path $toolsRoot "platform-tools.zip"
        try {
            Write-Host "[INFO] 下载平台工具..." -ForegroundColor Cyan
            Invoke-WebRequest -Uri "https://dl.google.com/android/repository/platform-tools-latest-windows.zip" -OutFile $zipPath -UseBasicParsing
            Write-Host "[INFO] 解压平台工具..." -ForegroundColor Cyan
            if (Test-Path $platformDir) { Remove-Item -Recurse -Force $platformDir }
            Expand-Archive -Path $zipPath -DestinationPath $toolsRoot -Force
            Remove-Item $zipPath -Force
        } catch {
            Write-Host "[ERROR] 平台工具下载或解压失败: $($_.Exception.Message)" -ForegroundColor Red
            Write-Host "        请手动安装后将 platform-tools 加入 PATH" -ForegroundColor Yellow
            return
        }
    }

    # 将当前会话 PATH 追加 platform-tools
    $env:Path = "$platformDir;$env:Path"
    Write-Host "[INFO] 已将 $platformDir 追加到当前会话 PATH" -ForegroundColor Green
    $adbExe = Ensure-Command "adb"
    if ($adbExe) {
        $ver = (& $adbExe version)
        Write-Host "[SUCCESS] adb 可用: $ver" -ForegroundColor Green
    } else {
        Write-Host "[WARN] adb 仍不可用，请关闭终端并重新打开或重启系统" -ForegroundColor Yellow
    }
}

# 流程执行
$pythonExe = Ensure-Python
Ensure-Venv -PythonExe $pythonExe -Path $VenvPath
Install-Requirements
Ensure-Node
Ensure-Appium
Ensure-Adb

if ($StartGui) {
    Write-Host "[INFO] 启动 GUI..." -ForegroundColor Cyan
    $pythonwExe = Ensure-Command "pythonw"
    if ($pythonwExe) {
        & $pythonwExe "$Root\start_gui.pyw"
    } else {
        # 回退方案：使用 python 启动（会留下终端窗口）
        python "$Root\start_gui.pyw"
    }
    Write-Host "[SUCCESS] 启动流程已触发。如未弹出 GUI，请检查日志与依赖状态。" -ForegroundColor Green
} else {
    Write-Host "[INFO] 已完成一键安装，未自动启动 GUI（-StartGui=false）" -ForegroundColor Yellow
}

exit 0