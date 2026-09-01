"""报表查询引擎：N+1 与 批量查询两种实现（案例 01 的可运行复刻）。

问题背景（详见 docs/case-studies/01-report-query-optimization.md）：
    老报表实现为「每测点 × 每时段」循环逐条查询，最差 2700 次 SQL 调用、40s；
    重构后「批量 IN 查询 + 内存 Map 索引」，4 次 SQL、亚秒级响应。

本模块在内存模拟数据集上复刻两种实现，并统计「数据库查询次数」与耗时，
让性能对比可复现、可量化。
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta
from typing import Dict, List

from data import PointData


class QueryEngine:
    """持有点位数据，提供两种报表查询实现，内置查询计数器。"""

    def __init__(self, dataset: Dict[str, PointData], db_latency_ms: float = 0.0):
        self.dataset = dataset
        self.query_count = 0  # 模拟数据库查询次数
        self.db_latency_ms = db_latency_ms  # 每次查询的模拟 DB 往返延迟

    def _simulate_latency(self) -> None:
        """模拟一次数据库往返延迟（连接 + 网络 + 执行）。"""
        if self.db_latency_ms > 0:
            time.sleep(self.db_latency_ms / 1000)

    # ---------- 底层模拟 DB 查询 ----------

    def _db_query(self, point_id: str, start: datetime, end: datetime) -> List[tuple]:
        """模拟一次数据库查询：单测点单时间范围。"""
        self.query_count += 1
        self._simulate_latency()
        return self.dataset[point_id].values_between(start, end)

    def _db_query_bulk(self, point_ids: List[str], start: datetime, end: datetime) -> Dict[str, List[tuple]]:
        """模拟一次批量查询：IN 多测点一次性取数。"""
        self.query_count += 1
        self._simulate_latency()
        return {pid: self.dataset[pid].values_between(start, end) for pid in point_ids}

    def fetch_bulk(self, point_ids: List[str], start: datetime, end: datetime) -> Dict[str, List[tuple]]:
        """公开批量取数接口：一次查询返回多测点时序数据（供报表工具等消费）。"""
        return self._db_query_bulk(point_ids, start, end)

    # ---------- 报表聚合（二维数组 + 中文表头，对齐真实接口规范） ----------

    @staticmethod
    def _slot_buckets(start: datetime, end: datetime) -> List[datetime]:
        """把时间范围切分为日粒度时段（报表列）。"""
        buckets: List[datetime] = []
        day = start.replace(hour=0, minute=0, second=0, microsecond=0)
        while day <= end:
            buckets.append(day)
            day += timedelta(days=1)
        return buckets

    def report_monthly_n1(self, point_ids: List[str], start: datetime, end: datetime) -> List[List[str]]:
        """优化前：N+1 循环查询。

        对每个测点、每个时段逐条查询（模拟最差实现）。
        查询次数 ≈ 测点数 × 时段数。
        """
        self.query_count = 0
        buckets = self._slot_buckets(start, end)
        header = ["测点"] + [b.strftime("%Y-%m-%d") for b in buckets]
        rows: List[List[str]] = [header]
        for pid in point_ids:
            point = self.dataset[pid]
            row = [f"{point.name}({pid})"]
            for bucket in buckets:
                slot_end = bucket.replace(hour=23, minute=59, second=59)
                values = self._db_query(pid, bucket, slot_end)
                avg = round(sum(v for _, v in values) / len(values), 2) if values else ""
                row.append(str(avg))
            rows.append(row)
        return rows

    def report_monthly_batch(self, point_ids: List[str], start: datetime, end: datetime) -> List[List[str]]:
        """优化后：批量 IN 查询 + 内存 Map 索引。

        一次取全部测点数据到内存，再用索引聚合。
        查询次数 = 1（批量）+ 可选回读校验。
        """
        self.query_count = 0
        buckets = self._slot_buckets(start, end)
        header = ["测点"] + [b.strftime("%Y-%m-%d") for b in buckets]
        rows: List[List[str]] = [header]

        bulk = self._db_query_bulk(point_ids, start, end)
        # 内存 Map 索引：point_id -> {日期 -> 当日值列表}
        index: Dict[str, Dict[datetime, List[float]]] = {}
        for pid, ts_values in bulk.items():
            day_map: Dict[datetime, List[float]] = {}
            for ts, v in ts_values:
                day = ts.replace(hour=0, minute=0, second=0, microsecond=0)
                day_map.setdefault(day, []).append(v)
            index[pid] = day_map

        for pid in point_ids:
            point = self.dataset[pid]
            day_map = index[pid]
            row = [f"{point.name}({pid})"]
            for bucket in buckets:
                values = day_map.get(bucket, [])
                avg = round(sum(values) / len(values), 2) if values else ""
                row.append(str(avg))
            rows.append(row)
        return rows

    # ---------- 基准辅助 ----------

    def run_report(self, point_ids: List[str], start: datetime, end: datetime, mode: str) -> tuple:
        """执行报表查询，返回 (rows, query_count, elapsed_ms)。"""
        t0 = time.perf_counter()
        if mode == "n1":
            rows = self.report_monthly_n1(point_ids, start, end)
        else:
            rows = self.report_monthly_batch(point_ids, start, end)
        elapsed = (time.perf_counter() - t0) * 1000
        return rows, self.query_count, round(elapsed, 1)


if __name__ == "__main__":
    from data import build_dataset

    ds = build_dataset()
    engine = QueryEngine(ds)
    point_ids = list(ds.keys())[:8]
    start = datetime(2026, 7, 1)
    end = datetime(2026, 7, 15)

    rows_n1, q_n1, ms_n1 = engine.run_report(point_ids, start, end, "n1")
    rows_batch, q_batch, ms_batch = engine.run_report(point_ids, start, end, "batch")

    print(f"=== 8 测点 × 15 天 日报表 ===")
    print(f"N+1 模式:    {q_n1:>5} 次查询, {ms_n1:>8.1f} ms")
    print(f"批量模式:    {q_batch:>5} 次查询, {ms_batch:>8.1f} ms")
    print(f"提速: {(ms_n1 / ms_batch):.1f}x, 查询次数: {q_n1} → {q_batch}")
    print(f"\n表头: {rows_batch[0]}")
    print(f"首行: {rows_batch[1]}")
