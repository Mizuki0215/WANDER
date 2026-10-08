"""
wander.localgeo — 本地城市／地區座標庫
======================================

⚠️ 為咩要有呢個（用戶提議，好正確）：
   每次查 Photon 要 200–800ms，而且免費服務會 rate limit
   （實測連續查十幾個城市就開始冇反應）。
   但世界重點城市嘅座標係**唔會變**嘅 —— 冇理由每次上網查。

   本地查 = 0ms + 離線都用得 + 唔會 rate limit + 唔會撞同名地方
   （「明洞」喺中國都有，中文查 Photon 會攞錯；本地庫已經校正過）。

資料來源：
   · data/cities.json    GeoNames cities15000（34,153 個城市）
                         過濾：人口 >= 50000 或首都／行政中心
                         134,655 個名稱索引（中／英／日／韓／諺文…）
   · data/districts.json 重點旅遊地區（博多、明洞、銅鑼灣…）
                         由 Photon 抓一次然後永久存本地

查詢次序：
   ① 本地城市庫（cities.json）      ← 99% 嘅情況
   ② 本地地區庫（districts.json）    ← 博多、明洞呢類
   ③ 詞典（lexicon DISTRICTS）已有座標
   ④ Photon（fallback，然後寫入永久 cache）
"""
from __future__ import annotations

import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Optional

DATA = Path(__file__).resolve().parent / "data"

# 國家碼 → 中文名（顯示用）
# ⚠️ 反向表：中文國名 → ISO 碼。
#    地區庫（districts.json）淨係有中文國名，但時區估算要 ISO 碼。
_ZH_TO_CC = None


def _zh_to_cc(zh):
    """中文國名 → ISO 碼（搵唔到就回 None）。"""
    global _ZH_TO_CC
    if _ZH_TO_CC is None:
        _ZH_TO_CC = {v: k for k, v in COUNTRY_ZH.items()}
    return _ZH_TO_CC.get(zh)


COUNTRY_ZH = {
    "JP": "日本", "KR": "韓國", "TW": "台灣", "HK": "香港", "MO": "澳門",
    "CN": "中國", "TH": "泰國", "VN": "越南", "SG": "新加坡", "MY": "馬來西亞",
    "ID": "印尼", "PH": "菲律賓", "KH": "柬埔寨", "LA": "寮國", "MM": "緬甸",
    "IN": "印度", "NP": "尼泊爾", "LK": "斯里蘭卡", "BD": "孟加拉",
    "US": "美國", "CA": "加拿大", "MX": "墨西哥", "BR": "巴西", "AR": "阿根廷",
    "GB": "英國", "IE": "愛爾蘭", "FR": "法國", "DE": "德國", "IT": "意大利",
    "ES": "西班牙", "PT": "葡萄牙", "NL": "荷蘭", "BE": "比利時",
    "CH": "瑞士", "AT": "奧地利", "SE": "瑞典", "NO": "挪威", "DK": "丹麥",
    "FI": "芬蘭", "IS": "冰島", "PL": "波蘭", "CZ": "捷克", "HU": "匈牙利",
    "GR": "希臘", "TR": "土耳其", "RU": "俄羅斯", "UA": "烏克蘭",
    "AE": "阿聯酋", "SA": "沙地阿拉伯", "QA": "卡塔爾", "IL": "以色列",
    "EG": "埃及", "MA": "摩洛哥", "ZA": "南非", "KE": "肯尼亞", "TZ": "坦桑尼亞",
    "AU": "澳洲", "NZ": "紐西蘭", "FJ": "斐濟", "GU": "關島",
}


def norm(s: str) -> str:
    """
    正規化查詢字串。

    ⚠️ 要同建庫時用同一個函式，否則查唔到。
       建庫時：NFKC → 細階 → 縣→県、區→区、臺→台 → 去空格／連接符
    """
    if not s:
        return ""
    s = unicodedata.normalize("NFKC", str(s)).strip().lower()
    s = s.replace("縣", "県").replace("區", "区").replace("臺", "台")
    s = re.sub(r"[\s\-\.'’]+", "", s)
    return s


@lru_cache(maxsize=1)
def _cities() -> dict:
    f = DATA / "cities.json"
    if not f.exists():
        return {}
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        return {}


@lru_cache(maxsize=1)
def _districts() -> dict:
    f = DATA / "districts.json"
    if not f.exists():
        return {}
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        return {}


def stats() -> dict:
    return {"cities": len(_cities()), "districts": len(_districts())}


def lookup(name: str, *, hint: str | None = None) -> Optional[dict]:
    """
    本地查座標。搵到就即刻回傳（0ms，唔使上網）。

    回傳 {"lat","lng","country","population","canonical","source"}
    搵唔到 → None（呼叫者可以 fallback 去 Photon）
    """
    key = norm(name)
    # ⚠️ 唔可以用 len<2 就拒絕 —— 日文有單字地名（「栄」名古屋、「嵐」…）
    if not key:
        return None

    # ① 地區庫優先（「博多」比「博多区」更貼近用戶講法）
    #    但如果同時係城市名而且人口更高，城市庫更啱
    d = _districts().get(name) or _districts().get(key)
    c = _cities().get(key)

    # ② 有 hint 就試「名 + hint」嘅組合（罕有）
    if not c and hint:
        c = _cities().get(norm(f"{name}{hint}"))

    # ⚠️⚠️ 地區庫要**優先過**城市庫。
    #    原因：GeoNames 有好多同名小鎮會搶走正確答案，實測：
    #       「祇園」→ GeoNames 攞到広島附近嘅祇園町（34.43,132.47）
    #                 但用戶講嘅係福岡中洲隔離嘅祇園（33.59,130.42）
    #       「安平」→ GeoNames 攞到河北安平縣（38.23,115.51）唔係台南安平
    #       「梅田」→ 埼玉縣嘅梅田，唔係大阪梅田
    #    地區庫係**人工校正**過嘅，所以佢嘅答案一定比 GeoNames 準。
    if d:
        lat, lng, country, canonical = d
        return {
            "lat": lat, "lng": lng, "country": country,
            # ⚠️⚠️ 地區庫淨係存**中文國名**，但下游需要 ISO 碼
            #    （時區估算靠 `cc`，見 wander/tz.py）。
            #    原本回 None → 去布院／鹿兒島攞到 `Etc/GMT-9`
            #    （經度估算）而唔係 `Asia/Tokyo`。
            #    兩者都係 UTC+9，但 `Etc/GMT-9` 嘅**標籤**係「GMT-9」
            #    而唔係「東京」→ 用戶睇落會覺得錯。
            "country_code": _zh_to_cc(country),
            "population": 0, "canonical": canonical,
            "source": "local_districts",
        }
    if c:
        lat, lng, cc, pop, canonical = c
        return {
            "lat": lat, "lng": lng, "country": COUNTRY_ZH.get(cc, cc),
            "country_code": cc, "population": pop, "canonical": canonical,
            "source": "local_cities",
        }
    return None


def search(prefix: str, *, limit: int = 8) -> list[dict]:
    """
    前綴搜尋（俾用戶打字時揀城市）。

    ⚠️ 134,655 個鍵，逐個 startswith 要 ~40ms；所以只喺 >= 1 個字先做
       （1 個中文字已經好有指向性，例如「香」「福」「首」）。

    ⚠️⚠️ 回傳要包括「匹配到嘅名」——
       因為索引係「任何語言嘅別名 → 記錄」，而 canonical 通常係
       當地語言／英文。用戶打「香港」會 match 到 key "香港"，
       但 canonical 係 "Hong Kong"。
       要顯示「Hong Kong · 香港」用戶先肯定揀啱咗。
    """
    key = norm(prefix)
    if not key:
        return []
    out = []
    for k, v in _cities().items():
        if k.startswith(key):
            lat, lng, cc, pop, canonical = v
            matched = k
            out.append({
                "query": canonical, "matched": matched, "lat": lat, "lng": lng,
                "country": COUNTRY_ZH.get(cc, cc), "population": pop,
            })
    # ⚠️⚠️ 排序 —— 單靠人口會出「打 hong 竟然出 Hangzhou」呢種結果。
    #
    #    為咩會咁：索引係「**任何語言嘅別名** → 記錄」。
    #    Hangzhou 有個別名 "hongchusu"（韓文羅馬拼音），
    #    所以 startswith("hong") 都會中，而佢人口（750萬）
    #    仲多過香港（740萬）→ 排第一。但用戶打 "hong"
    #    幾乎一定係想搵 **Hong Kong**。
    #
    #    評分（由高到低）：
    #      100  正名完全等於查詢         打 "tokyo" → Tokyo
    #       80  正名以查詢開頭           打 "hong"  → Hong Kong   ← 關鍵
    #       60  別名完全等於查詢         打 "香港"  → Hong Kong（別名就係「香港」）
    #       35  別名以查詢開頭           打 "hong"  → Hangzhou（別名 hongchusu）
    #      +0~20 人口（同分時大城市優先）
    #      -0~6  匹配字長度（"hongkong" 比 "hongkongisland" 準）
    import math
    for r in out:
        canon = norm(r["query"] or "")
        matched = r["matched"]
        if canon == key:
            sc = 100.0
        elif canon.startswith(key):
            sc = 80.0
        elif matched == key:
            sc = 60.0
        else:
            sc = 35.0
        pop = r["population"] or 0
        if pop > 0:
            # ⚠️ 用 log 而唔係線性 —— 否則東京（3700萬）會壓死一切
            sc += min(20.0, math.log10(pop + 1) * 2.2)
        sc -= min(6.0, (len(matched) - len(key)) * 0.35)
        r["_s"] = sc

    out.sort(key=lambda x: (-x["_s"], x["query"]))
    for r in out:
        r.pop("_s", None)

    # 同名去重
    seen, uniq = set(), []
    for r in out:
        k = (r["query"], round(r["lat"], 2))
        if k in seen:
            continue
        seen.add(k)
        uniq.append(r)
        if len(uniq) >= limit:
            break
    return uniq


# ── 永久 cache（Photon 查到之後寫入，之後唔使再上網）──
_CACHE_FILE = DATA / "geocode_cache.json"


@lru_cache(maxsize=1)
def _cache() -> dict:
    if _CACHE_FILE.exists():
        try:
            return json.loads(_CACHE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def cache_get(name: str) -> Optional[dict]:
    return _cache().get(name)


def cache_put(name: str, rec: dict) -> None:
    """寫入永久 cache（下次唔使再查 Photon）。"""
    c = _cache()
    c[name] = rec
    try:
        _CACHE_FILE.write_text(
            json.dumps(c, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8")
    except Exception:
        pass          # 寫唔到唔緊要，下次再查
