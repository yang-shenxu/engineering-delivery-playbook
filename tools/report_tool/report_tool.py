"""配置驱动的通用报表工具（案例 01 方法论的可运行实现）。

核心思想（与 docs/case-studies/01-report-query-optimization.md 呼应）：
    「把"怎么查"写进配置，把"查什么"留给提示词 / 调用方」

- 报表的表头、统计维度、计算列、行（测点）全部由 YAML 配置声明
- 新增一张报表 = 新增一个 YAML 文件，零代码改动（呼应"单工具覆盖 20+ 报表"）
- 计算列模式（calcColMap）：派生指标用 formula 声明（如 avg/capacity*100），
  运营侧新增指标无需改代码
- 统一输出：List[String[]] 二维数组 + 中文表头 + 两位小数
  （对齐真实系统的统一接口规范，前端零适配）

使用：
    python report_tool.py --config configs/monthly_report.yaml

典型输出：
    === 月度生产报表 ===
    测点        月均负荷(MW)  月最高(MW)  负荷率(%)
    point_001   512.34       987.12      51.23
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import yaml

# 复用 mock-api 的数据层与查询引擎（同进程调用，演示无需起服务）
_MOCK_API_DIR = Path(__file__).resolve().parents[2] / "mock-api"
sys.path.insert(0, str(_MOCK_API_DIR))

from data import build_dataset  # noqa: E402
from query_engine import QueryEngine  # noqa: E402

# 白名单校验：计算列 formula 只允许数字、四则运算、括号、变量名、小数点
_SAFE_EXPR_RE = re.compile(r"^[0-9+\-*/().\s_a-zA-Z]+$")

# 支持的聚合函数（calcColMap 的白名单）
AGG_FUNCS = {
    "avg": lambda vals: sum(vals) / len(vals) if vals else None,
    "max": lambda vals: max(vals) if vals else None,
    "min": lambda vals: min(vals) if vals else None,
    "sum": lambda vals: sum(vals) if vals else None,
    "count": lambda vals: float(len(vals)) if vals else None,
}


def safe_eval(formula: str, env: Dict[str, float]) -> float:
    """白名单安全的表达式求值（仅四则运算 + 已解析变量）。"""
    if not _SAFE_EXPR_RE.match(formula):
        raise ValueError(f"formula 含非法字符: {formula!r}")
    try:
        return float(eval(formula, {"__builtins__": {}}, env))  # noqa: S307 - 已白名单校验
    except (ZeroDivisionError, TypeError, NameError, ValueError) as exc:
        raise ValueError(f"formula 求值失败: {formula!r} -> {exc}") from exc


def fmt(value: Any, unit: str = "") -> str:
    """数值统一两位小数；空值输出空串（对齐真实系统报表格式）。"""
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.2f}{unit}"
    return f"{value}{unit}"


class ReportTool:
    """配置驱动的通用报表执行器。"""

    def __init__(self, dataset: Dict[str, Any], db_latency_ms: float = 1.5):
        self.engine = QueryEngine(dataset, db_latency_ms=db_latency_ms)

    # ---------- 配置加载 ----------

    @staticmethod
    def load_config(path: str) -> Dict[str, Any]:
        cfg = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        if "report" not in cfg:
            raise ValueError(f"配置缺少 report 节点: {path}")
        return cfg["report"]

    # ---------- 执行 ----------

    def execute(self, cfg: Dict[str, Any], start: datetime, end: datetime) -> List[List[str]]:
        """按配置生成报表：批量取数 → 聚合 → 计算列 → 二维数组输出。"""
        columns: List[Dict[str, Any]] = cfg["columns"]
        rows_cfg: List[Dict[str, Any]] = cfg["rows"]
        point_ids = [str(r["point"]) for r in rows_cfg]

        # 每次报表执行自包含：查询次数从 0 计
        self.engine.query_count = 0

        # 1. 批量查询一次取全部测点数据（对应案例 01：2700 次 → 1 次）
        bulk = self.engine.fetch_bulk(point_ids, start, end)

        # 2. 逐行聚合 + 计算列
        rows: List[List[str]] = []
        for row_cfg in rows_cfg:
            pid = str(row_cfg["point"])
            values = [v for _, v in bulk.get(pid, [])]
            env: Dict[str, float] = {}
            out_row: List[str] = []

            for col in columns:
                ctype = col.get("type", "agg")
                label = col["label"]
                unit = col.get("unit", "")

                if ctype == "point_name":
                    out_row.append(str(row_cfg.get("name", pid)))
                    continue

                if ctype == "agg":
                    agg = AGG_FUNCS.get(col["agg"])
                    if agg is None:
                        raise ValueError(f"未知聚合函数: {col['agg']}")
                    # 聚合结果写入 env，供后续计算列引用
                    env[col["key"]] = agg(values) or 0.0
                    out_row.append(fmt(agg(values), unit))
                    continue

                if ctype == "calc":
                    # 计算列模式：formula 引用列 key 或行属性
                    formula_env = dict(env)
                    for k, v in row_cfg.items():
                        if isinstance(v, (int, float)):
                            formula_env[k] = float(v)
                    out_row.append(fmt(safe_eval(col["formula"], formula_env), unit))
                    continue

                raise ValueError(f"未知列类型: {ctype}")

            rows.append(out_row)

        # 3. 表头行（中文表头，含单位）
        header = [f"{c['label']}({c.get('unit', '')})" if c.get("unit") else c["label"] for c in columns]
        return [header] + rows

    def run(self, config_path: str, start: datetime, end: datetime) -> tuple:
        """加载配置并执行，返回 (rows, query_count, elapsed_ms)。"""
        import time

        cfg = self.load_config(config_path)
        t0 = time.perf_counter()
        rows = self.execute(cfg, start, end)
        elapsed = (time.perf_counter() - t0) * 1000
        return rows, self.engine.query_count, round(elapsed, 1)


def print_report(rows: List[List[str]]) -> None:
    """终端打印二维数组报表（对齐对齐：中文表头 + 两位小数）。"""
    widths = [max(len(str(row[i])) for row in rows) for i in range(len(rows[0]))]
    for row in rows:
        line = "  ".join(str(cell).ljust(w) for cell, w in zip(row, widths))
        print(line.rstrip())


def main() -> None:
    parser = argparse.ArgumentParser(description="配置驱动的通用报表工具")
    parser.add_argument("--config", default=str(Path(__file__).parent / "configs" / "monthly_report.yaml"))
    parser.add_argument("--start", default="2026-07-01")
    parser.add_argument("--end", default="2026-07-31")
    args = parser.parse_args()

    start = datetime.strptime(args.start, "%Y-%m-%d")
    end = datetime.strptime(args.end, "%Y-%m-%d")

    tool = ReportTool(build_dataset())
    rows, query_count, elapsed = tool.run(args.config, start, end)

    title = ReportTool.load_config(args.config).get("title", "报表")
    print(f"=== {title} ===  (时间范围: {args.start} ~ {args.end})")
    print_report(rows)
    print(f"\n[统计] 数据库查询次数: {query_count} 次 | 耗时: {elapsed} ms")
    print(f"       报表行数: {len(rows) - 1} 行 | 新增报表 = 新增 YAML 配置，零代码改动")


if __name__ == "__main__":
    main()
