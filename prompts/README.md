# prompts/ · 防幻觉提示词资产库

> 沉淀自生产环境 30+ 轮提示词迭代（案例 02「小U同学」），把"防幻觉"从**口头要求**变成**可检查的工程约束**。

## 目录结构

```
prompts/
├── anti-hallucination.md      # 方法论总纲：防幻觉四铁律（讲原理、讲反例）
├── validator.py               # 静态校验器：把铁律变成 CI 可自动检查的规则
├── templates/                 # 三份落地模板（全部通过校验器检查 ✅）
│   ├── agent_base.md          #   通用 Agent 系统提示词骨架
│   ├── report_query_agent.md  #   报表问答 Agent（呼应案例 01）
│   └── kb_ops_agent.md        #   知识库运维助手（呼应案例 02）
├── examples/
│   └── bad_prompt.md          # 反面教材：写死数据的典型反例（校验器拦截样例）
└── tests/
    └── test_validator.py      # 5 个用例：好模板放行 / 坏模板拦截 / 代码块豁免 / CI 退出码
```

## 防幻觉四铁律（速记）

| # | 铁律 | 一句话 |
|---|---|---|
| 1 | 未查询，不得断言 | 数值必须来自工具返回值，查不到就说「未查询到」 |
| 2 | 写规则，不写死数据 | 指标/阈值/模型全部动态注入，禁止固化 |
| 3 | 没有依据的推断，一个字不写 | 数据结论与经验建议分两段，禁止混淆 |
| 4 | 引用来源，让答案可回溯 | 知识标注文档，数值标注接口，无来源不写 |

详见 [`anti-hallucination.md`](anti-hallucination.md)（每条含落地写法 + 反例）。

## 校验器：把铁律变成机器检查

```bash
python validator.py                 # 扫描 templates/ 全部模板
python validator.py -f 指定文件      # 扫单个文件
python validator.py --ci            # CI 模式：违规即非零退出（接流水线用）
python validator.py --list-entities # 查看内置实体黑名单
```

四类自动检查：

| 规则 | 检查内容 | 对应铁律 |
|---|---|---|
| R1 裸数字 | 正文出现阈值/百分比/固定参数 | 铁律二 |
| R2 写死实体 | 命中内置业务指标/模型黑名单 | 铁律二 |
| R3 缺占位符 | 动态占位符 `{{...}}` 数量不足 | 铁律一/三 |
| R4 缺铁律 | 未包含「未查询不得断言/引用来源/禁止编造」等约束 | 铁律四 |

### 实测效果

```
$ python validator.py
扫描 3 个文件：违规 0 项，警告 0 项
[✅ 通过] agent_base.md
[✅ 通过] kb_ops_agent.md
[✅ 通过] report_query_agent.md

$ python validator.py -f examples/bad_prompt.md --ci
扫描 1 个文件：违规 17 项，警告 0 项
[⚠️ 警告] bad_prompt.md
    ERROR R1: 正文出现裸数字「80%」…（写死阈值）
    ERROR R2: 写死业务指标「负荷率」「煤耗」…（写死实体）
    ERROR R3: 动态占位符仅 0 个（缺注入点）
    ERROR R4: 防幻觉铁律关键词仅命中 0/3（缺约束）
退出码: 2   ← CI 直接拦下
```

## 如何接入团队工作流

1. **新 Agent 上线**：复制 `templates/agent_base.md`，替换 `{{...}}` 占位符，跑一次 `validator.py -f` 确认全绿；
2. **改提示词后**：跑校验器，防止"为了加功能顺手写死一个阈值"的回归；
3. **接 CI**：`python validator.py --ci` 挂到提交流水线，违规自动红；
4. **扩展词表**：团队指标/模型清单变化时，维护 `validator.py` 顶部的黑名单即可，规则零改动。

## 与案例的关联

- 案例 02（小U同学）：30+ 轮迭代的防幻觉经验 → 本文档四铁律 + kb_ops_agent 模板；
- 案例 01（报表优化）：报表口径以返回值为准 → report_query_agent 模板；
- mock-api / report_tool：提供了工具返回值长什么样，模板里的 `{{tools}}` 直接对接。
