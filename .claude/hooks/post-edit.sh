#!/usr/bin/env bash
# PostToolUse (Edit|Write): format + lint edited Python, type-check frontend after TS edits.
# Exit 2 = feed errors back to Claude so it fixes them.
root="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
f=$(jq -r '.tool_input.file_path // .tool_response.filePath // empty')
[ -z "$f" ] && exit 0
case "$f" in
  "$root"/backend/*.py)
    ruff="$root/backend/.venv/bin/ruff"
    [ -x "$ruff" ] || exit 0
    "$ruff" format -q "$f"
    if ! out=$("$ruff" check --fix -q "$f" 2>&1); then
      printf 'ruff check failed for %s:\n%s\n' "$f" "$out" >&2; exit 2
    fi ;;
  "$root"/frontend/src/*.ts|"$root"/frontend/src/*.tsx)
    [ -d "$root/frontend/node_modules" ] || exit 0
    if ! out=$(cd "$root/frontend" && npx --no-install tsc --noEmit -p tsconfig.app.json 2>&1); then
      printf 'tsc failed:\n%s\n' "$(printf '%s' "$out" | head -30)" >&2; exit 2
    fi ;;
esac
exit 0
