# 下载 BGE-M3 权重（约 2.2GB）到 ai-service/models/bge-m3
# 使用 ModelScope（国内网络可直连）；下载完成后运行 ai-service/build_index.py 重建索引
# 用法：powershell -ExecutionPolicy Bypass -File scripts\download_models.ps1
$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$target = Join-Path $root "ai-service\models\bge-m3"

Write-Host "下载 BGE-M3 到 $target ..."
modelscope download --model BAAI/bge-m3 --local_dir $target

Write-Host "权重下载完成，开始重建检索索引 ..."
Push-Location (Join-Path $root "ai-service")
try {
    python build_index.py
} finally {
    Pop-Location
}
