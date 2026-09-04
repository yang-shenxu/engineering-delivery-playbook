#!/usr/bin/env bash
# install.sh — 一键把 AI 协作体系接入新项目（对应 sop/project-onboarding.md 的 Step 1-3）
#
# 用法：
#   bash install.sh /path/to/your/project
#
# 动作：
#   1. 创建 <项目>/.trae/{rules,agents} 与 docs/ 四个分类子目录
#   2. 复制 roles/*.md → .trae/agents/
#   3. 写入 .trae/rules/user_rules.md（已存在则不覆盖）
#   4. 已有 rules 文件但缺「工作风格与协作规范」节时，自动追加模板段
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"   # ai-collab/

if [[ $# -lt 1 ]]; then
  echo "用法: bash install.sh <目标项目路径>"
  exit 1
fi

TARGET="$1"
mkdir -p "$TARGET/.trae/rules" "$TARGET/.trae/agents"
mkdir -p "$TARGET/docs/analysis" "$TARGET/docs/database" "$TARGET/docs/design" "$TARGET/docs/devlog"
echo "✅ 1/4 目录结构就绪: $TARGET/.trae + docs/{analysis,database,design,devlog}"

# 2/4 复制 4 个通用角色
cp "$ROOT"/roles/*.md "$TARGET/.trae/agents/"
echo "✅ 2/4 已安装 subagent: $(ls "$TARGET/.trae/agents" | tr '\n' ' ')"

# 3/4 项目 rules
RULES="$TARGET/.trae/rules/user_rules.md"
if [[ -f "$RULES" ]]; then
  echo "ℹ️  3/4 $RULES 已存在，跳过骨架写入（不覆盖你的项目规则）"
else
  cp "$ROOT/templates/user-rules-template.md" "$RULES"
  echo "✅ 3/4 已写入规则骨架: $RULES （记得替换 <尖括号> 占位符）"
fi

# 4/4 工作风格节追加（幂等：已有则跳过）
if [[ -f "$RULES" ]] && ! grep -q "工作风格与协作规范" "$RULES"; then
  {
    echo ""
    cat "$ROOT/templates/rules-workflow-section.md"
  } >> "$RULES"
  echo "✅ 4/4 已追加「工作风格与协作规范」节"
else
  echo "ℹ️  4/4 工作风格节已存在，跳过"
fi

echo ""
echo "收尾（手动，约 3 分钟）："
echo "  1. 替换 $RULES 中的 <尖括号> 占位符（只读目录/文档根/环境信息务必写实）"
echo "  2. 在 AI IDE「创建智能体」UI 按 frontmatter 登记各角色（多数平台不自动扫描）"
echo "  3. 重启窗口后验证: 对话发「@code-reviewer 读一下项目 rules 并列出待审文件清单」"
echo "详见 sop/project-onboarding.md"
