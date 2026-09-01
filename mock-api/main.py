"""FastAPI 模拟实时数据接口（脱敏版）。

对应 README 架构图中的 Mock API：以 FastAPI 模拟火优实时数据接口，
提供「测点 / 时序 / 报表」三类 REST 接口，并内置 N+1 vs 批量查询性能对比。

启动：
    uvicorn main:app --port 8018 --reload
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Query

from data import build_dataset
from query_engine import QueryEngine

app = FastAPI(
    title="Mock 实时数据接口（工程交付演示）",
    description="模拟火电测点实时数据：测点列表、单点时序、月度报表（N+1 与批量两种实现）",
    version="0.1.0",
)

DATASET = build_dataset()
ENGINE = QueryEngine(DATASET)

PAGE_SIZE = 20


def _parse_date(value: str, field: str) -> datetime:
    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=422, detail=f"{field} 格式应为 YYYY-MM-DD，收到: {value}")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "points": len(DATASET)}


@app.get("/points")
def list_points(page: int = Query(1, ge=1), size: int = Query(PAGE_SIZE, ge=1, le=100)) -> dict:
    """测点列表（分页）。"""
    items = list(DATASET.values())
    start = (page - 1) * size
    end = start + size
    return {
        "total": len(items),
        "page": page,
        "size": size,
        "items": [
            {"point_id": p.point_id, "name": p.name, "unit": p.unit}
            for p in items[start:end]
        ],
    }


@app.get("/points/{point_id}/values")
def point_values(
    point_id: str,
    start: str = Query(..., description="起始日期 YYYY-MM-DD"),
    end: str = Query(..., description="结束日期 YYYY-MM-DD"),
    limit: int = Query(500, ge=1, le=5000),
) -> dict:
    """单测点时序数据。"""
    if point_id not in DATASET:
        raise HTTPException(status_code=404, detail=f"测点不存在: {point_id}")
    start_dt = _parse_date(start, "start")
    end_dt = _parse_date(end, "end")
    point = DATASET[point_id]
    values = point.values_between(start_dt, end_dt)
    return {
        "point_id": point_id,
        "name": point.name,
        "unit": point.unit,
        "total": len(values),
        "data": [
            {"ts": ts.strftime("%Y-%m-%d %H:%M"), "value": v}
            for ts, v in values[:limit]
        ],
    }


@app.get("/reports/monthly")
def report_monthly(
    points: str = Query(..., description="测点列表，逗号分隔，如 point_001,point_002"),
    start: str = Query(..., description="起始日期 YYYY-MM-DD"),
    end: str = Query(..., description="结束日期 YYYY-MM-DD"),
    mode: str = Query("batch", pattern="^(batch|n1)$", description="batch=批量优化版 / n1=复刻优化前的循环逐点版"),
) -> dict:
    """月度报表：统一二维数组 + 中文表头。

    mode=batch 走批量 IN + Map 索引（优化后）；
    mode=n1 走循环逐点查询（复刻 N+1 慢实现），用于性能对比演示。
    """
    point_ids = [p.strip() for p in points.split(",") if p.strip()]
    unknown = [p for p in point_ids if p not in DATASET]
    if unknown:
        raise HTTPException(status_code=404, detail=f"测点不存在: {unknown}")
    start_dt = _parse_date(start, "start")
    end_dt = _parse_date(end, "end")

    rows, query_count, elapsed_ms = ENGINE.run_report(point_ids, start_dt, end_dt, mode)
    return {
        "mode": mode,
        "points": len(point_ids),
        "days": (end_dt - start_dt).days + 1,
        "query_count": query_count,
        "elapsed_ms": elapsed_ms,
        "rows": rows,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8018)
