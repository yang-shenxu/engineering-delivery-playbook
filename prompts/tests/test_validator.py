"""validator.py 单元测试。"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from validator import main, scan  # noqa: E402

PROMPTS = Path(__file__).resolve().parent.parent
TEMPLATES = PROMPTS / "templates"
EXAMPLES = PROMPTS / "examples"


def test_all_templates_pass() -> None:
    """3 份正式模板应全部通过（无违规项）。"""
    for tpl in sorted(TEMPLATES.glob("*.md")):
        report = scan(tpl)
        assert report.errors == [], f"{tpl.name} 有违规: {report.errors}"
        assert report.findings == [], f"{tpl.name} 有警告: {report.findings}"


def test_bad_prompt_is_blocked() -> None:
    """反面教材应被拦截：写死数字 + 写死实体 + 缺占位符 + 缺铁律。"""
    report = scan(EXAMPLES / "bad_prompt.md")
    codes = {f.code for f in report.errors}
    assert "R1" in codes, "应检出裸数字（80% / 500 / 300）"
    assert "R2" in codes, "应检出写死实体（负荷率/煤耗/gpt-4o）"
    assert "R3" in codes, "应检出缺占位符"
    assert "R4" in codes, "应检出缺铁律关键词"


def test_code_block_numbers_are_exempt() -> None:
    """代码块/配置示例中的数字不应判为写死（示例值不属于提示词正文知识）。"""
    tmp = PROMPTS / "tests" / "_tmp_codeblock.md"
    tmp.write_text(
        "```yaml\nthreshold: 80\npoints: [point_001]\n```\n\n正文没有数字。\n"
        "回答须以工具返回值为准，未查询不得断言，引用来源。\n"
        "{{tools}} {{task}} {{output_format}}\n",
        encoding="utf-8",
    )
    try:
        report = scan(tmp)
        assert "R1" not in {f.code for f in report.errors}
    finally:
        tmp.unlink(missing_ok=True)


def test_ci_exit_code_on_violation(capsys: pytest.CaptureFixture) -> None:
    """CI 模式：bad_prompt 违规应返回 2。"""
    rc = main(["-f", str(EXAMPLES / "bad_prompt.md"), "--ci"])
    assert rc == 2


def test_ci_exit_code_clean(capsys: pytest.CaptureFixture) -> None:
    """CI 模式：好模板应返回 0。"""
    rc = main(["-f", str(TEMPLATES / "agent_base.md"), "--ci"])
    assert rc == 0
