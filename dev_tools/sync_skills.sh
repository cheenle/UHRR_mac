#!/usr/bin/env bash
# 把仓库内的 pi skills 同步到全局（~/.pi/agent/skills），保持单一真相源。
# 仓库里的 .pi/skills/<name>/SKILL.md 是权威版本；本脚本负责复制到全局目录。
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="${HOME}/.pi/agent/skills"
mkdir -p "$DEST"
changed=0
for src in "$REPO"/.pi/skills/*/; do
  name="$(basename "$src")"
  [ -f "$src/SKILL.md" ] || continue
  mkdir -p "$DEST/$name"
  if diff -q "$src/SKILL.md" "$DEST/$name/SKILL.md" >/dev/null 2>&1; then
    echo "= $name 已是最新（$(wc -c < "$DEST/$name/SKILL.md" | tr -d ' ') 字节）"
  else
    cp "$src/SKILL.md" "$DEST/$name/SKILL.md"
    echo "→ $name 已同步（$(wc -c < "$DEST/$name/SKILL.md" | tr -d ' ') 字节）"
    changed=1
  fi
done
# 其它 harness（Claude Code / Codex 约定目录）也给一份，便于跨工具使用
if [ -d "${HOME}/.agents/skills" ]; then
  for src in "$REPO"/.pi/skills/*/; do
    name="$(basename "$src")"
    [ -f "$src/SKILL.md" ] || continue
    mkdir -p "${HOME}/.agents/skills/$name"
    cp -f "$src/SKILL.md" "${HOME}/.agents/skills/$name/SKILL.md"
  done
  echo "→ 也同步到了 ~/.agents/skills/"
fi
echo "全局 skill 目录：$DEST"
ls -1 "$DEST" 2>/dev/null | sed 's/^/  /'
exit $(( changed == 0 ? 0 : 0 ))
