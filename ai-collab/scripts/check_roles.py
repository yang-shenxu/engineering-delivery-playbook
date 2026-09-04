#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_roles.py — 角色资产静态校验器（AI 协作体系的 CI 关卡）

三类检查：
  R1  frontmatter 完整性：每个角色文件必须有 name 与 description
  R2  写作纪律：正文不写死盘符路径 / 内网 IP / 端口（项目差异应放项目 rules）
  R3  泄漏扫描：公司名 / 项目名 / 真实路径残留 —— 防止内部信息进入公开仓库

用法：
  python check_roles.py [目录]              # 默认扫描本脚本所在 ai-collab 根
  python check_roles.py --ci                # CI 模式：有问题退出码 2
  python check_roles.py --blocklist xx.txt  # 追加自定义泄漏黑名单（每行一个词）

退出码：0=全绿  1=参数错误  2=发现问题
"""
import sys
import re
from pathlib import Path

# ---------------------------------------------------------------------------
# 泄漏黑名单（R3）：内网 IP / 盘符路径为通用内置模式；公司/项目专属词遵循
# "写规则不写死数据"——放本脚本同级 blocklist.txt（已被 .gitignore 忽略，不入库），
# 每行一个词。可经 --blocklist 追加其他清单。
# ---------------------------------------------------------------------------
DEFAULT_BLOCKLIST = [
    "natapp", "famentemple",  # 通用内部基础设施特征示例
]

# 内网 IP 段（R3）
PRIVATE_IP = re.compile(r"\b(10\.\d{1,3}\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3}|172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})\b")
# 盘符绝对路径（R2：角色文件正文不应写死本机路径；R3 同样视为泄漏）
WIN_PATH = re.compile(r"\b[A-Za-z]:\\[\w\\\-\. ()\uFF08\uFF09]+")

SEVERITY = {"R1": "P0", "R2": "P1", "R3": "P0"}


def parse_frontmatter(text: str):
    """返回 (frontmatter dict|None, body str)。"""
    m = re.match(r"\A---\s*\n(.*?)\n---\s*\n?(.*)\Z", text, re.S)
    if not m:
        return None, text
    fm_raw, body = m.group(1), m.group(2)
    fm = {}
    for line in fm_raw.splitlines():
        if ":" in line and not line.startswith((" ", "\t")):
            k, _, v = line.partition(":")
            fm[k.strip()] = v.strip()
    return fm, body


def check_file(path: Path, blocklist):
    """返回 [(rule, level, line_no, message)]。"""
    problems = []
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return [("R3", "P0", 0, f"{path}: 非 UTF-8 编码文件（疑似二进制/其他来源），禁止入库")]

    fm, body = parse_frontmatter(text)
    is_role = path.suffix == ".md" and "roles" in path.parts
    # 黑名单文件与脚本自身豁免黑名单词扫描（黑名单天然包含黑名单词，避免自指误报）
    self_file = path.resolve() == Path(__file__).resolve()
    skip_words = path.name.startswith("blocklist") or self_file

    # R1 仅校验角色文件
    if is_role:
        if fm is None:
            problems.append(("R1", "P0", 1, "缺少 frontmatter（--- 块），平台无法识别 @ 调用"))
        else:
            if not fm.get("name"):
                problems.append(("R1", "P0", 1, "frontmatter 缺少 name 字段（@ 调用名）"))
            elif not re.fullmatch(r"[a-z][a-z0-9\-]*", fm["name"]):
                problems.append(("R1", "P1", 1, f"name={fm['name']!r} 不符合小写字母-数字-连字符规范"))
            if not fm.get("description"):
                problems.append(("R1", "P0", 1, "frontmatter 缺少 description 字段（触发场景）"))
            if not fm.get("tools"):
                problems.append(("R1", "P2", 1, "frontmatter 未声明 tools（权限最小化建议显式声明）"))

    # R2/R3 逐行扫（frontmatter 的 tools 字段可能含 Bash 等词，与泄漏无关，全扫即可）
    for i, line in enumerate(text.splitlines(), 1):
        if PRIVATE_IP.search(line):
            problems.append(("R3", "P0", i, f"内网 IP 残留: {PRIVATE_IP.search(line).group(0)}"))
        for w in WIN_PATH.finditer(line):
            problems.append(("R2", "P1", i, f"正文写死盘符路径（应放项目 rules）: {w.group(0)[:40]}"))
        low = line.lower()
        if skip_words:
            continue
        for word in blocklist:
            if word and word.lower() in low:
                problems.append(("R3", "P0", i, f"泄漏词命中 [{word}]: {line.strip()[:50]}"))
    return problems


def load_blocklist(script_dir: Path, extra_path=None):
    """内置黑名单 + 同级 blocklist.txt（若存在）+ --blocklist 指定文件。"""
    words = list(DEFAULT_BLOCKLIST)
    auto = script_dir / "blocklist.txt"
    if auto.exists():
        words += [l.strip() for l in auto.read_text(encoding="utf-8").splitlines()
                  if l.strip() and not l.strip().startswith("#")]
    if extra_path:
        words += [l.strip() for l in Path(extra_path).read_text(encoding="utf-8").splitlines()
                  if l.strip() and not l.strip().startswith("#")]
    return words


def main():
    args = [a for a in sys.argv[1:]]
    ci = "--ci" in args
    args = [a for a in args if a != "--ci"]
    script_dir = Path(__file__).resolve().parent
    extra_bl = None
    if "--blocklist" in args:
        i = args.index("--blocklist")
        try:
            extra_bl = args[i + 1]
            args = args[:i] + args[i + 2:]
        except IndexError:
            print("参数错误：--blocklist 需要文件路径")
            return 1
    blocklist = load_blocklist(script_dir, extra_bl)

    root = Path(args[0]) if args else Path(__file__).resolve().parent.parent
    targets = [p for p in sorted(root.rglob("*")) if p.is_file() and p.suffix in (".md", ".py", ".sh", ".yml", ".yaml", ".txt")]

    all_problems = []
    for p in targets:
        all_problems.extend((p,) + pr for pr in check_file(p, blocklist))

    # 结论先行
    p0 = sum(1 for item in all_problems if item[-2] == "P0")
    p1 = sum(1 for item in all_problems if item[-2] == "P1")
    print(f"扫描目录: {root}")
    print(f"检查文件: {len(targets)} 个 ｜ R1 frontmatter / R2 写作纪律 / R3 泄漏扫描（黑名单 {len(blocklist)} 词）")
    if not all_problems:
        print("\n结论：✅ 全部通过（P0=0, P1=0）——角色资产可安全公开发布")
        return 0
    print(f"\n结论：❌ 发现问题 P0={p0} P1={len([x for x in all_problems if x[-2]=='P1'])}，明细如下\n")
    print(f"{'级别':<4} {'规则':<4} {'位置':<46} 问题")
    for item in all_problems:
        f, rule, level, line_no, msg = item
        loc = f"{f.name}:{line_no}" if line_no else f.name
        print(f"{level:<4} {rule:<4} {loc:<46} {msg}")
    return 2 if (ci and (p0 or p1)) else 0


if __name__ == "__main__":
    sys.exit(main())
