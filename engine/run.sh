#!/usr/bin/env bash
# Wander 引擎快速啟動
# 用法：./run.sh selftest | ./run.sh demo | ./run.sh parse <url> | ...
set -e
PY="${WANDER_PYTHON:-/opt/anaconda3/bin/python3}"
[ -x "$PY" ] || PY="$(command -v python3)"
cd "$(dirname "$0")"
exec "$PY" -m wander "$@"
