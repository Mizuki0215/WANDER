#!/usr/bin/env python3
"""
帳號重設工具
==============

⚠️⚠️ 用戶情況：
   「我登入唔返 icychan51@gmail.com，可能係個密碼問題啦，
    你可以幫我重設下，即係冇咗呢個紀錄、注銷咗佢，
    咁重新註冊一個。」

⚠️⚠️ 但「刪除帳號」係**破壞性**嘅，而且通常**唔需要**：
   實測 icychan51@gmail.com **冇密碼**（`password_hash` 空白）——
   係「驗證碼時代」開嘅舊帳號。
   → 佢唔係「密碼錯」，係**從來冇密碼**。
   → 只要**設一個密碼**就得，**唔使刪任何嘢**。

⚠️ 而嗰個帳號有 3 個旅程（其中一個有 2 個成員 = 有朋友嘅資料）。
   刪咗嘅話朋友都會受影響。

用法：
    python tools/manage_account.py icychan51@gmail.com --show
    python tools/manage_account.py icychan51@gmail.com --set-password 新密碼
    python tools/manage_account.py icychan51@gmail.com --clear-password
    python tools/manage_account.py icychan51@gmail.com --delete        # ⚠️ 破壞性
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

SERVER = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SERVER))
sys.path.insert(0, str(SERVER.parent / "engine"))


def find_user(email: str):
    from app import db
    with db.connect() as conn:
        return conn.execute(
            "SELECT * FROM users WHERE lower(email) = ?", (email.strip().lower(),)
        ).fetchone()


def owned_data(uid: str) -> dict:
    """數下呢個帳號擁有嘅嘢（刪之前一定要睇）。"""
    from app import db
    out = {"trips": [], "friends": 0, "requests": 0, "invites": 0, "sessions": 0}
    with db.connect() as conn:
        rows = conn.execute("SELECT * FROM trips").fetchall()
        for t in rows:
            mem = conn.execute(
                "SELECT COUNT(*) FROM members WHERE trip_id=?", (t["id"],)).fetchone()[0]
            mine = conn.execute(
                "SELECT COUNT(*) FROM members WHERE trip_id=? AND user_id=?",
                (t["id"], uid)).fetchone()[0]
            if not mine:
                continue
            out["trips"].append({
                "name": t["name"],
                "items": conn.execute("SELECT COUNT(*) FROM items WHERE trip_id=?",
                                      (t["id"],)).fetchone()[0],
                "stops": conn.execute("SELECT COUNT(*) FROM trip_stops WHERE trip_id=?",
                                      (t["id"],)).fetchone()[0],
                "members": mem,
                "expenses": conn.execute("SELECT COUNT(*) FROM expenses WHERE trip_id=?",
                                         (t["id"],)).fetchone()[0],
                "shopping": conn.execute(
                    "SELECT COUNT(*) FROM shopping_items WHERE trip_id=?",
                    (t["id"],)).fetchone()[0],
            })
        # ⚠️ 欄位名要跟真正嘅 schema（我第一版寫咗 a/b，係錯嘅）
        for k, sql in [
            ("friends", "SELECT COUNT(*) FROM friends WHERE user_id=? OR friend_id=?"),
            ("requests", "SELECT COUNT(*) FROM friend_requests "
                         "WHERE from_id=? OR to_id=?"),
            ("invites", "SELECT COUNT(*) FROM signup_invites WHERE created_by=?"),
            ("sessions", "SELECT COUNT(*) FROM sessions WHERE user_id=?"),
        ]:
            # ⚠️ 按 `?` 嘅數量傳參數（唔可以死傳兩個）
            out[k] = conn.execute(sql, tuple([uid] * sql.count("?"))).fetchone()[0]
    return out


def cmd_show(email: str) -> int:
    u = find_user(email)
    print("=" * 70)
    if not u:
        print(f"  ✗ 搵唔到「{email}」")
        return 1
    print(f"  帳號 {email}")
    print("=" * 70)
    for k in u.keys():
        v = u[k]
        if k == "password_hash":
            v = f"（有，{len(v)} 字）" if v else "⚠️（冇 —— 從未設密碼）"
        print(f"  {k:16} {v}")

    d = owned_data(u["id"])
    print()
    print("  擁有嘅資料：")
    if not d["trips"]:
        print("    （冇旅程）")
    for t in d["trips"]:
        mark = " ⚠️ 有其他人" if t["members"] > 1 else ""
        print(f"    · {t['name']:22} 景點 {t['items']:3} · 城市 {t['stops']} · "
              f"成員 {t['members']} · 開支 {t['expenses']} · 購物 {t['shopping']}{mark}")
    print(f"    朋友 {d['friends']} · 請求 {d['requests']} · "
          f"邀請碼 {d['invites']} · session {d['sessions']}")

    if not u["password_hash"]:
        print()
        print("  ⚠️⚠️ 呢個帳號**冇密碼** → 打咩密碼都登入唔到。")
        print("     唔使刪！只要設一個密碼：")
        print(f"       python tools/manage_account.py {email} --set-password 新密碼")
    return 0


def cmd_set_password(email: str, pw: str) -> int:
    from app import db, main
    u = find_user(email)
    if not u:
        print(f"  ✗ 搵唔到「{email}」")
        return 1
    if len(pw) < 6:
        print("  ✗ 密碼最少 6 個字")
        return 1
    with db.connect() as conn:
        conn.execute("UPDATE users SET password_hash=? WHERE id=?",
                     (main._hash_password(pw), u["id"]))
        # ⚠️ 順便清走舊 session —— 如果帳號被盜用，改密碼之後
        #    舊 token 應該即刻失效。
        conn.execute("DELETE FROM sessions WHERE user_id=?", (u["id"],))
    print(f"  ✅ {email} 嘅密碼已重設（舊 session 已清走）")
    print("  ⚠️ 登入之後即刻去設定改做你自己嘅密碼")
    return 0


def cmd_clear_password(email: str) -> int:
    from app import db
    u = find_user(email)
    if not u:
        print(f"  ✗ 搵唔到「{email}」")
        return 1
    with db.connect() as conn:
        conn.execute("UPDATE users SET password_hash=NULL WHERE id=?", (u["id"],))
        conn.execute("DELETE FROM sessions WHERE user_id=?", (u["id"],))
    print(f"  ✅ {email} 嘅密碼已清除（可以用「認領帳號」重新設定）")
    return 0


def cmd_delete(email: str) -> int:
    """
    ⚠️⚠️ 破壞性：連旅程、景點、開支全部一齊冇。
       如果旅程有**其他成員**，佢哋都會失去資料。
    """
    from app import db
    u = find_user(email)
    if not u:
        print(f"  ✗ 搵唔到「{email}」")
        return 1

    d = owned_data(u["id"])
    print("=" * 70)
    print(f"  ⚠️⚠️ 將會**永久刪除**「{email}」同以下所有資料：")
    print("=" * 70)
    for t in d["trips"]:
        warn = f"  ⚠️ 有 {t['members']} 個成員（朋友都會受影響）" if t["members"] > 1 else ""
        print(f"    · {t['name']}：景點 {t['items']} · 城市 {t['stops']} · "
              f"開支 {t['expenses']} · 購物 {t['shopping']}{warn}")
    print(f"    朋友 {d['friends']} · session {d['sessions']}")

    # ⚠️⚠️ 一定要喺確認**之前**講清楚：
    #    邊啲旅程會轉移擁有權（朋友保得住）、邊啲會一齊刪。
    print()
    print("  擁有嘅旅程：")
    with db.connect() as conn:
        owned_rows = conn.execute(
            "SELECT id, name FROM trips WHERE owner_id=?", (u["id"],)).fetchall()
        if not owned_rows:
            print("    （冇）")
        for t in owned_rows:
            others = conn.execute(
                "SELECT COUNT(*) FROM members WHERE trip_id=? AND user_id<>?",
                (t["id"], u["id"])).fetchone()[0]
            if others:
                print(f"    ↻ 「{t['name']}」仲有 {others} 個成員 → "
                      f"擁有權會**轉移**（旅程同朋友嘅資料都保住）")
            else:
                print(f"    ⚠️ 「{t['name']}」冇其他成員 → 會**一齊刪**")

    print()
    print("  ⚠️ 冇得復原。")
    print()
    print("  ⚠️ 但多數情況**唔需要刪** —— 如果只係登入唔到，")
    print("     用 --set-password 就得（唔會冇任何資料）。")
    print()
    ans = input(f"  真係要刪？打「DELETE {email}」確認：").strip()
    if ans != f"DELETE {email}":
        print("  ✗ 取消（冇刪任何嘢）")
        return 1

    uid = u["id"]
    with db.connect() as conn:
        # ══════════════════════════════════════════════════════════
        # ⚠️⚠️⚠️ 最重要嘅一步：**轉移旅程擁有權**
        #
        #   我第一版漏咗，結果**刪走咗朋友嘅旅程**（實測發生過）：
        #
        #     schema:  trips.owner_id REFERENCES users(id) ON DELETE CASCADE
        #
        #   ⚠️ 即係刪一個 user 就會**連坐刪走佢擁有嘅所有旅程** ——
        #      就算旅程入面仲有**其他成員**（朋友）。
        #      `members` 又有 `ON DELETE CASCADE` →
        #      朋友嘅成員記錄都會一齊冇。
        #
        #   ⚠️ 呢個唔止係工具嘅問題，係**產品層面**嘅問題：
        #      任何「刪帳號」功能都會令朋友失去共同旅程。
        #
        #   ✅ 做法：擁有嘅旅程如果仲有**其他成員**，
        #      就將 owner 轉移畀最早加入嗰個（並改 role='owner'）。
        #      冇其他成員嘅旅程就真係可以刪。
        # ══════════════════════════════════════════════════════════
        owned = conn.execute(
            "SELECT id, name FROM trips WHERE owner_id=?", (uid,)).fetchall()
        # ⚠️⚠️ 記住邊啲旅程**保住**（轉移咗擁有權）。
        #    保住嘅旅程，**內容一個都唔可以刪** ——
        #    我第二版仍然刪走咗朋友旅程入面嘅景點／城市／購物，
        #    朋友會見到一個**空旅程**。
        keep: list[str] = []
        for t in owned:
            others = conn.execute(
                "SELECT user_id FROM members WHERE trip_id=? AND user_id<>? "
                "ORDER BY joined_at LIMIT 1", (t["id"], uid)).fetchone()
            if others:
                conn.execute("UPDATE trips SET owner_id=? WHERE id=?",
                             (others["user_id"], t["id"]))
                conn.execute(
                    "UPDATE members SET role='owner' WHERE trip_id=? AND user_id=?",
                    (t["id"], others["user_id"]))
                keep.append(t["id"])
                print(f"    ↻ 「{t['name']}」擁有權轉移畀 "
                      f"{others['user_id'][:14]}…（旅程同內容都保住）")
            else:
                print(f"    · 「{t['name']}」冇其他成員 → 會一齊刪")

        # ⚠️⚠️ 只有**冇其他成員**嘅旅程，佢嘅內容先可以刪。
        #    保住嘅旅程，內容要**原封不動**留畀朋友。
        #    → 用「我參與嘅旅程」減去「保住嘅旅程」。
        if keep:
            marks = ",".join("?" for _ in keep)
            member_scope = (
                f"SELECT trip_id FROM members WHERE user_id=? "
                f"AND trip_id NOT IN ({marks})", (uid, *keep))
        else:
            member_scope = ("SELECT trip_id FROM members WHERE user_id=?", (uid,))
        scope_sql, scope_args = member_scope
        INSCOPE = f"trip_id IN ({scope_sql})"

        # ══════════════════════════════════════════════════════════
        # ⚠️⚠️⚠️ 第三個坑：`items.created_by` 都係 ON DELETE CASCADE
        #
        #   schema:  items.created_by TEXT NOT NULL
        #              REFERENCES users(id) ON DELETE CASCADE
        #
        #   ⚠️ 即係刪一個 user 就會**連帶刪走佢喺其他旅程建立嘅景點** ——
        #      即使嗰個旅程係朋友嘅、而且會保住。
        #      實測：朋友嘅「trip」3 個景點變成 1 個。
        #
        #   ⚠️ 點解只有 `items` 中招：
        #      `expenses.created_by`     → ON DELETE SET NULL  ✅
        #      `shopping_items.created_by` → ON DELETE SET NULL  ✅
        #      `items.created_by`        → ON DELETE CASCADE   ❌
        #      （唔一致 —— 應該全部都用 SET NULL）
        #
        #   ✅ 工具層面嘅做法：刪之前將 `created_by` **轉移**畀
        #      同一個旅程嘅另一個成員。
        #   ⚠️ Schema 層面應該改做 SET NULL，但要重建表（SQLite 改唔到 FK）——
        #      喺 docs 記錄咗，留待有需要先做 migration。
        # ══════════════════════════════════════════════════════════
        orphan_items = conn.execute(
            "SELECT COUNT(*) FROM items WHERE created_by=?", (uid,)).fetchone()[0]
        if orphan_items:
            # 逐個景點搵新主人：同旅程最早加入嘅其他成員
            fixed = 0
            for it in conn.execute(
                    "SELECT id, trip_id FROM items WHERE created_by=?", (uid,)).fetchall():
                heir = conn.execute(
                    "SELECT user_id FROM members WHERE trip_id=? AND user_id<>? "
                    "ORDER BY joined_at LIMIT 1", (it["trip_id"], uid)).fetchone()
                if heir:
                    conn.execute("UPDATE items SET created_by=? WHERE id=?",
                                 (heir["user_id"], it["id"]))
                    fixed += 1
            print(f"    ↻ 景點作者轉移：{fixed}/{orphan_items} 個（保住朋友旅程嘅內容）")
            left = orphan_items - fixed
            if left:
                print(f"    ⚠️ 仲有 {left} 個景點冇人可以接手 → 會一齊刪")

        # ⚠️ 順序：先刪子表，再刪父表（有 FK 就唔會爆）
        # ⚠️ 順序好重要：先刪**子表**（items / expenses / members），
        #    最後先刪 trips 同 users。次序錯會被 FK 擋住。
        plan = [
            ("votes", "DELETE FROM votes WHERE user_id=?", None),
            ("shopping_items", f"DELETE FROM shopping_items WHERE {INSCOPE}", scope_args),
            ("expenses", f"DELETE FROM expenses WHERE {INSCOPE}", scope_args),
            ("items", f"DELETE FROM items WHERE {INSCOPE}", scope_args),
            ("trip_stops", f"DELETE FROM trip_stops WHERE {INSCOPE}", scope_args),
            ("trip_invites", f"DELETE FROM trip_invites WHERE from_id=? OR to_id=? "
                             f"OR {INSCOPE}", (uid, uid, *scope_args)),
            ("members", "DELETE FROM members WHERE user_id=?", None),
            ("friends", "DELETE FROM friends WHERE user_id=? OR friend_id=?", None),
            ("friend_requests", "DELETE FROM friend_requests "
                                "WHERE from_id=? OR to_id=?", None),
            ("friend_invites", "DELETE FROM friend_invites WHERE from_user=?", None),
            ("sessions", "DELETE FROM sessions WHERE user_id=?", None),
            ("events", "DELETE FROM events WHERE user_id=?", None),
            ("login_codes", "DELETE FROM login_codes WHERE lower(email)=?", (email,)),
            ("invites", "UPDATE signup_invites SET used_by=NULL, used_at=NULL "
                        "WHERE used_by=?", None),
        ]
        for label, sql, explicit in plan:
            args = explicit if explicit else tuple([uid] * sql.count("?"))
            try:
                n = conn.execute(sql, args).rowcount
                print(f"    · {label:16} 刪咗 {n} 行")
            except Exception as e:
                print(f"    ⚠️ {label}: {e}")
        # ⚠️ 清走孤兒旅程（冇任何成員）——
        #    包括「本來就冇人」同「啱啱冇咗唯一成員」嗰啲。
        #    ⚠️ 有轉移過擁有權嘅旅程會有返個 owner 成員 → 唔會被刪。
        n = conn.execute(
            """DELETE FROM trips
               WHERE id NOT IN (SELECT DISTINCT trip_id FROM members)""").rowcount
        if n:
            print(f"    · {'孤兒旅程':16} 刪咗 {n} 行")
        conn.execute("DELETE FROM users WHERE id=?", (uid,))
    print(f"  ✅ 已刪除「{email}」")
    print("  → 而家可以用同一個 email 重新註冊")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="帳號管理工具")
    ap.add_argument("email")
    ap.add_argument("--show", action="store_true", help="睇狀態同擁有嘅資料")
    ap.add_argument("--set-password", metavar="PW", help="重設密碼（唔會冇資料）")
    ap.add_argument("--clear-password", action="store_true", help="清除密碼")
    ap.add_argument("--delete", action="store_true", help="⚠️ 永久刪除帳號")
    a = ap.parse_args()

    if a.set_password:
        return cmd_set_password(a.email, a.set_password)
    if a.clear_password:
        return cmd_clear_password(a.email)
    if a.delete:
        return cmd_delete(a.email)
    return cmd_show(a.email)


if __name__ == "__main__":
    sys.exit(main())
