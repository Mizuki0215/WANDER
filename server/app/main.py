"""
Wander 後端 — API
=================

包住已經寫好嘅解析引擎，提供 Web App 需要嘅 HTTP 介面。

啟動：
    cd server && python -m app          # 或 ./run.sh
    → http://127.0.0.1:8787

⚠️ 設計決定：
  · 單一 port（FastAPI 同時 serve API + 前端 build 出嘅 static）
    → 冇 CORS 問題，手機連同一個 WiFi 就開得
  · SQLite（零安裝）。Schema 寫成 Postgres 兼容，將來搬 Supabase 好易
  · 登入用 email 驗證碼。開發模式**印喺 console**（唔使裝 SMTP）
"""
from __future__ import annotations

import json
import os
import re
import secrets
import string
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

# 令 engine 可以被 import
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "engine"))

from fastapi import Depends, FastAPI, Header, HTTPException, Query, status  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import FileResponse, JSONResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from pydantic import BaseModel, EmailStr, Field  # noqa: E402

from . import db  # noqa: E402

# ⚠️⚠️ 一定要喺呢度載入 `.env`！
#
#    原本 `main.py` **唔喺 module 層** import mailer
#    （`from .mailer import ...` 寫喺函數入面，lazy import），
#    而 `load_env()` 係 mailer 喺 module 層呼叫嘅。
#
#    → 後果：main.py 頂層任何讀環境變數嘅嘢
#      （例如 `ADMIN_EMAILS`）都讀到**未載入**嘅值 → 永遠係空。
#
#    ⚠️ 症狀好誤導：`.env` 明明寫咗 `WANDER_ADMIN_EMAILS=...`，
#       但 `/api/admin/me` 一直回 `{admin: false}`，
#       睇落似「權限邏輯寫錯」而唔似「載入次序」。
from .mailer import load_env as _load_env  # noqa: E402

_load_env()

# ══════════════════════════════════════════════════════════════
# App
# ══════════════════════════════════════════════════════════════

app = FastAPI(title="Wander API", version="0.1.0")

# ⚠️⚠️ GZip 壓縮 ——
#    `web/public/city-tz.json` 有 947 KB（城市→時區本地資料），
#    gzip 之後 ~270 KB。冇壓縮嘅話手機下載好慢。
#    ⚠️ 順便壓縮全部 JSON API 回應。
#    ⚠️ minimum_size=800 —— 太細嘅回應壓縮反而更慢。
from fastapi.middleware.gzip import GZipMiddleware  # noqa: E402
app.add_middleware(GZipMiddleware, minimum_size=800)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # 本機開發；上線要收窄
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 開發模式：驗證碼印喺 console（唔使 SMTP）
DEV_MODE = True

CODE_TTL_MINUTES = 10


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


def _new_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_urlsafe(10)}"


def _invite_code() -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(6))


# ══════════════════════════════════════════════════════════════
# Auth
# ══════════════════════════════════════════════════════════════

class LoginRequest(BaseModel):
    email: str


class VerifyRequest(BaseModel):
    email: str
    code: str = Field(min_length=4, max_length=8)


def current_user(authorization: Optional[str] = Header(None)) -> dict:
    """由 Authorization: Bearer <token> 攞當前用戶。"""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "未登入")
    token = authorization.split(" ", 1)[1].strip()
    with db.connect() as conn:
        row = conn.execute(
            """SELECT u.* FROM sessions s JOIN users u ON u.id = s.user_id
               WHERE s.token = ? AND s.expires_at > ?""",
            (token, _iso(_now())),
        ).fetchone()
    if not row:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session 已過期，請重新登入")
    return dict(row)


def _ig_status() -> dict:
    """IG 第三方抓取服務狀態（俾前端顯示）。"""
    try:
        from wander.igprovider import status as ig_status
        return ig_status()
    except Exception as e:
        return {"enabled": False, "error": str(e)}


# ══════════════════════════════════════════════════════════════
# 分區行程規劃
# ══════════════════════════════════════════════════════════════

@app.get("/api/trips/{trip_id}/zones")
def trip_zones(trip_id: str, days: int | None = None,
               user: dict = Depends(current_user)) -> dict:
    """
    按地理位置分區，並建議每日去邊一區。

    ⚠️ 純幾何計算（Haversine + 確定性貪心聚類），唔用 AI：
       距離係數學，唔需要「理解」。同一 input 永遠同一 output。
    """
    trip = _require_member(trip_id, user["id"])
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT * FROM items WHERE trip_id = ? ORDER BY sort_order, created_at",
            (trip_id,)).fetchall()
    items = []
    for r in rows:
        p = db.item_row_to_api(r)
        items.append(p)

    from wander.zones import suggest
    total = int(days or trip.get("days") or 3)
    result = suggest(items, max(1, min(60, total)))
    result["trip_days"] = total
    return result


# ══════════════════════════════════════════════════════════════
# 附近邊度買得到
# ══════════════════════════════════════════════════════════════

@app.get("/api/trips/{trip_id}/nearby")
def nearby_shops(trip_id: str, item: str, radius: int = 1500,
                 user: dict = Depends(current_user)) -> dict:
    """
    搵附近邊度買得到（購物清單用）。

    ⚠️ 用 Nominatim（免費免 key）＋ 當地語言關鍵字。
       實測：「ドラッグストア」喺福岡搵到 20 間，
             「drugstore」搵到 0 間 —— 所以一定要用當地字。
    """
    trip = _require_member(trip_id, user["id"])
    if not (item or "").strip():
        raise HTTPException(400, "請填要買咩")
    radius = max(300, min(5000, int(radius or 1500)))

    with db.connect() as conn:
        stops = conn.execute(
            "SELECT city, lat, lng, country FROM trip_stops WHERE trip_id=? ORDER BY position",
            (trip_id,)).fetchall()
        # ⚠️ items 表冇 address 欄 —— address 喺 parsed JSON 入面
        items = conn.execute(
            "SELECT name, lat, lng, category, parsed FROM items WHERE trip_id=?",
            (trip_id,)).fetchall()

    from wander.nearby import find_nearby, classify, default_center
    trip_d = {"stops": [dict(s) for s in stops]}
    center = default_center(trip_d, [dict(i) for i in items])
    if not center:
        raise HTTPException(400, "呢個旅程未有座標 —— 先設定城市，或者加有地址嘅景點")
    lat, lng = center
    country = next((s["country"] for s in stops if s["country"]), None)

    result = find_nearby(item.strip(), lat, lng, radius=radius, country=country)
    result["center"] = {"lat": round(lat, 5), "lng": round(lng, 5)}

    # ⚠️ 用戶自己已經收藏嘅同類店鋪 —— 呢啲一定最相關，排前面
    cat = classify(item)
    want = {
        "drug": ("shopping", "药", "藥", "妆", "妝", "drug", "pharmacy", "藥局"),
        "souvenir": ("手信", "土產", "souvenir", "gift", "菓子"),
        "food": ("超市", "食品", "food", "supermarket", "market"),
        "cloth": ("服", "衣", "cloth", "fashion", "uniqlo"),
        "electronics": ("電器", "电", "electronics", "camera", "bic"),
        "other": ("商場", "百貨", "mall", "store"),
    }.get(cat, ())
    mine = []
    import math as _m

    def _dist(a, b, c, d):
        R = 6371000.0
        p1, p2 = _m.radians(a), _m.radians(c)
        dp, dl = _m.radians(c - a), _m.radians(d - b)
        x = _m.sin(dp / 2) ** 2 + _m.cos(p1) * _m.cos(p2) * _m.sin(dl / 2) ** 2
        return 2 * R * _m.asin(_m.sqrt(min(1.0, x)))

    for it in items:
        if it["lat"] is None or it["lng"] is None:
            continue
        try:
            _p = json.loads(it["parsed"] or "{}")
        except Exception:
            _p = {}
        _addr = _p.get("address") or ""
        blob = f'{it["name"] or ""} {_addr} {it["category"] or ""}'.lower()
        if any(w.lower() in blob for w in want):
            mine.append({
                "name": it["name"], "kind": "saved",
                "label": "⭐ 你收藏嘅", "lat": it["lat"], "lng": it["lng"],
                "distance_m": round(_dist(lat, lng, it["lat"], it["lng"])),
                "address": _addr or None, "hours": None, "phone": None,
            })
    if mine:
        result["shops"] = mine + result["shops"]
        result["saved"] = len(mine)
    return result


# ══════════════════════════════════════════════════════════════
# 購物清單
# ══════════════════════════════════════════════════════════════

SHOP_CATS = ("food", "souvenir", "drug", "cloth", "electronics", "other")


@app.get("/api/trips/{trip_id}/shopping")
def list_shopping(trip_id: str, user: dict = Depends(current_user)) -> dict:
    _require_member(trip_id, user["id"])
    with db.connect() as conn:
        rows = conn.execute(
            """SELECT * FROM shopping_items WHERE trip_id = ?
               ORDER BY done, position, created_at""", (trip_id,)).fetchall()
    items = [db.row_to_dict(r) for r in rows]

    # ⚠️⚠️ 用戶要求：「根據匯率去轉返嗰個你想要嘅錢」
    #
    #   每項可能有**自己嘅貨幣**（去日本買嘢 = JPY），
    #   但總額一定要用**一個貨幣**先有意義（通常 HKD）。
    #
    #   ⚠️ 用旅程嘅記帳貨幣做基準 —— 冇設就 HKD。
    with db.connect() as conn2:
        row = conn2.execute("SELECT currency FROM trips WHERE id=?",
                            (trip_id,)).fetchone()
    trip_cur = ((db.row_to_dict(row) or {}).get("currency") or "HKD").upper()

    from wander import currency as _cur
    rates = _cur.get_rates(trip_cur)
    rmap = rates.get("rates") or {}

    def to_trip(price, code):
        """⚠️ 換唔到就回 None（**唔可以**當同一個數 —— 會靜靜咁畀錯錢）。"""
        if price is None:
            return None
        c = (code or trip_cur).upper()
        if c == trip_cur:
            return round(float(price), 2)
        r = rmap.get(c)
        if not r:
            return None
        return round(float(price) * (1.0 / r), 2)

    total = 0.0
    unconverted = 0
    for i in items:
        v = to_trip(i.get("price"), i.get("currency"))
        i["price_trip"] = v                 # 換算後（睇總額用）
        i["currency"] = i.get("currency") or trip_cur
        if not i["done"] and i.get("price") is not None:
            if v is None:
                unconverted += 1
            else:
                total += v

    return {
        "items": items,
        "total": round(total, 2),
        "currency": trip_cur,
        "rates_at": rates.get("at"),
        "rates_stale": bool(rates.get("stale")),
        # ⚠️ 有幾項換唔到 → 前端要提示「總額可能唔齊」
        "unconverted": unconverted,
        "done_count": sum(1 for i in items if i["done"]),
        "pending_count": sum(1 for i in items if not i["done"]),
    }


@app.post("/api/trips/{trip_id}/shopping")
def add_shopping(trip_id: str, body: dict, user: dict = Depends(current_user)) -> dict:
    _require_member(trip_id, user["id"])
    title = (body.get("title") or "").strip()
    if not title:
        raise HTTPException(400, "請填寫要買咩")
    with db.connect() as conn:
        n = conn.execute("SELECT COUNT(*) c FROM shopping_items WHERE trip_id=?",
                         (trip_id,)).fetchone()["c"]
        sid = _new_id("shop")
        # ⚠️⚠️ `image` 之前**冇寫入** —— 前端明明有送，
        #    但後端 INSERT 漏咗個欄 → **相片無聲無息咁消失**。
        #    （schema 有 `image` 欄，前端 `add()` 有送，就係呢度漏。）
        # ⚠️⚠️ 用戶要求：「有時你去旅行如果唔係都係用港幣㗎嘛，
        #    所以你要 mark 低返嗰個嘅價錢係有得揀嗰個 Yen or KRW…」
        #    → 每項都可以有**自己嘅貨幣**。
        #    ⚠️ 空 = 用旅程嘅記帳貨幣（唔係硬編碼 HKD）。
        cur_code = (body.get("currency") or "").strip().upper() or None
        conn.execute(
            """INSERT INTO shopping_items
               (id, trip_id, title, qty, note, category, assignee, price, position,
                created_by, image, currency)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (sid, trip_id, title, (body.get("qty") or "").strip(),
             (body.get("note") or "").strip(),
             (body.get("category") or "other").strip(),
             (body.get("assignee") or "").strip(),
             body.get("price"), n, user["id"],
             (body.get("image") or "").strip() or None, cur_code))
        row = conn.execute("SELECT * FROM shopping_items WHERE id=?", (sid,)).fetchone()
    return {"item": db.row_to_dict(row)}


@app.patch("/api/shopping/{item_id}")
def update_shopping(item_id: str, body: dict,
                    user: dict = Depends(current_user)) -> dict:
    with db.connect() as conn:
        row = conn.execute("SELECT trip_id FROM shopping_items WHERE id=?",
                           (item_id,)).fetchone()
    if not row:
        raise HTTPException(404, "搵唔到呢個項目")
    _require_member(row["trip_id"], user["id"])

    fields, vals = [], []
    for k in ("title", "qty", "note", "category", "assignee"):
        if k in body and body[k] is not None:
            fields.append(f"{k}=?"); vals.append(str(body[k]).strip())
    # ⚠️ `image` 都要可以 patch —— 前端而家係
    #    「先加 item（即刻有反應）→ 上傳完再補相」。
    #    ⚠️ `None` = 移除相片（唔係「唔改」）——
    #       所以用 `is not None or k == 'image'` 分開處理。
    if "image" in body and body["image"] is not None:
        fields.append("image=?"); vals.append(str(body["image"]).strip() or None)
    # ⚠️ 貨幣：空字串 = 清走（用返旅程嘅記帳貨幣）
    if "currency" in body:
        fields.append("currency=?")
        vals.append((str(body["currency"]).strip().upper() or None))
    if "price" in body:
        fields.append("price=?"); vals.append(body["price"])
    if "done" in body:
        fields.append("done=?"); vals.append(1 if body["done"] else 0)
    if "position" in body:
        fields.append("position=?"); vals.append(int(body["position"] or 0))
    if not fields:
        raise HTTPException(400, "冇嘢改")
    vals.append(item_id)
    with db.connect() as conn:
        conn.execute(f"UPDATE shopping_items SET {', '.join(fields)} WHERE id=?", tuple(vals))
        row2 = conn.execute("SELECT * FROM shopping_items WHERE id=?", (item_id,)).fetchone()
    return {"item": db.row_to_dict(row2)}


@app.delete("/api/shopping/{item_id}")
def delete_shopping(item_id: str, user: dict = Depends(current_user)) -> dict:
    with db.connect() as conn:
        row = conn.execute("SELECT trip_id FROM shopping_items WHERE id=?",
                           (item_id,)).fetchone()
    if not row:
        raise HTTPException(404, "搵唔到呢個項目")
    _require_member(row["trip_id"], user["id"])
    with db.connect() as conn:
        conn.execute("DELETE FROM shopping_items WHERE id=?", (item_id,))
    return {"ok": True}


@app.post("/api/trips/{trip_id}/shopping/clear-done")
def clear_done_shopping(trip_id: str, user: dict = Depends(current_user)) -> dict:
    """一次過清走買咗嘅嘢。"""
    _require_member(trip_id, user["id"])
    with db.connect() as conn:
        cur = conn.execute("DELETE FROM shopping_items WHERE trip_id=? AND done=1",
                           (trip_id,))
        n = cur.rowcount
    return {"ok": True, "deleted": n}


# ══════════════════════════════════════════════════════════════
# 分帳
# ══════════════════════════════════════════════════════════════

def _expense_dict(r) -> dict:
    d = dict(r) if not isinstance(r, dict) else dict(r)
    try:
        d["participants"] = json.loads(d.get("participants") or "[]")
    except Exception:
        d["participants"] = []
    return d


@app.get("/api/trips/{trip_id}/expenses")
def list_expenses(trip_id: str, user: dict = Depends(current_user)) -> dict:
    """列出開支 + 即時計分帳。"""
    _require_member(trip_id, user["id"])
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT * FROM expenses WHERE trip_id = ? ORDER BY created_at",
            (trip_id,)).fetchall()
        mrows = conn.execute(
            """SELECT u.display_name, u.email FROM members m
               JOIN users u ON u.id = m.user_id WHERE m.trip_id = ?""",
            (trip_id,)).fetchall()
    # ⚠️⚠️ 一定要用 _expense_dict（會 json.loads participants）！
    #    用 db.row_to_dict 嘅話 participants 係 raw JSON 字串，
    #    跟住 parse_expense 會將個字串當「逗號分隔人名」拆開 →
    #    出現 ["Alice" 同 "Bob"] 呢種「人名」❌
    exps = [_expense_dict(db.row_to_dict(r)) for r in rows]

    from wander.settle import parse_expense, summarize
    members = [(m["display_name"] or m["email"]) for m in mrows]
    currency = exps[0]["currency"] if exps else "JPY"
    symbol = {"JPY": "¥", "USD": "$", "HKD": "HK$", "TWD": "NT$",
              "KRW": "₩", "CNY": "¥", "EUR": "€", "GBP": "£"}.get(currency, "$")
    result = summarize([parse_expense(e) for e in exps], symbol=symbol)
    return {"expenses": exps, "settlement": result,
            "members": members, "currency": currency, "symbol": symbol}


@app.post("/api/trips/{trip_id}/expenses")
def add_expense(trip_id: str, body: dict, user: dict = Depends(current_user)) -> dict:
    """加一筆開支。"""
    _require_member(trip_id, user["id"])
    title = (body.get("title") or "").strip()
    if not title:
        raise HTTPException(400, "請填寫項目名稱")
    try:
        amount = float(body.get("amount") or 0)
    except (TypeError, ValueError):
        raise HTTPException(400, "金額唔係數字")
    if amount <= 0:
        raise HTTPException(400, "金額要大過 0")

    parts = body.get("participants") or []
    if isinstance(parts, str):
        parts = [p.strip() for p in parts.replace("，", ",").split(",") if p.strip()]
    if not parts:
        parts = [body.get("payer") or user["display_name"] or user["email"]]

    eid = _new_id("exp")
    with db.connect() as conn:
        conn.execute(
        """INSERT INTO expenses
           (id, trip_id, title, amount, payer, participants, category,
            day_index, note, currency, created_by)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (eid, trip_id, title, amount,
         (body.get("payer") or "").strip() or user["display_name"] or user["email"],
         json.dumps(parts, ensure_ascii=False),
         (body.get("category") or "other").strip(),
         body.get("day_index"), (body.get("note") or "").strip(),
         (body.get("currency") or "JPY").strip(), user["id"]))
    with db.connect() as conn:
        row = conn.execute("SELECT * FROM expenses WHERE id = ?", (eid,)).fetchone()
    return {"expense": _expense_dict(db.row_to_dict(row))}


@app.patch("/api/expenses/{expense_id}")
def update_expense(expense_id: str, body: dict,
                   user: dict = Depends(current_user)) -> dict:
    """改一筆開支（要係該 trip 嘅成員）。"""
    with db.connect() as conn:
        row = conn.execute("SELECT * FROM expenses WHERE id = ?", (expense_id,)).fetchone()
    if not row:
        raise HTTPException(404, "搵唔到呢筆開支")
    row = dict(row)
    _require_member(row["trip_id"], user["id"])

    fields, vals = [], []
    for k in ("title", "payer", "category", "note", "currency"):
        if k in body and body[k] is not None:
            fields.append(f"{k}=?")
            vals.append(str(body[k]).strip())
    if "amount" in body and body["amount"] is not None:
        try:
            amt = float(body["amount"])
        except (TypeError, ValueError):
            raise HTTPException(400, "金額唔係數字")
        if amt < 0:
            raise HTTPException(400, "金額唔可以係負數")
        fields.append("amount=?")
        vals.append(amt)
    if "participants" in body and body["participants"] is not None:
        parts = body["participants"]
        if isinstance(parts, str):
            parts = [p.strip() for p in parts.replace("，", ",").split(",") if p.strip()]
        fields.append("participants=?")
        vals.append(json.dumps(list(parts), ensure_ascii=False))
    if "day_index" in body:
        fields.append("day_index=?")
        vals.append(body["day_index"])
    if not fields:
        raise HTTPException(400, "冇嘢改")

    vals.append(expense_id)
    with db.connect() as conn:
        conn.execute(f"UPDATE expenses SET {', '.join(fields)} WHERE id = ?", tuple(vals))
        row2 = conn.execute("SELECT * FROM expenses WHERE id = ?", (expense_id,)).fetchone()
    return {"expense": _expense_dict(db.row_to_dict(row2))}


@app.delete("/api/expenses/{expense_id}")
def delete_expense(expense_id: str, user: dict = Depends(current_user)) -> dict:
    with db.connect() as conn:
        row = conn.execute("SELECT trip_id FROM expenses WHERE id = ?", (expense_id,)).fetchone()
    if not row:
        raise HTTPException(404, "搵唔到呢筆開支")
    _require_member(row["trip_id"], user["id"])
    with db.connect() as conn:
        conn.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
    return {"ok": True}


# ══════════════════════════════════════════════════════════════
# 圖片上傳（購物清單用）
# ══════════════════════════════════════════════════════════════

# ⚠️⚠️ 上傳目錄 —— 一定要可以用 env 蓋過。
#
#   為咩：Docker / Fly.io 入面 `ROOT = /app` →
#   `UPLOAD_DIR = /app/server/uploads` ——
#   ⚠️ 但 volume 掛喺 `/data` → **唔喺 volume 入面** →
#   **每次 deploy 都會清空所有用戶上傳嘅相片**！
#
#   ✅ 預設行為唔變（本機跑照樣 `server/uploads`），
#      但 Dockerfile / fly.toml 會設 `WANDER_UPLOAD_DIR=/data/uploads`。
import os as _os
UPLOAD_DIR = Path(_os.environ.get("WANDER_UPLOAD_DIR") or (ROOT / "server" / "uploads"))
MAX_UPLOAD = 6 * 1024 * 1024          # 6 MB（base64 後）


@app.post("/api/upload")
def upload_image(body: dict, user: dict = Depends(current_user)) -> dict:
    """
    上傳一張圖（購物清單用）。

    ⚠️ 設計決定：
       · 收 base64 JSON（唔用 multipart）—— 前端 canvas 縮圖之後直接送，
         少一層 parsing，而且手機上更可靠
       · 前端**一定要先縮圖**（最長邊 1200px）——
         手機影相郁啲就 4MB，直接上傳會好慢
       · 只接受 image/jpeg|png|webp，唔接受 SVG（SVG 可以帶 script = XSS）
       · 檔名用隨機 token，唔用用戶提供嘅名（防路徑穿越）
    """
    import base64, re as _re
    data = (body or {}).get("data") or ""
    m = _re.match(r"^data:image/(jpeg|jpg|png|webp);base64,(.+)$", data, _re.S)
    if not m:
        raise HTTPException(400, "只接受 JPEG / PNG / WebP 圖片")
    if len(data) > MAX_UPLOAD:
        raise HTTPException(413, f"圖片太大（上限 {MAX_UPLOAD // 1024 // 1024} MB）")
    try:
        raw = base64.b64decode(m.group(2))
    except Exception:
        raise HTTPException(400, "圖片格式錯誤")
    # ⚠️ 用 magic bytes 驗證真係圖片，而唔係靠大小 ——
    #    1×1 PNG 只有 70 bytes，用大小判斷會誤殺。
    #    同時防止有人上傳 .php / .html 改名做 .png。
    magic_ok = (
        raw[:8] == b"\x89PNG\r\n\x1a\n"
        or raw[:3] == b"\xff\xd8\xff"
        or (raw[:4] == b"RIFF" and raw[8:12] == b"WEBP")
    )
    if not magic_ok:
        raise HTTPException(400, "檔案內容唔係有效圖片")
    if len(raw) < 30:
        raise HTTPException(400, "圖片太細")

    ext = {"jpeg": "jpg", "jpg": "jpg", "png": "png", "webp": "webp"}[m.group(1)]
    name = f"{secrets.token_urlsafe(16)}.{ext}"
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    (UPLOAD_DIR / name).write_bytes(raw)
    return {"url": f"/uploads/{name}", "bytes": len(raw)}


@app.get("/api/qr")
def qr_code(url: str | None = None) -> dict:
    """
    產生 QR Code（俾手機掃）。

    ⚠️ 為咩要呢個：
       手機要用 `http://192.168.x.x:8787` —— 喺手機打呢串好煩。
       喺電腦出個 QR，手機一掃就開到。

    ⚠️ 呢個 endpoint **唔需要登入** —— 因為手機掃之前未登入。
       而且只會回傳「本機 URL 嘅 QR」，唔會洩漏任何資料。
    """
    from wander.qr import svg as qr_svg
    if not url:
        from .__main__ import lan_ips
        import os
        port = os.environ.get("WANDER_PORT", "8787")
        ips = lan_ips()
        url = f"http://{ips[0]}:{port}" if ips else "http://127.0.0.1:8787"
    # 只准我哋自己嘅 URL（防止有人用呢個 endpoint 生成任意 QR）
    if not (url.startswith("http://192.168.") or url.startswith("http://10.")
            or url.startswith("http://172.") or url.startswith("http://127.0.0.1")
            or url.startswith("https://")):
        raise HTTPException(400, "只可以生成本機／https URL 嘅 QR")
    svg = qr_svg(url, module=6, border=4, dark="#0b0518", light="#ffffff")
    if not svg:
        raise HTTPException(400, "URL 太長")
    return {"url": url, "svg": svg}


# ══════════════════════════════════════════════════════════════
# 個人 QR Code（加朋友用）
# ══════════════════════════════════════════════════════════════

def _base_url() -> str:
    """本機 URL（俾 QR code 用）。"""
    import os as _os
    from .__main__ import lan_ips
    if _os.environ.get("WANDER_BASE_URL"):
        return _os.environ["WANDER_BASE_URL"].rstrip("/")
    port = _os.environ.get("WANDER_PORT", "8787")
    ips = lan_ips()
    return f"http://{ips[0]}:{port}" if ips else f"http://127.0.0.1:{port}"


@app.get("/api/me/qr")
def my_qr(user: dict = Depends(current_user)) -> dict:
    """
    自己嘅個人 QR Code。

    ⚠️ 內容係一條 **URL**（唔係淨係個 username）：
       · 用手機原生相機掃 → 直接開到 Wander 並彈「加 @xxx 做朋友?」
       · 用 app 內掃描   → 我哋由 URL 抽出 username
       如果只編碼 "alice"，原生相機掃到只會顯示文字，做唔到任何嘢。
    """
    from wander.qr import svg as qr_svg
    with db.connect() as conn:
        me = conn.execute("SELECT * FROM users WHERE id = ?", (user["id"],)).fetchone()
    me = db.row_to_dict(me)
    uname = me.get("username")
    if not uname:
        raise HTTPException(400, "要先設定帳號名")
    url = f"{_base_url()}/?add={uname}"
    svg = qr_svg(url, module=7, border=4, dark="#0b0518", light="#ffffff")
    if not svg:
        raise HTTPException(400, "URL 太長，產生唔到 QR")
    return {"url": url, "svg": svg, "username": uname,
            "display_name": me.get("display_name")}


class QRDecodeIn(BaseModel):
    data: str          # data:image/...;base64,...


@app.post("/api/qr/decode")
def decode_qr(body: QRDecodeIn, user: dict = Depends(current_user)) -> dict:
    """
    解一張 QR 圖（加朋友用）。

    ⚠️⚠️ 為咩要喺**後端**解而唔係前端：
       瀏覽器冇內置 QR 解碼器。可以：
         · 用 BarcodeDetector API —— 但 Safari / Firefox 冇
         · 自己寫 JS decoder —— 幾百行，風險高
         · 用 jsQR 等 library —— 加依賴
       而後端**已經有 OpenCV**（之前寫 QR 產生器時用嚟驗證），
       cv2.QRCodeDetector() 一行就搞掂，而且經過實測。

    ⚠️ 手機影相 4MB，所以前端一定要先縮圖（最長邊 1400px）。
    """
    import base64
    import re as _re
    m = _re.match(r"^data:image/(jpeg|jpg|png|webp|heic);base64,(.+)$",
                  body.data or "", _re.S)
    if not m:
        raise HTTPException(400, "只接受 JPEG / PNG / WebP 圖片")
    try:
        raw = base64.b64decode(m.group(2))
    except Exception:
        raise HTTPException(400, "圖片格式錯誤")
    if len(raw) > MAX_UPLOAD:
        raise HTTPException(413, "圖片太大")

    try:
        import cv2
        import numpy as np
    except ImportError:
        raise HTTPException(503, "伺服器未安裝 OpenCV，用唔到 QR 掃描（可以手動打 @帳號名）")

    arr = np.frombuffer(raw, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise HTTPException(400, "讀唔到呢張圖")
    # ⚠️⚠️ cv2.QRCodeDetector().detectAndDecode() 回 **3 個值**：
    #      (解到嘅文字, 四個角座標, 校正後嘅 QR 圖)
    #    寫 `found, _pts = ...` 會 `ValueError: too many values to unpack`。
    #    （我喺測試檔寫 `txt, _, _ = ...` 係啱嘅，但 endpoint 寫漏咗 ——
    #     所以「測試通過」唔等於「產品通過」，一定要真打 API。）
    det = cv2.QRCodeDetector()
    found = det.detectAndDecode(img)[0]
    if not found and max(img.shape) < 1200:
        img2 = cv2.resize(img, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
        found = det.detectAndDecode(img2)[0]
    # 再試多一次：OpenCV 5 有 detectAndDecodeMulti，對「圖入面多過一個 QR」更好
    if not found:
        try:
            m_ok, m_texts, _, _ = det.detectAndDecodeMulti(img)
            if m_ok and m_texts:
                found = next((t for t in m_texts if t), "")
        except Exception:
            pass
    if not found:
        raise HTTPException(404, "喺呢張圖搵唔到 QR Code —— 試下影清楚啲、或者裁到只剩個 QR")

    text = (found or "").strip()
    # 由 URL 抽出 username（支援 ?add= / ?friend= / 純 @username）
    uname = None
    for pat in (r"[?&]add=([A-Za-z0-9_]{1,30})",
                r"[?&]friend=([A-Za-z0-9_\-]{1,60})",
                r"^@?([A-Za-z][A-Za-z0-9_]{2,19})$"):
        mm = _re.search(pat, text)
        if mm:
            uname = mm.group(1)
            break
    return {"text": text, "username": uname}


@app.get("/api/ig-provider")
def ig_provider_info(user: dict = Depends(current_user)) -> dict:
    """
    IG 抓取服務資訊（俾設定頁顯示選項）。

    ⚠️ 呢個 endpoint 係為咗老實話俾用戶知：
        IG 封鎖係硬事實，自動抓取要俾錢。
    """
    return _ig_status()


@app.get("/api/cities")
def search_cities(q: str = "", limit: int = 8, user: dict = Depends(current_user)) -> dict:
    """
    城市搜尋（俾行程規劃自動完成）。

    ⚠️ 用本地城市庫（GeoNames 34,153 個城市 / 134,655 個名稱索引），
       所以係 0ms 而且離線都用得。
    """
    from wander.localgeo import lookup, search, stats
    q = (q or "").strip()
    if not q:
        return {"results": [], "stats": stats()}
    results = search(q, limit=max(1, min(30, limit)))
    # 加埋精確命中（例如打「福岡」）
    exact = lookup(q)
    if exact and not any(r["query"] == exact.get("canonical") for r in results):
        results.insert(0, {
            "query": exact.get("canonical") or q,
            "matched": q,
            "lat": exact["lat"], "lng": exact["lng"],
            "country": exact.get("country"), "population": exact.get("population", 0),
        })
    return {"results": results[:limit], "stats": stats()}


@app.get("/api/geocode")
def geocode_one(q: str, user: dict = Depends(current_user)) -> dict:
    """將一個城市名轉座標（本地優先）。"""
    from wander.lookup import geocode_city
    c = geocode_city(q)
    if not c:
        raise HTTPException(404, f"搵唔到「{q}」嘅座標")
    return {"city": q, "lat": c.lat, "lng": c.lng,
            "country": c.country, "canonical": c.name, "source": c.source,
            "district": getattr(c, "district", None),
            "city_name": getattr(c, "city", None)}


# ══════════════════════════════════════════════════════════════
# 密碼登入（同 email 驗證碼並存）
# ══════════════════════════════════════════════════════════════

def _hash_password(password: str, salt: bytes | None = None) -> str:
    """
    密碼雜湊。

    ⚠️ 用 PBKDF2-HMAC-SHA256（標準庫有，唔使裝嘢）：
       · 60 萬次迭代 —— 2024 年 OWASP 建議嘅最低要求
       · 每個用戶獨立 salt（16 bytes 隨機）
       · 格式：pbkdf2_sha256$迭代次數$salt$hash（方便將來升級參數）

    ⚠️ 唔可以用 md5 / sha1 / 單次 sha256 —— 而家 GPU 一秒撞幾十億次。
    """
    import hashlib, os, base64
    if salt is None:
        salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 600_000)
    return "pbkdf2_sha256$600000${}${}".format(
        base64.b64encode(salt).decode(), base64.b64encode(dk).decode())


def _auto_accept_invites(conn, user_row) -> int:
    """
    登入時自動接受「用 email 邀請過佢」嘅交友邀請。

    ⚠️ 為咩要喺登入時做：
       對方撳咗 email 連結 → 去到我哋個 app → 但佢未註冊。
       註冊（= 第一次登入）之後，我哋要憑 email 對返個邀請，
       自動成為朋友。否則用戶要「撳連結 → 註冊 → 再加一次」＝ 3 步。
    """
    email = (user_row["email"] or "").lower()
    try:
        rows = conn.execute(
            """SELECT * FROM friend_invites
               WHERE email=? AND status='pending'""", (email,)).fetchall()
    except Exception:
        return 0
    n = 0
    for r in rows:
        from_id = r["from_user"]
        if from_id == user_row["id"]:
            continue
        conn.execute(
            """INSERT OR IGNORE INTO friends (user_id, friend_id) VALUES (?,?)""",
            (from_id, user_row["id"]))
        conn.execute(
            """INSERT OR IGNORE INTO friends (user_id, friend_id) VALUES (?,?)""",
            (user_row["id"], from_id))
        # 順便接受 any pending friend_request
        conn.execute(
            """UPDATE friend_requests SET status='accepted'
               WHERE from_id=? AND to_id=? AND status='pending'""",
            (from_id, user_row["id"]))
        conn.execute("UPDATE friend_invites SET status='accepted' WHERE id=?",
                     (r["id"],))
        n += 1
    return n


def _issue_session(user_row) -> dict:
    """建立 session token 並回傳登入回應（password / 驗證碼 兩條路共用）。"""
    token = secrets.token_urlsafe(32)
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO sessions (token, user_id, expires_at) VALUES (?, ?, ?)",
            (token, user_row["id"], _iso(_now() + timedelta(days=90))),
        )
        # 用邀請連結嚟註冊 → 自動成為朋友
        try:
            _auto_accept_invites(conn, user_row)
        except Exception:
            pass
    return {
        "token": token,
        "user": {
            "id": user_row["id"], "email": user_row["email"],
            "display_name": user_row["display_name"],
            "username": user_row["username"] if "username" in user_row.keys() else None,
            "avatar": user_row["avatar"], "theme": user_row["theme"],
            # ⚠️⚠️ 一定要回 onboarded ——
            #    前端用 `!user.onboarded` 決定要唔要出新手教學。
            #    漏咗嘅話，**每次登入都會出教學**（undefined 係 falsy）。
            "onboarded": bool(user_row["onboarded"]
                              if "onboarded" in user_row.keys() else False),
            "has_password": bool(user_row["password_hash"]),
        },
    }


def _check_password(password: str, stored: str | None) -> bool:
    """驗證密碼（用 hmac.compare_digest 防 timing attack）。"""
    import hashlib, hmac, base64
    if not stored:
        return False
    try:
        algo, iters, salt_b64, hash_b64 = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        salt = base64.b64decode(salt_b64)
        want = base64.b64decode(hash_b64)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(iters))
        # ⚠️ 一定要用 compare_digest，唔可以 ==（會洩漏時間資訊）
        return hmac.compare_digest(dk, want)
    except Exception:
        return False


class PasswordLogin(BaseModel):
    email: str
    password: str
    # ⚠️ 註冊時可能要邀請碼（見 signup_mode）
    invite_code: Optional[str] = None


class PasswordSet(BaseModel):
    password: str
    current: str | None = None


@app.post("/api/auth/register")
def register(body: PasswordLogin) -> dict:
    """
    註冊新帳號（email + 密碼）。

    ⚠️⚠️ 點解唔可以「email 已存在就當佢係本人」：
       咁樣任何人打你個 email 就可以**搶你個帳號**。
       所以分三種情況：

         ① email 全新                    → 直接建立，回 token
         ② 已存在**而且有密碼**          → 409「已經註冊，去登入」
         ③ 已存在**但冇密碼**（舊帳號）  → 409 + needs_claim
            （要用 email 收驗證碼先可以認領，見 /api/auth/claim）
    """
    email = (body.email or "").strip().lower()
    pw = body.password or ""
    if "@" not in email or "." not in email.split("@")[-1]:
        raise HTTPException(400, "Email 格式唔啱")
    if len(pw) < 6:
        raise HTTPException(400, "密碼最少 6 個字")
    if len(pw) > 200:
        raise HTTPException(400, "密碼太長")

    # ⚠️⚠️ 邀請碼檢查（`invite` 模式）——
    #    冇 SMTP 之下，邀請碼就係「驗證」：
    #    你親手畀條碼佢，比寄 email 更實在。
    mode = signup_mode()
    code = (getattr(body, "invite_code", None) or "").strip().upper()

    # ⚠️⚠️ 邀請碼喺**所有模式**都接受 —— 呢個係安全網。
    #
    #    為咩：如果管理員設定咗 SMTP 但設定錯（App Password 打錯、
    #    或者被 revoke），`signup_mode()` 會變 `email` ——
    #    但驗證碼**寄唔到** → **所有人都註冊唔到**，包括管理員自己。
    #
    #    ⚠️ 呢個係真實風險：`mode` 只睇「有冇設定」，
    #       唔會知「寄唔寄得到」。而唯一知道嘅方法就係真寄一封。
    #
    #    ✅ 所以：有有效邀請碼就一律放行 ——
    #       管理員永遠可以用「開發版後台 → 產生邀請碼」解鎖。
    invite_ok = False
    if code:
        with db.connect() as conn:
            inv = conn.execute(
                "SELECT * FROM signup_invites WHERE code = ?", (code,)).fetchone()
        if not inv:
            # ⚠️ invite 模式之下「打錯碼」同「冇打碼」要分開講
            if mode == "invite":
                raise HTTPException(403, "邀請碼唔啱")
        elif inv["used_by"]:
            if mode == "invite":
                raise HTTPException(403, "呢個邀請碼已經用咗")
        elif inv["expires_at"] and _iso(_now()) > inv["expires_at"]:
            if mode == "invite":
                raise HTTPException(403, "呢個邀請碼已經過期")
        else:
            invite_ok = True

    if mode == "invite" and not invite_ok:
        if not code:
            raise HTTPException(403, "呢個 app 要邀請碼先註冊得到")
        # 上面已經 raise 咗具體原因，行到呢度即係有古怪
        raise HTTPException(403, "邀請碼唔啱")

    with db.connect() as conn:
        user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if user:
            # ⚠️ 唔可以講太多 —— 但呢度必須講，否則用戶唔知點做。
            #    只講「有冇設密碼」，唔洩漏其他嘢。
            if user["password_hash"]:
                raise HTTPException(409, "呢個 email 已經註冊咗，請去登入")
            raise HTTPException(409, {
                "detail": "呢個 email 已經有帳號，但未設密碼。要先用 email 驗證碼確認身份。",
                "needs_claim": True,
                "email": email,
            })

        uid = _new_id("usr")
        conn.execute(
            """INSERT INTO users (id, email, display_name, password_hash, onboarded)
               VALUES (?, ?, ?, ?, 0)""",
            (uid, email, email.split("@")[0], _hash_password(pw)))
        # ⚠️ 標記邀請碼已用（一次性）—— 就算條碼流出都只可以用一次
        if invite_ok and code:
            conn.execute(
                "UPDATE signup_invites SET used_by=?, used_at=? WHERE code=?",
                (uid, _iso(_now()), code))
        row = conn.execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()

    # ⚠️⚠️ 用戶要求：「我係真係想我 email 收到有呢一封嘅 email。」
    #     → 註冊完即刻寄歡迎信。
    #     ⚠️ 一定要喺 DB commit **之後**（`with` 出咗）——
    #        寄信要幾百 ms，唔好霸住個 connection。
    #     ⚠️ 唔可以令註冊失敗：`send_welcome_email` 本身唔 raise。
    try:
        from .mailer import send_welcome_email
        _wr = send_welcome_email(email, email.split("@")[0])
        if _wr.get("error"):
            print(f"  ⚠️ 歡迎信寄唔到：{_wr['error']}", flush=True)
    except Exception as _e:
        print(f"  ⚠️ 歡迎信例外：{_e}", flush=True)

    return _issue_session(dict(row))


class ClaimIn(BaseModel):
    """認領舊帳號（未設密碼）：email + 驗證碼 + 新密碼。"""
    email: str
    code: str
    password: str


@app.post("/api/auth/claim")
def claim_account(body: ClaimIn) -> dict:
    """
    認領一個**未設密碼**嘅舊帳號。

    ⚠️⚠️ 一定要驗證碼 ——
       冇嘅話，任何人打你個 email 就可以搶你個帳號。
       驗證碼寄去**該 email**，所以只有真正擁有嗰個 email 嘅人做得到。
    """
    email = (body.email or "").strip().lower()
    pw = body.password or ""
    if len(pw) < 6:
        raise HTTPException(400, "密碼最少 6 個字")
    ok = _consume_code(email, body.code)
    if not ok:
        raise HTTPException(400, "驗證碼唔啱或者過期")
    with db.connect() as conn:
        user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if not user:
            raise HTTPException(404, "搵唔到呢個帳號")
        if user["password_hash"]:
            raise HTTPException(409, "呢個帳號已經有密碼，請直接登入")
        conn.execute("UPDATE users SET password_hash = ? WHERE id = ?",
                     (_hash_password(pw), user["id"]))
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user["id"],)).fetchone()
    return _issue_session(dict(row))


@app.post("/api/auth/password")
def password_login(body: PasswordLogin) -> dict:
    """用 email + 密碼登入。

    ⚠️ 呢個係**唯一**嘅登入方式（UI 已經冇驗證碼登入）。
       驗證碼只保留做「認領舊帳號」同「重設密碼」。
    """
    email = body.email.strip().lower()
    if not email or not body.password:
        raise HTTPException(400, "請填 email 同密碼")
    with db.connect() as conn:
        user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    # ⚠️ 唔可以講「冇呢個 email」—— 咁樣會洩漏邊啲 email 註冊過
    if not user or not _check_password(body.password, user["password_hash"]):
        # ⚠️⚠️ 「有呢個 email 但未設密碼」→ 要**講清楚**，
        #    否則用戶會卡死：
        #      用戶報嘅 bug：「我登入嘅時候佢同我講登入已過期，
        #                      20 秒之內去登入都話過期。」
        #      實情：佢個帳號係**驗證碼時代**開嘅，冇密碼。
        #      打咩密碼都 401 → 前端（修正前）當成 session 過期。
        #
        #    ✅ 而家前端收到「未設密碼」會自動轉去「認領帳號」流程
        #       （發驗證碼 → 設新密碼），唔會再卡死。
        #
        #    ⚠️ 代價：呢句會洩漏「邊個 email 註冊過但未設密碼」。
        #      對一個朋友之間用嘅旅行 app，**用戶體驗 > 呢個風險**。
        #      （而且「密碼唔啱」同「未設密碼」都已經係 401，
        #        攻擊者要靠訊息內容先分辨得出。）
        if user and not user["password_hash"]:
            raise HTTPException(401, "未設密碼")
        raise HTTPException(401, "Email 或密碼唔啱")
    return _issue_session(dict(user))


@app.post("/api/me/password")
def set_password(body: PasswordSet, user: dict = Depends(current_user)) -> dict:
    """
    設定／更改密碼。

    ⚠️ 如果已經有密碼，一定要提供現有密碼（唔可以淨係有 session 就改）——
       否則有人偷到你部手機就可以改密碼鎖你出嚟。
    """
    if len(body.password) < 6:
        raise HTTPException(400, "密碼最少 6 個字")
    with db.connect() as conn:
        row = conn.execute("SELECT password_hash FROM users WHERE id = ?",
                           (user["id"],)).fetchone()
        has_pw = bool(row and row["password_hash"])
        if has_pw and not _check_password(body.current or "", row["password_hash"]):
            raise HTTPException(403, "現有密碼唔啱")
        conn.execute("UPDATE users SET password_hash = ? WHERE id = ?",
                     (_hash_password(body.password), user["id"]))
    return {"ok": True, "has_password": True}


@app.delete("/api/me/password")
def remove_password(body: dict, user: dict = Depends(current_user)) -> dict:
    """移除密碼（之後只可以用驗證碼登入）。要提供現有密碼。"""
    with db.connect() as conn:
        row = conn.execute("SELECT password_hash FROM users WHERE id = ?",
                           (user["id"],)).fetchone()
        if row and row["password_hash"]:
            if not _check_password((body or {}).get("current") or "", row["password_hash"]):
                raise HTTPException(403, "現有密碼唔啱")
        conn.execute("UPDATE users SET password_hash = NULL WHERE id = ?", (user["id"],))
    return {"ok": True, "has_password": False}


@app.post("/api/auth/request-code")
def request_code(body: LoginRequest) -> dict:
    """寄驗證碼。開發模式：直接喺 console 印出。"""
    email = body.email.strip().lower()
    if "@" not in email:
        raise HTTPException(400, "Email 格式唔啱")

    code = "".join(secrets.choice(string.digits) for _ in range(6))
    with db.connect() as conn:
        conn.execute(
            """INSERT INTO login_codes (email, code, expires_at, tries)
               VALUES (?, ?, ?, 0)
               ON CONFLICT(email) DO UPDATE SET
                 code = excluded.code, expires_at = excluded.expires_at, tries = 0""",
            (email, code, _iso(_now() + timedelta(minutes=CODE_TTL_MINUTES))),
        )

    # 寄信（Gmail SMTP / Resend）—— 未設定就 fallback 去 console
    from .mailer import mail_status, send_code_email
    result = send_code_email(email, code, CODE_TTL_MINUTES)

    if result["sent"]:
        print(f"  ✉️  驗證碼已寄去 {email}（經 {result['mode']}）", flush=True)
    else:
        if result.get("error"):
            print(f"  ⚠️  寄信失敗（{result['mode']}）：{result['error']}", flush=True)
        print(f"\n  ┌─ Wander 登入驗證碼 ─────────────────────")
        print(f"  │  {email}")
        print(f"  │  驗證碼：  {code}")
        print(f"  └─ 有效期 {CODE_TTL_MINUTES} 分鐘 ────────────────\n", flush=True)

    out: dict[str, Any] = {
        "ok": True,
        "expires_in_minutes": CODE_TTL_MINUTES,
        "delivery": result["mode"],
        "email_sent": result["sent"],
    }
    if result.get("error"):
        out["delivery_error"] = result["error"]
    # ⚠️ 只有「完全冇設定過寄信」先回傳 dev_code。
    #    如果設定咗但寄失敗（例如 App Password 錯），唔應該靜靜俾人用 dev_code 登入 ——
    #    咁樣會掩蓋設定問題。
    if result["mode"] == "console" and DEV_MODE:
        out["dev_code"] = code
    return out


def _consume_code(email: str, code: str) -> bool:
    """
    檢查＋消耗一個驗證碼。回 True/False（唔會拋錯）。

    ⚠️ 抽做 helper 係為咗俾 `/api/auth/claim` 共用 ——
       如果兩處各寫一份，將來一定會有一邊改漏（例如忘記加次數限制）。
    """
    email = (email or "").strip().lower()
    code = (code or "").strip()
    if not email or not code:
        return False
    with db.connect() as conn:
        row = conn.execute("SELECT * FROM login_codes WHERE email = ?", (email,)).fetchone()
        if not row:
            return False
        if row["tries"] >= 5:
            return False
        if _iso(_now()) > row["expires_at"]:
            return False
        if not secrets.compare_digest(row["code"], code):
            conn.execute("UPDATE login_codes SET tries = tries + 1 WHERE email = ?", (email,))
            return False
        conn.execute("DELETE FROM login_codes WHERE email = ?", (email,))
    return True


@app.post("/api/auth/verify")
def verify_code(body: VerifyRequest) -> dict:
    """
    驗證碼 → 建立／取回用戶 → 出 session token。

    ⚠️ UI 已經**冇**驗證碼登入（用戶要求刪走）。
       呢個 endpoint 保留做：
         · 「認領舊帳號」流程（/api/auth/claim 用 _consume_code）
         · 將來嘅「忘記密碼」
    """
    email = body.email.strip().lower()
    code = body.code.strip()

    with db.connect() as conn:
        row = conn.execute("SELECT * FROM login_codes WHERE email = ?", (email,)).fetchone()
        if not row:
            raise HTTPException(400, "請先索取驗證碼")
        if row["tries"] >= 5:
            raise HTTPException(429, "嘗試次數過多，請重新索取驗證碼")
        if _iso(_now()) > row["expires_at"]:
            raise HTTPException(400, "驗證碼已過期")
        if not secrets.compare_digest(row["code"], code):
            conn.execute("UPDATE login_codes SET tries = tries + 1 WHERE email = ?", (email,))
            raise HTTPException(400, "驗證碼唔啱")

        conn.execute("DELETE FROM login_codes WHERE email = ?", (email,))

        user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if not user:
            uid = _new_id("usr")
            conn.execute(
                # ⚠️⚠️ 明確寫 onboarded = 0（唔好靠 NULL）——
                #    「0 = 未睇教學 → 登入會出」係一個**明確嘅狀態**，
                #    靠 NULL 嘅話將來加其他欄位好易撞。
                #    舊用戶由 db.py 嘅 backfill 設做 1（唔會再出）。
                """INSERT INTO users (id, email, display_name, onboarded)
                   VALUES (?, ?, ?, 0)""",
                (uid, email, email.split("@")[0]),
            )
            user = conn.execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()

    return _issue_session(user)


@app.get("/api/me")
def me(user: dict = Depends(current_user)) -> dict:
    with db.connect() as conn:
        trips = db.rows_to_list(conn.execute(
            """SELECT t.*, (SELECT COUNT(*) FROM members m WHERE m.trip_id = t.id) AS member_count,
                      (SELECT COUNT(*) FROM items i WHERE i.trip_id = t.id) AS item_count
               FROM trips t JOIN members m2 ON m2.trip_id = t.id AND m2.user_id = ?
               ORDER BY t.created_at DESC""",
            (user["id"],),
        ).fetchall())
    return {
        # ⚠️ 用 .get() —— migration 加咗欄位之後，舊 session 嘅 user dict
        #    可能仲係舊 schema（冇 username key），直接索引會 KeyError。
        "user": {
            "id": user.get("id"),
            "email": user.get("email"),
            "username": user.get("username"),
            "display_name": user.get("display_name"),
            "avatar": user.get("avatar"),
            "theme": user.get("theme"),
            "onboarded": bool(user.get("onboarded")),
            # ⚠️⚠️ 用戶報嘅 bug：
            #   「我個帳號本身係 set 咗一個密碼嘅，所以呢你去改密碼
            #    嘅時候呢，例如去 setting，佢冇理由會同你講你仲未
            #    有密碼。我覺得呢個要改。」
            #
            #   ⚠️ 根因：`/api/me` **根本冇回 `has_password`** ——
            #      前端 `user.has_password` 永遠 `undefined`（falsy）
            #      → Settings 永遠顯示「未設定」。
            #      （`_issue_session()` 有計，但嗰個係登入回嘅，
            #        `/api/me` 冇跟。）
            "has_password": bool(user.get("password_hash")),
        },
        "trips": trips,
    }


# ══════════════════════════════════════════════════════════════
# 帳號名（@username）
# ══════════════════════════════════════════════════════════════

# ⚠️ 為咩要嚴格驗證 username：
#   · 佢係「俾人打嘅身份」—— 有同形字（l/1/I、O/0）就會有人冒充
#   · 只准 a-z 0-9 _ ，全部轉細階 → 冇大小寫混淆
#   · 開頭一定要字母 → 唔會同純數字（例如電話號碼）撞
#   · **一定要有字母 + 數字** → 防止用「alice」「bob」呢類純字詞
#     （純字詞好易撞名、好易估，加數字之後撞名機會細好多）
#   · 保留字要擋（admin / wander / support…）防止冒充官方
USERNAME_RE = re.compile(r"^[a-z][a-z0-9_]{2,19}$")
USERNAME_HAS_LETTER = re.compile(r"[a-z]")
USERNAME_HAS_DIGIT = re.compile(r"[0-9]")
USERNAME_RESERVED = {
    "admin", "administrator", "root", "wander", "support", "help", "official",
    "system", "api", "www", "mail", "me", "you", "null", "undefined", "test",
    "about", "settings", "friends", "trips", "money", "shopping", "zones",
    "all", "everyone", "here", "there", "nobody", "someone",
}


def _norm_username(raw: str) -> str:
    """正規化：去 @、去空白、轉細階。"""
    return (raw or "").strip().lstrip("@＠").strip().lower()


def _check_username(u: str) -> str:
    """驗證並回傳正規化嘅 username（唔啱就 raise）。"""
    u = _norm_username(u)
    if not u:
        raise HTTPException(400, "請填帳號名")
    if len(u) < 3:
        raise HTTPException(400, "帳號名最少 3 個字")
    if len(u) > 20:
        raise HTTPException(400, "帳號名最多 20 個字")
    if not USERNAME_RE.match(u):
        raise HTTPException(400, "帳號名只可以用英文字母、數字、底線，而且要字母開頭")

    # ⚠️ 保留字檢查一定要排喺「要數字」**之前** ——
    #    否則「admin」（冇數字）會先被「要數字」擋，
    #    訊息會變成「要有埋數字」而唔係「呢個係保留字」→ 誤導用戶。
    for word in USERNAME_RESERVED:
        # 唔止擋完全相同，仲要擋「admin1」「admin_2026」呢類前綴冒充
        if u == word or u.startswith(word + "_") or \
                (u.startswith(word) and u[len(word):].isdigit()):
            raise HTTPException(400, f"「{word}」係保留字（或者太似），揀第二個")

    # ⚠️ 用戶要求：一定要「字母 + 數字」都有
    if not USERNAME_HAS_DIGIT.search(u):
        raise HTTPException(400, "帳號名要有埋數字（例如 alice99、alice_2026）")
    if not USERNAME_HAS_LETTER.search(u):
        raise HTTPException(400, "帳號名要有英文字母（唔可以全部數字）")
    return u


def _public_user(row, *, viewer: str | None = None) -> dict:
    """對外公開嘅用戶資料（包含 username / avatar）。"""
    d = db.row_to_dict(row) or {}
    return {
        "id": d.get("id"),
        "email": d.get("email"),
        "username": d.get("username"),
        "display_name": d.get("display_name"),
        "avatar": d.get("avatar"),
        "theme": d.get("theme"),
        # ⚠️ 要帶 onboarded 俾前端決定要唔要出新手教學
        "onboarded": bool(d.get("onboarded")),
    }


# 像素頭像 id（同 web/src/lib/avatars.js 保持一致）
#   ⚠️ 一定要驗證 —— 唔可以任由用戶塞任意字串入 avatar 欄，
#      因為前端會將佢當 id 用（將來如果用嚟做檔名就更危險）。
AVATAR_IDS = {
    "cat", "dog", "pig", "rabbit", "duck", "bear", "panda", "fox", "frog",
    "penguin", "hamster", "unicorn", "moon", "star", "cloud", "flower",
    "ring", "heart", "bolt", "wave", "sun", "tree", "mountain", "diamond",
    "ghost", "rubik", "phone", "camera", "suitcase", "plane", "rocket",
    "icecream", "cake", "coffee", "rainbow", "alien", "robot",
}


class OnboardIn(BaseModel):
    """新手教學最後一步：設定名字。⚠️ 名字係**必填**。"""
    display_name: str


class UpdateMe(BaseModel):
    avatar: Optional[str] = None
    username: Optional[str] = None
    display_name: Optional[str] = None
    theme: Optional[str] = None


@app.post("/api/me/onboard")
def finish_onboarding(body: OnboardIn, user: dict = Depends(current_user)) -> dict:
    """
    完成新手教學（同時設定名字）。

    ⚠️⚠️ 用戶明確要求：「你叫乜嘢名…呢個係必做嘅」

       所以：
         · 名字唔可以空白
         · 名字最少 1 個字、最多 40 字（同 PATCH /api/me 一致）
         · **只有喺呢一步成功之後**先會設 `onboarded = 1`
           → 用戶中途閂咗個 app，下次登入會再見到教學
             （唔會出現「未改名但當佢完成咗」嘅狀態）
    """
    name = (body.display_name or "").strip()
    if not name:
        raise HTTPException(400, "請填你嘅名")
    if len(name) > 40:
        raise HTTPException(400, "名太長（最多 40 個字）")
    with db.connect() as conn:
        conn.execute(
            "UPDATE users SET display_name = ?, onboarded = 1 WHERE id = ?",
            (name, user["id"]))
    return {"ok": True, "display_name": name, "onboarded": True}


@app.patch("/api/me")
def update_me(body: UpdateMe, user: dict = Depends(current_user)) -> dict:
    fields, vals = [], []
    if body.display_name is not None:
        fields.append("display_name = ?"); vals.append(body.display_name.strip()[:40])
    if body.theme is not None:
        fields.append("theme = ?"); vals.append(body.theme.strip()[:20])
    if body.avatar is not None:
        av = body.avatar.strip()
        if av and av not in AVATAR_IDS:
            raise HTTPException(400, f"冇呢個頭像：{av}")
        fields.append("avatar = ?"); vals.append(av or None)
    if getattr(body, "username", None) is not None:
        u = _check_username(body.username)
        with db.connect() as conn:
            taken = conn.execute("SELECT id FROM users WHERE username = ?", (u,)).fetchone()
        if taken and taken["id"] != user["id"]:
            raise HTTPException(409, f"「@{u}」已經有人用")
        fields.append("username = ?"); vals.append(u)
    if not fields:
        return {"ok": True}
    vals.append(user["id"])
    with db.connect() as conn:
        conn.execute(f"UPDATE users SET {', '.join(fields)} WHERE id = ?", vals)
    return {"ok": True}


# ══════════════════════════════════════════════════════════════
# Trips（group）
# ══════════════════════════════════════════════════════════════

class TripCreate(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    destination: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    days: int = Field(default=3, ge=1, le=30)


class TripUpdate(BaseModel):
    name: Optional[str] = None
    destination: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    days: Optional[int] = Field(default=None, ge=1, le=30)
    # ⚠️⚠️ 記帳貨幣（用戶要求：「根據匯率去轉返嗰個你想要嘅錢」）
    #    ⚠️ 3 個大寫字母（ISO 4217）—— 太長／有古怪字元要擋。
    currency: Optional[str] = Field(default=None, max_length=3)


def _require_member(trip_id: str, user_id: str) -> dict:
    with db.connect() as conn:
        row = conn.execute(
            """SELECT t.*, m.role FROM trips t
               JOIN members m ON m.trip_id = t.id
               WHERE t.id = ? AND m.user_id = ?""",
            (trip_id, user_id),
        ).fetchone()
    if not row:
        raise HTTPException(404, "搵唔到呢個旅程，或者你唔係成員")
    return dict(row)


@app.post("/api/trips")
def create_trip(body: TripCreate, user: dict = Depends(current_user)) -> dict:
    tid = _new_id("trip")
    with db.connect() as conn:
        conn.execute(
            """INSERT INTO trips (id, name, destination, start_date, end_date, days, invite_code, owner_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (tid, body.name.strip(), body.destination, body.start_date,
             body.end_date, body.days, _invite_code(), user["id"]),
        )
        conn.execute("INSERT INTO members (trip_id, user_id, role) VALUES (?, ?, 'owner')",
                     (tid, user["id"]))
        row = conn.execute("SELECT * FROM trips WHERE id = ?", (tid,)).fetchone()
        # ⚠️ 用戶打咗「目的地」就即刻幫佢建立城市（有座標）——
        #    否則地圖會跌落 fallback，用戶見到完全不同嘅地方。
        _ensure_stops_from_destination(conn, row)
    return dict(row)


@app.get("/api/trips/{trip_id}")
def get_trip(trip_id: str, user: dict = Depends(current_user)) -> dict:
    trip = _require_member(trip_id, user["id"])
    with db.connect() as conn:
        members = db.rows_to_list(conn.execute(
            """SELECT u.id, u.email, u.display_name, u.avatar, m.role, m.joined_at
               FROM members m JOIN users u ON u.id = m.user_id
               WHERE m.trip_id = ? ORDER BY m.joined_at""",
            (trip_id,),
        ).fetchall())
        items = db.rows_to_list(conn.execute(
            "SELECT * FROM items WHERE trip_id = ? ORDER BY sort_order, created_at",
            (trip_id,),
        ).fetchall())
    trip["members"] = members
    trip["items"] = [db.item_row_to_api(r) for r in items]
    return trip


@app.patch("/api/trips/{trip_id}")
def update_trip(trip_id: str, body: TripUpdate, user: dict = Depends(current_user)) -> dict:
    _require_member(trip_id, user["id"])
    fields, vals = [], []
    for f in ("name", "destination", "start_date", "end_date", "days", "currency"):
        v = getattr(body, f)
        if v is not None:
            if f == "currency":
                v = str(v).strip().upper()
                # ⚠️ 唔可以用 len != 3 就 raise —— 空字串 = 還原預設
                if v and not v.isalpha():
                    raise HTTPException(400, "貨幣代碼唔啱（要 3 個英文字母）")
                v = v or "HKD"
            fields.append(f"{f} = ?"); vals.append(v)
    if fields:
        vals.append(trip_id)
        with db.connect() as conn:
            conn.execute(f"UPDATE trips SET {', '.join(fields)} WHERE id = ?", vals)
            # ⚠️ 改咗目的地 → 如果本來冇城市，就補返一個
            if "destination" in body:
                row = conn.execute("SELECT * FROM trips WHERE id = ?", (trip_id,)).fetchone()
                _ensure_stops_from_destination(conn, row)
    return {"ok": True}


class StopIn(BaseModel):
    city: str = Field(min_length=1, max_length=40)
    days: int = Field(default=1, ge=1, le=60)


def _ensure_stops_from_destination(conn, trip_row) -> int:
    """
    如果 trip 冇城市但有 `destination` → 自動由 destination 建立城市。

    ⚠️⚠️ 為咩要呢個（真實用戶 bug）：
       用戶建立 trip 嗰陣打「香港」落**目的地**欄，
       但地圖只讀 🧭「城市」編輯器（空嘅）
       → 地圖跌落 fallback（福岡）→ 用戶見到完全不同嘅地方。

       佢嘅資料冇錯，係我哋冇將「目的地」當一回事。
       所以：只要有任何地方寫住個目的地，就應該用嚟定位。

    ⚠️ 只會喺 `trip_stops` **完全空**嘅時候做 ——
       唔可以覆蓋用戶明確設定嘅多城市行程。
    """
    try:
        tid = trip_row["id"]
        dest = (trip_row["destination"] or "").strip()
        if not dest:
            return 0
        n = conn.execute("SELECT COUNT(*) c FROM trip_stops WHERE trip_id=?",
                         (tid,)).fetchone()["c"]
        if n:
            return 0
        from wander.lookup import geocode_city
        c = geocode_city(dest)
        if not c or c.lat is None:
            return 0
        days = int(trip_row["days"] or 1) or 1
        # ⚠️ 順便計埋時區 —— 唔使前端做，因為前端冇國家代碼
        from wander.tz import lookup as tz_lookup
        tz = tz_lookup(c.lat, c.lng, getattr(c, "cc", None))
        conn.execute(
            """INSERT INTO trip_stops
                 (id, trip_id, city, days, position, lat, lng, country, timezone)
               VALUES (?,?,?,?,0,?,?,?,?)""",
            (_new_id("stop"), tid, dest, days, c.lat, c.lng, c.country, tz.get("tz")))
        return 1
    except Exception:
        return 0


@app.get("/api/trips/{trip_id}/stops")
def get_stops(trip_id: str, user: dict = Depends(current_user)) -> dict:
    trip = _require_member(trip_id, user["id"])
    with db.connect() as conn:
        # ⚠️ 冇城市但有「目的地」→ 查座標 + 真正寫入 trip_stops
        #    （修用戶報嘅 bug：佢打「香港」落目的地，地圖卻顯示福岡）
        _ensure_stops_from_destination(conn, trip)
        rows = db.rows_to_list(conn.execute(
            "SELECT * FROM trip_stops WHERE trip_id=? ORDER BY position", (trip_id,)).fetchall())

    # ⚠️⚠️ 唔可以「合成」一個冇座標嘅假城市！
    #
    #    舊 code 咁做：
    #      if not rows and trip.get("destination"):
    #          rows = [{"id": None, "city": ..., }]     ← 冇 lat/lng
    #
    #    兩個問題：
    #      ① `id: None` → 前端 React key 撞、撳「刪除」會亂、
    #         地圖 `filter(s => s.lat != null)` 會剔走佢 → 地圖仍然冇中心
    #      ② 用戶見到「香港」喺清單度以為設定好咗，但其實冇座標
    #         → 佢唔會知要再撳入去設定
    #
    #    寧願誠實咁顯示「未設定城市」，等用戶去撳。
    return {"stops": rows, "total_days": sum(r["days"] or 0 for r in rows)}


@app.put("/api/trips/{trip_id}/stops")
def set_stops(trip_id: str, body: dict, user: dict = Depends(current_user)) -> dict:
    """
    一次過覆蓋整個城市清單（最簡單、最唔會唔一致）。

    body = {"stops": [{"city": "福岡", "days": 4}, {"city": "首爾", "days": 3}]}

    ⚠️ 同時更新 trips.days = 所有 stops 嘅總和
       （如果有 start_date，end_date 都會跟住推）。
    """
    trip = _require_member(trip_id, user["id"])
    raw = body.get("stops") or []
    stops = []
    for i, st in enumerate(raw):
        city = (st.get("city") or "").strip()
        if not city:
            continue
        stops.append((city[:40], max(1, min(60, int(st.get("days") or 1))), i))
    if not stops:
        raise HTTPException(400, "至少要有一個城市")

    total = sum(d for _, d, _ in stops)

    # 城市 → 座標（地圖定位用）
    #   ⚠️ 用本地城市庫（0.03ms），本地搵唔到先 fallback 上網
    coords: dict[str, tuple] = {}
    try:
        from wander.lookup import geocode_city
        for city, _d, _p in stops:
            try:
                c = geocode_city(city)
                if c and c.lat is not None:
                    # ⚠️ 順便計埋時區（前端冇國家代碼，做唔到）
                    from wander.tz import lookup as tz_lookup
                    tz = tz_lookup(c.lat, c.lng, getattr(c, "cc", None))
                    coords[city] = (c.lat, c.lng, c.country, tz.get("tz"))
            except Exception:
                pass
    except Exception:
        pass

    with db.connect() as conn:
        conn.execute("DELETE FROM trip_stops WHERE trip_id=?", (trip_id,))
        for city, days, pos in stops:
            la, ln, cc, tz = coords.get(city, (None, None, None, None))
            conn.execute(
                """INSERT INTO trip_stops
                     (id, trip_id, city, days, position, lat, lng, country, timezone)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (_new_id("stop"), trip_id, city, days, pos, la, ln, cc, tz))

        # 更新總日數，同步 end_date
        patch: dict[str, Any] = {"days": total}
        if trip.get("start_date"):
            from datetime import date as _date, timedelta as _td
            try:
                y, m, d = map(int, str(trip["start_date"]).split("-"))
                patch["end_date"] = str(_date(y, m, d) + _td(days=total - 1))
            except Exception:
                pass
        sets = ", ".join(f"{k} = ?" for k in patch)
        conn.execute(f"UPDATE trips SET {sets} WHERE id = ?",
                     [*patch.values(), trip_id])

    return get_stops(trip_id, user)


@app.delete("/api/trips/{trip_id}")
def delete_trip(trip_id: str, user: dict = Depends(current_user)) -> dict:
    """只有 owner 可以刪除。"""
    trip = _require_member(trip_id, user["id"])
    if trip.get("role") != "owner":
        raise HTTPException(403, "只有建立者可以刪除旅程")
    with db.connect() as conn:
        conn.execute("DELETE FROM trips WHERE id = ?", (trip_id,))
    return {"ok": True}


@app.post("/api/trips/{trip_id}/leave")
def leave_trip(trip_id: str, user: dict = Depends(current_user)) -> dict:
    """成員退出（owner 唔可以退出，要刪除或者轉讓）。"""
    trip = _require_member(trip_id, user["id"])
    if trip.get("role") == "owner":
        raise HTTPException(400, "建立者唔可以退出，請改為刪除旅程")
    with db.connect() as conn:
        conn.execute("DELETE FROM members WHERE trip_id = ? AND user_id = ?",
                     (trip_id, user["id"]))
        # 一齊清走自己嘅投票
        conn.execute("""DELETE FROM votes WHERE user_id = ?
                        AND item_id IN (SELECT id FROM items WHERE trip_id = ?)""",
                     (user["id"], trip_id))
    return {"ok": True}


class MemberAdd(BaseModel):
    email: str


@app.post("/api/trips/{trip_id}/members")
def add_member(trip_id: str, body: MemberAdd, user: dict = Depends(current_user)) -> dict:
    """直接將朋友加入旅程（唔使邀請碼）。"""
    _require_member(trip_id, user["id"])
    email = body.email.strip().lower()
    with db.connect() as conn:
        target = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if not target:
            raise HTTPException(404, "搵唔到呢個用戶（要對方先登入過一次）")
        conn.execute(
            "INSERT OR IGNORE INTO members (trip_id, user_id, role) VALUES (?, ?, 'member')",
            (trip_id, target["id"]),
        )
    return {"ok": True, "added": {"id": target["id"], "display_name": target["display_name"]}}


@app.post("/api/trips/join/{invite_code}")
def join_trip(invite_code: str, user: dict = Depends(current_user)) -> dict:
    with db.connect() as conn:
        trip = conn.execute("SELECT * FROM trips WHERE invite_code = ?",
                            (invite_code.strip().upper(),)).fetchone()
        if not trip:
            raise HTTPException(404, "邀請碼唔啱")
        conn.execute(
            "INSERT OR IGNORE INTO members (trip_id, user_id, role) VALUES (?, ?, 'member')",
            (trip["id"], user["id"]),
        )
    return dict(trip)


@app.get("/api/trips/{trip_id}/items")
def list_items(trip_id: str, user: dict = Depends(current_user)) -> dict:
    _require_member(trip_id, user["id"])
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT * FROM items WHERE trip_id = ? ORDER BY sort_order, created_at",
            (trip_id,),
        ).fetchall()
    return {"items": [db.item_row_to_api(r) for r in rows]}


# ══════════════════════════════════════════════════════════════
# 解析引擎（包住 engine）
# ══════════════════════════════════════════════════════════════

class ParseRequest(BaseModel):
    url: Optional[str] = None
    text: Optional[str] = None
    no_fetch: bool = False
    enrich: bool = True          # 解析完再用搜尋補完


@app.post("/api/parse")
def parse(body: ParseRequest, user: dict = Depends(current_user)) -> dict:
    """
    貼 link 或文字 → 解析成 item。

    呢個係整個 App 嘅核心 endpoint。
    """
    from wander import fetch_item, parse_caption_multi, parse_url_offline
    from wander.lookup import enrich_caption_item

    if not body.url and not body.text:
        raise HTTPException(400, "要提供 url 或者 text")

    results: list[dict] = []
    trace: list[dict] = []

    # ⚠️ 支援「url + text 一齊」：用戶貼咗 IG link，但 IG 封鎖咗，
    #    所以再貼 caption。呢個時候要解析 caption，但保留 link 做記錄。
    if body.url and body.text:
        results = parse_caption_multi(body.text)
        for it in results:
            it.url = body.url
            it.notes.append("caption 由用戶提供（IG 封鎖自動讀取）")
        trace.append({"rule": "USER_CAPTION", "match": body.url[:80],
                      "note": "用戶提供 caption + 原 link"})
    elif body.url:
        if body.no_fetch:
            item = parse_url_offline(body.url)
            results = [item]
        else:
            item, trace, _meta = fetch_item(body.url, respect_robots=False)
            results = [item]
    elif body.text:
        results = parse_caption_multi(body.text)

    # 用搜尋補完（唔使 AI）
    if body.enrich:
        enriched = []
        for it in results:
            try:
                it2, log = enrich_caption_item(it)
                trace.extend({"rule": "ENRICH", "match": l[:120], "note": ""} for l in log)
                enriched.append(it2)
            except Exception:                       # 補完失敗唔可以影響主流程
                enriched.append(it)
        results = enriched

    return {
        "items": [it.to_dict() for it in results],
        "trace": trace,
    }


@app.get("/api/tz")
def api_tz(city: str, user: dict = Depends(current_user)) -> dict:
    """
    城市 → 時區。

    ⚠️⚠️ 用戶要求：
       「第二個就係有得比你揀 —— 你可以輸入嗰個城市嘅名，
        用英文或者中文都可以，之後呢例如你揀咗，
        然後就會有對應嘅時區。」

    ⚠️ 為咩要獨立一個 endpoint：
       世界時鐘唔一定要有旅程（冇旅程都想睇其他城市幾點）。
       ⚠️ 亦都唔應該為咗攞個時區而建立一個 trip_stop。

    回：{"city","matched","tz","source","confident","country"}
    """
    from wander.localgeo import search
    from wander.tz import lookup as tz_lookup

    q = (city or "").strip()
    if len(q) < 2:
        raise HTTPException(400, "城市名太短")

    hits = search(q, limit=1) or []
    if not hits:
        raise HTTPException(404, f"搵唔到「{q}」")

    # ⚠️ `localgeo.search()` 回 **dict** 而唔係 object
    #    （{"query","matched","lat","lng","country","population"}）
    c = hits[0]
    # ⚠️⚠️ `localgeo.search()` **冇回** country_code（只有中文國名）
    #    → 要用 `_zh_to_cc("日本")` 反查 "JP"。
    #    ⚠️ `_zh_to_cc` 係**函數**（接收一個中文名），
    #       唔係回一個 dict —— 我第一版寫錯咗，搞到成日 fallback 去
    #       `Etc/GMT-9`（功能啱但唔靚，前端顯示唔到「東京」）。
    try:
        from wander.localgeo import _zh_to_cc
        cc = _zh_to_cc(c.get("country") or "")
    except Exception:
        cc = None
    tz = tz_lookup(c.get("lat"), c.get("lng"), cc)
    return {
        "city": q,
        "matched": c.get("matched") or c.get("query") or q,
        "country": c.get("country"),
        "lat": c.get("lat"),
        "lng": c.get("lng"),
        "tz": tz.get("tz"),
        "source": tz.get("source"),
        # ⚠️ `confident=False` → 前端要顯示「約」
        "confident": bool(tz.get("confident")),
    }


@app.get("/api/lookup")
def lookup(name: str, hint: Optional[str] = None,
           user: dict = Depends(current_user)) -> dict:
    """由店名反查完整資料。"""
    from wander.lookup import lookup_place
    item, log = lookup_place(name, hint=hint)
    return {"item": item.to_dict(), "trace": log}


@app.post("/api/items")
def create_item(trip_id: str, parsed: dict, user: dict = Depends(current_user)) -> dict:
    """將一個解析好嘅 item 存入 trip。"""
    _require_member(trip_id, user["id"])
    iid = _new_id("item")
    with db.connect() as conn:
        nxt = conn.execute(
            "SELECT COALESCE(MAX(sort_order), -1) + 1 AS n FROM items WHERE trip_id = ?",
            (trip_id,),
        ).fetchone()["n"]
        conn.execute(
            """INSERT INTO items (id, trip_id, created_by, parsed, name, category,
                                  country, district, lat, lng, confidence, needs_review, sort_order)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (iid, trip_id, user["id"], json.dumps(parsed, ensure_ascii=False),
             parsed.get("name"), parsed.get("category"), parsed.get("country"),
             parsed.get("district"), parsed.get("lat"), parsed.get("lng"),
             int(parsed.get("confidence") or 0),
             1 if parsed.get("needs_review") else 0, nxt),
        )
        row = conn.execute("SELECT * FROM items WHERE id = ?", (iid,)).fetchone()
    return db.item_row_to_api(row)


class ItemPatch(BaseModel):
    # 行程編排
    day_index: Optional[int] = None
    sort_order: Optional[int] = None
    clear_day: bool = False
    # 內容編輯（補名稱、改分類、加座標…）
    name: Optional[str] = None
    district: Optional[str] = None
    category: Optional[str] = None
    parsed: Optional[dict] = None        # 整個 item 覆蓋（例如 lookup 補完之後）


@app.patch("/api/items/{item_id}")
def update_item(item_id: str, body: ItemPatch, user: dict = Depends(current_user)) -> dict:
    """
    更新一個 item。

    支援兩類更新：
      1. 行程編排（day_index / sort_order / clear_day）
      2. 內容編輯（name / district / category / 整個 parsed 覆蓋）
    """
    with db.connect() as conn:
        row = conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
        if not row:
            raise HTTPException(404, "搵唔到")
        _require_member(row["trip_id"], user["id"])

        # ① parsed 覆蓋（最完整嘅更新方式）
        parsed = json.loads(row["parsed"])
        if body.parsed:
            parsed.update(body.parsed)
        if body.name is not None:
            parsed["name"] = body.name or None
            parsed["name_method"] = parsed.get("name_method") or "用戶手動輸入"
        if body.district is not None:
            parsed["district"] = body.district or None
        if body.category is not None:
            parsed["category"] = body.category or None
            parsed["category_label"] = parsed.get("category_label") or None

        # 重算信心分數（用戶補咗名／地區應該升分）
        if body.name or body.district or body.category:
            try:
                from wander.caption import CaptionParser
                from wander.models import Item as EItem
                tmp = EItem(**{k: v for k, v in parsed.items()
                               if k in EItem.__dataclass_fields__})
                if tmp.name:
                    tmp.field_confidence["name"] = 92
                if tmp.district or tmp.city:
                    tmp.field_confidence["location"] = max(
                        tmp.field_confidence.get("location", 0), 84)
                CaptionParser._score(tmp, dict(tmp.field_confidence))
                parsed["confidence"] = tmp.confidence
                parsed["needs_review"] = tmp.needs_review
                parsed["field_confidence"] = tmp.field_confidence
            except Exception:
                pass                    # 計分失敗唔影響更新

        # ② 寫入（parsed + 方便查詢嘅 denormalized 欄位）
        conn.execute(
            """UPDATE items SET parsed = ?, name = ?, category = ?, country = ?,
                                district = ?, lat = ?, lng = ?, confidence = ?,
                                needs_review = ? WHERE id = ?""",
            (json.dumps(parsed, ensure_ascii=False), parsed.get("name"),
             parsed.get("category"), parsed.get("country"), parsed.get("district"),
             parsed.get("lat"), parsed.get("lng"), int(parsed.get("confidence") or 0),
             1 if parsed.get("needs_review") else 0, item_id),
        )

        # ③ 行程編排
        if body.clear_day:
            conn.execute("UPDATE items SET day_index = NULL WHERE id = ?", (item_id,))
        else:
            if body.day_index is not None:
                conn.execute("UPDATE items SET day_index = ? WHERE id = ?",
                             (body.day_index, item_id))
            if body.sort_order is not None:
                conn.execute("UPDATE items SET sort_order = ? WHERE id = ?",
                             (body.sort_order, item_id))

        row = conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
    return db.item_row_to_api(row)


@app.delete("/api/items/{item_id}")
def delete_item(item_id: str, user: dict = Depends(current_user)) -> dict:
    with db.connect() as conn:
        row = conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
        if not row:
            raise HTTPException(404, "搵唔到")
        _require_member(row["trip_id"], user["id"])
        conn.execute("DELETE FROM items WHERE id = ?", (item_id,))
    return {"ok": True}


@app.post("/api/items/{item_id}/vote")
def toggle_vote(item_id: str, user: dict = Depends(current_user)) -> dict:
    with db.connect() as conn:
        row = conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
        if not row:
            raise HTTPException(404, "搵唔到")
        _require_member(row["trip_id"], user["id"])
        has = conn.execute("SELECT 1 FROM votes WHERE item_id = ? AND user_id = ?",
                           (item_id, user["id"])).fetchone()
        if has:
            conn.execute("DELETE FROM votes WHERE item_id = ? AND user_id = ?",
                         (item_id, user["id"]))
            conn.execute("UPDATE items SET votes = MAX(0, votes - 1) WHERE id = ?", (item_id,))
            voted = False
        else:
            conn.execute("INSERT INTO votes (item_id, user_id) VALUES (?, ?)",
                         (item_id, user["id"]))
            conn.execute("UPDATE items SET votes = votes + 1 WHERE id = ?", (item_id,))
            voted = True
        total = conn.execute("SELECT votes FROM items WHERE id = ?", (item_id,)).fetchone()["votes"]
    return {"voted": voted, "votes": total}


@app.post("/api/items/reorder")
def reorder(payload: dict, user: dict = Depends(current_user)) -> dict:
    """
    批量更新行程編排（拖拽之後一次過送）。

    payload = {"trip_id": "...", "layout": [{"id": "...", "day_index": 1, "sort_order": 0}, …]}
    """
    trip_id = payload.get("trip_id")
    layout = payload.get("layout") or []
    if not trip_id:
        raise HTTPException(400, "要提供 trip_id")
    _require_member(trip_id, user["id"])
    with db.connect() as conn:
        for i, entry in enumerate(layout):
            conn.execute(
                "UPDATE items SET day_index = ?, sort_order = ? WHERE id = ? AND trip_id = ?",
                (entry.get("day_index"), entry.get("sort_order", i), entry["id"], trip_id),
            )
    return {"ok": True, "count": len(layout)}


# ══════════════════════════════════════════════════════════════
# 好友（要 accept 先成為朋友）
# ══════════════════════════════════════════════════════════════

@app.get("/api/friends")
def list_friends(user: dict = Depends(current_user)) -> dict:
    """我嘅朋友 + 待處理請求（收到／發出）。"""
    with db.connect() as conn:
        friends = db.rows_to_list(conn.execute(
            """SELECT u.id, u.email, u.display_name, u.avatar, f.created_at
               FROM friends f JOIN users u ON u.id = f.friend_id
               WHERE f.user_id = ? ORDER BY u.display_name""",
            (user["id"],),
        ).fetchall())

        # ⚠️ 唔可以同時有 `id`（請求 id）同 `id`（用戶 id）——
        #    同一個 object 有兩個 "id" 係災難（前端好易攞錯）。
        #    所以用戶 id 改名做 `user_id`，請求 id 叫 `request_id`。
        incoming = db.rows_to_list(conn.execute(
            """SELECT r.id AS request_id, r.created_at,
                      u.id AS user_id, u.email, u.display_name, u.avatar
               FROM friend_requests r JOIN users u ON u.id = r.from_id
               WHERE r.to_id = ? AND r.status = 'pending'
               ORDER BY r.created_at DESC""",
            (user["id"],),
        ).fetchall())

        outgoing = db.rows_to_list(conn.execute(
            """SELECT r.id AS request_id, r.created_at,
                      u.id AS user_id, u.email, u.display_name, u.avatar
               FROM friend_requests r JOIN users u ON u.id = r.to_id
               WHERE r.from_id = ? AND r.status = 'pending'
               ORDER BY r.created_at DESC""",
            (user["id"],),
        ).fetchall())

    return {"friends": friends, "incoming": incoming, "outgoing": outgoing}


class FriendRequestIn(BaseModel):
    # ⚠️ 加朋友改用 @帳號名，唔再用 email。
    #    email 保留做向後兼容（舊前端 / 舊連結）。
    username: Optional[str] = None
    email: Optional[str] = None


@app.post("/api/friends/invite")
def invite_friend_by_email(body: dict, user: dict = Depends(current_user)) -> dict:
    """
    用 email 邀請朋友（**真寄 email**）。

    ⚠️ 三種情況要分清楚：
      ① 對方已經係朋友        → 唔使做嘢
      ② 對方有帳號但未係朋友   → 建 friend_request（app 內通知）+ 都寄 email
      ③ 對方冇帳號            → 建 friend_invite（一次性連結）+ 寄 email

    ⚠️ 無論 email 寄唔寄到，**邀請本身都會建立** ——
       寄信失敗唔應該令「加朋友」失敗。連結可以自己複製畀對方。
    """
    email = (body.get("email") or "").strip().lower()
    note = (body.get("note") or "").strip()[:200]
    if "@" not in email or "." not in email.split("@")[-1]:
        raise HTTPException(400, "Email 格式唔啱")
    with db.connect() as conn:
        me = db.row_to_dict(conn.execute(
            "SELECT * FROM users WHERE id = ?", (user["id"],)).fetchone())
    if email == (me.get("email") or "").lower():
        raise HTTPException(400, "唔可以加自己")

    from .mailer import send_friend_invite
    import secrets as _secrets

    resp_status = "unknown"
    with db.connect() as conn:
        target = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()

        # ① 已經係朋友？
        if target:
            fr = conn.execute(
                """SELECT 1 FROM friends
                   WHERE (user_id=? AND friend_id=?) OR (user_id=? AND friend_id=?)""",
                (user["id"], target["id"], target["id"], user["id"])).fetchone()
            if fr:
                return {"ok": True, "status": "already_friends", "email": email}

        # ② 已經有 pending 請求？
        if target:
            ex = conn.execute(
                """SELECT * FROM friend_requests
                   WHERE from_id=? AND to_id=? AND status='pending'""",
                (user["id"], target["id"])).fetchone()
            if ex:
                req_id = ex["id"]
            else:
                # 對方之前有冇邀請過我？有就自動成為朋友
                rev = conn.execute(
                    """SELECT * FROM friend_requests
                       WHERE from_id=? AND to_id=? AND status='pending'""",
                    (target["id"], user["id"])).fetchone()
                if rev:
                    conn.execute("UPDATE friend_requests SET status='accepted' WHERE id=?",
                                 (rev["id"],))
                    conn.execute("INSERT OR IGNORE INTO friends (user_id, friend_id) VALUES (?,?)",
                                 (user["id"], target["id"]))
                    conn.execute("INSERT OR IGNORE INTO friends (user_id, friend_id) VALUES (?,?)",
                                 (target["id"], user["id"]))
                    target_row = target
                    resp_status = "now_friends"
                    req_id = None
                else:
                    req_id = _new_id("freq")
                    conn.execute(
                        """INSERT INTO friend_requests (id, from_id, to_id, status)
                           VALUES (?,?,?,'pending')""",
                        (req_id, user["id"], target["id"]))
                    resp_status = "requested"

        # ③ 建立一次性邀請連結
        #    ⚠️ 無論對方有冇帳號都要建立 —— 因為：
        #       · 對方冇帳號 → 佢撳 email 連結去註冊
        #       · 對方有帳號但未登入 → 佢撳連結登入就自動加
        token = _secrets.token_urlsafe(24)
        conn.execute(
            """UPDATE friend_invites SET status='expired'
               WHERE email=? AND from_user=? AND status='pending'""",
            (email, user["id"]))
        conn.execute(
            """INSERT INTO friend_invites (id, from_user, email, token, expires_at)
               VALUES (?,?,?,?,?)""",
            (_new_id("finv"), user["id"], email, token,
             _iso(_now() + timedelta(days=30))))
        if not target:
            resp_status = "invited"

    # ── 寄 email（真寄）──
    from .__main__ import lan_ips
    import os as _os
    port = _os.environ.get("WANDER_PORT", "8787")
    ips = lan_ips()
    base = _os.environ.get("WANDER_BASE_URL") or (
        f"http://{ips[0]}:{port}" if ips else f"http://127.0.0.1:{port}")
    url = f"{base}/?friend={token}"

    mail = send_friend_invite(
        email, from_name=me.get("display_name") or me.get("email") or "你嘅朋友",
        url=url, note=note)

    return {
        "ok": True,
        "status": resp_status,          # requested | invited | now_friends | already_friends
        "email": email,
        "url": url,
        "email_sent": bool(mail.get("sent")),
        "delivery": mail.get("mode"),
        "delivery_error": mail.get("error"),
    }


@app.get("/api/users/lookup")
def lookup_user(username: str, user: dict = Depends(current_user)) -> dict:
    """
    查有冇呢個 @帳號名（加朋友之前預覽）。

    ⚠️ 只回公開資料（username / display_name / avatar），唔回 email ——
       否則可以用嚟掃描邊啲 email 註冊過（私隱洩漏）。
    """
    u = _norm_username(username)
    if not u:
        raise HTTPException(400, "請填帳號名")
    if not USERNAME_RE.match(u):
        raise HTTPException(404, f"搵唔到 @{u}")
    with db.connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE username = ?", (u,)).fetchone()
    if not row:
        raise HTTPException(404, f"搵唔到 @{u}")
    if row["id"] == user["id"]:
        return {"user": _public_user(row), "is_self": True}
    return {"user": _public_user(row), "is_self": False}


@app.post("/api/friends/requests")
def send_friend_request(body: FriendRequestIn, user: dict = Depends(current_user)) -> dict:
    """
    發好友請求（唔會即刻成為朋友，要對方 accept）。

    特殊情況：如果對方已經向我發過請求 → 直接 accept（互相加，唔使等）。
    """
    # ⚠️ 主要用 @username；email 只係向後兼容
    if body.username:
        uname = _norm_username(body.username)
        if not uname:
            raise HTTPException(400, "請填帳號名")
        with db.connect() as conn:
            target = conn.execute("SELECT * FROM users WHERE username = ?",
                                  (uname,)).fetchone()
        if not target:
            raise HTTPException(404, f"搵唔到 @{uname}")
    else:
        email = (body.email or "").strip().lower()
        if "@" not in email:
            raise HTTPException(400, "請填帳號名（@someone）")
        if email == user["email"]:
            raise HTTPException(400, "唔可以加自己做朋友")
        with db.connect() as conn:
            target = conn.execute("SELECT * FROM users WHERE email = ?",
                                  (email,)).fetchone()
        if not target:
            raise HTTPException(404, "搵唔到呢個用戶")

    if target["id"] == user["id"]:
        raise HTTPException(400, "唔可以加自己做朋友")

    with db.connect() as conn:
        already = conn.execute(
            "SELECT 1 FROM friends WHERE user_id = ? AND friend_id = ?",
            (user["id"], target["id"])).fetchone()
        if already:
            return {"ok": True, "status": "already_friends",
                    "friend": _public_user(target)}

        # 對方已經發過請求？→ 即刻互相加
        reverse = conn.execute(
            """SELECT * FROM friend_requests
               WHERE from_id = ? AND to_id = ? AND status = 'pending'""",
            (target["id"], user["id"])).fetchone()
        if reverse:
            conn.execute(
                "UPDATE friend_requests SET status='accepted', updated_at=? WHERE id=?",
                (_iso(_now()), reverse["id"]))
            for a, b in ((user["id"], target["id"]), (target["id"], user["id"])):
                conn.execute("INSERT OR IGNORE INTO friends (user_id, friend_id) VALUES (?, ?)",
                             (a, b))
            return {"ok": True, "status": "accepted_mutual",
                    "friend": _public_user(target)}

        # 已經有待處理請求？
        existing = conn.execute(
            """SELECT * FROM friend_requests WHERE from_id = ? AND to_id = ?""",
            (user["id"], target["id"])).fetchone()
        if existing and existing["status"] == "pending":
            return {"ok": True, "status": "already_pending",
                    "request_id": existing["id"]}

        rid = _new_id("frq")
        conn.execute(
            """INSERT INTO friend_requests (id, from_id, to_id, status)
               VALUES (?, ?, ?, 'pending')
               ON CONFLICT(from_id, to_id) DO UPDATE SET
                 status='pending', updated_at=datetime('now')""",
            (rid, user["id"], target["id"]))

    return {"ok": True, "status": "pending", "request_id": rid,
            "to": _public_user(target)}


@app.post("/api/friends/requests/{request_id}/accept")
def accept_friend_request(request_id: str, user: dict = Depends(current_user)) -> dict:
    with db.connect() as conn:
        req = conn.execute("SELECT * FROM friend_requests WHERE id = ?",
                           (request_id,)).fetchone()
        if not req:
            raise HTTPException(404, "搵唔到請求")
        if req["to_id"] != user["id"]:
            raise HTTPException(403, "呢個請求唔係發俾你")
        if req["status"] != "pending":
            raise HTTPException(400, f"請求已經係 {req['status']}")

        conn.execute("UPDATE friend_requests SET status='accepted', updated_at=? WHERE id=?",
                     (_iso(_now()), request_id))
        # ⚠️ 雙向都要寫，否則兩邊朋友清單唔同步
        for a, b in ((req["from_id"], req["to_id"]), (req["to_id"], req["from_id"])):
            conn.execute("INSERT OR IGNORE INTO friends (user_id, friend_id) VALUES (?, ?)",
                         (a, b))
        other = conn.execute("SELECT * FROM users WHERE id = ?", (req["from_id"],)).fetchone()
    return {"ok": True, "friend": _public_user(other)}


@app.post("/api/friends/requests/{request_id}/reject")
def reject_friend_request(request_id: str, user: dict = Depends(current_user)) -> dict:
    with db.connect() as conn:
        req = conn.execute("SELECT * FROM friend_requests WHERE id = ?",
                           (request_id,)).fetchone()
        if not req:
            raise HTTPException(404, "搵唔到請求")
        if req["to_id"] != user["id"]:
            raise HTTPException(403, "呢個請求唔係發俾你")
        conn.execute("UPDATE friend_requests SET status='rejected', updated_at=? WHERE id=?",
                     (_iso(_now()), request_id))
    return {"ok": True}


@app.delete("/api/friends/{friend_id}")
def remove_friend(friend_id: str, user: dict = Depends(current_user)) -> dict:
    """刪除好友（雙向一齊刪）。"""
    with db.connect() as conn:
        conn.execute("DELETE FROM friends WHERE (user_id=? AND friend_id=?) OR (user_id=? AND friend_id=?)",
                     (user["id"], friend_id, friend_id, user["id"]))
        conn.execute("""UPDATE friend_requests SET status='rejected', updated_at=?
                        WHERE (from_id=? AND to_id=?) OR (from_id=? AND to_id=?)""",
                     (_iso(_now()), user["id"], friend_id, friend_id, user["id"]))
    return {"ok": True}


# ══════════════════════════════════════════════════════════════
# 行程邀請（都要 accept）
# ══════════════════════════════════════════════════════════════

@app.get("/api/invites")
def list_invites(user: dict = Depends(current_user)) -> dict:
    """我收到嘅行程邀請。"""
    with db.connect() as conn:
        rows = db.rows_to_list(conn.execute(
            """SELECT i.id AS invite_id, i.created_at, i.status,
                      t.id AS trip_id, t.name AS trip_name, t.destination,
                      t.start_date, t.end_date,
                      u.display_name AS from_name, u.email AS from_email
               FROM trip_invites i
               JOIN trips t ON t.id = i.trip_id
               JOIN users u ON u.id = i.from_id
               WHERE i.to_id = ? AND i.status = 'pending'
               ORDER BY i.created_at DESC""",
            (user["id"],),
        ).fetchall())
    return {"invites": rows}


@app.post("/api/trips/{trip_id}/invite")
def invite_to_trip(trip_id: str, body: MemberAdd, user: dict = Depends(current_user)) -> dict:
    """
    邀請朋友入 trip（**要對方 accept**）。
    ⚠️ 之前係直接 INSERT 入 members —— 咁樣對方會無聲無息多咗個 trip。
    """
    _require_member(trip_id, user["id"])
    email = body.email.strip().lower()
    with db.connect() as conn:
        target = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if not target:
            raise HTTPException(404, "搵唔到呢個用戶（要對方先登入過一次）")
        if conn.execute("SELECT 1 FROM members WHERE trip_id=? AND user_id=?",
                        (trip_id, target["id"])).fetchone():
            return {"ok": True, "status": "already_member"}
        iid = _new_id("inv")
        conn.execute(
            """INSERT INTO trip_invites (id, trip_id, from_id, to_id, status)
               VALUES (?, ?, ?, ?, 'pending')
               ON CONFLICT(trip_id, to_id) DO UPDATE SET
                 status='pending', from_id=excluded.from_id""",
            (iid, trip_id, user["id"], target["id"]))
        trip = conn.execute("SELECT name FROM trips WHERE id=?", (trip_id,)).fetchone()
    return {"ok": True, "status": "pending", "invite_id": iid,
            "to": _public_user(target), "trip_name": trip["name"]}


@app.post("/api/invites/{invite_id}/accept")
def accept_invite(invite_id: str, user: dict = Depends(current_user)) -> dict:
    with db.connect() as conn:
        inv = conn.execute("SELECT * FROM trip_invites WHERE id = ?",
                           (invite_id,)).fetchone()
        if not inv:
            raise HTTPException(404, "搵唔到邀請")
        if inv["to_id"] != user["id"]:
            raise HTTPException(403, "呢個邀請唔係發俾你")
        conn.execute("UPDATE trip_invites SET status='accepted' WHERE id=?", (invite_id,))
        conn.execute("INSERT OR IGNORE INTO members (trip_id, user_id, role) VALUES (?, ?, 'member')",
                     (inv["trip_id"], user["id"]))
        trip = conn.execute("SELECT * FROM trips WHERE id=?", (inv["trip_id"],)).fetchone()
    return {"ok": True, "trip": dict(trip)}


@app.post("/api/invites/{invite_id}/reject")
def reject_invite(invite_id: str, user: dict = Depends(current_user)) -> dict:
    with db.connect() as conn:
        inv = conn.execute("SELECT * FROM trip_invites WHERE id = ?",
                           (invite_id,)).fetchone()
        if not inv:
            raise HTTPException(404, "搵唔到邀請")
        if inv["to_id"] != user["id"]:
            raise HTTPException(403, "呢個邀請唔係發俾你")
        conn.execute("UPDATE trip_invites SET status='rejected' WHERE id=?", (invite_id,))
    return {"ok": True}


# ══════════════════════════════════════════════════════════════
# 健康檢查 + 前端 static# ══════════════════════════════════════════════════════════════════
# 開發版後台（Admin Dashboard）
# ══════════════════════════════════════════════════════════════════
#
# ⚠️⚠️ 用戶要求：
#   「我見其實而家整到都差唔多嘅話，其實我覺得另外仲要整一個
#    叫做開發版，係放我自己睇啲人用呢個 App 嘅數據。」
#
# ⚠️ 權限：兩種方法（任何一個中就得）
#   ① `WANDER_ADMIN_EMAILS`（逗號分隔）—— 唔使入 DB，最簡單
#   ② `users.is_admin = 1` —— 方便臨時開／收權限
#
#   ⚠️ 預設**冇人**係 admin —— 唔可以有一個「永遠係 admin」嘅
#      後門帳號（例如 admin@wander.app），因為咁樣一旦個 app
#      公開就即刻有人撞。
#
# ⚠️ 事件記錄：只有**明確叫** `POST /api/events` 先記。
#    唔會自動 log 所有 request —— 咁樣會爆 DB 而且侵犯私隱。

def signup_mode() -> str:
    """
    而家嘅註冊模式：
      · `open`   —— 任何人都可以註冊（⚠️ 公開上網有風險）
      · `invite` —— 要邀請碼（**推薦**，唔使 SMTP）
      · `email`  —— 要 email 驗證碼（要設定 SMTP）

    ⚠️ 預設：有 SMTP 就 `email`，冇就 `invite` ——
       因為冇 SMTP 就寄唔到驗證碼，`email` 模式會令所有人都註冊唔到。
    """
    v = (os.environ.get("WANDER_SIGNUP_MODE") or "").strip().lower()
    if v in ("open", "invite", "email"):
        return v
    from .mailer import mail_status
    return "email" if mail_status().get("mode") != "console" else "invite"


def _admin_emails() -> set:
    """
    讀 `WANDER_ADMIN_EMAILS`（逗號分隔）。

    ⚠️ 用**函數**而唔係 module 常數 ——
       module 常數喺 import 一刻就定死，之後改 env 或者
       遲咗載入 `.env` 都唔會生效（我哋中過呢個 bug）。
    """
    return {
        e.strip().lower()
        for e in (os.environ.get("WANDER_ADMIN_EMAILS") or "").split(",")
        if e.strip()
    }


def _is_admin(user: dict) -> bool:
    """係唔係管理員（env allowlist 或者 DB 旗標）。"""
    email = (user.get("email") or "").strip().lower()
    if email and email in _admin_emails():
        return True
    return bool(user.get("is_admin"))


def admin_user(user: dict = Depends(current_user)) -> dict:
    """FastAPI dependency：唔係 admin 就 403。"""
    if not _is_admin(user):
        # ⚠️ 403 而唔係 404 —— 404 會令 admin 以為「route 打錯」。
        #    但都唔可以回 401（前端會當 session 過期踢你出嚟）。
        raise HTTPException(403, "冇後台權限")
    return user


def _track(conn, user_id: str | None, kind: str, target: str | None = None) -> None:
    """記一個使用事件。"""
    try:
        conn.execute(
            "INSERT INTO events (user_id, kind, target, created_at) VALUES (?,?,?,?)",
            (user_id, kind[:40], (target or None) and str(target)[:60], _iso(_now())),
        )
    except Exception:
        pass          # ⚠️ 記錄失敗唔可以影響主流程


# ══════════════════════════════════════════════════════════════════
# 註冊模式 + 邀請碼
# ══════════════════════════════════════════════════════════════════
#
# ⚠️⚠️ 用戶問：「未設定 SMTP 你係諗住點搞？」
#
#   誠實答：**冇 SMTP 就寄唔到驗證碼**。所以有三條路：
#
#     ① 設定 SMTP（Gmail App Password / Resend）
#        → 見 docs/smtp/README.md，5 分鐘搞完，免費
#
#     ② **邀請碼**（推薦，尤其係朋友之間用）
#        → 你親手畀條碼朋友，佢用條碼註冊
#        → 完全唔使 email、冇成本、冇 spam 風險
#
#     ③ 公開註冊（`open`）
#        → ⚠️ 任何人都可以註冊，只適合純內網

class InviteGen(BaseModel):
    count: int = 1
    note: Optional[str] = None
    days: int = 30


@app.get("/api/auth/signup-mode")
def get_signup_mode() -> dict:
    """
    前端問「註冊要咩」。

    ⚠️ 呢個係**公開** endpoint（未登入都用得）——
       因為註冊畫面要知要唔要顯示邀請碼欄。
       但唔可以洩漏任何敏感嘢：只回模式 + 有冇 SMTP。
    """
    from .mailer import mail_status
    st = mail_status()
    return {
        "mode": signup_mode(),
        "mail_configured": st.get("mode") != "console",
        "need_invite": signup_mode() == "invite",
    }


class InviteCheck(BaseModel):
    code: str


@app.post("/api/auth/check-invite")
def check_invite(body: InviteCheck) -> dict:
    """
    檢查邀請碼係唔係有效（**公開** endpoint）。

    ⚠️⚠️ 用戶要求：
       「你真係要搞邀請碼個位，應該係一欄 —— 寫邀請碼嗰欄
        應該係冇咁闊，然後旁邊落返一個掣叫做『驗證』。」

    ⚠️ 為咩要「先驗證」而唔係註冊時一次過檢查：
       · 用戶打錯一個字，要填晒 email + 密碼 + 確認密碼
         先知道錯 → 好蝕
       · 分開之後，驗證成功就即刻顯示「✓ 可以繼續註冊」，
         用戶有信心填落去

    ⚠️ 安全性：呢個 endpoint 可以被 brute force 撞邀請碼。
       6 位 A-Z0-9 = 36^6 ≈ 21.8 億個組合 —— 實際撞唔到。
       但**唔可以**回傳任何關於「邊個產生」嘅資料。
    """
    code = (body.code or "").strip().upper()
    if not code:
        return {"valid": False, "reason": "請輸入邀請碼"}
    if not re.fullmatch(r"[A-Z0-9]{4,12}", code):
        return {"valid": False, "reason": "邀請碼格式唔啱"}

    with db.connect() as conn:
        inv = conn.execute(
            "SELECT * FROM signup_invites WHERE code=?", (code,)).fetchone()
    if not inv:
        return {"valid": False, "reason": "冇呢個邀請碼"}
    if inv["used_by"]:
        return {"valid": False, "reason": "呢個邀請碼已經用咗"}
    if inv["expires_at"] and _iso(_now()) > inv["expires_at"]:
        return {"valid": False, "reason": "呢個邀請碼已經過期"}
    # ⚠️ 只回「有效」+ 備註（備註係用戶自己打嘅，例如「阿明」）
    return {
        "valid": True,
        "note": inv["note"] or "",
        "expires_at": inv["expires_at"],
    }


@app.get("/api/admin/signup-invites")
def list_signup_invites(user: dict = Depends(admin_user)) -> dict:
    """列出所有註冊邀請碼（admin）。"""
    with db.connect() as conn:
        rows = conn.execute(
            """SELECT * FROM signup_invites ORDER BY created_at DESC LIMIT 200"""
        ).fetchall()
    now = _iso(_now())
    out = []
    for r in rows:
        state = ("used" if r["used_by"]
                 else "expired" if (r["expires_at"] and now > r["expires_at"])
                 else "ok")
        out.append({
            "code": r["code"], "note": r["note"], "state": state,
            "created_at": r["created_at"], "expires_at": r["expires_at"],
            "used_at": r["used_at"],
        })
    return {"invites": out, "mode": signup_mode(),
            "available": sum(1 for x in out if x["state"] == "ok")}


@app.post("/api/admin/signup-invites")
def make_signup_invites(body: InviteGen,
                        user: dict = Depends(admin_user)) -> dict:
    """
    產生註冊邀請碼（admin）。

    ⚠️ 碼用 `_invite_code()`（撇除易混淆字元）——
       用戶要**手打**呢條碼（例如喺電話度打），
       所以唔可以有 O/0、I/1/l 呢類睇錯嘅字。
    """
    n = max(1, min(50, int(body.count or 1)))
    days = max(1, min(365, int(body.days or 30)))
    exp = _iso(_now() + timedelta(days=days))
    codes = []
    with db.connect() as conn:
        for _ in range(n):
            for _try in range(8):
                c = _invite_code()
                try:
                    conn.execute(
                        """INSERT INTO signup_invites
                             (code, created_by, note, created_at, expires_at)
                           VALUES (?,?,?,?,?)""",
                        (c, user["id"], (body.note or "")[:60], _iso(_now()), exp))
                    codes.append(c)
                    break
                except Exception:
                    continue
    return {"codes": codes, "expires_at": exp}


# ══════════════════════════════════════════════════════════════
# ⚠️⚠️ 注意：呢個檔案有 SPA catch-all `@app.get("/{full_path:path}")`
#    喺最尾。FastAPI 係**按定義次序**配對 route ——
#    任何新嘅 API route **一定要定義喺 catch-all 之前**，
#    否則會被 catch-all 食咗，回 404 "Not found"。
#
#    ⚠️ 我加後台 API 嗰陣就中咗：`/api/admin/me` 回 404，
#       因為寫咗喺 catch-all 之後。
#       （catch-all 只擋 `api/` 開頭 → raise 404，所以睇落似
#        「route 唔存在」而唔似「次序錯」，好難察覺。）
# ══════════════════════════════════════════════════════════════


class TrackBody(BaseModel):
    kind: str
    target: Optional[str] = None


@app.post("/api/events")
def track_event(body: TrackBody, user: dict = Depends(current_user)) -> dict:
    """
    前端回報一個使用事件（app 開啟、建立旅程…）。

    ⚠️ 只記類型 + 目標，**唔記內容** ——
       我哋要「用咗幾多次」，唔要「睇咗咩」。
    """
    kind = (body.kind or "").strip()
    if not kind:
        return {"ok": False}
    with db.connect() as conn:
        _track(conn, user["id"], kind, body.target)
    return {"ok": True}


class TestMailBody(BaseModel):
    to: Optional[str] = None


@app.get("/api/admin/mail")
def admin_mail(user: dict = Depends(admin_user)) -> dict:
    """睇寄信設定狀態（admin）。"""
    from .mailer import mail_status
    return mail_status()


@app.post("/api/admin/test-mail")
def admin_test_mail(body: TestMailBody,
                    user: dict = Depends(admin_user)) -> dict:
    """
    寄一封測試信（admin）。

    ⚠️⚠️ 為咩要呢個：
       設定 SMTP 之後最怕「以為設定好但其實寄唔到」。
       撳一下就即刻知 —— 唔使等真有新用戶註冊先發現。
    """
    to = (body.to or user.get("email") or "").strip()
    if "@" not in to:
        raise HTTPException(400, "冇有效嘅 email")
    from .mailer import send_test_email
    r = send_test_email(to)
    # ⚠️ 唔 raise —— 要回傳失敗原因畀前端顯示
    return {"to": to, **r}


@app.get("/api/currencies")
def list_currencies() -> dict:
    """
    揀貨幣用嘅清單。

    ⚠️ 回**常用**（排前面）+ **全部**（API 有嘅）。
       唔可以淨係回常用 —— 去埃及、摩洛哥都要用到其他幣。
    """
    from wander import currency as cur
    r = cur.get_rates("HKD", max_age=cur.TTL_SECONDS * 24)
    rates = r.get("rates") or {}
    common = [{"code": c, "label": cur.label(c), "symbol": cur.symbol(c)}
              for c, _, _ in cur.COMMON]
    allc = sorted(
        [{"code": c, "label": cur.label(c), "symbol": cur.symbol(c)}
         for c in rates.keys()],
        key=lambda x: x["code"])
    return {"common": common, "all": allc, "stale": bool(r.get("stale"))}


@app.get("/api/rates")
def get_rates(base: str = "HKD") -> dict:
    """
    匯率（⚠️ 有快取，唔係每次查 API）。

    ⚠️⚠️ 用戶問：「呢個可唔可以實時整㗎？」
       → 唔係「每次 request 查一次」，係**快取 6 個鐘**。
         為咩：匯率一日只變幾次；狂查會被免費 API 封；
         而且飛機／地鐵冇網嗰陣一定要有最後一次嘅 rate。

    ⚠️ `stale: true` = 個 rate 過期但 API 攞唔到 → 用舊嘅頂住。
       前端應該顯示「匯率可能舊咗」而唔係當佢準。
    """
    from wander import currency as cur
    r = cur.get_rates(base)
    return {
        "base": r.get("base"),
        "rates": r.get("rates") or {},
        "at": r.get("at"),
        "age_seconds": r.get("age"),
        "stale": bool(r.get("stale")),
        "source": r.get("source"),
        "ttl_hours": cur.TTL_SECONDS // 3600,
    }


@app.get("/api/convert")
def api_convert(amount: float, from_: str = Query("HKD", alias="from"),
                to: str = "HKD") -> dict:
    """換錢（單次）。⚠️ 前端通常用 `/api/rates` 自己計，唔使逐個查。"""
    from wander import currency as cur
    v = cur.convert(amount, from_, to)
    return {"amount": amount, "from": (from_ or "").upper(),
            "to": (to or "").upper(), "result": v,
            "ok": v is not None}


@app.get("/api/admin/me")
def admin_me(user: dict = Depends(current_user)) -> dict:
    """前端問「我係唔係 admin」→ 決定要唔要顯示後台入口。"""
    return {"admin": _is_admin(user)}


# ══════════════════════════════════════════════════════════════
# 後台：數據管理（用戶要求「我想有個後台去管理數據」）
# ══════════════════════════════════════════════════════════════

@app.get("/api/admin/active-users")
def admin_active_users(days: int = 30, limit: int = 40,
                       user: dict = Depends(admin_user)) -> dict:
    """
    「邊個用戶用緊」—— 活躍用戶清單。
    ⚠️⚠️ 用戶要求：
       「我淨係想整嘅係有幾多數據？有啲咩用戶用緊咁樣我哋嘅 Dashboard。」

    ⚠️ 按**最後活動時間**排序（唔係註冊時間）——
       咁先睇到「邊個真係用緊」而唔係「邊個註冊過」。

    ⚠️ 回：
       · last_seen  —— 最後活動時間
       · events     —— 期內事件數
       · sessions   —— 仲有效嘅 session 數（≈ 幾部裝置）
       · 用戶自己做咗幾多嘢（旅程／景點／購物）
    """
    limit = max(1, min(200, limit))
    since = _iso(_now() - timedelta(days=max(1, min(365, days))))
    with db.connect() as conn:
        rows = conn.execute("""
            SELECT u.id, u.email, u.username, u.display_name, u.avatar,
                   u.is_admin, u.onboarded, u.created_at,
                   (SELECT MAX(created_at) FROM events e WHERE e.user_id = u.id) AS last_seen,
                   (SELECT COUNT(*) FROM events e
                     WHERE e.user_id = u.id AND e.created_at >= ?) AS events,
                   (SELECT COUNT(*) FROM sessions s
                     WHERE s.user_id = u.id
                       AND (s.expires_at IS NULL OR s.expires_at > ?)) AS sessions,
                   (SELECT COUNT(*) FROM members m WHERE m.user_id = u.id) AS trips,
                   (SELECT COUNT(*) FROM items i WHERE i.created_by = u.id) AS items_made,
                   (SELECT COUNT(*) FROM shopping_items sh
                     WHERE sh.created_by = u.id) AS shopping_made,
                   (SELECT COUNT(*) FROM expenses ex
                     WHERE ex.created_by = u.id) AS expenses_made
            FROM users u
            ORDER BY last_seen DESC NULLS LAST, u.created_at DESC
            LIMIT ?""", (since, _iso(_now()), limit)).fetchall()

        # ⚠️ 「有幾多數據」—— 一眼睇晒
        def n(sql, *a):
            try:
                return conn.execute(sql, a).fetchone()[0]
            except Exception:
                return 0

        counts = {
            "users": n("SELECT COUNT(*) FROM users"),
            "users_active": n("SELECT COUNT(DISTINCT user_id) FROM events "
                              "WHERE created_at >= ?", since),
            "sessions_live": n("SELECT COUNT(*) FROM sessions "
                               "WHERE expires_at IS NULL OR expires_at > ?",
                               _iso(_now())),
            "trips": n("SELECT COUNT(*) FROM trips"),
            "stops": n("SELECT COUNT(*) FROM trip_stops"),
            "items": n("SELECT COUNT(*) FROM items"),
            "shopping": n("SELECT COUNT(*) FROM shopping_items"),
            "expenses": n("SELECT COUNT(*) FROM expenses"),
            "friends": n("SELECT COUNT(*) FROM friends"),
            "events": n("SELECT COUNT(*) FROM events"),
            "events_period": n("SELECT COUNT(*) FROM events WHERE created_at >= ?",
                               since),
        }
        # ⚠️ 幾多 % 嘅數據有真內容
        counts["empty_trips"] = n(
            """SELECT COUNT(*) FROM trips t
               WHERE NOT EXISTS (SELECT 1 FROM items i WHERE i.trip_id = t.id)""")

    return {"days": days, "counts": counts,
            "users": db.rows_to_list(rows)}


@app.get("/api/admin/users")
def admin_users(q: str = "", limit: int = 50, offset: int = 0,
                user: dict = Depends(admin_user)) -> dict:
    """
    用戶清單（可以搜尋）。

    ⚠️ 只回**必要**欄位 —— 唔好將 `password_hash` 之類嘅嘢送出街。
    """
    limit = max(1, min(200, limit))
    with db.connect() as conn:
        where, vals = "", []
        if (q or "").strip():
            where = "WHERE u.email LIKE ? OR u.username LIKE ? OR u.display_name LIKE ?"
            like = f"%{q.strip()}%"
            vals = [like, like, like]
        total = conn.execute(
            f"SELECT COUNT(*) c FROM users u {where}", vals).fetchone()["c"]
        rows = conn.execute(f"""
            SELECT u.id, u.email, u.username, u.display_name, u.avatar,
                   u.is_admin, u.onboarded, u.created_at,
                   (SELECT COUNT(*) FROM trips t WHERE t.owner_id = u.id) AS owned,
                   (SELECT COUNT(*) FROM members m WHERE m.user_id = u.id) AS member_of,
                   (SELECT COUNT(*) FROM items i WHERE i.created_by = u.id) AS items_made
            FROM users u {where}
            ORDER BY u.created_at DESC LIMIT ? OFFSET ?""",
            (*vals, limit, offset)).fetchall()
    return {"total": total, "limit": limit, "offset": offset,
            "users": db.rows_to_list(rows)}


@app.get("/api/admin/trips")
def admin_trips(q: str = "", limit: int = 50, offset: int = 0,
                user: dict = Depends(admin_user)) -> dict:
    """旅程清單（可以搜尋）。"""
    limit = max(1, min(200, limit))
    with db.connect() as conn:
        where, vals = "", []
        if (q or "").strip():
            where = "WHERE t.name LIKE ? OR t.destination LIKE ?"
            like = f"%{q.strip()}%"
            vals = [like, like]
        total = conn.execute(
            f"SELECT COUNT(*) c FROM trips t {where}", vals).fetchone()["c"]
        rows = conn.execute(f"""
            SELECT t.id, t.name, t.destination, t.days, t.currency,
                   t.start_date, t.created_at, t.invite_code,
                   u.email AS owner_email,
                   (SELECT COUNT(*) FROM members m WHERE m.trip_id = t.id) AS members,
                   (SELECT COUNT(*) FROM items i WHERE i.trip_id = t.id) AS items,
                   (SELECT COUNT(*) FROM shopping_items s WHERE s.trip_id = t.id) AS shopping,
                   (SELECT COUNT(*) FROM expenses e WHERE e.trip_id = t.id) AS expenses
            FROM trips t LEFT JOIN users u ON u.id = t.owner_id
            {where}
            ORDER BY t.created_at DESC LIMIT ? OFFSET ?""",
            (*vals, limit, offset)).fetchall()
    return {"total": total, "limit": limit, "offset": offset,
            "trips": db.rows_to_list(rows)}


@app.get("/api/admin/export")
def admin_export(what: str = "summary", user: dict = Depends(admin_user)) -> dict:
    """
    匯出數據（JSON）。

    ⚠️⚠️ **唔會**匯出 `password_hash` —— 就算係 admin 都唔應該見到。
    """
    with db.connect() as conn:
        if what == "users":
            rows = conn.execute(
                """SELECT id, email, username, display_name, avatar, is_admin,
                          onboarded, created_at FROM users
                   ORDER BY created_at""").fetchall()
            return {"what": "users", "count": len(rows),
                    "rows": db.rows_to_list(rows)}
        if what == "trips":
            rows = conn.execute(
                """SELECT id, name, destination, days, currency, start_date,
                          end_date, owner_id, created_at FROM trips
                   ORDER BY created_at""").fetchall()
            return {"what": "trips", "count": len(rows),
                    "rows": db.rows_to_list(rows)}
        if what == "items":
            rows = conn.execute(
                """SELECT id, trip_id, name, category, country, district,
                          lat, lng, confidence, day_index, created_at
                   FROM items ORDER BY created_at""").fetchall()
            return {"what": "items", "count": len(rows),
                    "rows": db.rows_to_list(rows)}
    # summary
    with db.connect() as conn:
        def n(sql):
            try:
                return conn.execute(sql).fetchone()[0]
            except Exception:
                return 0
        return {"what": "summary", "counts": {
            "users": n("SELECT COUNT(*) FROM users"),
            "trips": n("SELECT COUNT(*) FROM trips"),
            "items": n("SELECT COUNT(*) FROM items"),
            "shopping": n("SELECT COUNT(*) FROM shopping_items"),
            "expenses": n("SELECT COUNT(*) FROM expenses"),
            "events": n("SELECT COUNT(*) FROM events"),
            "friends": n("SELECT COUNT(*) FROM friends"),
        }}


@app.get("/api/admin/overview")
def admin_overview(days: int = 30, user: dict = Depends(admin_user)) -> dict:
    """
    後台總覽。

    ⚠️ 全部係**聚合數字**，唔會回傳個別用戶嘅內容
       （除咗最近活動嘅 email 前綴，方便 debug）。
    """
    from datetime import timedelta as _td
    now = _now()
    days = max(1, min(365, int(days or 30)))
    since = _iso(now - _td(days=days))
    d1 = _iso(now - _td(days=1))
    d7 = _iso(now - _td(days=7))

    with db.connect() as conn:
        q = lambda sql, *a: conn.execute(sql, a).fetchone()[0]  # noqa: E731

        # ── 用戶 ──
        users = {
            "total": q("SELECT COUNT(*) FROM users"),
            "new_7d": q("SELECT COUNT(*) FROM users WHERE created_at >= ?", d7),
            "new_period": q("SELECT COUNT(*) FROM users WHERE created_at >= ?", since),
            "onboarded": q("SELECT COUNT(*) FROM users WHERE onboarded = 1"),
            "with_password": q(
                "SELECT COUNT(*) FROM users WHERE password_hash IS NOT NULL"),
            "with_username": q(
                "SELECT COUNT(*) FROM users WHERE username IS NOT NULL"),
        }
        # ── 活躍（用 events 表；冇事件就 fallback 去 sessions）──
        active = {
            "dau": q("SELECT COUNT(DISTINCT user_id) FROM events WHERE created_at >= ?", d1),
            "wau": q("SELECT COUNT(DISTINCT user_id) FROM events WHERE created_at >= ?", d7),
            "period": q("SELECT COUNT(DISTINCT user_id) FROM events WHERE created_at >= ?", since),
            "sessions_live": q("SELECT COUNT(*) FROM sessions WHERE expires_at > ?",
                               _iso(now)),
        }
        # ── 內容 ──
        content = {
            "trips": q("SELECT COUNT(*) FROM trips"),
            "trips_period": q("SELECT COUNT(*) FROM trips WHERE created_at >= ?", since),
            "stops": q("SELECT COUNT(*) FROM trip_stops"),
            "items": q("SELECT COUNT(*) FROM items"),
            "expenses": q("SELECT COUNT(*) FROM expenses"),
            "shopping": q("SELECT COUNT(*) FROM shopping_items"),
        }
        # ── 事件：總數 + 按類型 ──
        events = {
            "total": q("SELECT COUNT(*) FROM events"),
            "period": q("SELECT COUNT(*) FROM events WHERE created_at >= ?", since),
            "by_kind": [
                {"kind": r[0], "n": r[1]}
                for r in conn.execute(
                    """SELECT kind, COUNT(*) n FROM events
                       WHERE created_at >= ? GROUP BY kind
                       ORDER BY n DESC LIMIT 20""", (since,))
            ],
            "by_day": [
                {"d": r[0], "n": r[1]}
                for r in conn.execute(
                    """SELECT substr(created_at,1,10) d, COUNT(*) n FROM events
                       WHERE created_at >= ? GROUP BY d ORDER BY d""", (since,))
            ],
        }
        # ── 每日新用戶（走勢）──
        signups = [
            {"d": r[0], "n": r[1]}
            for r in conn.execute(
                """SELECT substr(created_at,1,10) d, COUNT(*) n FROM users
                   WHERE created_at >= ? GROUP BY d ORDER BY d""", (since,))
        ]
        # ── 最近活動（只顯示 email 前綴，唔顯示全個）──
        recent = [
            {"kind": r[0], "target": r[1], "at": r[2],
             "who": (r[3] or "—")[:3] + "…"}
            for r in conn.execute(
                """SELECT e.kind, e.target, e.created_at, u.email
                   FROM events e LEFT JOIN users u ON u.id = e.user_id
                   ORDER BY e.id DESC LIMIT 40""")
        ]
        # ── 旅程規模分佈 ──
        distrib = {
            "avg_days": round(q("SELECT AVG(days) FROM trips") or 0, 1),
            "avg_stops": round(
                q("""SELECT AVG(c) FROM (SELECT COUNT(*) c FROM trip_stops
                                       GROUP BY trip_id)""") or 0, 1),
            "avg_items": round(
                q("""SELECT AVG(c) FROM (SELECT COUNT(*) c FROM items
                                       GROUP BY trip_id)""") or 0, 1),
            "multi_city": q(
                """SELECT COUNT(*) FROM (SELECT trip_id FROM trip_stops
                                        GROUP BY trip_id HAVING COUNT(*) > 1)"""),
            "empty_trips": q(
                """SELECT COUNT(*) FROM trips t WHERE NOT EXISTS
                   (SELECT 1 FROM items i WHERE i.trip_id = t.id)"""),
        }

    return {
        "generated_at": _iso(now), "days": days,
        "users": users, "active": active, "content": content,
        "events": events, "signups": signups, "recent": recent,
        "distrib": distrib,
    }



# ══════════════════════════════════════════════════════════════

@app.get("/api/health")
def health() -> dict:
    from wander import __version__
    from .mailer import mail_status
    return {
        "ok": True,
        "engine": __version__,
        "mail": mail_status(),
        "ig_provider": _ig_status(),
    }


# 上傳嘅圖片
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

WEB_DIST = ROOT / "web" / "dist"
if WEB_DIST.exists():
    app.mount("/assets", StaticFiles(directory=WEB_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}")
    def spa(full_path: str):
        """
        SPA fallback：**路由**交俾 index.html，但**資源**唔可以。

        ⚠️⚠️ 為咩要分開：
           SPA fallback 原本係「所有搵唔到嘅路徑都回 index.html」——
           咁樣 `/mascot-hello.png`（未放）都會回 **HTML**，
           瀏覽器會當佢係圖片咁 decode → 失敗 → 觸發 `onError`。

           雖然 `onError` 最後都會 fallback 成功，但：
             · 白白下載一份 index.html（幾 KB）
             · 狀態碼係 **200** 而唔係 404 → 診斷困難
             · 瀏覽器 console 會出「HTML 當圖片」嘅警告

           ✅ 正確做法：**有副檔名**嘅路徑搵唔到就回 404。
              （SPA 嘅路由唔會有 `.png` / `.js` 呢類副檔名。）
        """
        if full_path.startswith("api/"):
            raise HTTPException(404, "Not found")
        candidate = WEB_DIST / full_path
        # ⚠️ 有副檔名 = 資源 → 搵唔到就 404，唔可以 fallback 去 HTML
        if not (full_path and candidate.is_file()):
            # ⚠️ 用 {2,12} 而唔係 {2,5} —— `manifest.webmanifest` 嘅副檔名有 11 個字，
            #    {2,5} 會漏咗佢（實測捉到）。
            if re.search(r"\.[a-z0-9]{2,12}$", full_path, re.I):
                raise HTTPException(404, "Not found")
        if full_path and candidate.is_file():
            headers = {}
            # ⚠️ service worker 同 manifest **一定唔可以** 被 HTTP 快取住，
            #    否則用戶永遠拎到舊 SW，更新唔到。
            if full_path in ("sw.js", "manifest.webmanifest"):
                headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            return FileResponse(candidate, headers=headers)
        # index.html 都唔應該長快取（要拎到最新 asset hash）
        return FileResponse(WEB_DIST / "index.html",
                            headers={"Cache-Control": "no-cache"})

