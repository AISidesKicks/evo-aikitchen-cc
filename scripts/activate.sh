#!/usr/bin/env bash
# Runs on every pixi environment activation.
#
# Why TMPDIR is not created here: pixi captures activation script output by
# writing a temp file, and it resolves that path from the environment before
# this script runs. If TMPDIR points at a directory that does not exist yet,
# pixi fails to activate at all. So TMPDIR points at /tmp, which always
# exists, and this script maintains EVO_TMP as the private per-project temp
# directory.

set -eu

if [ -z "${EVO_TMP:-}" ]; then
    exit 0
fi

# /run/user/$UID is tmpfs and is created by logind at login. Fall back to a
# directory under TMPDIR when it is missing, for example in a container
# without logind.
parent=$(dirname "$EVO_TMP")
if [ ! -d "$parent" ]; then
    EVO_TMP="${TMPDIR:-/tmp}/${PIXI_PROJECT_NAME:-evo1}"
fi

mkdir -p "$EVO_TMP"

if [ -n "${SCRATCH:-}" ]; then
    mkdir -p "$SCRATCH"
fi

export EVO_TMP
