#!/usr/bin/env bash
# Run a command inside a bubblewrap sandbox.
#
# The sandbox is the permission boundary for unattended runs: the repository is
# mounted read-only, the only writable path is a throwaway work directory, and
# the network namespace is unshared. Tools run with no access to the host home
# directory, so credentials in ~/.config or .env cannot be read by the model.
#
# Usage: scripts/sandbox.sh REPO COMMAND [ARG...]
#
# Exits with the command's exit status. The work directory is removed on exit.

set -euo pipefail

if [ "$#" -lt 2 ]; then
    echo "usage: $0 REPO COMMAND [ARG...]" >&2
    exit 64
fi

repo=$(cd "$1" && pwd)
shift

tmp_root="${EVO_TMP:-${TMPDIR:-/tmp}}"
mkdir -p "$tmp_root"
work=$(mktemp -d "$tmp_root/evo-sandbox.XXXXXX")
trap 'rm -rf "$work"' EXIT

# Bind the runtime pieces a command needs to start, read-only. Anything not
# listed here is invisible inside the sandbox.
binds=()
for path in /usr /bin /sbin /lib /lib64 /etc/alternatives; do
    if [ -e "$path" ]; then
        binds+=(--ro-bind "$path" "$path")
    fi
done

bwrap \
    "${binds[@]}" \
    --ro-bind "$repo" /work \
    --bind "$work" /tmp \
    --dev /dev \
    --proc /proc \
    --tmpfs /run \
    --unshare-net \
    --unshare-pid \
    --unshare-uts \
    --unshare-ipc \
    --die-with-parent \
    --chdir /work \
    --clearenv \
    --setenv PATH /usr/local/bin:/usr/bin:/bin \
    --setenv HOME /tmp \
    --setenv TMPDIR /tmp \
    -- "$@"
