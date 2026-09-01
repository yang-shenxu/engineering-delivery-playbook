"""report_tool 测试：配置驱动、计算列、安全校验、查询次数。"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from report_tool import ReportTool, safe_eval  # noqa: E402

from data import build_dataset  # noqa: E402  (复用 mock-api 数据层)

CONFIGS = Path(__file__).resolve().parents[1] / "configs"
START = datetime(2026, 7, 1)
END = datetime(2026, 7, 31)


@pytest.fixture()
def tool() -> ReportTool:
    return ReportTool(build_dataset())


def test_load_config_monthly(tool: ReportTool) -> None:
    cfg = ReportTool.load_config(str(CONFIGS / "monthly_report.yaml"))
    assert cfg["title"] == "月度生产报表"
    assert len(cfg["columns"]) == 5
    assert len(cfg["rows"]) == 5


def test_monthly_report_structure(tool: ReportTool) -> None:
    rows, query_count, _ = tool.run(str(CONFIGS / "monthly_report.yaml"), START, END)
    # 表头 + 5 行数据
    assert len(rows) == 6
    assert rows[0] == ["测点", "月均负荷(MW)", "月最高(MW)", "月最低(MW)", "负荷率(%)"]
    # 批量查询：全部测点 1 次取数
    assert query_count == 1
    # 数据行：测点名列 + 4 个数值列
    for row in rows[1:]:
        assert len(row) == 5
        assert row[0].endswith("号机组")


def test_monthly_calc_col(tool: ReportTool) -> None:
    """计算列：负荷率 = 月均负荷 / 容量 * 100（容量从配置读取，不写死）。"""
    cfg = ReportTool.load_config(str(CONFIGS / "monthly_report.yaml"))
    capacities = {str(r["point"]): float(r["capacity"]) for r in cfg["rows"]}
    rows, _, _ = tool.run(str(CONFIGS / "monthly_report.yaml"), START, END)
    for row, row_cfg in zip(rows[1:], cfg["rows"]):
        avg_mw = float(row[1].removesuffix("MW"))
        factor = float(row[4].removesuffix("%"))
        assert factor == pytest.approx(avg_mw / capacities[str(row_cfg["point"])] * 100, abs=0.01)


def test_daily_summary_calc_cols(tool: ReportTool) -> None:
    """计算列：发电量=日均×24；峰值负荷率=max/容量；峰谷差率=(max-min)/容量。"""
    cfg = ReportTool.load_config(str(CONFIGS / "daily_summary.yaml"))
    capacities = {str(r["point"]): float(r["capacity"]) for r in cfg["rows"]}
    rows, query_count, _ = tool.run(str(CONFIGS / "daily_summary.yaml"), START, END)
    assert query_count == 1
    assert rows[0] == [
        "测点", "日均负荷(MW)", "日峰值(MW)", "日谷值(MW)",
        "日累计发电量(MWh)", "峰值负荷率(%)", "峰谷差率(%)",
    ]
    for row, row_cfg in zip(rows[1:], cfg["rows"]):
        avg_mw, mx, mn = float(row[1].removesuffix("MW")), float(row[2].removesuffix("MW")), float(row[3].removesuffix("MW"))
        energy, peak_f, spread = float(row[4].removesuffix("MWh")), float(row[5].removesuffix("%")), float(row[6].removesuffix("%"))
        cap = capacities[str(row_cfg["point"])]
        # 用显示值反推存在两位小数截断误差（≤0.5%），故采用相对误差断言
        assert energy == pytest.approx(avg_mw * 24, rel=0.01)
        assert peak_f == pytest.approx(mx / cap * 100, rel=0.01)
        assert spread == pytest.approx((mx - mn) / cap * 100, rel=0.01)


def test_config_driven_no_code_change(tool: ReportTool) -> None:
    """两张报表共用同一执行器 —— 验证"新增报表零代码改动"。"""
    _, q1, _ = tool.run(str(CONFIGS / "monthly_report.yaml"), START, END)
    _, q2, _ = tool.run(str(CONFIGS / "daily_summary.yaml"), START, END)
    assert q1 == 1 and q2 == 1


def test_safe_eval_rejects_injection() -> None:
    """白名单：拒绝非法表达式（注入攻击防护）。"""
    with pytest.raises(ValueError):
        safe_eval("__import__('os').system('rm -rf /')", {})


def test_safe_eval_accepts_math() -> None:
    assert safe_eval("avg / capacity * 100", {"avg": 512.34, "capacity": 1000.0}) == pytest.approx(51.234)
