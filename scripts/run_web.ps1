# 启动 Vue 前端（默认 http://localhost:5174）
# 用法：powershell -ExecutionPolicy Bypass -File scripts\run_web.ps1
$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$web = Join-Path $root "web"

Push-Location $web
try {
    if (-not (Test-Path (Join-Path $web "node_modules"))) {
        npm install
    }
    npm run dev
} finally {
    Pop-Location
}
