#!/usr/bin/env bash
# Install the secret-check pre-commit hook.
#
# Run once per clone:  scripts/install-hooks.sh
#
# The hook rejects a commit if a value from .env appears in a tracked file or in
# history. It is a safety net for the common accident, which is pasting a key
# into a note, a test or a stack trace.

set -euo pipefail

root=$(git rev-parse --show-toplevel)
source_file="$root/scripts/pre-commit"
target="$root/.git/hooks/pre-commit"

if [ ! -f "$source_file" ]; then
    echo "missing $source_file" >&2
    exit 1
fi

if [ -f "$target" ] && ! grep -q "evo_bench secrets" "$target"; then
    backup="$target.before-evo-bench"
    cp "$target" "$backup"
    echo "kept the previous hook at $backup"
fi

cp "$source_file" "$target"
chmod +x "$target"
echo "installed pre-commit secret check"
