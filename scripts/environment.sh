#!/usr/bin/env bash
# Source from the project root. Keep generated caches and temporary files on /data.
export TMPDIR="$PWD/tmp"
export MPLCONFIGDIR="$PWD/tmp/matplotlib"
export XDG_CACHE_HOME="$PWD/tmp/cache"
export PYTHONPYCACHEPREFIX="$PWD/tmp/pycache"
mkdir -p "$TMPDIR" "$MPLCONFIGDIR" "$XDG_CACHE_HOME" "$PYTHONPYCACHEPREFIX"
