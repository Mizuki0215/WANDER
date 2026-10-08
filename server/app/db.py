"""
Wander 後端 — 資料庫層

用 SQLite（標準庫，零安裝、零依賴）。
⚠️ 刻意寫成 Postgres 兼容嘅 SQL，將來搬去 Supabase 只需要換 connection。

Schema 設計原則：
  1. 所有 item 保留 raw_*（原始 link／caption／圖），方便日後 re-parse
  2. 分類存英文 enum（food/shopping/play/stay/transport），顯示時先翻譯
  3. 行程用 (day_index, sort_order) 表達，唔用時間戳 —— 因為拖拽排序係整數操作
"""
from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

DB_PATH = Path(os.environ.get("WANDER_DB", Path(__file__).resolve().parent.parent / "wander.db"))

SCHEMA = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- ═══ 用戶 ═══
CREATE TABLE IF NOT EXISTS users (
    id           TEXT PRIMARY KEY,
    email        TEXT UNIQUE NOT NULL,
    username     TEXT UNIQUE,              -- @帳號名（加朋友用，唔使 email）
    display_name TEXT,
    avatar       TEXT,
    password_hash TEXT,
    theme        TEXT DEFAULT 'galaxy',
    -- ⚠️ 自訂 wallpaper（用戶要求）—— `/uploads/xxx.jpg` 或 preset key
    wallpaper    TEXT,
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ═══ 登入驗證碼（email OTP）═══
CREATE TABLE IF NOT EXISTS login_codes (
    email      TEXT PRIMARY KEY,
    code       TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    tries      INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ═══ Session token ═══
CREATE TABLE IF NOT EXISTS sessions (
    token      TEXT PRIMARY KEY,
    user_id    TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ═══ 旅程 group ═══
CREATE TABLE IF NOT EXISTS trips (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    destination TEXT,
    start_date  TEXT,
    end_date    TEXT,
    days        INTEGER NOT NULL DEFAULT 3,
    invite_code TEXT UNIQUE NOT NULL,
    owner_id    TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    -- ⚠️ 旅程嘅「記帳貨幣」—— 總額用呢個顯示（預設 HKD）
    currency    TEXT DEFAULT 'HKD',
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ═══ 成員 ═══
CREATE TABLE IF NOT EXISTS members (
    trip_id   TEXT NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
    user_id   TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role      TEXT NOT NULL DEFAULT 'member',      -- owner | member
    joined_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (trip_id, user_id)
);

-- ═══ 城市停留（一個 trip 可以去多個城市）═══
--   例：福岡 4 日 + 首爾 3 日
--   ⚠️ 用 days 而唔係日期，因為用戶改 start_date 時要自動跟住推。
CREATE TABLE IF NOT EXISTS trip_stops (
    id       TEXT PRIMARY KEY,
    trip_id  TEXT NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
    city     TEXT NOT NULL,
    days     INTEGER NOT NULL DEFAULT 1,
    position INTEGER NOT NULL DEFAULT 0,
    lat      REAL,
    lng      REAL,
    country  TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_stops_trip ON trip_stops(trip_id, position);

-- ═══ 收藏項目 ═══
--    parsed 存成 JSON（同 engine 嘅 Item.to_dict() 完全一致）
--    咁樣 engine 加欄位唔使改 schema
CREATE TABLE IF NOT EXISTS items (
    id          TEXT PRIMARY KEY,
    trip_id     TEXT NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
    created_by  TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    parsed      TEXT NOT NULL,                     -- JSON
    name        TEXT,                              -- 抽出嚟方便查詢
    category    TEXT,
    country     TEXT,
    district    TEXT,
    lat         REAL,
    lng         REAL,
    confidence  INTEGER NOT NULL DEFAULT 0,
    needs_review INTEGER NOT NULL DEFAULT 1,
    votes       INTEGER NOT NULL DEFAULT 0,
    -- 行程編排
    day_index   INTEGER,                           -- NULL = 未排入行程
    sort_order  INTEGER NOT NULL DEFAULT 0,
    -- ⚠️⚠️ public／private（用戶要求）
    --    「Save 低嘅景點應該分 public 同 Private。
    --      Public = 全 group 見到，Private = 得自己睇到。」
    --    ⚠️ 預設 `private`（唔會唔小心泄漏用戶嘅收藏）
    visibility  TEXT DEFAULT 'private',
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_items_trip ON items(trip_id);
CREATE INDEX IF NOT EXISTS idx_items_day  ON items(trip_id, day_index, sort_order);

-- ═══ 投票（邊個投過）═══
CREATE TABLE IF NOT EXISTS votes (
    item_id TEXT NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    PRIMARY KEY (item_id, user_id)
);

-- ═══ 好友關係（雙向，accept 之後先寫入）═══
CREATE TABLE IF NOT EXISTS friends (
    user_id   TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    friend_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (user_id, friend_id)
);

-- ═══ 好友請求（要對方 accept 先成為朋友）═══
--   ⚠️ 用 (from,to) pair 做 key，令方向唯一。
--      但查詢「我有咩待處理請求」要兩個方向都睇（對方可能已經向我發過）。
CREATE TABLE IF NOT EXISTS friend_requests (
    id         TEXT PRIMARY KEY,
    from_id    TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    to_id      TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status     TEXT NOT NULL DEFAULT 'pending',   -- pending | accepted | rejected
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (from_id, to_id)
);
CREATE INDEX IF NOT EXISTS idx_fr_to ON friend_requests(to_id, status);

-- ═══ 行程邀請（朋友直接拉入 trip 都要 accept）═══
-- 購物清單
CREATE TABLE IF NOT EXISTS shopping_items (
    id         TEXT PRIMARY KEY,
    trip_id    TEXT NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
    title      TEXT NOT NULL DEFAULT '',
    qty        TEXT NOT NULL DEFAULT '',      -- 「2 個」「3 盒」
    note       TEXT NOT NULL DEFAULT '',
    category   TEXT NOT NULL DEFAULT 'other',
    assignee   TEXT NOT NULL DEFAULT '',      -- 邊個負責買
    price      REAL,                          -- 單價（可選）
    image      TEXT,                          -- 相片路徑（可選）
    -- ⚠️ 呢項嘅貨幣（JPY / KRW / EUR / HKD…）
    --    NULL = 用旅程嘅記帳貨幣
    currency   TEXT,
    done       INTEGER NOT NULL DEFAULT 0,
    position   INTEGER NOT NULL DEFAULT 0,
    created_by TEXT REFERENCES users(id) ON DELETE SET NULL,
    -- ⚠️ 私人／全組（用戶要求）—— 預設 `private`（自己睇）
    visibility TEXT DEFAULT 'private',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_shopping_trip ON shopping_items(trip_id);

-- 旅行開支（分帳用）
CREATE TABLE IF NOT EXISTS expenses (
    id           TEXT PRIMARY KEY,
    trip_id      TEXT NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
    title        TEXT NOT NULL DEFAULT '',
    amount       REAL NOT NULL DEFAULT 0,
    payer        TEXT NOT NULL DEFAULT '',
    participants TEXT NOT NULL DEFAULT '[]',   -- JSON array
    category     TEXT NOT NULL DEFAULT 'other',
    day_index    INTEGER,
    note         TEXT NOT NULL DEFAULT '',
    currency     TEXT NOT NULL DEFAULT 'JPY',
    created_by   TEXT REFERENCES users(id) ON DELETE SET NULL,
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_expenses_trip ON expenses(trip_id);

-- 交友邀請（用 email 邀請未註冊嘅人）
CREATE TABLE IF NOT EXISTS friend_invites (
    id         TEXT PRIMARY KEY,
    from_user  TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    email      TEXT NOT NULL,
    token      TEXT UNIQUE NOT NULL,
    status     TEXT NOT NULL DEFAULT 'pending',   -- pending | accepted | expired
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_finvite_email ON friend_invites(email);
CREATE INDEX IF NOT EXISTS idx_finvite_token ON friend_invites(token);

CREATE TABLE IF NOT EXISTS trip_invites (
    id         TEXT PRIMARY KEY,
    trip_id    TEXT NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
    from_id    TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    to_id      TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status     TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (trip_id, to_id)
);
CREATE INDEX IF NOT EXISTS idx_ti_to ON trip_invites(to_id, status);
"""


# 簡單 migration：加新欄位落現有表
#   ⚠️ CREATE TABLE IF NOT EXISTS 唔會為已存在嘅表加欄位 ——
#      所以要明確 ALTER TABLE。SQLite 冇 ADD COLUMN IF NOT EXISTS，要自己檢查。
MIGRATIONS: list[tuple[str, str, str]] = [
    # (表, 欄位, 型別)
    ("trip_stops", "lat", "REAL"),
    ("trip_stops", "lng", "REAL"),
    ("trip_stops", "country", "TEXT"),
    # ⚠️ IANA 時區（"Asia/Tokyo"）——
    #    旅行 app 一定要知**目的地**而家幾點，
    #    因為手機只會話你知「你身處邊度」嘅時間。
    ("trip_stops", "timezone", "TEXT"),
    # ⚠️ 後台管理員（開發版）。用 env allowlist 都得，
    #    但 DB 欄位方便「臨時開權限」而唔使重啟。
    ("users", "is_admin", "INTEGER NOT NULL DEFAULT 0"),
    ("users", "avatar", "TEXT"),
    ("users", "password_hash", "TEXT"),
    ("users", "username", "TEXT"),
    ("users", "onboarded", "INTEGER"),
    ("shopping_items", "image", "TEXT"),
    # ⚠️⚠️ 用戶要求：
    #   「有時你去旅行如果唔係都係用港幣㗎嘛，所以你要 mark 低返
    #    嗰個嘅價錢係有得揀嗰個 Yen or KRW or EUR、HKD 定係點樣？」
    #   → 每項購物可以係**唔同貨幣**（去日本買嘢用 JPY）
    ("shopping_items", "currency", "TEXT"),
    # ⚠️ 旅程嘅「記帳貨幣」—— 總額用呢個顯示（通常 HKD）
    ("trips", "currency", "TEXT"),
    # ⚠️⚠️ 自訂 wallpaper（用戶要求）
    #    「我哋整一個 function 就係改 wallpaper？…另外就係有個選項
    #     就係加咁樣嘅選項啦…可以自訂 wallpaper 咁然後你就可以
    #     加返自己嘅相上去。」
    #    ⚠️ 存 `/uploads/xxx.jpg`（自己上載）或者 preset key
    #      （`galaxy` / `none` …）—— 兩種都用同一欄位。
    ("users", "wallpaper", "TEXT"),
    # ⚠️⚠️ 購物清單**私人**（用戶要求）
    #    「shopping list 係自己嘅，就算人哋加落去加咗落去呢個
    #      planner 度呢，佢哋應該係睇唔到嘅。」
    #    ⚠️ 值：`private`（預設，只有自己）／`group`（全組睇到）
    ("shopping_items", "visibility", "TEXT"),
    # ⚠️⚠️ 收藏景點 public／private（用戶要求）
    #    「你 Save 低嘅景點呢應該有分可以分作 public 同埋 Private。
    #      Public 就係大家喺呢個 group 裏面嘅都見到，
    #      而 Private 就係得自己睇到呢一張。」
    #    ⚠️ 值：`private`（預設）／`public`
    ("items", "visibility", "TEXT"),
    ("items", "day_index", "INTEGER"),
]


# ⚠️⚠️ 一次性「資料」遷移（唔係 schema 遷移）。
#
#   點解要分開：`MIGRATIONS` 只做 ALTER TABLE ADD COLUMN，
#   但加完欄位之後，**舊資料**通常要補一個合理嘅預設值。
#
#   呢個 bug 就係咁嚟嘅：
#     加咗 users.onboarded 之後，所有舊用戶都係 NULL，
#     而 NULL 係 falsy → **所有現有帳號登入都會被逼睇新手教學**。
#     用戶原話：「我呢一個帳號登入咗嘅話呢，
#                其實正常就唔應該會有指示嘅出現囉」
#
#   用一個 `_applied_migrations` 表記錄邊啲跑過 ——
#   唔可以靠「欄位存在就當跑過」，因為欄位同 backfill 係兩件事。
BACKFILLS: list[tuple[str, str]] = [
    # 現有用戶當「已經睇過教學」—— 佢哋早就用緊個 app。
    # 只有**之後**新開嘅帳號（onboarded = 0）先會見到教學。
    ("2026-10-08-onboarded-grandfather",
     "UPDATE users SET onboarded = 1 WHERE onboarded IS NULL"),
]


def _run_backfills(conn) -> None:
    conn.execute(
        """CREATE TABLE IF NOT EXISTS _applied_migrations (
               name       TEXT PRIMARY KEY,
               applied_at TEXT NOT NULL DEFAULT (datetime('now'))
           )""")
    for name, sql in BACKFILLS:
        done = conn.execute(
            "SELECT 1 FROM _applied_migrations WHERE name = ?", (name,)).fetchone()
        if done:
            continue
        cur = conn.execute(sql)
        conn.execute("INSERT INTO _applied_migrations (name) VALUES (?)", (name,))
        n = cur.rowcount if cur.rowcount and cur.rowcount > 0 else 0
        print(f"  ↻ backfill: {name}  （影響 {n} 行）")


def _migrate(conn) -> None:
    for table, col, typ in MIGRATIONS:
        try:
            cols = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
            if not cols:
                continue                      # 表未建立（schema 會處理）
            if col not in cols:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {typ}")
                print(f"  ↻ migration: {table}.{col} {typ}")
        except Exception as e:
            print(f"  ⚠️ migration {table}.{col} 失敗: {e}")


def init_db() -> None:
    """建立 schema + 跑 migration（idempotent，可以每次啟動都跑）。"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with connect() as conn:
        conn.executescript(SCHEMA)
        # ⚠️ events 表用 executescript 另開（有 index，唔可以放入 MIGRATIONS）
        conn.executescript(EVENTS_SQL)
        conn.executescript(SIGNUP_INVITE_SQL)
        _migrate(conn)
        _run_backfills(conn)


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    """開一個 connection，自動 commit / rollback。"""
    conn = sqlite3.connect(DB_PATH, timeout=15, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── 小工具 ─────────────────────────────────────────────────

def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


def rows_to_list(rows) -> list[dict[str, Any]]:
    return [dict(r) for r in rows]


def item_row_to_api(row: sqlite3.Row, *, viewer_id: str | None = None) -> dict[str, Any]:
    """
    將 DB row 轉成 API 輸出：engine 嘅 parsed JSON + DB 嘅編排／投票資料。
    """
    out = json.loads(row["parsed"])
    out.update({
        "id": row["id"],
        "trip_id": row["trip_id"],
        "votes": row["votes"],
        "day_index": row["day_index"],
        "sort_order": row["sort_order"],
        "created_at": row["created_at"],
        # ⚠️⚠️ 可見度（用戶要求）—— 前端要顯示鎖／地球圖示
        #    ⚠️ 舊 row 可能係 NULL → 當 `private`（安全預設）
        "visibility": (row["visibility"] or "private") if "visibility" in row.keys() else "private",
        # ⚠️ 前端要知「呢項係唔係我加嘅」→ 決定可唔可以改可見度
        "mine": (row["created_by"] == viewer_id) if viewer_id else None,
        "created_by": row["created_by"] if "created_by" in row.keys() else None,
    })
    return out


# ══════════════════════════════════════════════════════════════════
# 使用事件（開發版後台嘅數據來源）
# ══════════════════════════════════════════════════════════════════
#
# ⚠️⚠️ 為咩要一張 events 表：
#   用戶要求：「整一個叫開發版，係放我自己睇啲人用呢個 App 嘅數據。」
#
#   ⚠️ 唔可以由 Items / Expenses 反推「使用情況」——
#      嗰啲只記錄**結果**（加咗 3 個景點），唔記錄**過程**：
#        · 邊個 app 最多人用？（Planner？Shopping？）
#        · 用戶登入完之後有冇真係做嘢？（激活率）
#        · 邊個功能開咗但冇用過？（= 唔知點用）
#
# ⚠️ 設計取捨：
#   · **只記事件類型 + 極簡 meta**，唔記內容 ——
#     我哋要「用咗幾多次」，唔要「睇咗咩」。私隱最低限度。
#   · 加索引 (user_id, created_at) —— 後台要按時間／用戶查。
#   · 冇外鍵約束到 CASCADE？⚠️ 有 —— 刪用戶就應該一齊清。

# ⚠️⚠️ 註冊邀請碼（唔使 SMTP 嘅註冊方式）
#
#   點解需要：用戶問「未設定 SMTP 你係諗住點搞？」
#     · 冇 SMTP = 寄唔到驗證碼 = 冇得驗證 email
#     · 但「朋友之間用」根本唔需要驗證 email ——
#       你**親手**畀個邀請碼佢就係最好嘅驗證
#     · 而且邀請碼冇成本、冇 rate limit、冇 spam 風險
#
#   ⚠️ 設計：一次性（用咗就標記 used_by），有期限，可加備註。
#      咁樣就算條碼流出咗，都只可以用一次。
SIGNUP_INVITE_SQL = """
CREATE TABLE IF NOT EXISTS signup_invites (
    code       TEXT PRIMARY KEY,
    created_by TEXT,
    note       TEXT,
    used_by    TEXT,
    used_at    TEXT,
    created_at TEXT NOT NULL,
    expires_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_si_used ON signup_invites(used_by);
"""

EVENTS_SQL = """
CREATE TABLE IF NOT EXISTS events (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    TEXT,
    kind       TEXT NOT NULL,       -- 事件類型（app_open / login / create_trip …）
    target     TEXT,                -- 對象（app id / trip id …）
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_time ON events(created_at);
CREATE INDEX IF NOT EXISTS idx_events_user ON events(user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_events_kind ON events(kind, created_at);
"""
