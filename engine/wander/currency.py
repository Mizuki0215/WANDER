"""
匯率
======
⚠️ 用戶要求：
   「有時你去旅行如果唔係都係用港幣㗎嘛，所以你要 mark 低返嗰個
    嘅價錢係有得揀嗰個 Yen or KRW or EUR、HKD 定係點樣？
    另外講起錢呢樣嘢…就係根據匯率去轉返嗰個你想要嘅錢，
    呢個可唔可以實時整㗎？」

⚠️⚠️ 設計決定：

  ① **兩個免費 API fallback**（唔使 API key）
     · 主：`cdn.jsdelivr.net`（fawazahmed0，340 個幣，CDN 快）
     · 備：`open.er-api.com`（166 個幣）
     ⚠️ 實測兩個都 HTTP 200。冇 key = 冇成本、冇註冊。

  ② **快取 6 個鐘**（唔係「實時」查）
     ⚠️ 為咩唔真係實時：
        · 匯率一日只變幾次，每個 request 查一次係浪費
        · 免費 API 有 rate limit → 狂查會被封
        · 飛機上／地鐵冇網 → 一定要有**最後一次成功**嘅 rate
     ✅ 6 個鐘係平衡：值日內夠新，又唔會狂查。

  ③ **永遠唔可以 raise**
     ⚠️ 匯率攞唔到**唔應該**令「睇購物清單」失敗 ——
        回最後快取（就算過期），再唔得就回 `None`，
        前端顯示「匯率未更新」而唔係爆。
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Optional

_HERE = Path(__file__).resolve().parent
CACHE_FILE = _HERE / "data" / "rates.json"

# ⚠️ 6 個鐘。太短 = 狂查 API；太長 = 值日唔準。
TTL_SECONDS = 6 * 60 * 60

# ⚠️ 兩個來源（次序 = 優先）。兩個都係免費、冇 key。
SOURCES = [
    ("jsdelivr",
     "https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1/currencies/{base}.json",
     "lower"),
    ("er-api",
     "https://open.er-api.com/v6/latest/{base}",
     "upper"),
]

# ⚠️ 常用幣（前端揀嘅時候排前面）。
#    唔係「支援嘅幣」—— 支援嘅係 API 回嘅全部（340 個）。
COMMON = [
    ("HKD", "🇭🇰", "港幣"),
    ("JPY", "🇯🇵", "日圓"),
    ("KRW", "🇰🇷", "韓圜"),
    ("TWD", "🇹🇼", "台幣"),
    ("CNY", "🇨🇳", "人民幣"),
    ("THB", "🇹🇭", "泰銖"),
    ("SGD", "🇸🇬", "新加坡元"),
    ("MYR", "🇲🇾", "馬幣"),
    ("VND", "🇻🇳", "越南盾"),
    ("PHP", "🇵🇭", "披索"),
    ("IDR", "🇮🇩", "印尼盾"),
    ("INR", "🇮🇳", "盧比"),
    ("USD", "🇺🇸", "美金"),
    ("EUR", "🇪🇺", "歐元"),
    ("GBP", "🇬🇧", "英鎊"),
    ("AUD", "🇦🇺", "澳元"),
    ("CAD", "🇨🇦", "加元"),
    ("CHF", "🇨🇭", "瑞士法郎"),
    ("NZD", "🇳🇿", "紐西蘭元"),
    ("AED", "🇦🇪", "迪拉姆"),
]

_SYMBOLS = {
    "HKD": "HK$", "JPY": "¥", "KRW": "₩", "TWD": "NT$", "CNY": "CN¥",
    "USD": "$", "EUR": "€", "GBP": "£", "THB": "฿", "SGD": "S$",
    "MYR": "RM", "VND": "₫", "PHP": "₱", "IDR": "Rp", "INR": "₹",
    "AUD": "A$", "CAD": "C$", "CHF": "CHF", "NZD": "NZ$", "AED": "د.إ",
}

# ⚠️ Thread lock —— uvicorn 用 threadpool 跑 sync endpoint，
#    兩個 request 同時 refresh 會寫爛個 cache 檔。
_LOCK = threading.Lock()


def symbol(code: str) -> str:
    """貨幣符號（唔知就回個 code）。"""
    return _SYMBOLS.get((code or "").upper(), (code or "").upper())


def label(code: str) -> str:
    """「🇯🇵 JPY 日圓」—— 前端 dropdown 用。"""
    c = (code or "").upper()
    for k, flag, zh in COMMON:
        if k == c:
            return f"{flag} {k} {zh}"
    return c


def _read_cache() -> dict:
    try:
        if CACHE_FILE.exists():
            return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _write_cache(d: dict) -> None:
    try:
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        # ⚠️ 先寫 .tmp 再 rename —— 唔係嘅話中途死會留半個檔
        tmp = CACHE_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
        tmp.replace(CACHE_FILE)
    except Exception:
        pass


def _fetch(base: str) -> Optional[dict]:
    """
    由兩個免費 API 攞 rate。

    ⚠️ 永遠唔 raise —— 回 None 代表攞唔到。
    """
    import requests

    base = base.upper()
    for name, tpl, case in SOURCES:
        url = tpl.format(base=base.lower() if case == "lower" else base)
        try:
            r = requests.get(url, timeout=12,
                             headers={"User-Agent": "Wander/2.0"})
            if r.status_code != 200:
                continue

            d = r.json()
            # ⚠️ 兩個 API 嘅 shape 唔同：
            #    jsdelivr → {"date": "...", "hkd": {"jpy": 20.1, ...}}
            #    er-api   → {"result":"success", "rates": {"JPY": 20.1, ...}}
            raw = d.get(base.lower()) if case == "lower" else d.get("rates")
            if not isinstance(raw, dict) or not raw:
                continue

            rates = {}
            for k, v in raw.items():
                try:
                    f = float(v)
                    # ⚠️ 過濾垃圾（0 或者負數 → 除數會爆）
                    if f > 0:
                        rates[str(k).upper()] = f
                except (TypeError, ValueError):
                    continue

            if rates:
                rates[base] = 1.0          # ⚠️ 自己對自己一定係 1
                return {"base": base, "rates": rates,
                        "at": int(time.time()), "source": name}
        except Exception:
            continue
    return None


def get_rates(base: str = "HKD", *, max_age: int = TTL_SECONDS) -> dict:
    """
    攞 `base` 嘅匯率（**有快取**）。

    回：
        {"base","rates","at","age","stale","source"}

    ⚠️ `stale=True` = 個 rate 過期但 API 攞唔到 → 用**舊嘅**頂住。
       前端應該顯示「匯率可能舊咗」。
    """
    base = (base or "HKD").upper()

    with _LOCK:
        cache = _read_cache()
        hit = cache.get(base)
        now = int(time.time())

        if hit and (now - int(hit.get("at") or 0)) < max_age:
            return {**hit, "age": now - int(hit["at"]), "stale": False}

        fresh = _fetch(base)
        if fresh:
            cache[base] = fresh
            _write_cache(cache)
            return {**fresh, "age": 0, "stale": False}

        # ⚠️ 攞唔到 → 用舊嘅（就算過期）
        if hit:
            return {**hit, "age": now - int(hit.get("at") or 0), "stale": True}

    return {"base": base, "rates": {base: 1.0}, "at": 0,
            "age": 0, "stale": True, "source": None}


def convert(amount, frm: str, to: str, *, base: str = "HKD") -> Optional[float]:
    """
    換錢。

    ⚠️ 用**交叉匯率**（唔使每個 pair 都查一次）：
       amount × (rate[to] / rate[frm])   ← 兩個都以 `base` 為基準

    ⚠️ 攞唔到 rate → 回 None（**唔係**回原數 —— 咁樣會靜靜咁畀錯數）。
    """
    try:
        a = float(amount)
    except (TypeError, ValueError):
        return None

    frm = (frm or base).upper()
    to = (to or base).upper()
    if frm == to:
        return a

    r = get_rates(base)
    rates = r.get("rates") or {}
    rf, rt = rates.get(frm), rates.get(to)
    if not rf or not rt:
        return None
    return round(a * (rt / rf), 2)


def stats() -> dict:
    """俾 /api/status 同 selftest 用。"""
    cache = _read_cache()
    return {
        "cache_file": str(CACHE_FILE),
        "ttl_hours": TTL_SECONDS // 3600,
        "sources": [s[0] for s in SOURCES],
        "cached_bases": sorted(cache.keys()),
        "common": [c[0] for c in COMMON],
    }
