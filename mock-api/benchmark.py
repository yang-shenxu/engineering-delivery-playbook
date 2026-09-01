"""性能对比基准脚本：复刻案例 01 的「2700 次 SQL → 4 次」可复现演示。

直接调用查询引擎（不走 HTTP），避免网络开销干扰对比。
用法：
    python benchmark.py [测点数] [天数]
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta

from data import build_dataset
from query_engine import QueryEngine

# 每次模拟 DB 查询的往返延迟（连接+网络+执行），贴近真实数据库
DB_LATENCY_MS = 0.5


def main(point_count: int = 60, days: int = 30) -> None:
    ds = build_dataset()
    engine = QueryEngine(ds, db_latency_ms=DB_LATENCY_MS)
    point_ids = list(ds.keys())[:point_count]
    start = datetime(2026, 7, 1)
    end = start + timedelta(days=days - 1)

    rows_n1, q_n1, ms_n1 = engine.run_report(point_ids, start, end, "n1")
    rows_batch, q_batch, ms_batch = engine.run_report(point_ids, start, end, "batch")

    width = 72
    print("=" * width)
    print(f"  月度日报表性能对比  |  测点 {point_count} 个  ×  {days} 天")
    print("=" * width)
    print(f"  {'实现':<20}{'SQL 查询次数':<16}{'耗时 (ms)':<12}")
    print("-" * width)
    print(f"  {'N+1 循环逐点(优化前)':<16}{q_n1:<20}{ms_n1:<12}")
    print(f"  {'批量 IN + Map(优化后)':<16}{q_batch:<20}{ms_batch:<12}")
    print("-" * width)
    speedup = ms_n1 / ms_batch if ms_batch > 0 else float("inf")
    reduction = q_n1 / q_batch if q_batch > 0 else float("inf")
    print(f"  SQL 调用次数: {q_n1} → {q_batch}  (降至 1/{reduction:.0f})")
    print(f"  响应耗时:     {ms_n1}ms → {ms_batch}ms  (提速 {speedup:.0f}x)")
    print("=" * width)
    print(f"\n  表头: {rows_batch[0]}")
    print(f"  示例: {rows_batch[1]}")


if __name__ == "__main__":
    n_points = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    n_days = int(sys.argv[2]) if len(sys.argv) > 2 else 30
    main(n_points, n_days)
