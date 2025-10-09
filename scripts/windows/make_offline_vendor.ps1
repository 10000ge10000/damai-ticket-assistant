Param(
    [Parameter(Mandatory = $false)]
    [string]$PythonExe = "python",

    [Parameter(Mandatory = $false)]
    [string]$NodeZipUrl = "https://nodejs.org/dist/latest-v20.x/node-v20.11.1-win-x64.zip",

    [Parameter(Mandatory = $false)]
    [string]$PlatformToolsUrl = "https://dl.google.com/android/repository/platform-tools-latest-windows.zip"
)

# 输出统一为 UTF-8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "  生成离线依赖包（vendor/） - Windows  " -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan

# 项目根目录（脚本位于 scripts\windows）
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location $Root
Write-Host "[INFO] 项目根目录: $Root" -ForegroundColor Cyan

# 目录结构
$vendorDir = Join-Path $Root "vendor"
$wheelsDir = Join-Path $vendorDir "wheels"
$nodeDir   = Join-Path $vendorDir "node"
$appiumDir = Join-Path $vendorDir "appium"
$ptDir     = Join-Path $vendorDir "platform-tools"

# 创建目录
foreach ($d in @($vendorDir, $wheelsDir, $nodeDir, $appiumDir, $ptDir)) {
    if (-not (Test-Path $d)) {
        New-Item -ItemType Directory -Force -Path $d | Out-Null
    }
}

function Ensure-Command {
    param([string]$Name)
    try {
        return (Get-Command $Name -ErrorAction Stop).Source
    } catch {
        return $null
    }
}

function Step-Python-Wheelhouse {
    Write-Host "[STEP] 构建 Python wheelhouse..." -ForegroundColor Cyan
    $py = Ensure-Command $PythonExe
    if (-not $py) {
        $py = Ensure-Command "py"
    }
    if (-not $py) {
        Write-Host "[ERROR] 未检测到 Python，请先安装并加入 PATH" -ForegroundColor Red
        return $false
    }

    # 确保 pip wheel 可用
    & $py -m pip install -U pip wheel
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[WARN] pip/wheel 安装失败，继续尝试下载依赖..." -ForegroundColor Yellow
    }

    # 下载 requirements 依赖为本地 wheel
    & $py -m pip download -r requirements.txt -d $wheelsDir
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] 依赖下载失败，请检查 requirements 与网络环境" -ForegroundColor Red
        return $false
    }

    Write-Host "[SUCCESS] wheelhouse 生成完成: $wheelsDir" -ForegroundColor Green
    return $true
}

function Step-Node-Zip {
    Write-Host "[STEP] 下载 Node.js LTS Zip..." -ForegroundColor Cyan
    $dest = Join-Path $nodeDir (Split-Path $NodeZipUrl -Leaf)
    try {
        Invoke-WebRequest -Uri $NodeZipUrl -OutFile $dest -UseBasicParsing
        Write-Host "[SUCCESS] Node Zip 已下载: $(Split-Path $dest -Leaf)" -ForegroundColor Green
        return $true
    } catch {
        Write-Host "[ERROR] Node Zip 下载失败: $($_.Exception.Message)" -ForegroundColor Red
        Write-Host "        可替换参数 -NodeZipUrl 指向具体 LTS 版本" -ForegroundColor Yellow
        return $false
    }
}

function Step-Appium-Pack {
    Write-Host "[STEP] 打包 Appium 离线 tgz..." -ForegroundColor Cyan
    $npm = Ensure-Command "npm"
    if (-not $npm) {
        Write-Host "[WARN] 未检测到 npm，跳过 Appium tgz 打包。完成 Node 安装后重试。" -ForegroundColor Yellow
        return $false
    }
    try {
        Push-Location $appiumDir
        & $npm pack appium@latest
        & $npm pack appium-doctor@latest
        Pop-Location
        Write-Host "[SUCCESS] 生成 appium/appium-doctor tgz 完成" -ForegroundColor Green
        return $true
    } catch {
        Write-Host "[WARN] Appium tgz 打包失败: $($_.Exception.Message)" -ForegroundColor Yellow
        return $false
    }
}

function Step-PlatformTools-Zip {
    Write-Host "[STEP] 下载 Android Platform Tools..." -ForegroundColor Cyan
    $dest = Join-Path $ptDir (Split-Path $PlatformToolsUrl -Leaf)
    try {
        Invoke-WebRequest -Uri $PlatformToolsUrl -OutFile $dest -UseBasicParsing
        Write-Host "[SUCCESS] Platform Tools Zip 已下载: $(Split-Path $dest -Leaf)" -ForegroundColor Green
        return $true
    } catch {
        Write-Host "[WARN] Platform Tools 下载失败: $($_.Exception.Message)" -ForegroundColor Yellow
        return $false
    }
}

function Step-Checksums {
    Write-Host "[STEP] 生成 SHA256SUMS..." -ForegroundColor Cyan
    $sumFile = Join-Path $vendorDir "SHA256SUMS.txt"
    try {
        Get-ChildItem -Path $vendorDir -Recurse -File | ForEach-Object {
            $hash = Get-FileHash $_.FullName -Algorithm SHA256
            "{0}  {1}" -f $hash.Hash, $_.FullName
        } | Set-Content -Path $sumFile -Encoding UTF8
        Write-Host "[SUCCESS] 校验文件生成完成: $sumFile" -ForegroundColor Green
        return $true
    } catch {
        Write-Host "[WARN] 生成校验文件失败: $($_.Exception.Message)" -ForegroundColor Yellow
        return $false
    }
}

# 执行各步骤
$okWheels = Step-Python-Wheelhouse
$okNode   = Step-Node-Zip
$okAppium = Step-Appium-Pack
$okPT     = Step-PlatformTools-Zip
$okSum    = Step-Checksums

Write-Host ""
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host " 离线包生成结果：" -ForegroundColor Cyan
Write-Host " - wheels:  $(if($okWheels){'OK'}else{'FAIL'})"
Write-Host " - node:    $(if($okNode){'OK'}else{'FAIL'})"
Write-Host " - appium:  $(if($okAppium){'OK'}else{'SKIP/FAIL'})"
Write-Host " - pt:      $(if($okPT){'OK'}else{'FAIL'})"
Write-Host " - sums:    $(if($okSum){'OK'}else{'FAIL'})"
Write-Host "=========================================" -ForegroundColor Cyan

Write-Host "`n使用说明：" -ForegroundColor Cyan
Write-Host "1) 将 vendor/ 目录随仓库或发布包一并分发。" -ForegroundColor Gray
Write-Host "2) 目标机器上直接运行：pwsh ./scripts/windows/install_all.ps1" -ForegroundColor Gray
Write-Host "   脚本会优先使用 vendor 离线内容（wheels/node/appium/platform-tools），无法使用时回退在线安装。" -ForegroundColor Gray

exit 0