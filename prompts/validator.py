#!/usr/bin/env python3
"""防幻觉提示词静态校验器（Anti-Hallucination Prompt Validator）。

把「防幻觉四铁律」转成可自动执行的检查项：
  R1 写死数字     —— 模板正文（非代码块/标题/序号）出现裸数字 → 铁律二违规
  R2 写死实体     —— 出现已知业务实体名（指标名/模型名）      → 铁律二违规
  R3 缺动态占位符 —— 模板缺少 {{...}} / {tool_...} 占位符      → 铁律一/三违规
  R4 缺铁律约束   —— 模板未包含防幻觉核心关键词                → 铁律四违规

用法:
  python validator.py                # 扫描 templates/ 全部模板
  python validator.py -f 文件路径     # 扫描单个文件（支持多个 -f）
  python validator.py --ci           # CI 模式：存在违规即以非零码退出
  python validator.py --list-entities # 打印内置实体黑名单

退出码（--ci）: 0 全部通过 | 1 有警告 | 2 有违规
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Tuple

# ---------------------------------------------------------------- 实体黑名单

# 电厂业务指标名（示例，可按团队词表扩展；命中即判定"写死实体"）
INDICATOR_ENTITIES = {
    "负荷率", "煤耗", "主汽温度", "主汽压力", "给水流量", "凝汽器真空",
    "再热汽温", "再热汽压", "汽包水位", "排烟温度", "烟气含氧量",
    "供电煤耗", "厂用电率", "锅炉效率", "汽机热耗", "发电量", "厂用电量",
}

# 模型名（命中即判定"写死模型"）
MODEL_ENTITIES = {
    "gpt-4o", "gpt-4", "gpt-3.5", "claude", "deepseek", "qwen", "glm",
    "doubao", "kimi", "llama", "mistral", "gemini", "ernie", "bge",
}

# 铁律关键词：模板至少命中 MIN_IRON_HITS 个才算"包含防幻觉约束"
IRON_KEYWORDS = [
    "未查询", "不得断言", "编造", "来源", "返回值为准",
    "无数据", "禁止", "如实", "以.*为准",
]
MIN_IRON_HITS = 3

# 最小占位符数量：低于则判"写死"
MIN_PLACEHOLDERS = 3

# 忽略列表：这些词汇里的数字不算裸数字（单位词根等）
_IGNORED_WORDS = {"2d", "3d"}

# ---------------------------------------------------------------- 校验实现


@dataclass
class Finding:
    level: str  # "error" | "warning"
    code: str   # R1 / R2 / R3 / R4
    message: str
    line: int


@dataclass
class Report:
    path: Path
    findings: List[Finding] = field(default_factory=list)

    @property
    def errors(self) -> List[Finding]:
        return [f for f in self.findings if f.level == "error"]

    @property
    def warnings(self) -> List[Finding]:
        return [f for f in self.findings if f.level == "warning"]

    @property
    def ok(self) -> bool:
        return not self.findings


def _strip_code_blocks(lines: List[str]) -> List[Tuple[int, str]]:
    """去掉代码块（``` 包裹）与标题/列表序号后的正文行。"""
    out: List[Tuple[int, str]] = []
    in_code = False
    for i, raw in enumerate(lines, start=1):
        line = raw.rstrip("\n")
        if line.strip().startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        if line.lstrip().startswith("#"):  # 标题
            continue
        if line.lstrip().startswith(">"):  # blockquote：人读的元信息/备注，非提示词正文
            continue
        if re.match(r"^\s*\d+[\.、)]\s", line):  # 列表序号
            continue
        out.append((i, line))
    return out


def _check_hardcoded_numbers(path: Path, lines: List[str]) -> List[Finding]:
    findings: List[Finding] = []
    for line_no, line in _strip_code_blocks(lines):
        # 剔除占位符内容后，找裸数字（含百分号/小数）
        stripped = re.sub(r"\{\{[^}]*\}\}", "{{}}", line)
        for m in re.finditer(r"(?<![\w\.])-?\d+(?:\.\d+)?%?", stripped):
            token = m.group(0)
            if token.rstrip("%").rstrip(".") in _IGNORED_WORDS:
                continue
            findings.append(Finding(
                level="error", code="R1", line=line_no,
                message=f"正文出现裸数字「{token}」：阈值/参数写死，应以 {{占位符}} 或规则描述替代",
            ))
    return findings


def _check_hardcoded_entities(path: Path, lines: List[str]) -> List[Finding]:
    findings: List[Finding] = []
    for line_no, line in _strip_code_blocks(lines):
        low = line.lower()
        for ent in INDICATOR_ENTITIES:
            if ent in line:
                findings.append(Finding(
                    level="error", code="R2", line=line_no,
                    message=f"写死业务指标「{ent}」：指标清单应运行时注入，不得固化为提示词知识",
                ))
        for ent in MODEL_ENTITIES:
            if ent in low:
                findings.append(Finding(
                    level="error", code="R2", line=line_no,
                    message=f"写死模型名「{ent}」：模型由平台配置，提示词不应绑定具体型号",
                ))
    return findings


def _check_placeholders(path: Path, lines: List[str]) -> List[Finding]:
    findings: List[Finding] = []
    text = "\n".join(l for _, l in _strip_code_blocks(lines))
    n_placeholders = len(re.findall(r"\{\{[^}]*\}\}|tool_\w+|\{[a-z_]+\}", text))
    if n_placeholders < MIN_PLACEHOLDERS:
        findings.append(Finding(
            level="error", code="R3", line=0,
            message=(
                f"动态占位符仅 {n_placeholders} 个（要求 ≥{MIN_PLACEHOLDERS}）："
                "提示词缺少动态注入点，容易退化为写死"
            ),
        ))
    return findings


def _check_iron_rules(path: Path, lines: List[str]) -> List[Finding]:
    findings: List[Finding] = []
    # 铁律关键词检查针对全文档正文：只剥离代码块，保留序号行/标题行
    text_lines: List[str] = []
    in_code = False
    for raw in lines:
        line = raw.rstrip("\n")
        if line.strip().startswith("```"):
            in_code = not in_code
            continue
        if not in_code:
            text_lines.append(line)
    text = "\n".join(text_lines)
    hits = [kw for kw in IRON_KEYWORDS if re.search(kw, text)]
    if len(hits) < MIN_IRON_HITS:
        findings.append(Finding(
            level="error", code="R4", line=0,
            message=(
                f"防幻觉铁律关键词仅命中 {len(hits)}/{MIN_IRON_HITS}"
                f"（{', '.join(hits) or '无'}）：模板未包含「未查询不得断言/引用来源/禁止编造」等约束"
            ),
        ))
    return findings


def _check_basic(path: Path, lines: List[str]) -> List[Finding]:
    findings: List[Finding] = []
    total = len(lines)
    if total < 10:
        findings.append(Finding(
            level="warning", code="R0", line=0,
            message=f"文件仅 {total} 行，疑似骨架/占位文档",
        ))
    return findings


CHECKS = [
    _check_basic,
    _check_hardcoded_numbers,
    _check_hardcoded_entities,
    _check_placeholders,
    _check_iron_rules,
]


def scan(path: Path) -> Report:
    report = Report(path=path)
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        report.findings.append(Finding(level="error", code="IO", line=0, message=str(exc)))
        return report
    for check in CHECKS:
        report.findings.extend(check(path, lines))
    return report


# ---------------------------------------------------------------- CLI


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(description="防幻觉提示词静态校验器")
    ap.add_argument("-f", "--file", action="append", default=None, help="指定文件（可多次）")
    ap.add_argument("--ci", action="store_true", help="CI 模式：违规/警告即非零退出")
    ap.add_argument("--list-entities", action="store_true", help="打印内置实体黑名单")
    args = ap.parse_args(argv)

    if args.list_entities:
        for name, ents in (("业务指标", INDICATOR_ENTITIES), ("模型", MODEL_ENTITIES)):
            print(f"=== {name} ===")
            for e in sorted(ents):
                print(f"  {e}")
        return 0

    if args.file:
        targets = [Path(p) for p in args.file]
    else:
        targets = sorted((Path(__file__).parent / "templates").glob("*.md"))

    reports = [scan(t) for t in targets]
    n_err = sum(len(r.errors) for r in reports)
    n_warn = sum(len(r.warnings) for r in reports)

    print(f"扫描 {len(reports)} 个文件：违规 {n_err} 项，警告 {n_warn} 项\n")
    for r in reports:
        mark = "✅ 通过" if r.ok else ("⚠️ 警告" if r.errors else "❌ 违规")
        print(f"[{mark}] {r.path.name}")
        for f in r.findings:
            loc = f"L{f.line}" if f.line else "--"
            print(f"    {f.level.upper():7s} {f.code} {loc}: {f.message}")
        print()

    if n_err or (args.ci and n_warn):
        return 2 if n_err else 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
