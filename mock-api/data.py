"""模拟火电测点数据层。

生成 60 个脱敏测点、每个测点 30 天、5 分钟间隔的时序数据。
数据全部在内存中，无外部依赖，保证仓库可复现。
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta
from typing import Dict, List, Tuple

# 测点通用名（脱敏：仅保留电厂常见指标类别名，不含真实测点编码）
POINT_NAMES: List[str] = [
    "主汽温度", "主汽压力", "再热汽温", "给水流量", "凝结水流量", "烟气温度",
    "炉膛负压", "一次风压", "二次风压", "凝汽器真空", "机组负荷", "给煤量",
    "送风量", "引风量", "汽包水位", "排烟温度", "飞灰含碳量", "磨煤机电流",
    "送风机电流", "引风机电流", "给水泵电流", "循环水泵电流", "凝结水泵电流",
    "高压加热器水位", "低压加热器水位", "除氧器水位", "除氧器压力", "辅汽压力",
    "主蒸汽流量", "再热蒸汽流量", "补水量", "真空严密性", "轴承温度", "润滑油压",
    "密封油压", "氢压", "励磁电压", "励磁电流", "定子电压", "定子电流",
    "有功功率", "无功功率", "功率因数", "频率", "汽轮机转速", "胀差",
    "轴向位移", "缸胀", "调节级压力", "调节级温度", "高压缸排汽温度", "中压缸排汽温度",
    "低压缸排汽温度", "暖风器温度", "空预器入口烟温", "空预器出口烟温", "省煤器出口水温",
    "过热器出口汽温", "再热器出口汽温", "省煤器入口水温",
]

INTERVAL_MINUTES = 5
DEFAULT_DAYS = 30

# 每个测点的基准值与波动幅度（用于生成形态各异的模拟曲线）
_POINT_PROFILE: Dict[str, Tuple[float, float]] = {}


def _make_profile(name: str) -> Tuple[float, float]:
    rng = random.Random(hash(name) & 0xFFFF)
    base = round(rng.uniform(20.0, 540.0), 1)
    amp = round(base * rng.uniform(0.01, 0.08), 2)
    return base, amp


def _profile(name: str) -> Tuple[float, float]:
    if name not in _POINT_PROFILE:
        _POINT_PROFILE[name] = _make_profile(name)
    return _POINT_PROFILE[name]


class PointData:
    """单个测点的元信息 + 时序数据。"""

    def __init__(self, point_id: str, name: str, unit: str, ts_values: List[Tuple[datetime, float]]):
        self.point_id = point_id
        self.name = name
        self.unit = unit
        self.ts_values = ts_values

    def values_between(self, start: datetime, end: datetime) -> List[Tuple[datetime, float]]:
        """按时间范围过滤（模拟 SQL WHERE ts BETWEEN ? AND ?）。"""
        return [(ts, v) for ts, v in self.ts_values if start <= ts <= end]


def generate_series(name: str, start: datetime, days: int) -> List[Tuple[datetime, float]]:
    """按 5 分钟间隔生成一段带波动的模拟时序。"""
    base, amp = _profile(name)
    rng = random.Random(f"{name}-{start.isoformat()}")
    series: List[Tuple[datetime, float]] = []
    t = start
    total_points = days * 24 * 60 // INTERVAL_MINUTES
    for i in range(total_points):
        # 简单正弦趋势 + 随机噪声，模拟真实测量波动
        trend = base + amp * ((i / total_points) * 2 - 1)
        noise = amp * (rng.random() - 0.5) * 0.6
        value = round(trend + noise, 2)
        series.append((t, value))
        t += timedelta(minutes=INTERVAL_MINUTES)
    return series


def build_dataset(days: int = DEFAULT_DAYS, point_count: int = 60) -> Dict[str, PointData]:
    """构建全量模拟数据集。

    Returns:
        {point_id: PointData}
    """
    start = datetime(2026, 7, 1, 0, 0, 0)
    dataset: Dict[str, PointData] = {}
    for idx in range(min(point_count, len(POINT_NAMES))):
        name = POINT_NAMES[idx]
        point_id = f"point_{idx + 1:03d}"
        unit = "℃" if "温度" in name or "汽温" in name else (
            "MPa" if "压力" in name or "真空" in name else
            "t/h" if "流量" in name or "给煤量" in name else
            "kW" if "功率" in name or "负荷" in name else
            "A" if "电流" in name else
            "mm" if "水位" in name else
            "%" if "含碳" in name or "功率因数" in name else
            "Hz" if "频率" in name else
            "kPa" if "真空" in name else "—")
        dataset[point_id] = PointData(
            point_id=point_id,
            name=name,
            unit=unit,
            ts_values=generate_series(name, start, days),
        )
    return dataset


if __name__ == "__main__":
    ds = build_dataset()
    pid = "point_001"
    print(f"测点总数: {len(ds)}")
    print(f"示例测点: {pid} -> {ds[pid].name} ({ds[pid].unit})")
    print(f"单测点数据行数: {len(ds[pid].ts_values)}")
    print(f"首行: {ds[pid].ts_values[0]}")
    print(f"末行: {ds[pid].ts_values[-1]}")
