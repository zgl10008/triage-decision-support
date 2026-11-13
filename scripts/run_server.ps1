# 启动 Spring Boot 后端（默认 http://localhost:8014）
# 首次运行前请执行 server/src/main/resources/sql/schema.sql 并配置 .env.example 中的环境变量
# 用法：powershell -ExecutionPolicy Bypass -File scripts\run_server.ps1
$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..")

Push-Location (Join-Path $root "server")
try {
    mvn spring-boot:run
} finally {
    Pop-Location
}
