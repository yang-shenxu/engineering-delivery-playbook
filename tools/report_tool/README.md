# report_tool — 配置驱动的通用报表工具

> 「把**怎么查**写进配置，把**查什么**留给调用方」—— 案例 01 方法论（2700 次 SQL → 4 次）的**可运行实现**。

## 为什么有这个模块

真实系统里，报表工具链的核心痛点不是"写 SQL"，而是**报表数量爆炸**：20+ 张报表，每张都要开发、联调、维护。`report_tool` 用配置驱动解决这个问题：

1. **一张报表 = 一个 YAML**：表头、统计维度、行（测点）、计算列全部声明式定义，**新增报表零代码改动**
2. **计算列模式（calcColMap）**：派生指标（负荷率、峰谷差率、日发电量…）用 `formula` 声明，运营侧加指标不动代码
3. **统一输出规范**：`List[String[]]` 二维数组 + 中文表头 + 两位小数，前端零适配（呼应案例 01 的接口规范）
4. **批量取数**：一次查询取全部测点数据（复用 `mock-api` 的批量引擎），不是 N+1

## 快速开始

```bash
# 依赖 mock-api 的数据层（同仓库，无需起服务）
python report_tool.py --config configs/monthly_report.yaml

# 换一张报表 = 换一个配置，零代码改动
python report_tool.py --config configs/daily_summary.yaml

# 指定时间范围
python report_tool.py --config configs/monthly_report.yaml --start 2026-07-01 --end 2026-07-31
```

## 配置驱动（核心）

以 `configs/monthly_report.yaml` 为例：

```yaml
report:
  id: monthly_report
  title: 月度生产报表
  columns:                      # 列定义：表头 + 统计维度
    - { key: point,       type: point_name, label: "测点" }
    - { key: avg,         type: agg, agg: avg,   label: "月均负荷", unit: "MW" }
    - { key: load_factor, type: calc, formula: "avg / capacity * 100", label: "负荷率", unit: "%" }
  rows:                         # 行定义：每行一个测点（可附静态属性供计算列引用）
    - { point: point_001, name: 1号机组, capacity: 1000 }
    - { point: point_002, name: 2号机组, capacity: 1000 }
```

| 列类型 | 说明 | 示例 |
|---|---|---|
| `point_name` | 测点名列 | `{ key: point, type: point_name, label: "测点" }` |
| `agg` | 聚合列（avg/max/min/sum/count） | `{ key: max, type: agg, agg: max, label: "月最高", unit: "MW" }` |
| `calc` | 计算列：引用聚合列 key 或行属性 | `{ key: load_factor, type: calc, formula: "avg / capacity * 100", label: "负荷率", unit: "%" }` |

## 实测输出

```
=== 月度生产报表 ===  (时间范围: 2026-07-01 ~ 2026-07-31)
测点    月均负荷(MW)  月最高(MW)   月最低(MW)   负荷率(%)
1号机组  75.60MW   81.36MW   69.88MW   7.56%
2号机组  139.61MW  145.46MW  133.75MW  13.96%
...
[统计] 数据库查询次数: 1 次 | 耗时: 9.2 ms
```

`[统计]` 行输出本次报表的**数据库查询次数**——单测点循环查是 N 次，这里永远是 1 次（批量取数 + 内存索引）。

## 安全设计

- 计算列 `formula` 走**白名单校验**（仅数字、四则运算、括号、变量名），拒绝 `__import__`、`os.system` 等注入（测试覆盖）
- 聚合函数白名单：avg / max / min / sum / count

## 运行测试

```bash
python -m pytest tests/ -v
```

当前 7 个用例全部通过：配置加载、二维数组结构、计算列正确性、**两张报表共用同一执行器（零代码改动验证）**、注入防护。

## 目录结构

```
report_tool/
├── report_tool.py            # 配置加载 + 执行器 + 计算列引擎
├── configs/
│   ├── monthly_report.yaml   # 示例 1：月度生产报表
│   └── daily_summary.yaml    # 示例 2：日运行摘要（计算列集中演示）
├── tests/
│   └── test_report_tool.py
└── README.md
```

## 与案例的关联

| 本模块能力 | 对应案例/方法论 | 关键数字 |
|---|---|---|
| 批量取数（1 次查询全测点） | 案例 01：2700 次 SQL → 4 次 | 报表查询次数恒为 1 |
| 配置驱动（报表=YAML） | 案例 01/02：单工具覆盖 20+ 报表 | 新增报表零代码改动 |
| 计算列模式（calcColMap） | 案例 02：运营侧新增指标无需改代码 | formula 声明即用 |
| 统一二维数组 + 中文表头 | 案例 01：前端零适配 | `List[String[]]` 规范 |

---

*数据为模拟生成，脱敏处理，仅用于技术演示。*
