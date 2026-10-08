#!/usr/bin/env bash
# Wander 引擎入口（喺 workspace 根目錄直接跑，唔使 cd）
#
#   ./wander.sh selftest
#   ./wander.sh demo
#   ./wander.sh parse "<url>"
#   ./wander.sh text "地址：〒823-0003 福岡縣宮若市本城65-1"
set -e
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="${WANDER_PYTHON:-/opt/anaconda3/bin/python3}"
[ -x "$PY" ] || PY="$(command -v python3)"
cd "$HERE/engine"
exec "$PY" -m wander "$@"
