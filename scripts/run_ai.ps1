# 启动 AI 服务（Flask，默认 http://localhost:5800）
# 用法：powershell -ExecutionPolicy Bypass -File scripts\run_ai.ps1
# 指定解释器：-Python "D:\path\to\python.exe"
param([string]$Python = "python")

$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..")

Push-Location (Join-Path $root "ai-service")
try {
    & $Python app.py
} finally {
    Pop-Location
}
