#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════
#  Wander — 一鍵啟動
#
#     ./run.sh              啟動（第一次會自動 build 前端）
#     ./run.sh rebuild      強制重新 build 前端
#     ./run.sh reset        清空資料庫再啟動
# ═══════════════════════════════════════════════════════════
set -e
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="${WANDER_PYTHON:-/opt/anaconda3/bin/python3}"
[ -x "$PY" ] || PY="$(command -v python3)"

cd "$HERE"

if [ "$1" = "reset" ]; then
  echo "⚠️  清空資料庫…"
  rm -f server/wander.db server/wander.db-wal server/wander.db-shm
  shift
fi

if [ "$1" = "rebuild" ] || [ ! -d "web/dist" ]; then
  echo "🔨 建立前端…"
  ( cd web && npm install --silent && npm run build )
fi

echo "🚀 啟動 Wander…"
cd server
exec "$PY" -m app
