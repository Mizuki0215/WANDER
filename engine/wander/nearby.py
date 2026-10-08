"""
wander.nearby — 附近邊度買得到
===============================

用戶要求（原文）：
    「有冇啲 information 係有曬附近有咩店呢？
      shopping 有個 function typing 可以等有得圓吧店，
      佢會提你附近有幾會有得買」

即係：購物清單入面打「合利他命」→ App 話你知附近邊幾間藥妝店有得買。

⚠️ 為咩用 Overpass API：
   · 完全免費、免 API key
   · 資料係 OpenStreetMap（同我哋地圖用同一個來源，一致）
   · 支援「半徑搜尋」—— 呢個正正係「附近」嘅意思

⚠️ 為咩要先分類再搜尋：
   OSM 冇「合利他命」呢個 tag，但有 shop=chemist（藥妝店）。
   所以流程係：貨品名 → 判斷類別 → 搵該類別嘅店。
   另外都會試直接搵同名嘅店（例如「白色戀人」→ 可能有間專門店）。
"""
from __future__ import annotations

import math
import re
import time
from typing import Optional

import requests

from .ua import API_UA

OVERPASS = "https://overpass-api.de/api/interpreter"
_TIMEOUT = 25
_cache: dict[str, tuple[float, list]] = {}
_CACHE_TTL = 600          # 10 分鐘（OSM 資料唔會咁快變）


# ══════════════════════════════════════════════════════════════
# 貨品 → 店鋪類別
# ══════════════════════════════════════════════════════════════

# OSM tag 組合。key = 我哋嘅類別，value = [(tag_key, tag_value), ...]
CATEGORY_TAGS: dict[str, list[tuple[str, str]]] = {
    "drug": [
        ("shop", "chemist"), ("shop", "beauty"), ("amenity", "pharmacy"),
        ("shop", "medical_supply"), ("shop", "cosmetics"),
    ],
    "souvenir": [
        ("shop", "gift"), ("shop", "souvenir"), ("shop", "confectionery"),
        ("shop", "bakery"), ("shop", "pastry"), ("shop", "deli"),
    ],
    "food": [
        ("shop", "supermarket"), ("shop", "convenience"),
        ("shop", "grocery"), ("shop", "food"), ("shop", "greengrocer"),
    ],
    "cloth": [
        ("shop", "clothes"), ("shop", "fashion"), ("shop", "shoes"),
        ("shop", "boutique"), ("shop", "department_store"),
    ],
    "electronics": [
        ("shop", "electronics"), ("shop", "computer"), ("shop", "mobile_phone"),
        ("shop", "appliance"), ("shop", "camera"),
    ],
    "other": [
        ("shop", "department_store"), ("shop", "mall"),
        ("shop", "variety_store"), ("shop", "general"),
    ],
}

# 中文／日文／韓文關鍵字 → 類別
#   ⚠️ 次序有意義：越具體越前（「藥妝」要贏過「妝」）
KEYWORDS: list[tuple[str, str]] = [
    # 藥妝／藥品
    ("藥妝", "drug"), ("药妆", "drug"), ("藥局", "drug"), ("药局", "drug"),
    ("ドラッグ", "drug"), ("薬", "drug"), ("药", "drug"), ("藥品", "drug"),
    ("약국", "drug"), ("화장품", "drug"), ("化妝品", "drug"), ("化妆品", "drug"),
    ("合利他命", "drug"), ("休足", "drug"), ("撒隆巴斯", "drug"), ("曼秀雷敦", "drug"),
    ("面膜", "drug"), ("防曬", "drug"), ("防晒", "drug"), ("眼藥水", "drug"),
    ("維他命", "drug"), ("ビタミン", "drug"), ("영양제", "drug"),
    # 手信／食品
    ("手信", "souvenir"), ("伴手禮", "souvenir"), ("お土産", "souvenir"),
    ("土產", "souvenir"), ("菓子", "souvenir"), ("お菓子", "souvenir"),
    ("白色戀人", "souvenir"), ("Royce", "souvenir"), ("巧克力", "souvenir"),
    ("チョコ", "souvenir"), ("餅", "souvenir"), ("饼", "souvenir"),
    ("蛋糕", "souvenir"), ("ケーキ", "souvenir"), ("和菓子", "souvenir"),
    ("기념품", "souvenir"), ("선물", "souvenir"),
    ("食品", "food"), ("零食", "food"), ("おつまみ", "food"),
    ("泡麵", "food"), ("拉麵", "food"), ("ラーメン", "food"),
    ("味噌", "food"), ("醬油", "food"), ("茶葉", "food"), ("日本茶", "food"),
    ("超市", "food"), ("コンビニ", "food"), ("편의점", "food"),
    # 衣物
    ("衣服", "cloth"), ("衫", "cloth"), ("褲", "cloth"), ("裙", "cloth"),
    ("鞋", "cloth"), ("靴", "cloth"), ("外套", "cloth"), ("ユニクロ", "cloth"),
    ("Uniqlo", "cloth"), ("GU", "cloth"), ("옷", "cloth"),
    # 電器
    ("電器", "electronics"), ("电器", "electronics"), ("相機", "electronics"),
    ("相機", "electronics"), ("鏡頭", "electronics"), ("耳機", "electronics"),
    ("電飯煲", "electronics"), ("吹風機", "electronics"), ("ドライヤー", "electronics"),
    ("ヨドバシ", "electronics"), ("ビックカメラ", "electronics"),
    ("家電", "electronics"), ("電玩", "electronics"), ("가전", "electronics"),
]


# ══════════════════════════════════════════════════════════════
# 地區關鍵字（俾 Nominatim 用）
# ══════════════════════════════════════════════════════════════
#
# ⚠️⚠️ 為咩要分地區語言：
#    實測 Nominatim：
#      「ドラッグストア」（日文）→ 福岡搵到 20 間 ✅
#      「drugstore」（英文）    → 福岡搵到 0 間 ❌
#    OSM 嘅 name 同 amenity 都係當地語言，所以要用當地字。
REGION_KEYWORDS: dict[str, dict[str, list[str]]] = {
    "jp": {
        "drug": ["ドラッグストア", "薬局", "調剤薬局"],
        "souvenir": ["お土産", "銘品館", "菓子店"],
        "food": ["スーパー", "コンビニ", "食料品"],
        "cloth": ["衣料品", "ユニクロ", "洋服"],
        "electronics": ["家電量販店", "電気店", "カメラ店"],
        "other": ["デパート", "百貨店", "ショッピングモール"],
    },
    "kr": {
        # ⚠️ 「옷」（衫）呢類單字喺 Nominatim 搵唔到嘢 —— 要用店名／具體詞
        "drug": ["약국", "화장품", "올리브영"],
        "souvenir": ["기념품", "선물가게", "면세점"],
        "food": ["마트", "편의점", "식료품"],
        "cloth": ["유니클로", "의류매장", "옷가게"],
        "electronics": ["전자제품", "가전", "하이마트"],
        "other": ["백화점", "쇼핑몰"],
    },
    "tw": {
        "drug": ["藥妝", "藥局", "屈臣氏", "康是美"],
        "souvenir": ["伴手禮", "名產", "餅店"],
        "food": ["超市", "便利商店", "全聯"],
        "cloth": ["服飾", "衣服"],
        "electronics": ["電器", "3C", "燦坤"],
        "other": ["百貨公司", "購物中心"],
    },
    "hk": {
        "drug": ["藥房", "藥妝", "屈臣氏", "萬寧"],
        "souvenir": ["手信", "餅家", "禮品"],
        "food": ["超市", "便利店", "惠康", "百佳"],
        "cloth": ["服裝", "時裝"],
        "electronics": ["電器", "豐澤", "百老匯"],
        "other": ["百貨公司", "商場"],
    },
    "en": {
        "drug": ["pharmacy", "drugstore", "cosmetics"],
        "souvenir": ["souvenir", "gift shop"],
        "food": ["supermarket", "convenience store"],
        "cloth": ["clothing", "fashion"],
        "electronics": ["electronics", "appliance store"],
        "other": ["department store", "shopping mall"],
    },
}


def region_of(lat: float, lng: float, country: str | None = None) -> str:
    """粗略判斷地區（用嚟揀關鍵字語言）。"""
    if country:
        c = country.strip()
        if c in ("日本", "Japan"): return "jp"
        if c in ("韓國", "Korea", "South Korea"): return "kr"
        if c in ("台灣", "Taiwan"): return "tw"
        if c in ("香港", "Hong Kong", "澳門", "Macau"): return "hk"
    # ⚠️⚠️ 用座標估嘅時候，**韓國一定要先過日本**。
    #    原因：福岡（33.59, 130.42）同釜山（35.18, 129.08）好近，
    #    兩個國家嘅 bounding box 重疊。
    #    如果日本先查（lng 128-146），釜山會被誤判成日本。
    #
    #    解法：韓國嘅 lng 上限收窄到 129.6（朝鮮海峽大約位置），
    #    咁福岡 130.42 就唔會落入韓國，而釜山 129.08 仍然係韓國。
    if 33 <= lat <= 39.5 and 124 <= lng <= 129.6: return "kr"    # ← 要先
    if 30 <= lat <= 46 and 128 <= lng <= 146: return "jp"
    if 21.5 <= lat <= 25.5 and 119 <= lng <= 122.5: return "tw"
    if 22.0 <= lat <= 22.6 and 113.8 <= lng <= 114.5: return "hk"
    return "en"


def bbox_around(lat: float, lng: float, km: float) -> str:
    """Nominatim 嘅 viewbox（left,top,right,bottom）。"""
    dlat = km / 111.0
    dlng = km / (111.0 * max(0.2, math.cos(math.radians(lat))))
    return f"{lng - dlng},{lat - dlat},{lng + dlng},{lat + dlat}"


def _nominatim(keyword: str, lat: float, lng: float, km: float,
               limit: int = 25) -> list[dict]:
    """
    Nominatim 搜尋（免費、免 key）。

    ⚠️ 用咗 bounded=1（限制喺 viewbox 內）+ viewbox ——
       冇嘅話會搵到成個國家嘅同名店。
    """
    try:
        r = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={
                "q": keyword, "format": "json", "limit": limit,
                "viewbox": bbox_around(lat, lng, km), "bounded": 1,
                "addressdetails": 0, "extratags": 1,
            },
            headers={"User-Agent": API_UA, "Accept": "application/json"},
            timeout=20)
        if r.status_code != 200:
            return []
        return r.json() or []
    except Exception:
        return []


def classify(title: str, category: str | None = None) -> str:
    """
    判斷一件貨品應該去邊類店買。

    先用關鍵字（最準），冇就信用戶揀嘅分類，最後 fallback "other"。
    """
    t = (title or "").lower()
    for kw, cat in KEYWORDS:
        if kw.lower() in t:
            return cat
    if category and category in CATEGORY_TAGS:
        return category
    return "other"


# ══════════════════════════════════════════════════════════════
# Overpass 查詢
# ══════════════════════════════════════════════════════════════

def _build_query(lat: float, lng: float, radius: int,
                 tags: list[tuple[str, str]], limit: int) -> str:
    """
    砌 Overpass 查詢。

    ⚠️⚠️ 為咩要合併成 regex 而唔係逐個 tag 查：
       原本寫法係「每個 tag × node/way」= 5 個 tag → 10 個 subquery。
       藥妝類有 5 個 tag → 10 個 subquery，直接令 Overpass **HTTP 504 超時**。
       （實測：逐個 tag → 504；regex 合併 → 200，快 9 秒）

       做法：同一個 key 嘅多個 value 用 regex 一次過查：
         nwr["shop"~"^(chemist|beauty|cosmetics)$"](around:...)
       而 `nwr` 係 Overpass 嘅簡寫，等於 node+way+relation 一次過。

       結果：10 個 subquery → 1-2 個。
    """
    by_key: dict[str, list[str]] = {}
    for k, v in tags:
        by_key.setdefault(k, []).append(v)
    parts = []
    for k, vals in by_key.items():
        rx = "|".join(re.escape(v) for v in vals)
        parts.append(f'nwr["{k}"~"^({rx})$"](around:{radius},{lat},{lng});')
    body = "".join(parts)
    return f"[out:json][timeout:{_TIMEOUT}];({body});out center {limit * 3};"


def _haversine_m(lat1, lng1, lat2, lng2) -> float:
    R = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(min(1.0, a)))


SHOP_LABELS = {
    "chemist": "💊 藥妝店", "beauty": "💄 美妝店", "pharmacy": "💊 藥局",
    "medical_supply": "🏥 醫療用品", "cosmetics": "💄 化妝品",
    "gift": "🎁 禮品店", "souvenir": "🎁 手信店", "confectionery": "🍫 菓子店",
    "bakery": "🥐 麵包店", "pastry": "🍰 甜點店", "deli": "🥗 熟食店",
    "supermarket": "🛒 超市", "convenience": "🏪 便利店", "grocery": "🥬 雜貨",
    "food": "🍱 食品店", "greengrocer": "🥬 蔬果店",
    "clothes": "👕 服裝店", "fashion": "👗 時裝店", "shoes": "👟 鞋店",
    "boutique": "👜 精品店", "department_store": "🏬 百貨公司",
    "electronics": "🔌 電器店", "computer": "💻 電腦店",
    "mobile_phone": "📱 手機店", "appliance": "🔌 家電店", "camera": "📷 相機店",
    "mall": "🛍 商場", "variety_store": "🎪 雜貨店", "general": "🏪 雜貨店",
}


def find_nearby(title: str, lat: float, lng: float, *,
                category: str | None = None, radius: int = 1500,
                limit: int = 12, country: str | None = None) -> dict:
    """
    搵附近邊度買得到。

    策略（⚠️ 因為 Overpass 唔穩定，所以要兩條路）：
      ① Nominatim + **當地語言**關鍵字   ← 主力，實測 1-2 秒穩定
      ② Overpass（結構化 tag 搜尋）      ← 補充，會 504 但唔緊要
      ③ 用戶自己已經收藏嘅同類店鋪       ← 一定搵到（喺 App 層加）

    回傳 {item, category, shops, total, sources}
    """
    cat = classify(title, category)
    region = region_of(lat, lng, country)
    km = radius / 1000.0
    keywords = REGION_KEYWORDS.get(region, REGION_KEYWORDS["en"]).get(cat) or \
        REGION_KEYWORDS["en"]["other"]

    shops: list[dict] = []
    sources: list[str] = []

    # ── ① Nominatim ──
    #
    # ⚠️⚠️ 為咩要並行：
    #   原本逐個關鍵字順序查（3 個 × (查詢 + 0.35s sleep)）＋ Overpass
    #   → 實測最慢 22.5 秒。用戶打一個字要等 22 秒 = 唔會用。
    #
    #   並行之後：max(Nominatim, Overpass) 而唔係 sum → 通常 3-7 秒。
    #   注意仍然要尊重 Nominatim 嘅 1 req/s 限制，所以關鍵字限制 3 個。
    now = time.time()
    cache_key = f"nom:{round(lat,3)},{round(lng,3)}:{km}:{cat}:{region}"
    ov_key = f"ov:{round(lat,3)},{round(lng,3)}:{radius}:{cat}"

    def do_nominatim() -> list:
        if cache_key in _cache and now - _cache[cache_key][0] < _CACHE_TTL:
            return _cache[cache_key][1]
        out: list = []
        for i, kw in enumerate(keywords[:3]):
            out.extend(_nominatim(kw, lat, lng, km))
            if i < 2:
                time.sleep(0.4)
        # ⚠️ 當地語言搵唔到 → 試英文（有啲地方 OSM 只有英文名）
        if not out:
            for kw in (REGION_KEYWORDS["en"].get(cat) or [])[:2]:
                out.extend(_nominatim(kw, lat, lng, km))
                time.sleep(0.4)
        _cache[cache_key] = (time.time(), out)
        return out

    def do_overpass() -> list:
        if ov_key in _cache and now - _cache[ov_key][0] < _CACHE_TTL:
            return _cache[ov_key][1]
        raw_: list = []
        try:
            q = _build_query(lat, lng, radius, tags, limit)
            r = requests.post(OVERPASS, data={"data": q},
                              headers={"User-Agent": API_UA,
                                       "Accept": "application/json"},
                              timeout=_TIMEOUT)
            # ⚠️ Overpass 經常 504 / 429 —— 唔可以當錯誤，靜靜跳過就得
            if r.status_code == 200:
                raw_ = (r.json().get("elements") or [])
        except Exception:
            raw_ = []
        _cache[ov_key] = (now, raw_)
        return raw_

    tags = CATEGORY_TAGS.get(cat) or CATEGORY_TAGS["other"]

    # ⚠️⚠️ 設計：**Nominatim 一回就返**，Overpass 用背景 thread 補。
    #    原因：實測 Overpass 成日 504，等到佢 timeout 要 10-20 秒。
    #    但用戶打一個字唔應該等 20 秒 —— 寧願先出 Nominatim 嘅結果，
    #    Overpass 查到嘅嘢下次查（cache 咗）就會多咗。
    _bg: set = globals().setdefault("_bg_running", set())

    def _bg_overpass():
        try:
            raw_ = do_overpass()
            _cache[ov_key] = (time.time(), raw_)
        except Exception:
            pass
        finally:
            _bg_running.discard(cat)

    import threading
    if ov_key not in _cache and cat not in _bg_running:
        _bg_running.add(cat)
        threading.Thread(target=_bg_overpass, daemon=True).start()

    # Nominatim 係主力，等佢（有 cache 就即刻）
    nom = do_nominatim()
    raw = _cache.get(ov_key, (0, []))[1]      # 有就用，冇就空
    if nom:
        sources.append("nominatim")

    for e in nom:
        try:
            la, ln = float(e["lat"]), float(e["lon"])
        except (KeyError, TypeError, ValueError):
            continue
        name = (e.get("name") or "").strip()
        if not name:
            # 由 display_name 抽第一段
            name = (e.get("display_name") or "").split(",")[0].strip()
        if not name:
            continue
        cls = e.get("class") or ""
        typ = e.get("type") or ""
        shops.append({
            "name": name,
            "kind": typ or cls,
            "label": SHOP_LABELS.get(typ) or SHOP_LABELS.get(cls) or "🏬 商店",
            "lat": la, "lng": ln,
            "distance_m": round(_haversine_m(lat, lng, la, ln)),
            "address": (e.get("display_name") or "")[:120] or None,
            "hours": (e.get("extratags") or {}).get("opening_hours"),
            "phone": (e.get("extratags") or {}).get("phone"),
        })

    # ── ② Overpass（已經喺上面並行跑咗）──
    if raw:
        sources.append("overpass")

    for e in raw:
        t = e.get("tags") or {}
        name = t.get("name:zh") or t.get("name:zh-Hant") or t.get("name") or \
               t.get("name:en") or t.get("brand")
        if not name:
            continue
        la = e.get("lat") or (e.get("center") or {}).get("lat")
        ln = e.get("lon") or (e.get("center") or {}).get("lon")
        if la is None or ln is None:
            continue
        kind = t.get("shop") or t.get("amenity") or ""
        addr = " ".join(x for x in (
            t.get("addr:city"), t.get("addr:suburb"),
            t.get("addr:street"), t.get("addr:housenumber")) if x)
        shops.append({
            "name": name,
            "kind": kind,
            "label": SHOP_LABELS.get(kind, "🏬 商店"),
            "lat": la, "lng": ln,
            "distance_m": round(_haversine_m(lat, lng, la, ln)),
            "address": addr or None,
            "hours": t.get("opening_hours"),
            "phone": t.get("phone") or t.get("contact:phone"),
        })

    # ── 去重 + 按距離排 ──
    seen, uniq = set(), []
    for s_ in sorted(shops, key=lambda x: x["distance_m"]):
        k = (s_["name"].lower()[:14], round(s_["distance_m"] / 80))
        if k in seen:
            continue
        seen.add(k)
        uniq.append(s_)

    return {
        "item": title,
        "category": cat,
        "region": region,
        "radius_m": radius,
        "keywords": keywords,
        "shops": uniq[:limit],
        "total": len(uniq),
        "sources": sources,
    }


def default_center(trip: dict, items: list | None = None) -> Optional[tuple[float, float]]:
    """
    揀一個「中心點」嚟搜尋附近。

    優先：旅程嘅城市座標 → 已收藏景點嘅中心 → None
    """
    stops = trip.get("stops") or []
    pts = [(s["lat"], s["lng"]) for s in stops if s.get("lat") is not None]
    if pts:
        return (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))
    if items:
        pts = [(i["lat"], i["lng"]) for i in items if i.get("lat") is not None]
        if pts:
            return (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))
    return None
