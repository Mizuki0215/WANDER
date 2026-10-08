#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════
#  📦 將本機 data 搬上 GCP VM
# ══════════════════════════════════════════════════════════════
#
#  ⚠️⚠️ 為咩要：
#     · `server/wander.db` 同 `server/uploads/` 係 **gitignored**
#       （正確 —— 唔應該上 GitHub）
#     · 所以 GCP VM 上係**全新空 DB**
#     · 用戶登入見到「冇旅程」= 空白
#
#  ⚠️⚠️ 做咩：
#     ① 停 app（唔好寫緊嗰陣覆蓋）
#     ② 備份 VM 上嘅現有 DB（如果有）
#     ③ 上傳 + 解壓
#     ④ 起返 app
#     ⑤ 驗證
#
#  ⚠️ 喺**邊度跑**：喺 VM 入面（`gcloud compute ssh`）
#
#  用法：
#     ① 本機（你部 Mac）：gcloud compute scp wander-data.tgz \
#          wander:/tmp/ --zone=us-central1-a
#     ② 入 VM：gcloud compute ssh wander --zone=us-central1-a
#     ③ 喺 VM 跑：bash /tmp/migrate-to-vm.sh
# ══════════════════════════════════════════════════════════════
set -euo pipefail

SRC="${WANDER_MIGRATE_SRC:-/tmp/wander-data.tgz}"
DEST="${WANDER_DATA_DIR:-/var/lib/wander}"
STAMP="$(date +%Y%m%d-%H%M%S)"

B=$'\033[1m'; G=$'\033[32m'; Y=$'\033[33m'; R=$'\033[31m'; N=$'\033[0m'
say()  { echo "${B}${G}▶${N} $*"; }
warn() { echo "${B}${Y}⚠${N} $*"; }
die()  { echo "${B}${R}✗${N} $*" >&2; exit 1; }

echo
echo "════════════════════════════════════════════════════════════"
echo "  📦 搬 data 上 VM"
echo "════════════════════════════════════════════════════════════"
echo

[ -f "$SRC" ] || die "搵唔到 $SRC —— 要先用 gcloud compute scp 上傳"
say "Bundle：$SRC（$(stat -c%s "$SRC" 2>/dev/null || stat -f%z "$SRC") bytes）"

# ── ① 檢查 bundle 內容 ────────────────────────────────────────
say "檢查 bundle…"
tar tzf "$SRC" | grep -q "wander.db" || die "bundle 入面冇 wander.db"
N_UP="$(tar tzf "$SRC" | grep -c 'uploads/' || true)"
say "  ✓ 有 wander.db + ${N_UP} 個 uploads 項"

# ── ② 停 app ──────────────────────────────────────────────────
say "停 app…"
systemctl stop wander 2>/dev/null || true

# ── ③ 備份 VM 上現有嘅 ────────────────────────────────────────
if [ -f "$DEST/wander.db" ]; then
  BK="$DEST/../wander-backup-$STAMP.tgz"
  warn "VM 上已經有 DB → 備份去 $BK"
  tar czf "$BK" -C "$DEST" . 2>/dev/null || warn "備份失敗（繼續）"
fi

# ── ④ 解壓 ────────────────────────────────────────────────────
say "解壓去 $DEST…"
mkdir -p "$DEST"
TMP="$(mktemp -d)"
tar xzf "$SRC" -C "$TMP"
[ -d "$TMP/wander" ] || die "bundle 結構唔啱（應該有 wander/ 目錄）"

cp -f "$TMP/wander/wander.db" "$DEST/wander.db"
if [ -d "$TMP/wander/uploads" ]; then
  mkdir -p "$DEST/uploads"
  cp -f "$TMP/wander/uploads/"* "$DEST/uploads/" 2>/dev/null || true
fi
rm -rf "$TMP"

# ⚠️ app 用 root 跑，但都要確保權限
chmod 644 "$DEST/wander.db"
chmod -R 755 "$DEST/uploads" 2>/dev/null || true
# ⚠️ SQLite journal 要可寫
chown -R root:root "$DEST" 2>/dev/null || true

# ── ⑤ 起返 app ────────────────────────────────────────────────
say "起返 app…"
systemctl start wander
sleep 4

# ── ⑥ 驗證 ────────────────────────────────────────────────────
say "驗證…"
if ! systemctl is-active --quiet wander; then
  warn "app 起唔到！睇 log："
  journalctl -u wander -n 20 --no-pager || true
  die "app 冇起"
fi

echo
echo "  ${B}VM 上嘅 data：${N}"
python3 - <<'PY' 2>/dev/null || warn "（讀唔到 DB 統計）"
import sqlite3
c = sqlite3.connect("/var/lib/wander/wander.db")
for t in ["users", "trips", "items", "shopping_items", "friends"]:
    try:
        print(f"    {t:18} {c.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]}")
    except Exception:
        pass
print()
for r in c.execute("SELECT email, username, display_name FROM users").fetchall():
    print(f"    @{r[1] or '—':12} {r[0]:28} {r[2] or ''}")
PY

N_FILES="$(ls "$DEST/uploads" 2>/dev/null | wc -l | tr -d ' ')"
echo "    相片：$N_FILES 張"

echo
echo "════════════════════════════════════════════════════════════"
echo "  ✅ 搞掂！"
echo "════════════════════════════════════════════════════════════"
echo
echo "  ⚠️ 用 Safari 開你嘅網址，登入睇下見到啲旅程未"
echo
echo "  ── 之後備份（定期做）──"
echo "    gcloud compute ssh wander --zone=us-central1-a \\"
echo "      --command='sudo tar czf - /var/lib/wander' > wander-backup-\$(date +%F).tgz"
echo
