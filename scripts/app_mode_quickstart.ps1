param(
    [Parameter(Mandatory = $false)]
    [string]
    $ConfigPath = (Join-Path $PSScriptRoot "..\damai_appium\config.jsonc"),

    [Parameter(Mandatory = $false)]
    [int]
    $Retries = 3,

    [Parameter(Mandatory = $false)]
    [string]
    $StartAt = "",

    [Parameter(Mandatory = $false)]
    [int]
    $WarmupSec = 0
)

Write-Host "[INFO] Damai App 模式快速启动脚本" -ForegroundColor Cyan
Write-Host "[INFO] 配置文件: $ConfigPath" -ForegroundColor Cyan
Write-Host "[INFO] 重试次数: $Retries" -ForegroundColor Cyan
if ($StartAt -and $StartAt.Trim().Length -gt 0) {
    Write-Host "[INFO] 定时开抢: $StartAt" -ForegroundColor Cyan
}
if ($WarmupSec -gt 0) {
    Write-Host "[INFO] 预热检查: $WarmupSec 秒" -ForegroundColor Cyan
}

if (-not (Test-Path $ConfigPath)) {
    Write-Host "[ERROR] 未找到配置文件: $ConfigPath" -ForegroundColor Red
    Write-Host "        请先在 damai_appium 目录准备 config.jsonc 或通过 GUI 导出配置" -ForegroundColor Yellow
    exit 2
}

$pythonCmd = $null
try {
    $pythonCmd = (Get-Command python -ErrorAction Stop).Source
} catch {
    try {
        $pythonCmd = (Get-Command py -ErrorAction Stop).Source
    } catch {
        Write-Host "[ERROR] 未找到 Python，请先安装并添加到 PATH" -ForegroundColor Red
        exit 2
    }
}

$arguments = @(
    "-m", "damai_appium.damai_app_v2",
    "--config", (Resolve-Path $ConfigPath).Path,
    "--retries", $Retries
)
if ($StartAt -and $StartAt.Trim().Length -gt 0) {
    $arguments += @("--start-at", $StartAt)
}
if ($WarmupSec -gt 0) {
    $arguments += @("--warmup-sec", $WarmupSec)
}

Write-Host "[INFO] 使用 Python 可执行文件: $pythonCmd" -ForegroundColor Cyan
Write-Host "[INFO] 开始执行 Appium 抢票流程..." -ForegroundColor Cyan

$env:PYTHONIOENCODING = "utf-8"
& $pythonCmd @arguments

if ($LASTEXITCODE -eq 0) {
    Write-Host "[SUCCESS] 抢票流程完成" -ForegroundColor Green
} else {
    Write-Host "[WARN] 抢票流程返回非零状态: $LASTEXITCODE" -ForegroundColor Yellow
    Write-Host "       可检查输出日志或在 GUI 中查看详细记录" -ForegroundColor Yellow
}

exit $LASTEXITCODE
