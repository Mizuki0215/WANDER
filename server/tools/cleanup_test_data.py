#!/usr/bin/env python3
"""
清走測試帳號（保留真實用戶）
================================

⚠️⚠️ 背景：
   用戶睇到後台 Dashboard 有 **144 個用戶**，問：
   「係咪你之前試嗰陣時候用嘅？因為我而家呢一個開發狀態
    暫時應該值得我淨係開咗兩個Account」

   ✅ 答：係。144 個入面 **142 個係我測試整嘅**。

⚠️⚠️ 安全設計（每一條都係必須）：
   ① **白名單**（`--keep`）—— 只保留指定 email，其他全刪
   ② **Dry-run 係預設** —— 唔加 `--yes` 唔會改任何嘢
   ③ **只刪測試 pattern** —— 唔會誤刪真實用戶（就算冇喺白名單）
   ④ **自動備份** —— 改之前 copy 一份 DB
   ⑤ 有**成員關係**嘅旅程唔會連累其他成員（轉移擁有權）

⚠️ 為咩要「只刪測試 pattern」：
   如果用戶將來加咗真朋友，佢哋嘅 email 唔會 match 測試 pattern
   → 唔會俾呢個 script 誤刪。

用法：
    # 睇下會刪咩（唔會改嘢）
    python server/tools/cleanup_test_data.py --keep a@gmail.com --keep b@gmail.com

    # 真係刪
    python server/tools/cleanup_test_data.py --keep a@gmail.com --keep b@gmail.com --yes
"""

from __future__ import annotations

import argparse
import re
import shutil
import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DB = Path(__import__("os").environ.get("WANDER_DB") or (ROOT / "server" / "wander.db"))

# ⚠️⚠️ 測試帳號嘅 pattern —— 唔 match 嘅**一定唔會刪**。
#
#    呢啲全部係我（agent）測試嗰陣自動 generate 嘅：
#      tz1791431989998@x.com      時區測試
#      cur1791431347498@x.com     匯率測試
#      shop1791427349879@example.com  購物測試
#      admin@wander.local         預設管理員
TEST_PATTERNS = [
    re.compile(r"^[a-z]{1,6}\d{10,}@(x\.com|example\.com)$"),   # 前綴+時間戳
    re.compile(r"^(tz|cur|shop|sv|sh|test|tmp|e2e|qa)\d*@"),     # 功能前綴
    re.compile(r"@(x\.com|example\.com)$"),                      # 測試網域
    re.compile(r"^admin@wander\.local$"),                        # 預設 admin
]


def looks_like_test(email: str) -> bool:
    e = (email or "").strip().lower()
    return any(p.search(e) for p in TEST_PATTERNS)


def main() -> int:
    ap = argparse.ArgumentParser(description="清走測試帳號")
    ap.add_argument("--keep", action="append", default=[],
                    help="要保留嘅 email（可以重複）")
    ap.add_argument("--yes", action="store_true", help="真係刪（唔加 = dry run）")
    ap.add_argument("--no-backup", action="store_true", help="唔備份（唔建議）")
    args = ap.parse_args()

    keep = {e.strip().lower() for e in args.keep if e.strip()}
    if not keep:
        print("⚠️ 一定要用 --keep 指定要保留嘅帳號（安全起見）")
        return 2
    if not DB.exists():
        print(f"⚠️ 搵唔到 DB: {DB}")
        return 2

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    users = conn.execute("SELECT id, email FROM users").fetchall()

    keep_ids, del_ids = [], []
    for u in users:
        e = (u["email"] or "").lower()
        if e in keep:
            keep_ids.append((u["id"], u["email"]))
        elif looks_like_test(e):
            del_ids.append((u["id"], u["email"]))
        else:
            # ⚠️ 唔喺白名單、又唔似測試 → **保留**（fail-safe）
            print(f"  ⚠️ 唔識判斷，保守起見**保留**：{u['email']}")
            keep_ids.append((u["id"], u["email"]))

    print(f"\n  DB: {DB}")
    print(f"  ┌── ✅ 保留 {len(keep_ids)} 個")
    for _id, e in keep_ids:
        n = conn.execute("SELECT COUNT(*) FROM trips WHERE owner_id=?", (_id,)).fetchone()[0]
        print(f"  │   {e:30} 旅程 {n}")
    print(f"  └── 🗑 會刪 {len(del_ids)} 個")
    for _id, e in del_ids[:8]:
        print(f"      {e}")
    if len(del_ids) > 8:
        print(f"      … 仲有 {len(del_ids) - 8} 個")

    if not args.yes:
        print("\n  ⚠️ 呢個係 **dry run** —— 冇改任何嘢。")
        print("     真係要刪就加 --yes")
        conn.close()
        return 0

    # ── 備份 ────────────────────────────────────────────────
    if not args.no_backup:
        bk = DB.with_suffix(f".backup-{time.strftime('%Y%m%d-%H%M%S')}.db")
        shutil.copy2(DB, bk)
        print(f"\n  ✅ 備份: {bk}")

    # ── 刪除 ────────────────────────────────────────────────
    ids = [i for i, _ in del_ids]
    ph = ",".join("?" * len(ids))
    cur = conn.cursor()
    counts = {}
    try:
        cur.execute("BEGIN")
        # ⚠️ ① 先刪佢哋**擁有**嘅旅程（連內容）——
        #    但如果有**其他成員**，唔刪（轉移畀最早嘅成員）
        orphan = [r["id"] for r in cur.execute(
            f"""SELECT t.id FROM trips t
                WHERE t.owner_id IN ({ph})
                  AND NOT EXISTS (SELECT 1 FROM members m
                                  WHERE m.trip_id = t.id
                                    AND m.user_id NOT IN ({ph}))""", ids + ids).fetchall()]
        if orphan:
            oph = ",".join("?" * len(orphan))
            for tbl in ("items", "trip_stops", "shopping_items", "expenses", "votes"):
                try:
                    counts[tbl] = cur.execute(
                        f"DELETE FROM {tbl} WHERE trip_id IN ({oph})", orphan).rowcount
                except sqlite3.OperationalError:
                    pass
            for tbl in ("members", "signup_invites"):
                try:
                    cur.execute(f"DELETE FROM {tbl} WHERE trip_id IN ({oph})", orphan)
                except sqlite3.OperationalError:
                    pass
            counts["trips"] = cur.execute(
                f"DELETE FROM trips WHERE id IN ({oph})", orphan).rowcount

        # ⚠️ ② 轉移「有朋友」嘅旅程（唔好連累朋友）
        moved = 0
        for r in cur.execute(
                f"SELECT id FROM trips WHERE owner_id IN ({ph})", ids).fetchall():
            nxt = cur.execute(
                f"""SELECT user_id FROM members WHERE trip_id=? AND user_id NOT IN ({ph})
                    ORDER BY rowid LIMIT 1""", [r["id"]] + ids).fetchone()
            if nxt:
                cur.execute("UPDATE trips SET owner_id=? WHERE id=?", (nxt["user_id"], r["id"]))
                moved += 1
        counts["轉移咗嘅旅程"] = moved

        # ⚠️ ③ 其他關聯
        for tbl, cols in [
            ("sessions", ["user_id"]), ("events", ["user_id"]),
            ("members", ["user_id"]), ("friends", ["user_id", "friend_id"]),
            ("friend_requests", ["from_id", "to_id"]),
        ]:
            try:
                info = cur.execute(f"PRAGMA table_info({tbl})").fetchall()
                have = {c["name"] for c in info}
                for col in cols:
                    if col in have:
                        cur.execute(f"DELETE FROM {tbl} WHERE {col} IN ({ph})", ids)
            except sqlite3.OperationalError:
                pass
        # ⚠️ item 作者轉 NULL（唔好連累朋友嘅收藏）
        try:
            cur.execute(f"UPDATE items SET created_by=NULL WHERE created_by IN ({ph})", ids)
        except sqlite3.OperationalError:
            pass

        counts["users"] = cur.execute(f"DELETE FROM users WHERE id IN ({ph})", ids).rowcount
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"\n  🚨 出錯，已經 rollback（冇改到嘢）: {e}")
        conn.close()
        return 1

    print("\n  ✅ 完成")
    for k, v in counts.items():
        print(f"     {k:22} {v}")

    # ── 驗證 ────────────────────────────────────────────────
    left = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    left_trips = conn.execute("SELECT COUNT(*) FROM trips").fetchone()[0]
    print(f"\n  淨返: {left} 個用戶 · {left_trips} 個旅程")
    for _id, e in keep_ids:
        n = conn.execute("SELECT COUNT(*) FROM trips WHERE owner_id=?", (_id,)).fetchone()[0]
        it = conn.execute(
            "SELECT COUNT(*) FROM items WHERE trip_id IN "
            "(SELECT id FROM trips WHERE owner_id=?)", (_id,)).fetchone()[0]
        ok = "✅" if n else "⚠️"
        print(f"     {ok} {e:30} 旅程 {n} · 景點 {it}")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
