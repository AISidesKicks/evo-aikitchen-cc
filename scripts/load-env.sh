#!/usr/bin/env bash
# Load .env into the current shell, without printing its values.
#
#   source scripts/load-env.sh
#
# The file is parsed rather than executed, so a stray line cannot run a command.
# Existing variables win: an explicit export in your shell is not overwritten.

set -eu

if [ ! -f .env ]; then
    echo "no .env file; copy .env.example to .env first" >&2
    return 1 2>/dev/null || exit 1
fi

while IFS= read -r line || [ -n "$line" ]; do
    case "$line" in
        ''|'#'*) continue ;;
    esac
    key=${line%%=*}
    value=${line#*=}
    case "$key" in
        *[!A-Za-z0-9_]*|'') continue ;;
    esac
    # Strip one layer of surrounding quotes.
    value=${value%\"}
    value=${value#\"}
    value=${value%\'}
    value=${value#\'}
    if [ -z "$(eval "printf '%s' \"\${$key:-}\"")" ]; then
        export "$key=$value"
    fi
done < .env

echo "loaded .env (provider=${EVO_PROVIDER:-unset}, model=${EVO_MODEL:-unset})"
