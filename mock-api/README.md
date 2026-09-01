# mock-api — 火电实时测点模拟服务

> 一个可运行的 FastAPI 演示服务：模拟火电实时测点系统，用「批量查询 vs N+1 查询」两种实现，把案例 01（节能报表 2700 次 SQL → 4 次）的方法论变成**真实可跑的 Demo**。

## 为什么有这个项目

仓库里如果只有文档，说服力是弱的。`mock-api` 给整个仓库补上了「可运行代码」这一层：

1. **方法论可复现**：案例 01 讲的是报表 N+1 优化，这里用代码真实复刻了两种查询模式，跑出来的数据（1800 次 → 1 次）就是方法论的最好证明
2. **补 Python 生产级短板**：FastAPI + 类型注解 + pytest + 基准脚本，一套完整的最小可运行工程
3. **面试可演示**：三分钟能起服务、三分钟能出性能对比数据

## 快速开始

```bash
# 1. 建虚拟环境（Python 3.9+）
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate

# 2. 安装依赖
pip install -r requirements.txt

# 3. 启动服务（默认端口 8018）
uvicorn main:app --port 8018
```

## 接口一览

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/health` | 健康检查，返回测点数与数据规模 |
| GET | `/points` | 测点列表（分页/关键字过滤） |
| GET | `/points/{point_id}/values` | 单测点时序数据（时间范围 + limit） |
| GET | `/reports/monthly` | **月报表**：支持 `mode=batch` 与 `mode=n1` 两种实现 |

报表接口核心参数：

```
/reports/monthly?points=point_001,point_002&start=2026-07-01&end=2026-07-31&mode=batch
```

- `points`：逗号分隔的测点 ID
- `start` / `end`：时间范围（`YYYY-MM-DD`）
- `mode`：`batch`（批量 IN 查询，推荐）或 `n1`（循环逐点查询，复刻 N+1）

## 实测性能基准

在默认数据集（60 测点 × 5 分钟间隔时序数据）上运行 `benchmark.py`：

```bash
python benchmark.py 60 30   # 60 个测点、30 天
```

| 指标 | N+1 循环查询 | 批量查询 | 提升 |
|---|---|---|---|
| 数据库查询次数 | **1800 次** | **1 次** | 1800x |
| 总耗时（含模拟 DB 往返延迟） | ~4.5 s | ~0.35 s | **~13x** |

真实 HTTP 请求对比（5 测点 × 5 天）：

| 模式 | 查询次数 | 耗时 |
|---|---|---|
| `batch` | 1 次 | 3.3 ms |
| `n1` | 25 次 | 9.8 ms |

> 为什么提升是「次数 1800x / 耗时 13x」而非同样 1800x？因为批量查询仍需逐行组装结果，耗时大头是内存计算；而真实数据库场景里，**单次查询的网络/连接/解析开销**占比极大，N+1 模式在真实系统里的耗时差距会比内存模拟更悬殊——案例 01 的 2700 → 4 就是这么来的。

## 运行测试

```bash
python -m pytest tests/ -v
```

当前 6 个用例全部通过（接口可用性 + 两种模式返回一致性 + 边界参数）。

## 项目结构

```
mock-api/
├── data.py          # 数据层：生成模拟测点时序数据
├── query_engine.py  # 查询引擎：N+1 vs 批量两种实现 + 查询计数器
├── main.py          # FastAPI 入口：4 组 REST 接口
├── benchmark.py     # 性能基准脚本
├── tests/
│   └── test_api.py  # 接口测试（pytest + httpx）
└── requirements.txt
```

## 与案例的关联

| 本仓库模块 | 对应案例 | 关键数字 |
|---|---|---|
| `reports/monthly?mode=n1` | 案例 01：节能四张老报表 N+1 优化 | 2700 次 SQL → 4 次 |
| `reports/monthly?mode=batch` | 案例 01 的批量 IN + 内存索引方案 | 报表从 4.5s → 0.8s |
| 测点/时序/报表三类接口 | 火电实时测点系统（案例 01/02 的真实背景） | — |

---

*数据为模拟生成，脱敏处理，仅用于技术演示。*
