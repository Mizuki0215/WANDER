"""
wander.links — URL 分類同結構解析（唔使上網就做得）

呢一層嘅價值：Google Maps link 本身就帶住店名 + 精確座標，
完全免費、即時、100% 準。所以永遠要做第一步。

支援嘅 Google Maps 格式：
  1. /maps/place/店名/@lat,lng,17z/data=!3d..!4d..   ← 最完整
  2. /maps/search/?api=1&query=店名
  3. maps.app.goo.gl/xxxx                            ← 短連結，要跟 redirect
  4. ?q=店名
  5. /maps/@lat,lng,17z                              ← 只有視窗中心，冇店名
"""
from __future__ import annotations

import re
from urllib.parse import parse_qs, unquote, urlparse

from .models import Item

# ══════════════════════════════════════════════════════════════
# 來源分類
# ══════════════════════════════════════════════════════════════

SOURCE_RULES: list[tuple[str, str, str]] = [
    # (regex 對 hostname, 來源 id, 顯示名)
    (r"^(maps\.app\.goo\.gl|goo\.gl|maps\.google\.[a-z.]+|google\.[a-z.]+)$", "gmaps",    "Google Maps"),
    (r"instagram\.com$",                                                        "instagram", "Instagram"),
    (r"(xiaohongshu\.com|xhslink\.com)$",                                       "xiaohongshu", "小紅書"),
    (r"(youtube\.com|youtu\.be)$",                                              "youtube",  "YouTube"),
    (r"tiktok\.com$",                                                           "tiktok",   "TikTok"),
    (r"tabelog\.com$",                                                          "tabelog",  "Tabelog"),
    (r"(tripadvisor\.[a-z.]+)$",                                                "tripadvisor", "TripAdvisor"),
    (r"(hotpepper\.jp|retty\.me|gnavi\.co\.jp|jalan\.net)$",                    "jp_gourmet", "日本美食網"),
    (r"(klook\.com|kkday\.com)$",                                               "ota",      "旅遊平台"),
    (r"(openrice\.com)$",                                                       "openrice", "OpenRice"),
    (r"(dianping\.com|meituan\.com)$",                                          "dianping", "大眾點評"),
    (r"google\.[a-z.]+$",                                                       "web",      "網頁"),
]

# 各來源「理論上」可以攞到嘅資料（用嚟設定用戶期望）
SOURCE_CAPABILITY: dict[str, dict[str, bool]] = {
    "gmaps":       {"name": True,  "address": True,  "coords": True,  "image": False, "text": False},
    "instagram":   {"name": True,  "address": False, "coords": False, "image": True,  "text": True},
    "xiaohongshu": {"name": False, "address": False, "coords": False, "image": False, "text": False},
    "youtube":     {"name": True,  "address": False, "coords": False, "image": True,  "text": True},
    "tabelog":     {"name": True,  "address": True,  "coords": True,  "image": True,  "text": True},
    "tripadvisor": {"name": True,  "address": True,  "coords": False, "image": True,  "text": True},
    "jp_gourmet":  {"name": True,  "address": True,  "coords": False, "image": True,  "text": True},
    "ota":         {"name": True,  "address": False, "coords": False, "image": True,  "text": True},
    "openrice":    {"name": True,  "address": True,  "coords": False, "image": True,  "text": True},
    "web":         {"name": True,  "address": False, "coords": False, "image": True,  "text": True},
}


def classify(url: str) -> dict[str, str]:
    """判斷 URL 屬於邊個來源。"""
    try:
        host = urlparse(url).hostname or ""
    except Exception:
        return {"id": "invalid", "name": "無法識別", "host": ""}
    host = re.sub(r"^www\.", "", host.lower())
    for pattern, sid, sname in SOURCE_RULES:
        if re.search(pattern, host):
            return {"id": sid, "name": sname, "host": host}
    return {"id": "web", "name": "一般網站", "host": host}


def is_short_link(url: str) -> bool:
    return bool(re.search(r"maps\.app\.goo\.gl|goo\.gl/maps|xhslink\.com|youtu\.be|bit\.ly|tinyurl", url))


# ══════════════════════════════════════════════════════════════
# Google Maps 結構解析
# ══════════════════════════════════════════════════════════════

# ⚠️⚠️ 用戶報：「貼 Google Maps link 之後，解析得唔夠準」
#
#    實測捉到 5 個問題：
#      ① 店名連埋地址一齊（`一蘭拉麵 本店, 1 Chome-1-1 ...`）
#      ② 純座標當咗做店名（`35.6586,139.7454`）
#      ③ `place_id:ChIJ...` 當咗做店名（係 Google 內部 ID）
#      ④ `dir?destination=` 完全冇解析
#      ⑤ 有座標但 country/city 都係 None
_COORD_RE = re.compile(r"^-?\d{1,3}\.\d+\s*,\s*-?\d{1,3}\.\d+$")


def _is_coord(s: str) -> bool:
    """⚠️ 呢個字串係唔係「緯度,經度」（唔係店名）？"""
    return bool(_COORD_RE.match((s or "").strip()))


def _is_place_id(s: str) -> bool:
    """⚠️ Google 內部 ID（`place_id:ChIJ...`、`ChIJ...`）—— 唔係店名。"""
    t = (s or "").strip()
    return t.lower().startswith("place_id:") or bool(re.match(r"^ChIJ[A-Za-z0-9_-]{10,}$", t))


def _split_name_addr(seg: str) -> tuple[str, str]:
    """
    拆開 Google 嘅 `店名, 地址`。

    ⚠️⚠️ Google 嘅 `/place/` 段落成日係 `名稱, 完整地址` ——
       我哋之前將成串當做**店名**（實測：
       `'一蘭拉麵 本店, 1 Chome-1-1 Hakataekichuogai, Hakata Ward'`）。

    ✅ 策略：由**第一個**逗號切開，但只喺第二段**似地址**嗰陣先切：
       · 開頭係數字（`1 Chome-1-1`、`4-16-2`）
       · 或者有地址關鍵字（都／道／府／県／縣／市／区／區／町／村）
       · 或者好長（> 12 字）—— 店名通常短

    ⚠️ 唔可以見逗號就切 —— 有啲店名本身有逗號。
    """
    t = (seg or "").strip()
    if "," not in t:
        return t, ""
    head, _, tail = t.partition(",")
    head, tail = head.strip(), tail.strip()
    if not head or not tail:
        return t, ""
    looks_addr = (
        tail[:1].isdigit()
        or any(k in tail for k in ("都", "道", "府", "県", "縣", "市", "区", "區", "町", "村"))
        or len(tail) > 12
    )
    # ⚠️ head 一定要有嘢（唔可以係空）
    if looks_addr and len(head) >= 2:
        return head, tail
    return t, ""


def parse_gmaps(url: str) -> tuple[Item, list[dict[str, str]]]:
    """
    解析 Google Maps link → Item。
    完全唔使上網：所有資料都喺 URL 入面。
    """
    item = Item(source="gmaps", source_name="Google Maps", url=url)
    steps: list[dict[str, str]] = []
    decoded = unquote(url)

    def step(rule: str, match: str, note: str) -> None:
        steps.append({"rule": rule, "match": match, "note": note})

    if is_short_link(url):
        step("GMAPS_SHORT", url, "短連結 → 需要 HTTP redirect 跟蹤拎最終 URL")
        item.notes.append("短連結需要跟 redirect 才可以解析")

    # ① 精確座標 !3d!4d（最準，優先）
    m34 = re.search(r"!3d(-?\d+\.?\d*)!4d(-?\d+\.?\d*)", url)
    if m34:
        item.lat, item.lng = float(m34.group(1)), float(m34.group(2))
        step("GMAPS_COORD_EXACT", f"{item.lat}, {item.lng}", "精確座標 !3d!4d（店舖本身）")

    # ② /place/店名（可能連地址）
    m_place = re.search(r"/place/([^/@?]+)", decoded)
    if m_place:
        seg = unquote(m_place.group(1)).replace("+", " ").strip()

        # ⚠️⚠️ **先**檢查成段係唔係座標 —— 一定要喺 `_split_name_addr` **之前**！
        #    唔係嘅話 `/place/35.6586,139.7454` 會被逗號拆開 →
        #    name='35.6586'、address='139.7454'（因為 '139...' 開頭係數字
        #    就當佢係地址）。實測捉到呢個 bug。
        if _is_coord(seg):
            step("GMAPS_PLACE", seg, "⚠️ /place/ 係座標（唔係店名）→ 存入座標")
            try:
                la, ln = [x.strip() for x in seg.split(",")]
                item.lat, item.lng = float(la), float(ln)
            except (ValueError, IndexError):
                pass
            name, addr = "", ""
        elif _is_place_id(seg):
            step("GMAPS_PLACE", seg, "⚠️ /place/ 係 Google 內部 ID（唔係名）→ 丟棄")
            name, addr = "", ""
        else:
            name, addr = _split_name_addr(seg)
            if _is_coord(name):
                step("GMAPS_PLACE", name, "⚠️ /place/ 係座標 → 唔當名")
                name = ""
        if name:
            item.name = name
            item.name_method = "Google Maps /place/ 路徑"
            step("GMAPS_PLACE", name, "由 /place/ 路徑抽店名")
        # ⚠️ 地址一定要留住（用戶要求「show 嘅係多嘅地址呢？」）
        if addr:
            item.address = item.address or addr
            step("GMAPS_PLACE_ADDR", addr, "由 /place/ 逗號後抽地址")
    else:
        step("GMAPS_PLACE", "(無)", "呢條 link 冇 /place/ 路徑")

    # ③ 座標 @lat,lng（視窗中心，唔一定係店舖）
    m_at = re.search(r"@(-?\d+\.\d+),(-?\d+\.\d+)", url)
    if m_at and not m34:
        item.lat, item.lng = float(m_at.group(1)), float(m_at.group(2))
        step("GMAPS_COORD_VIEW", f"{item.lat}, {item.lng}", "視窗中心座標（唔係店舖本身，要小心）")
    elif m_at:
        step("GMAPS_COORD_VIEW", f"{m_at.group(1)}, {m_at.group(2)}", "視窗中心（已有精確座標，忽略）")

    # ④ ?q= / query=
    qs = parse_qs(urlparse(url).query)
    # ⚠️ `destination=` / `origin=` 都要（`/maps/dir/?api=1&destination=成田機場`）——
    #    之前完全冇解析（實測 name=None）。
    for key in ("q", "query", "destination", "origin"):
        if key not in qs or not qs[key]:
            continue
        q = unquote(qs[key][0]).replace("+", " ").strip()
        if not q:
            continue
        if _is_place_id(q):
            step(f"GMAPS_QUERY_{key.upper()}", q, "⚠️ Google 內部 ID → 丟棄")
            continue
        if _is_coord(q):
            # ⚠️ `?q=35.6586,139.7454` —— 係座標唔係店名
            parts = [x.strip() for x in q.split(",")]
            try:
                if not item.lat:
                    item.lat, item.lng = float(parts[0]), float(parts[1])
                step("GMAPS_QUERY_COORD", q, "由 query 參數抽座標（唔係店名）")
            except (ValueError, IndexError):
                pass
            continue
        # ⚠️ 地名（可能連地址）
        nm, ad = _split_name_addr(q)
        if not item.name and nm:
            item.name = nm
            item.name_method = f"Google Maps ?{key}= 參數"
            step(f"GMAPS_QUERY_{key.upper()}", nm, "由查詢參數抽店名")
        if ad and not item.address:
            item.address = ad
            step(f"GMAPS_QUERY_{key.upper()}_ADDR", ad, "由查詢參數抽地址")

    # ⑤ 用地理詞典比對店名／地址
    hay = " ".join(filter(None, [item.name, decoded]))
    from .lexicon import ALL_DISTRICT_WORDS, GROUP_COUNTRY, match_region
    mr = match_region(hay)
    if mr:
        from .lexicon import _WORD_TO_GROUP
        grp = _WORD_TO_GROUP.get(mr[0])
        item.district = mr[0]
        if grp:
            item.country = GROUP_COUNTRY.get(grp)
            if grp == "福岡縣":
                item.prefecture = "福岡縣"
            elif grp == "福岡市":
                item.prefecture = "福岡縣"
                item.city = "福岡市"
            elif grp == "其他日本":
                item.prefecture = item.prefecture or "（日本）"
        step("GEO_MATCH", mr[0], f"地名比對命中「{mr[0]}」（{grp}）")
    else:
        step("GEO_MATCH", "(無命中)", "店名冇地區關鍵字 → 要靠座標反查（Nominatim）")

    # ⑤b ⚠️⚠️ 座標 → 最近城市（國家／城市）
    #
    #   實測：貼 `/maps/place/35.6586,139.7454/` 嗰陣
    #   country / city 全部 None（因為冇地名關鍵字可以 match）。
    #   ✅ 用座標反查本機 134k 城市庫 —— 唔使上網。
    if item.lat is not None and item.lng is not None and not item.country:
        try:
            from .localgeo import nearest as _nearest
            near = _nearest(item.lat, item.lng)
            # ⚠️ 只喺夠近（< 60km）嗰陣先用 —— 太遠就唔可靠
            if near and (near.get("km") or 999) < 60:
                item.country = item.country or near.get("country")
                item.city = item.city or near.get("name")
                step("GEO_REVERSE", f"{near.get('name')} ({near.get('km')}km)",
                     f"由座標反查最近城市 → {near.get('country')}")
        except Exception:
            pass

    # ⑥ 分類
    from .caption import CaptionParser
    if item.name:
        CaptionParser._extract_category(item.name, item, lambda *a: None)
    if item.category:
        step("CATEGORY", item.category_why or "", f"由店名推斷分類：{item.category}")
    else:
        step("CATEGORY", "(無)", "推斷唔到分類 → 標記待分類")

    # 信心分數
    C = {
        "name": 100 if item.name else 0,
        "location": 96 if item.lat else (80 if item.district else 0),
        "address": 0,
        "category": 70 if item.category else 0,
    }
    weights = [("name", 0.32), ("location", 0.26), ("category", 0.14)]
    item.field_confidence = C
    item.confidence = round(sum(C.get(k, 0) * w for k, w in weights)
                            + (26 if item.lat else 0))   # 有精確座標加成
    item.confidence = min(item.confidence, 100)
    item.needs_review = item.confidence < 70 or not item.name
    item.rules_matched = steps
    return item, steps


# ══════════════════════════════════════════════════════════════
# 結構解析入口（唔上網）
# ══════════════════════════════════════════════════════════════

def parse_url_offline(url: str) -> Item:
    """
    只靠 URL 結構解析，唔上網。
    對 Google Maps 極有效；其他來源只做到「識別 + 抽出 ID」。
    """
    kind = classify(url)
    if kind["id"] == "gmaps":
        item, _ = parse_gmaps(url)
        return item

    item = Item(source=kind["id"], source_name=kind["name"], url=url)
    rules = [{"rule": "CLASSIFY", "match": kind["host"], "note": f"識別為 {kind['name']}"}]

    if kind["id"] == "instagram":
        m = re.search(r"instagram\.com/(?:p|reel|tv)/([A-Za-z0-9_-]+)", url)
        if m:
            item.notes.append(f"IG post id: {m.group(1)}")
            rules.append({"rule": "IG_POST_ID", "match": m.group(1), "note": "貼文 ID"})
        rules.append({"rule": "NEEDS_FETCH", "match": "og:title / og:image / caption",
                      "note": "要後端抓 HTML"})

    elif kind["id"] == "xiaohongshu":
        rules.append({"rule": "XHS_BLOCKED", "match": kind["host"],
                      "note": "反爬嚴格 → 建議用戶貼文字或上傳截圖"})
        item.notes.append("小紅書建議改用「貼 caption」或「截圖上傳」")

    elif kind["id"] == "youtube":
        m = re.search(r"(?:v=|youtu\.be/|/shorts/)([A-Za-z0-9_-]{6,})", url)
        if m:
            item.notes.append(f"YouTube video id: {m.group(1)}")
            rules.append({"rule": "YT_ID", "match": m.group(1), "note": "可用官方 oEmbed（免費）"})

    else:
        rules.append({"rule": "NEEDS_FETCH", "match": "HTML meta / JSON-LD",
                      "note": "要後端抓 HTML 抽結構化資料"})

    item.rules_matched = rules
    item.confidence = 0
    item.needs_review = True
    return item
