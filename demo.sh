#!/usr/bin/env bash
# 一键演示：起 mock 数据接口 → 展示 4 组接口 → batch vs n1 性能对比
# 用法：./demo.sh   （依赖 Docker，Windows 用 demo.ps1）

set -euo pipefail
BASE="http://localhost:8018"
# 兼容 docker compose（v2）与 docker-compose（v1 standalone）
if docker compose version >/dev/null 2>&1; then COMPOSE="docker compose"; else COMPOSE="docker-compose"; fi

echo "==> 1/4 构建并启动 mock 数据接口"
$COMPOSE up -d --build

echo "==> 2/4 等待服务就绪"
for i in $(seq 1 30); do
  if curl -sf "$BASE/health" >/dev/null 2>&1; then break; fi
  sleep 1
  [ "$i" = 30 ] && { echo "服务启动超时"; exit 1; }
done

echo "==> 3/4 接口演示"
echo "--- GET /health ---"
curl -s "$BASE/health" | python3 -c "import json,sys; print(json.dumps(json.load(sys.stdin), ensure_ascii=False, indent=2))"

echo "--- GET /points?page=1&size=3 ---"
curl -s "$BASE/points?page=1&size=3" | python3 -c "import json,sys; print(json.dumps(json.load(sys.stdin), ensure_ascii=False, indent=2))"

echo "--- GET /points/point_001/values (最近 3 条) ---"
curl -s "$BASE/points/point_001/values?start=2026-07-01&end=2026-07-07&limit=3" | python3 -c "import json,sys; print(json.dumps(json.load(sys.stdin), ensure_ascii=False, indent=2))"

echo "==> 4/4 性能对比：10 个测点 × 7 天报表，batch vs n1"
echo "--- mode=batch（优化后：批量 IN + Map 索引）---"
curl -s "$BASE/reports/monthly?points=point_001,point_002,point_003,point_004,point_005,point_006,point_007,point_008,point_009,point_010&start=2026-07-01&end=2026-07-07&mode=batch" \
  | python3 -c "import json,sys; d=json.load(sys.stdin); print(f\"  模式={d['mode']}  SQL调用={d['query_count']}次  耗时={d['elapsed_ms']:.1f}ms  行数={len(d['rows'])}\")"

echo "--- mode=n1（复刻优化前的循环逐点）---"
curl -s "$BASE/reports/monthly?points=point_001,point_002,point_003,point_004,point_005,point_006,point_007,point_008,point_009,point_010&start=2026-07-01&end=2026-07-07&mode=n1" \
  | python3 -c "import json,sys; d=json.load(sys.stdin); print(f\"  模式={d['mode']}  SQL调用={d['query_count']}次  耗时={d['elapsed_ms']:.1f}ms  行数={len(d['rows'])}\")"

echo ""
echo "✅ 演示完成。更多玩法："
echo "  - 接口文档（Swagger UI）：$BASE/docs"
echo "  - 全量自检：$COMPOSE run --rm verify"
echo "  - 停止：$COMPOSE down"
