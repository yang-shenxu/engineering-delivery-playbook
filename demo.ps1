# 一键演示（Windows）：起 mock 数据接口 -> 展示接口 -> batch vs n1 性能对比
# 用法：在仓库根目录 PowerShell 执行  ./demo.ps1
# 依赖：Docker Desktop 已启动 + docker-compose 可用

$ErrorActionPreference = 'Stop'
$BASE = 'http://localhost:8018'

Write-Host '==> 1/4 构建并启动 mock 数据接口'
docker-compose up -d --build

Write-Host '==> 2/4 等待服务就绪'
$ready = $false
for ($i = 0; $i -lt 30; $i++) {
    try { Invoke-RestMethod "$BASE/health" -TimeoutSec 2 | Out-Null; $ready = $true; break } catch { Start-Sleep -Seconds 1 }
}
if (-not $ready) { Write-Host '服务启动超时'; exit 1 }

Write-Host '==> 3/4 接口演示'
Write-Host '--- GET /health ---'
Invoke-RestMethod "$BASE/health" | ConvertTo-Json -Depth 4

Write-Host '--- GET /points?page=1&size=3 ---'
$pts = Invoke-RestMethod "$BASE/points?page=1&size=3"
"total=$($pts.total) | 前3个测点: " + (($pts.items | ForEach-Object { "$($_.name)($($_.point_id))" }) -join ', ')

Write-Host '--- GET /points/point_001/values (最近 3 条) ---'
$v = Invoke-RestMethod "$BASE/points/point_001/values?start=2026-07-01&end=2026-07-07&limit=3"
"total=$($v.total) | 首条: $($v.data[0].ts) = $($v.data[0].value) $($v.unit)"

Write-Host '==> 4/4 性能对比：10 个测点 x 7 天报表，batch vs n1'
$url = "$BASE/reports/monthly?points=point_001,point_002,point_003,point_004,point_005,point_006,point_007,point_008,point_009,point_010&start=2026-07-01&end=2026-07-07"

Write-Host '--- mode=batch（优化后：批量 IN + Map 索引）---'
$b = Invoke-RestMethod "$url&mode=batch"
"  模式=$($b.mode)  SQL调用=$($b.query_count)次  耗时=$([math]::Round($b.elapsed_ms,1))ms  行数=$($b.rows.Count)"

Write-Host '--- mode=n1（复刻优化前的循环逐点）---'
$n = Invoke-RestMethod "$url&mode=n1"
"  模式=$($n.mode)  SQL调用=$($n.query_count)次  耗时=$([math]::Round($n.elapsed_ms,1))ms  行数=$($n.rows.Count)"

Write-Host ''
Write-Host '✅ 演示完成。更多玩法：'
Write-Host "  - 接口文档（Swagger UI）：$BASE/docs"
Write-Host '  - 全量自检：docker-compose run --rm verify'
Write-Host '  - 停止：docker-compose down'
