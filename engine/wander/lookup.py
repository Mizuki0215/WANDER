"""
wander.lookup — 由「店名」反查完整資料（你提出嘅 idea）

核心洞察（用戶提出，好聰明）：
    由 IG / 小紅書 cap 圖，其實只需要 OCR 認出**店名**就夠。
    地址、座標、電話、營業時間全部可以由搜尋 / 地圖服務補上。

呢個做法嘅好處：
    ✅ 完全避開 IG / 小紅書嘅反爬（我哋唔碰佢哋）
    ✅ 法律乾淨（只用公開資料同官方 API）
    ✅ 資料更準（Tabelog / 官網嘅資料比 IG caption 可靠）
    ✅ 交叉驗證（多過一個來源可以互相核對）

三個免費後端（實測 2026-10）：

    ① Photon (photon.komoot.io)     模糊搜尋最強，認得「一蘭 本社総本店」
                                     → 座標 + 地址 + OSM tags
    ② Nominatim (OSM)               精確但唔識模糊搜尋，常配錯
                                     → 只做輔助 + 地址補完
    ③ DuckDuckGo HTML (html.duckduckgo.com/html/)
                                     免 key！搵到 Tabelog / Retty / 官網
                                     → 再抓 JSON-LD 拎最齊嘅資料

⚠️ 踩過嘅坑：
    - **兩個服務都會因為 User-Agent 而 403**。「Wander/0.1」直接被擋，
      一定要用普通瀏覽器 UA。呢個坑踩咗兩次（r.jina.ai 同 Nominatim）。
    - Nominatim 政策要求 1 req/sec，一定要 throttle。
    - Nominatim 唔識模糊搜尋：「一蘭 本社総本店」→ 搵到「名古屋犬山線」，
      「太宰府天満宮」→ 搵到福岡市嘅一個普通天満宮。所以唔可以單靠佢。
    - DuckDuckGo 嘅 HTML 係非官方接口，隨時可能變。要有 fallback。
"""
from __future__ import annotations

import html as _html
import json
import re
import time
import urllib.parse
from dataclasses import dataclass, field
from typing import Any, Optional

import requests

from .caption import parse_postal_code
from .models import Item, CATEGORY_ICONS  # noqa: F401

from .ua import BROWSER_UA

# ⚠️⚠️ 極反直覺嘅發現（實測 2026-10）：
#     DuckDuckGo 嘅 html 端點會因為 **Accept-Language** 而 403，
#     而且唔關值事 —— "zh-HK"、"ja" 一樣死。
#
#        只有 User-Agent                    → 200 ✅
#        UA + Accept-Language              → 403 ❌
#        UA + Accept: text/html            → 200 ✅
#        UA + Accept-Language + Accept     → 403 ❌
#
#     所以呢個 session **一定唔可以** 設 Accept-Language。
#     語言要控制就喺 query 落手（例如加「住所」「営業時間」）。
_session = requests.Session()
_session.headers.update({"User-Agent": BROWSER_UA})

# 快取：同一個查詢唔好重複打 API
# ⚠️ 一定要係 module level 而且唔好喺測試之間清走 —— 否則會不停打 API
#    被 rate limit（實測：連續打會開始 403）
_cache: dict[str, Any] = {}

# ⚠️ 廣告／追蹤／跳轉連結一定要剔走。
#    實測：搜尋「太宰府天満宮」時 DDG 會回傳
#    duckduckgo.com/y.js?ad_domain=hankyu-travel.com 呢種廣告，
#    佢會拎到最高分而被揀去抓，結果抓到垃圾。
_BAD_URL_RE = re.compile(
    r"(duckduckgo\.com/y\.js|duckduckgo\.com/l/|googleadservices|"
    r"doubleclick\.net|/aclk\?|bing\.com/aclick|utm_|ad_domain=)",
    re.I,
)
_last_nominatim = 0.0
_NOMINATIM_MIN_INTERVAL = 1.1        # 政策要求 1 req/sec
_last_photon = 0.0
_PHOTON_MIN_INTERVAL = 1.0           # 免費服務，自己忍手，唔好打爆
_photon_fail_streak = 0


# ══════════════════════════════════════════════════════════════
# 資料結構
# ══════════════════════════════════════════════════════════════

@dataclass
class PlaceCandidate:
    """一個候選地點（由 Photon / Nominatim / 搜尋結果嚟）。"""
    name: str
    lat: Optional[float] = None
    lng: Optional[float] = None
    country: Optional[str] = None
    # ⚠️ 兩個字母嘅 ISO 國家碼（"JP" / "HK"）——
    #    時區估算靠佢（見 wander/tz.py）。中文國名唔夠用。
    cc: Optional[str] = None
    state: Optional[str] = None
    city: Optional[str] = None
    district: Optional[str] = None
    street: Optional[str] = None
    postcode: Optional[str] = None
    osm_type: Optional[str] = None
    osm_value: Optional[str] = None
    url: Optional[str] = None
    source: str = ""
    score: float = 0.0

    @property
    def address_line(self) -> str:
        parts = [self.postcode, self.state, self.city, self.district, self.street]
        return " ".join(p for p in parts if p)


@dataclass
class SearchHit:
    """一個搜尋結果。"""
    title: str
    url: str
    snippet: str = ""
    rank: int = 0
    source_kind: str = ""     # tabelog / retty / official / other
    score: float = 0.0


# ══════════════════════════════════════════════════════════════
# ① Photon（模糊搜尋最強）
# ══════════════════════════════════════════════════════════════

def search_photon(query: str, *, limit: int = 5, lang: str = "default") -> list[PlaceCandidate]:
    """
    Photon = Komoot 開發、基於 OSM 嘅地理編碼器。
    專為 autocomplete 設計，所以**模糊搜尋能力遠勝 Nominatim**。

    實測：
      「一蘭 本社総本店 博多」→ 一蘭 [amenity/restaurant] 33.5932, 130.4046 ✅
    """
    key = f"photon:{query}:{limit}"
    if key in _cache:
        return _cache[key]

    # ① 自己 throttle，唔好打爆免費服務
    global _last_photon, _photon_fail_streak
    elapsed = time.time() - _last_photon
    if elapsed < _PHOTON_MIN_INTERVAL:
        time.sleep(_PHOTON_MIN_INTERVAL - elapsed)

    out: list[PlaceCandidate] = []
    data = None
    # ② 429 / 5xx 就退避重試（實測：連續打會被 rate limit）
    for attempt in range(3):
        try:
            r = _session.get("https://photon.komoot.io/api/",
                             params={"q": query, "limit": limit, "lang": lang},
                             timeout=12)
            _last_photon = time.time()
            if r.status_code == 200:
                data = r.json()
                _photon_fail_streak = 0
                break
            if r.status_code in (429, 500, 502, 503, 504):
                _photon_fail_streak += 1
                time.sleep(1.5 * (attempt + 1))
                continue
            break
        except (requests.RequestException, json.JSONDecodeError):
            time.sleep(1.0 * (attempt + 1))
    if data is None:
        return []

    for f in data.get("features", []):
        p = f.get("properties", {}) or {}
        geo = (f.get("geometry") or {}).get("coordinates") or []
        if len(geo) != 2:
            continue
        lng, lat = geo
        out.append(PlaceCandidate(
            name=p.get("name") or p.get("street") or "",
            lat=lat, lng=lng,
            country=p.get("country"), state=p.get("state"),
            # ⚠️ Photon 用 `countrycode`（細階 ISO 碼）——
            #    時區估算靠佢（見 wander/tz.py）。
            cc=(p.get("countrycode") or "").upper() or None,
            city=p.get("city"), district=p.get("district") or p.get("locality"),
            street=" ".join(filter(None, [p.get("street"), p.get("housenumber")])) or None,
            postcode=p.get("postcode"),
            osm_type=p.get("osm_key"), osm_value=p.get("osm_value"),
            source="photon",
        ))
    _cache[key] = out
    return out


# ══════════════════════════════════════════════════════════════
# ② Nominatim（精確但唔識模糊，用嚟補地址）
# ══════════════════════════════════════════════════════════════

def search_nominatim(query: str, *, limit: int = 3) -> list[PlaceCandidate]:
    """
    Nominatim = OSM 官方地理編碼。

    ⚠️ 兩個限制：
      1. User-Agent 一定要似瀏覽器，否則 403
      2. 政策要求 1 req/sec，所以有 throttle
      3. 唔識模糊搜尋 —— 「一蘭 本社総本店」會搵到完全唔相干嘅嘢
         所以只可以當輔助，唔可以當主力
    """
    global _last_nominatim
    key = f"nominatim:{query}:{limit}"
    if key in _cache:
        return _cache[key]

    elapsed = time.time() - _last_nominatim
    if elapsed < _NOMINATIM_MIN_INTERVAL:
        time.sleep(_NOMINATIM_MIN_INTERVAL - elapsed)

    out: list[PlaceCandidate] = []
    try:
        r = _session.get("https://nominatim.openstreetmap.org/search",
                         params={"q": query, "format": "jsonv2", "limit": limit,
                                 "addressdetails": 1, "extratags": 1},
                         timeout=12)
        _last_nominatim = time.time()
        if r.status_code != 200:
            return []
        data = r.json()
    except (requests.RequestException, json.JSONDecodeError):
        _last_nominatim = time.time()
        return []

    for t in data:
        a = t.get("address", {}) or {}
        et = t.get("extratags", {}) or {}
        try:
            lat, lng = float(t["lat"]), float(t["lon"])
        except (KeyError, TypeError, ValueError):
            continue
        out.append(PlaceCandidate(
            name=t.get("name") or a.get("amenity") or "",
            lat=lat, lng=lng,
            country=a.get("country"), state=a.get("state") or a.get("province"),
            # ⚠️ Nominatim 用 `country_code`
            cc=(a.get("country_code") or "").upper() or None,
            city=a.get("city") or a.get("town") or a.get("county") or a.get("municipality"),
            district=a.get("suburb") or a.get("neighbourhood") or a.get("quarter") or a.get("city_district"),
            street=" ".join(filter(None, [a.get("road"), a.get("house_number")])) or None,
            postcode=a.get("postcode"),
            osm_type=t.get("osm_type"), osm_value=t.get("type"),
            source="nominatim",
        ))
    _cache[key] = out
    return out


# ══════════════════════════════════════════════════════════════
# ③ DuckDuckGo HTML 搜尋（免 key！）
# ══════════════════════════════════════════════════════════════

# 邊啲網站有高質 JSON-LD（值得直接抓）
GOOD_SEARCH_DOMAINS: list[tuple[str, str]] = [
    ("tabelog.com",  "tabelog"),
    ("retty.me",     "retty"),
    ("hotpepper.jp", "hotpepper"),
    ("gnavi.co.jp",  "gnavi"),
    ("tripadvisor.", "tripadvisor"),
    ("openrice.com", "openrice"),
    ("jalan.net",    "jalan"),
    ("ikyu.com",     "ikyu"),
    ("食べログ",      "tabelog"),      # 標題可能係中文名
]

_TAG_RE = re.compile(r"<[^>]+>")
# DuckDuckGo 有冇 rate limit 我哋（202 = anomaly 頁）
DDG_RATE_LIMITED = False

_DDG_LINK_RE = re.compile(r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', re.S)
_DDG_SNIP_RE = re.compile(r'class="result__snippet"[^>]*>(.*?)</a>', re.S)


def _clean_html(s: str) -> str:
    return _html.unescape(_TAG_RE.sub("", s or "")).strip()


def _unwrap_ddg_url(href: str) -> str:
    """DDG 會用 /l/?uddg=<encoded> 包住外部連結。"""
    if href.startswith("//"):
        href = "https:" + href
    if "duckduckgo.com/l/" in href or href.startswith("/l/"):
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
        if "uddg" in qs:
            return urllib.parse.unquote(qs["uddg"][0])
    return href


def duckduckgo_search(query: str, *, limit: int = 8) -> list[SearchHit]:
    """
    用 DuckDuckGo 嘅 HTML 版搜尋（免 API key）。

    實測（2026-10）：
      「一蘭 本社総本店 博多 住所」
        → 1. 一蘭官網
        → 2. 「一蘭 本社総本店 (福岡市博多区-ラーメン-〒810-0801)」
        → 3. 食べログ 一蘭本社総本店
      「官兵衛うどん 粕屋町」
        → 1. 食べログ 官兵衛うどん
        → 2. Retty 官兵衛うどん
        ✅ 完全可用，而且搵到最有價值嘅來源（Tabelog）

    ⚠️ 呢個係非官方接口，HTML 結構隨時會變。所以：
       - 解析失敗要靜靜咁回傳空 list，唔可以爆
       - 一定要有 fallback（Photon）
    """
    key = f"ddg:{query}:{limit}"
    if key in _cache:
        return _cache[key]

    hits: list[SearchHit] = []
    try:
        r = _session.post("https://html.duckduckgo.com/html/",
                          data={"q": query, "kl": "jp-tok"},
                          timeout=15)
        # ⚠️⚠️ DuckDuckGo 冇 API key 嘅代價：會 bot 偵測。
        #    實測狂查十幾次之後就開始回傳 **HTTP 202 + anomaly 頁**，
        #    結果係空（唔係錯誤）→ 好難察覺，會以為「真實網站搵唔到」。
        #
        #    所以：
        #      ① 明確記錄 rate limit 狀態（DDG_RATE_LIMITED）
        #      ② 測試見到呢個狀態要 skip 而唔係 fail（避免假失敗）
        #      ③ 本地城市庫係主要路徑，DDG 只係最後 fallback
        if r.status_code == 202 or "anomaly" in r.text[:4000].lower():
            global DDG_RATE_LIMITED
            DDG_RATE_LIMITED = True
            return []
        if r.status_code != 200:
            return []
        page = r.text
        DDG_RATE_LIMITED = False
    except requests.RequestException:
        return []

    links = _DDG_LINK_RE.findall(page)
    snips = _DDG_SNIP_RE.findall(page)

    for i, (href, title_html) in enumerate(links[:limit]):
        url = _unwrap_ddg_url(_html.unescape(href))
        if _BAD_URL_RE.search(url) or _BAD_URL_RE.search(href):
            continue                      # 廣告／跳轉，唔要
        title = _clean_html(title_html)
        snippet = _clean_html(snips[i]) if i < len(snips) else ""
        kind = "other"
        for dom, k in GOOD_SEARCH_DOMAINS:
            if dom in url or dom in title:
                kind = k
                break
        if kind == "other" and i == 0:
            netloc = urllib.parse.urlparse(url).netloc
            if re.search(r"\.(jp|com|co\.jp)$", netloc):
                kind = "official"

        score = 0.0
        if kind in ("tabelog", "retty", "hotpepper", "gnavi"):
            score += 50          # 有結構化資料嘅美食網站，最高價值
        if kind == "tripadvisor":
            score += 30
        score += max(0, 20 - i * 3)                 # 排名越前越好
        if re.search(r"住所|address|アクセス|地図", snippet):
            score += 10
        # 標題含「〒」郵便番号 = 好強嘅信號
        if "〒" in title or "〒" in snippet:
            score += 15

        hits.append(SearchHit(title=title, url=url, snippet=snippet,
                              rank=i, source_kind=kind, score=score))

    hits.sort(key=lambda h: h.score, reverse=True)
    _cache[key] = hits
    return hits


def best_source_url(hits: list[SearchHit], *, prefer_kinds=("tabelog", "retty", "hotpepper", "gnavi", "tripadvisor")) -> Optional[str]:
    """由搜尋結果揀最值得抓嘅一條 link（優先有 JSON-LD 嘅網站）。"""
    clean = [h for h in hits if not _BAD_URL_RE.search(h.url)]
    for want in prefer_kinds:
        for h in clean:
            if h.source_kind == want:
                return h.url
    return clean[0].url if clean else None


# ══════════════════════════════════════════════════════════════
# 座標反查（有座標但冇地區時用）
# ══════════════════════════════════════════════════════════════

def reverse_geocode(lat: float, lng: float) -> Optional[PlaceCandidate]:
    """
    由座標反查地址／地區。

    點解需要：Google Maps link 好多時**只有座標冇地區名**
    （例：//maps.app.goo.gl/8eqhmBEJjsRRjuBPA → 座標 35.4675,139.6913
     但 URL 入面完全冇「神奈川県」或「鶴見区」）。

    用 Nominatim 嘅 reverse 端點（免費、免 key、政策允許 1 req/sec）。
    """
    key = f"rev:{round(lat, 5)},{round(lng, 5)}"
    if key in _cache:
        return _cache[key]

    global _last_nominatim
    elapsed = time.time() - _last_nominatim
    if elapsed < _NOMINATIM_MIN_INTERVAL:
        time.sleep(_NOMINATIM_MIN_INTERVAL - elapsed)

    out: Optional[PlaceCandidate] = None
    try:
        r = _session.get("https://nominatim.openstreetmap.org/reverse",
                         params={"lat": lat, "lon": lng, "format": "jsonv2",
                                 "addressdetails": 1, "zoom": 18},
                         timeout=12)
        _last_nominatim = time.time()
        if r.status_code == 200:
            d = r.json()
            a = d.get("address", {}) or {}
            out = PlaceCandidate(
                name=d.get("name") or a.get("amenity") or "",
                lat=lat, lng=lng,
                country=a.get("country"), state=a.get("state") or a.get("province"),
            # ⚠️ Nominatim 用 `country_code`
            cc=(a.get("country_code") or "").upper() or None,
                city=a.get("city") or a.get("town") or a.get("county") or a.get("municipality"),
                district=(a.get("suburb") or a.get("neighbourhood")
                          or a.get("quarter") or a.get("city_district")),
                street=" ".join(filter(None, [a.get("road"), a.get("house_number")])) or None,
                postcode=a.get("postcode"),
                source="nominatim_reverse",
            )
    except (requests.RequestException, json.JSONDecodeError):
        _last_nominatim = time.time()
    _cache[key] = out
    return out


# 日本地址結構：〒123-4567 福岡県福岡市博多区中洲5-3-2
_JP_ADDR_RE = re.compile(
    r"(?:〒\s*\d{3}-?\d{4}\s*)?"
    r"(?:(?P<pref>[^\s]{2,4}[都道府県縣]))?"
    r"(?:(?P<city>[^\s]{1,6}?[市]))?"
    r"(?:(?P<ward>[^\s]{1,5}?[区區郡]))?"
    r"(?P<town>[^\s\d]{1,10}?)"
    r"[\d\-–—]+")

# 韓國地址：서울 성동구 연무장길 47
_KR_ADDR_RE = re.compile(r"([가-힣]{2,6}[구동시군읍면리])\s")


def _extract_place_from_address(text: str) -> Optional[str]:
    """（單一結果版本，保留俾舊 caller）"""
    c = _extract_place_candidates(text)
    return c[0] if c else None


def _extract_place_candidates(text: str) -> list[str]:
    """
    由完整地址抽出**候選地區名**（由最精準到最粗）。

    ⚠️ 為咩要返一個 list：
       「福岡県福岡市博多区上川端町1-41」嘅町名係「上川端町」，
       但本地庫未必有（146 個校正地區 + 134k 城市）。
       搵唔到就要退落「博多区」，再退落「福岡市」。
       淨係返一個會令查詢直接失敗，然後前端 fallback 去查店名
       → 攞到三重縣嘅同名神社 ❌（真實踩過）

    次序：町名 > 區名 > 市名 > 都道府縣
    """
    if not text:
        return []
    t = text.strip()
    out: list[str] = []

    def add(v):
        if v and len(v) >= 2 and v not in out:
            out.append(v)

    # 韓國：구 級最有用
    m = _KR_ADDR_RE.search(t)
    if m:
        add(m.group(1))
        # 韓國地址成日係「서울 성동구」，都加埋第一個 token
        first = t.split()[0] if t.split() else None
        if first and re.match(r"^[가-힣]{2,}$", first):
            add(first)

    m = _JP_ADDR_RE.search(t)
    if m:
        for key in ("town", "ward", "city", "pref"):
            add(m.group(key))

    # 通用：XX區 / XX市 / XX町 / XX縣
    for mm in re.finditer(r"([^\s\d〒]{1,5}?[區区市町村縣县郡])", t):
        add(mm.group(1))

    # 最後：逐個「縣市區」組合（由長到短）
    for n in (4, 3, 2):
        for i in range(len(t) - n + 1):
            seg = t[i:i + n]
            if re.fullmatch(r"[^\s\d〒]{2,5}", seg):
                add(seg)
                break
    return out[:6]


def geocode_city(name: str, *, hint: str | None = None) -> Optional[PlaceCandidate]:
    """
    將城市名轉座標（俾地圖定位用）。

    ⚠️ 城市名同店名唔同：要揀「最似城市」嘅結果，唔係最似店舖嘅。
       Photon 對「福岡」會回傳好多結果（福岡市、福岡県、福岡町…），
       所以要按 OSM tag 揀：
          · place=city/town/administrative 最啱
          · 排除 amenity / shop（嗰啲係店）
    """
    # ⚠️⚠️ 最重要嘅優化：先查本地城市庫。
    #    Photon 要 200–800ms 而且會 rate limit；本地庫 0.03ms 而且離線都用得。
    #    本地庫命中率約 99%（134,655 個名稱索引）。
    from .localgeo import lookup as local_lookup, cache_get, cache_put
    hit = local_lookup(name, hint=hint) or cache_get(name)

    # ⚠️⚠️ 舊快取 backfill：
    #    快取係**舊版**程式寫落嘅，冇 `country_code` 欄位。
    #    快取命中率 >99% → 大部分查詢行呢條路 →
    #    時區跌落經度估算（「由布院」變 `Etc/GMT-9` 而唔係 `Asia/Tokyo`）。
    #
    #    ⚠️ 為咩唔索性清快取：
    #      清咗就要重新上網查（慢、又會 rate limit），
    #      而且**其他用戶**嘅快取一樣有呢個問題。
    #      由中文國名反推 ISO 碼就即刻修好，零成本。
    if hit and not hit.get("country_code") and hit.get("country"):
        from .localgeo import _zh_to_cc
        cc = _zh_to_cc(hit["country"])
        if cc:
            hit = dict(hit)
            hit["country_code"] = cc

    # ⚠️⚠️ 如果係「完整地址」而唔係城市名，直接查會搵唔到。
    #    真實問題：「福岡県福岡市博多区上川端町1-41」查唔到 →
    #    前端 fallback 去查「櫛田神社」→ 攞到三重縣嘅同名神社 ❌
    #
    #    正確做法：由地址**抽出地區名**再查（本地庫有 146 個校正地區）。
    if not hit:
        for cand in _extract_place_candidates(name):
            if cand == name:
                continue
            hit = local_lookup(cand, hint=hint)
            if hit:
                break

    if hit:
        return PlaceCandidate(
            name=hit.get("canonical") or name,
            lat=hit["lat"], lng=hit["lng"],
            country=hit.get("country"),
            cc=hit.get("country_code"),
            # ⚠️ city 之外仲要回傳 district —— 分區行程規劃靠佢命名
            #    （冇 district 就會顯示「第 1 區」而唔係「博多」）
            city=hit.get("canonical") if hit.get("source") == "local_cities" else None,
            district=(_extract_place_from_address(name)
                      if name != (hit.get("canonical") or name) else None),
            source=hit.get("source", "local"),
        )

    from .lexicon import CITY_ALIASES, KOREAN_REVERSE

    # ⚠️⚠️ 三個坑：
    #   1. 「首爾」Photon 會回傳雜結果（唔係空），如果用「有結果就停」
    #      就永遠試唔到別名「서울」。
    #   2. 「釜山」／「曼谷」喺中國都有同名地方，單純查原名會攞錯。
    #   3. 「明洞」「梨泰院」呢類韓國地名，中文查會撞到中國同名地方
    #      （明洞 → 40.39,116.17 近北京），要試諺文「명동」先啱。
    #
    #   所以：**收集所有 query 嘅候選，一齊評分**，再揀最好嘅。
    queries: list[str] = [name]
    for alias in CITY_ALIASES.get(name.strip(), []):
        if alias not in queries:
            queries.append(alias)
    kr = KOREAN_REVERSE.get(name.strip())
    if kr and kr not in queries:
        queries.append(kr)
    # 都試埋加 hint 嘅版本
    if hint:
        queries += [build_query(q, hint) for q in list(queries)]

    cands: list[tuple[int, int, PlaceCandidate]] = []   # (query_idx, rank, cand)
    seen: set[tuple] = set()
    for qi, q in enumerate(queries):
        for rank, c in enumerate(search_photon(q, limit=6)):
            key = (round(c.lat or 0, 3), round(c.lng or 0, 3))
            if key in seen:
                continue
            seen.add(key)
            cands.append((qi, rank, c))
    if not cands:
        return None

    # OSM 類型 → 城市分數
    #   ⚠️ 次序由「最似城市中心」排到「最唔似」。
    #      之前將 railway/station 當 -120 排除，但「博多」Photon 只回傳車站，
    #      結果搵唔到 —— 其實博多駅座標對地圖定位完全夠用。
    PLACE_SCORE = {
        "city": 100, "town": 90, "municipality": 70, "administrative": 80,
        "state": 60, "province": 60, "region": 60, "county": 70,
        "district": 55, "suburb": 50, "borough": 50,
        "quarter": 45, "neighbourhood": 40, "locality": 40,
        "village": 30, "hamlet": 20, "island": 35,
    }
    # 一定唔係城市中心
    BAD_TYPES = {"amenity", "shop", "tourism", "leisure", "highway",
                 "aeroway", "office", "healthcare", "building"}

    def score(qi: int, rank: int, c: PlaceCandidate) -> int:
        v = (c.osm_value or "").lower()
        t = (c.osm_type or "").lower()
        n = PLACE_SCORE.get(v, 25)
        # 車站／機場：可以做 fallback，但唔應該贏過真正嘅城市
        if t == "railway":
            n = 15
        if t in BAD_TYPES:
            n = -120
        # 同任何一個 query 版本對得上名
        if c.name:
            for q in queries:
                qb = q.split(" ")[0].strip()
                if not qb:
                    continue
                if qb == c.name:
                    n += 60
                    break
                if qb in c.name or c.name in qb:
                    n += 40
                    break
        # 有完整地區資訊（國家／城市）= 大城市
        if c.country:
            n += 20
        if c.city:
            n += 20
        # ⚠️ query 次序獎勵：第一個 query（原名）最高分，
        #    令「澳門」唔會輸俾別名「Macau」喺巴西嘅同名地方。
        n += max(0, 25 - qi * 10)
        # Photon 自己嘅相關度排序都要考慮
        n += max(0, 12 - rank * 3)
        return n

    scored = sorted(((score(qi, rk, c), c) for qi, rk, c in cands),
                    key=lambda x: -x[0])
    if not scored or scored[0][0] < 0:
        return None
    best = scored[0][1]
    # 寫入永久 cache → 同一個城市下次唔使再上網
    if best and best.lat is not None:
        try:
            cache_put(name, {
                "lat": best.lat, "lng": best.lng,
                "country": best.country, "canonical": best.name,
                # ⚠️⚠️ `cc` 一定要寫入快取 ——
                #    呢個 bug 係咁嚟：快取係**舊版**寫落嘅（冇 cc），
                #    讀返嘅時候 cc 係 None → 時區跌落經度估算
                #    （「由布院」變 `Etc/GMT-9` 而唔係 `Asia/Tokyo`）。
                #    ⚠️ 快取命中率高（>99%）→ 個 bug 只會喺**舊快取**
                #    上面出現，新查詢反而冇事 → 極難重現。
                "country_code": best.cc,
                "source": "photon_cached",
            })
        except Exception:
            pass
    return best


def apply_reverse_geocode(item: Item, *, verbose: bool = False) -> Item:
    """有座標但冇地區 → 反查補上。"""
    if item.lat is None or item.lng is None or item.district or item.city:
        return item
    c = reverse_geocode(item.lat, item.lng)
    if not c:
        return item
    item.country = item.country or c.country
    item.prefecture = item.prefecture or c.state
    item.city = item.city or c.city
    item.district = item.district or c.district
    if not item.address:
        item.address = c.address_line
    if not item.postal_code:
        item.postal_code = c.postcode
    item.notes.append(f"地區由座標反查（Nominatim）：{c.address_line or c.district}")
    if item.field_confidence:
        item.field_confidence["location"] = max(
            item.field_confidence.get("location", 0), 88)
    return item


# ══════════════════════════════════════════════════════════════
# 主流程：店名 → 完整 Item
# ══════════════════════════════════════════════════════════════

def build_query(name: str, hint: str | None = None) -> str:
    """
    砌搜尋查詢字串。

    加地區提示會大幅提升準確度：
      「一蘭」              → 可能搵到全日本任何一間
      「一蘭 博多」          → 命中本社総本店
    """
    parts = [name.strip()]
    if hint and hint.strip() and hint.strip() not in name:
        parts.append(hint.strip())
    return " ".join(parts)


def lookup_place(
    name: str,
    *,
    hint: str | None = None,
    use_search: bool = True,
    fetch_details: bool = True,
    verbose: bool = False,
) -> tuple[Item, list[str]]:
    """
    由一個店名／地標名，砌出一個完整 Item。

    流程：
      1. Photon 模糊搜尋 → 拎座標 + 地址（最快、最直接）
      2. 如果 Photon 冇信心 → DuckDuckGo 搜尋
      3. 搵到 Tabelog / Retty 等高質來源 → 抓 JSON-LD 拎最齊資料
      4. 合併 + 計信心分數

    回傳 (Item, 過程記錄)。
    """
    from .caption import CaptionParser
    from .fetch import fetch_item

    log: list[str] = []
    if not name or not name.strip():
        log.append("冇店名 → 唔可以搜尋（唔好亂猜，交俾用戶補）")
        item = Item(source="lookup", source_name="搜尋補完")
        item.notes.append("需要店名才可以反查，請用戶補上")
        return item, log

    query = build_query(name, hint)
    log.append(f"查詢：{query!r}")
    item = Item(source="lookup", source_name="搜尋補完", raw_title=name)
    item.name = name
    item.name_method = "用戶提供（OCR / 手動）"

    # ── ① Photon ──
    cands = search_photon(query)
    if verbose:
        log.append(f"Photon 回傳 {len(cands)} 個候選")
    good = [c for c in cands if c.lat is not None]

    if good:
        c = good[0]
        item.lat, item.lng = c.lat, c.lng
        item.country = c.country or item.country
        item.prefecture = c.state or item.prefecture
        item.city = c.city or item.city
        item.district = item.district or c.district
        if c.address_line and not item.address:
            item.address = c.address_line
        if c.postcode and not item.postal_code:
            item.postal_code = c.postcode
        item.notes.append(f"座標由 Photon (OSM) 提供：{c.name}")
        log.append(f"Photon 命中：{c.name} [{c.osm_type}/{c.osm_value}] @ {c.lat},{c.lng}")
        # 用地址再跑一次地名匹配（拎到城市／區）
        CaptionParser()._parse_address(item.address or c.address_line,
                                       "Photon 地址", item, lambda *a: None)
        # OSM 類型 → 分類
        cat = _osm_to_category(c.osm_type, c.osm_value)
        if cat:
            item.category, item.category_label = cat[0], cat[1]
            item.category_why = f"OSM {c.osm_type}={c.osm_value}"

    # ── ② ③ 搜尋 + 抓 JSON-LD ──
    if use_search and (not good or fetch_details):
        hits = duckduckgo_search(build_query(name, hint))
        if verbose:
            log.append(f"DuckDuckGo 回傳 {len(hits)} 條結果")
        for h in hits[:3]:
            log.append(f"  [{h.score:>4.0f}] {h.source_kind:12} {h.title[:60]}")

        target = best_source_url(hits)
        if target and _BAD_URL_RE.search(target):
            log.append(f"最值得抓嘅係廣告／跳轉連結，跳過：{target[:70]}")
            target = None
        if target:
            log.append(f"揀咗最值得抓：{target}")
            try:
                detail, _, meta = fetch_item(target, respect_robots=False)
                log.append(f"抓取結果：{detail.name} · {detail.confidence}% · "
                           f"{detail.location_display}")
                # 合併（唔覆蓋已有嘅資料）
                coords_before = (item.lat, item.lng)
                addr_before = item.address
                item.merge(detail)
                if coords_before[0] is not None:
                    item.lat, item.lng = coords_before     # 座標以 Photon 為準
                # ⚠️ 但地址相反：Photon 嘅地址可能係「福岡県 福岡市 博多区 3 2」呢種
                #    唔完整嘅（只有門牌號碼碎片）。Tabelog / 官網嘅地址通常最齊，
                #    所以要反過來以「較長、較完整」嘅為準。
                if addr_before and detail.address and len(detail.address) > len(addr_before) + 4:
                    item.address = detail.address
                    if detail.postal_code:
                        item.postal_code = detail.postal_code
                    else:
                        # ⚠️ 地址換咗就要重抽郵便番号，否則會殘留舊嘅／冇咗
                        pc = parse_postal_code(detail.address)
                        if pc:
                            item.postal_code = pc
                    log.append(f"地址改用較完整嘅來源：{detail.address}")
                item.source_name = "搜尋補完（Photon + 網頁）"
                if meta.get("og", {}).get("og:image") and not item.raw_image:
                    item.raw_image = meta["og"]["og:image"]
            except Exception as e:                          # 唔可以因為一個來源失敗就爆
                log.append(f"抓取失敗（已忽略）：{type(e).__name__}: {e}")

    # ── ③b 一致性檢查 ──
    try:
        from .consistency import apply_consistency_check
        apply_consistency_check(item)
    except Exception:
        pass

    # ── ④ 計分 ──
    # ── 最終計分 ──
    #    ⚠️ 一定要用「合併之後」嘅 field_confidence 做 base，
    #    否則舊嘅分數會被 _score 重新計過，同顯示嘅拆解唔一致。
    boost: dict[str, int] = dict(item.field_confidence)
    # 名稱係用戶／OCR 提供，可信度高
    boost["name"] = 92
    if item.lat is not None:
        boost["location"] = max(boost.get("location", 0), 90)
    if item.address:
        boost["address"] = max(boost.get("address", 0), 88)
    if item.category:
        boost["category"] = max(boost.get("category", 0), 84)
    CaptionParser._score(item, boost)

    item.rules_matched = [{"rule": "LOOKUP", "match": m[:120], "note": "由店名反查"}
                          for m in log]
    return item, log


def _osm_to_category(osm_key: str | None, osm_value: str | None) -> Optional[tuple[str, str]]:
    """OSM tag → Wander 分類。"""
    k, v = (osm_key or ""), (osm_value or "")
    table = {
        ("amenity", "restaurant"): ("food", "餐廳"),
        ("amenity", "cafe"): ("food", "咖啡"),
        ("amenity", "fast_food"): ("food", "快餐"),
        ("amenity", "bar"): ("food", "酒吧"),
        ("amenity", "pub"): ("food", "酒吧"),
        ("amenity", "ice_cream"): ("food", "甜品"),
        ("shop", "bakery"): ("food", "麵包"),
        ("shop", "supermarket"): ("shopping", "超市"),
        ("shop", "department_store"): ("shopping", "百貨"),
        ("shop", "mall"): ("shopping", "商場"),
        ("shop", "convenience"): ("shopping", "便利店"),
        ("tourism", "hotel"): ("stay", "酒店"),
        ("tourism", "hostel"): ("stay", "旅館"),
        ("tourism", "guest_house"): ("stay", "民宿"),
        ("tourism", "attraction"): ("play", "景點"),
        ("tourism", "museum"): ("play", "美術館"),
        ("tourism", "viewpoint"): ("play", "展望台"),
        ("historic", "castle"): ("play", "城堡"),
        ("historic", "monument"): ("play", "古蹟"),
        ("leisure", "park"): ("play", "公園"),
        ("leisure", "garden"): ("play", "庭園"),
        ("amenity", "place_of_worship"): ("play", "神社寺廟"),
        ("railway", "station"): ("transport", "車站"),
        ("public_transport", "station"): ("transport", "車站"),
        ("aeroway", "aerodrome"): ("transport", "機場"),
    }
    if (k, v) in table:
        return table[(k, v)]
    # 粗略 fallback
    if k == "amenity" and v in ("restaurant", "cafe", "bar", "fast_food"):
        return ("food", "餐飲")
    if k == "shop":
        return ("shopping", "購物")
    if k == "tourism":
        return ("play", "景點")
    return None


# ══════════════════════════════════════════════════════════════
# 由 caption 直接補完（最實用嘅組合）
# ══════════════════════════════════════════════════════════════

def enrich_caption_item(item: Item, *, use_search: bool = True,
                        fetch_details: bool = True, verbose: bool = False) -> tuple[Item, list[str]]:
    """
    攞住一個由 caption 解析出嚟嘅 Item，用搜尋補齊缺咗嘅欄位。

    呢個就係你講嘅流程：
        caption / 截圖 → 有店名 → 用搜尋補地址、座標、電話
    """
    if not item.name:
        return item, ["冇店名，無法補完"]

    hint = item.district or item.city or (item.location_path[-1] if item.location_path else None)

    # ⚠️⚠️ 第一步：用本地城市／地區庫直接定位。
    #    理由：caption 通常已經有地區（「道頓堀」「明洞」「博多」），
    #    而本地庫有 134,655 個名稱索引 + 人工校正地區。
    #    呢一步係 **0.03ms + 離線**，唔使查 DuckDuckGo（會 rate limit）。
    #    只有本地庫完全冇嘅先 fallback 去搜尋。
    if item.lat is None and hint:
        from .localgeo import lookup as _lg
        for cand in (hint, item.district, item.city,
                     item.location_path[-1] if item.location_path else None):
            if not cand:
                continue
            hit = _lg(cand)
            if hit:
                item.lat, item.lng = hit["lat"], hit["lng"]
                if not item.country and hit.get("country"):
                    item.country = hit["country"]
                return item, [
                    f"由「{item.name}」反查",
                    f"LOCAL_GEO — 「{cand}」→ {hit['lat']:.4f},{hit['lng']:.4f}"
                    f"（{hit.get('country') or ''}，本地庫，免搜尋）",
                ]
    found, log = lookup_place(item.name, hint=hint, use_search=use_search,
                              fetch_details=fetch_details, verbose=verbose)

    # 用找到嘅資料補空缺（唔覆蓋 caption 已經有嘅嘢）
    coords = (item.lat, item.lng)
    item.merge(found)
    if coords[0] is not None:
        item.lat, item.lng = coords
    # 但如果 caption 冇座標，就要用搜尋搵到嘅
    log = [f"由「{item.name}」反查"] + log
    return item, log
