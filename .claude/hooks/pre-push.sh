#!/usr/bin/env bash
# PreToolUse (Bash): block `git push` when unit tests or frontend type-check fail.
root="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
cmd=$(jq -r '.tool_input.command // empty')
printf '%s' "$cmd" | grep -qE '(^|[;&|(] *)git( +-C +[^ ]+)? +push' || exit 0
if ! out=$(cd "$root/backend" && .venv/bin/pytest -q -x 2>&1); then
  printf 'Push zablokowany: pytest nie przechodzi.\n%s\n' "$(printf '%s' "$out" | tail -25)" >&2; exit 2
fi
if ! out=$(cd "$root/frontend" && npx --no-install tsc --noEmit -p tsconfig.app.json 2>&1); then
  printf 'Push zablokowany: tsc nie przechodzi.\n%s\n' "$(printf '%s' "$out" | head -30)" >&2; exit 2
fi
exit 0
