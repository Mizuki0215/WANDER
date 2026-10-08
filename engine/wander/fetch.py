"""
wander.fetch — 真正抓網頁（呢個就係瀏覽器做唔到嘅部分）

職責：
  1. 跟短連結 redirect（maps.app.goo.gl / xhslink.com / youtu.be）
  2. 抓 og:title / og:description / og:image
  3. 抽 JSON-LD（schema.org 結構化資料）← 呢個係最高價值嘅一層
  4. 抽 <title>、h1 做 fallback

⚠️ 法律／道德注意：
  - 只讀公開 HTML，唔會登入、唔會繞過任何保護
  - 只用官方 oEmbed（YouTube 等）或網站自願公開俾搜尋引擎嘅 JSON-LD
  - 小紅書：唔會嘗試繞過反爬，直接引導用戶貼文字或上傳截圖
  - 建議加 robots.txt 檢查同 rate limit（見 check_robots）
"""
from __future__ import annotations

import json
import os
import re
from urllib.parse import urljoin, urlparse

import html as _html_mod

import requests

from .ua import BROWSER_UA as _BROWSER_UA

DEFAULT_TIMEOUT = 12
# ⚠️ 唔可以加 "WanderBot/0.1" 落 UA —— 好多站會即刻 403（見 ua.py 實測記錄）
UA = _BROWSER_UA

session = requests.Session()
session.headers.update({
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-HK,zh-TW;q=0.9,ja;q=0.8,en;q=0.7",
})


# ══════════════════════════════════════════════════════════════
# HTTP
# ══════════════════════════════════════════════════════════════

# ⚠️⚠️ 極重要嘅實測發現（2026-10）：
#     **Google Maps 短連結用 desktop UA 唔會出 redirect！**
#     desktop UA → HTTP 200 + JS redirect 頁面，HTML 入面完全冇目標 URL
#     mobile UA  → HTTP 302 + Location header，直接有店名同精確座標 ✅
#
#     驗證：
#       desktop: status=200 Location=None
#       iPhone : status=302 Location=https://www.google.com/maps/place/
#                %E6%B3%A2%E6%AD%A2%E5%A0%B4%E9%A3%9F%E5%A0%82.../@35.48,139.62...
MOBILE_UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
             "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 "
             "Mobile/15E148 Safari/604.1")


def _html_unescape(x):
    return _html_mod.unescape(x)


def resolve_short_url(url: str, *, verbose: bool = False) -> str:
    """
    跟短連結。先用 mobile UA（Google 對 mobile 先出 302），
    再試 desktop UA + HTML 內挖 URL。
    """
    # ① mobile UA，唔自動跟 redirect，直接睇 Location header
    for ua in (MOBILE_UA, _BROWSER_UA):
        try:
            r = session.get(url, timeout=DEFAULT_TIMEOUT, allow_redirects=False,
                            headers={"User-Agent": ua})
            loc = r.headers.get("Location")
            if loc:
                return loc
            # 有時要多跳
            if r.status_code in (301, 302, 303, 307, 308) and loc:
                return loc
        except requests.RequestException:
            continue

    # ② 自動跟 redirect
    try:
        r = session.get(url, timeout=DEFAULT_TIMEOUT, allow_redirects=True,
                        headers={"User-Agent": MOBILE_UA})
        if str(r.url) != url:
            return str(r.url)
        # ③ 由 HTML 挖（meta refresh / canonical / 任何 maps URL）
        m = re.search(r'<meta[^>]+http-equiv=["\']refresh["\'][^>]+url=([^"\'>]+)', r.text, re.I)
        if m:
            return _html_unescape(m.group(1))
        m = re.search(r'(https://www\.google\.[a-z.]+/maps/[^"\'<>\s]{20,})', r.text)
        if m:
            return _html_unescape(m.group(1))
    except requests.RequestException:
        pass
    return url


def get_html(url: str) -> tuple[str, str, int]:
    """抓 HTML。回傳 (html, 最終url, status_code)。"""
    try:
        r = session.get(url, timeout=DEFAULT_TIMEOUT, allow_redirects=True)
        return r.text, str(r.url), r.status_code
    except requests.RequestException as e:
        return "", url, 0 if "Max retries" in str(e) else -1


def check_robots(url: str) -> bool | None:
    """
    檢查 robots.txt 有冇禁止。回傳 True=准, False=唔准, None=查唔到。
    做 product 之前一定要開呢個檢查。
    """
    try:
        p = urlparse(url)
        robots_url = f"{p.scheme}://{p.netloc}/robots.txt"
        r = session.get(robots_url, timeout=6)
        if r.status_code != 200:
            return None
        txt = r.text
        # 極簡判斷：搵 "User-agent: *" 之後嘅 Disallow: /
        blocks = re.findall(r"User-agent:\s*\*\s*((?:\n[^\n]*)+)", txt, re.I)
        for block in blocks:
            if re.search(r"^\s*Disallow:\s*/\s*$", block, re.M):
                return False
        return True
    except Exception:
        return None


# ══════════════════════════════════════════════════════════════
# HTML 抽取
# ══════════════════════════════════════════════════════════════

def _unescape(s: str) -> str:
    import html as _h
    return _h.unescape(s or "").strip()


def extract_og(html: str) -> dict[str, str]:
    """抽 Open Graph + Twitter Card + <title>。"""
    out: dict[str, str] = {}

    def meta(prop: str) -> str | None:
        for pat in (
            rf'<meta[^>]+(?:property|name)=["\']{re.escape(prop)}["\'][^>]*content=["\']([^"\']*)["\']',
            rf'<meta[^>]+content=["\']([^"\']*)["\'][^>]*(?:property|name)=["\']{re.escape(prop)}["\']',
        ):
            m = re.search(pat, html, re.I)
            if m:
                return _unescape(m.group(1))
        return None

    for key in ("og:title", "og:description", "og:image", "og:site_name",
                "og:url", "og:type", "twitter:title", "twitter:description",
                "twitter:image", "description", "keywords"):
        v = meta(key)
        if v:
            out[key] = v

    m = re.search(r"<title[^>]*>([^<]*)</title>", html, re.I)
    if m:
        out["_title"] = _unescape(m.group(1))
    return out


def extract_jsonld(html: str) -> list[dict]:
    """抽所有 JSON-LD 區塊（schema.org 結構化資料）—— 最高價值嘅來源。"""
    out: list[dict] = []
    for m in re.finditer(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html, re.I | re.S,
    ):
        raw = m.group(1).strip()
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            # 有時有雜物，試下粗略清理
            try:
                data = json.loads(re.sub(r"^\s*//.*$", "", raw, flags=re.M))
            except Exception:
                continue
        if isinstance(data, list):
            out.extend(d for d in data if isinstance(d, dict))
        elif isinstance(data, dict):
            if "@graph" in data and isinstance(data["@graph"], list):
                out.extend(d for d in data["@graph"] if isinstance(d, dict))
            else:
                out.append(data)
    return out


# schema.org type → Wander 分類
LD_TYPE_TO_CATEGORY = {
    "Restaurant": "food", "CafeOrCoffeeShop": "food", "BarOrPub": "food",
    "FastFoodRestaurant": "food", "Bakery": "food", "IceCreamShop": "food",
    "FoodEstablishment": "food", "LocalBusiness": "shopping", "Store": "shopping",
    "ShoppingCenter": "shopping", "DepartmentStore": "shopping",
    "Hotel": "stay", "LodgingBusiness": "stay", "Hostel": "stay",
    "TouristAttraction": "play", "Museum": "play", "Park": "play",
    "LandmarksOrHistoricalBuildings": "play", "Event": "play",
    "TouristDestination": "play", "AmusementPark": "play", "Zoo": "play",
    "Aquarium": "play", "Place": "other", "TransitStation": "transport",
}


def _ld_address(addr) -> str:
    if isinstance(addr, str):
        return addr
    if isinstance(addr, dict):
        parts = [
            addr.get("postalCode"), addr.get("addressRegion"),
            addr.get("addressLocality"), addr.get("streetAddress"),
        ]
        return " ".join(str(p) for p in parts if p)
    return ""


def _ld_geo(obj: dict):
    geo = obj.get("geo") or {}
    if isinstance(geo, dict):
        try:
            return float(geo.get("latitude")), float(geo.get("longitude"))
        except (TypeError, ValueError):
            return None, None
    return None, None


def jsonld_to_fields(blocks: list[dict], base_url: str = "") -> dict:
    """將 JSON-LD 轉成我哋嘅欄位。揀最似「一個地方」嘅 block。"""
    priority = ["Restaurant", "CafeOrCoffeeShop", "FoodEstablishment", "Hotel",
                "TouristAttraction", "LocalBusiness", "Store", "Museum", "Park", "Place"]
    best = None
    for want in priority:
        for b in blocks:
            t = b.get("@type")
            types = t if isinstance(t, list) else [t]
            if want in types:
                best = b
                break
        if best:
            break
    if best is None and blocks:
        best = blocks[0]
    if not best:
        return {}

    t = best.get("@type")
    types = t if isinstance(t, list) else [t]
    cat = next((LD_TYPE_TO_CATEGORY.get(x) for x in types if LD_TYPE_TO_CATEGORY.get(x)), None)

    img = best.get("image")
    if isinstance(img, list):
        img = img[0] if img else None
    if isinstance(img, dict):
        img = img.get("url")
    if isinstance(img, str) and base_url:
        img = urljoin(base_url, img)

    hours = best.get("openingHours") or best.get("openingHoursSpecification")
    if isinstance(hours, list):
        hours = " / ".join(str(h) for h in hours[:3])
    elif isinstance(hours, dict):
        hours = None

    rating = ""
    ar = best.get("aggregateRating")
    if isinstance(ar, dict) and ar.get("ratingValue"):
        rating = f"{ar['ratingValue']}"
        if ar.get("reviewCount") or ar.get("ratingCount"):
            rating += f" ({ar.get('reviewCount') or ar.get('ratingCount')} 則)"

    lat, lng = _ld_geo(best)

    return {
        "name": best.get("name"),
        "address": _ld_address(best.get("address")),
        "phone": best.get("telephone"),
        "hours": hours if isinstance(hours, str) else None,
        "price": best.get("priceRange") or (
            f"{best['priceRange']}" if best.get("priceRange") else None),
        "image": img,
        "url": best.get("url") or base_url,
        "category": cat,
        "rating": rating or None,
        "lat": lat, "lng": lng,
        "description": best.get("description"),
    }


# ══════════════════════════════════════════════════════════════
# 各來源嘅抓取策略
# ══════════════════════════════════════════════════════════════

IG_CAPTION_RE = re.compile(
    r'^(.{1,60}?)\s+on\s+Instagram\s*[:\-]\s*[「"\']?(.*?)[」"\']?\s*$', re.S | re.I)

# r.jina.ai：免費嘅「reader」服務，會用自己嘅渲染器拎到頁面內容。
# ⚠️ 呢個係第三方服務 —— 有 rate limit，唔好當佢係唯一方案。
#    但佢係目前唯一免費而過到 IG 登入牆嘅方法。
JINA_READER = "https://r.jina.ai/"

# 瀏覽器 UA —— 唔可以用自訂 UA，Cloudflare 會 403
from .ua import BROWSER_UA as _BROWSER_UA


def _jina_headers() -> dict[str, str]:
    """
    r.jina.ai 嘅 headers。

    冇 key：免費但要排隊，實測好容易被 Cloudflare 擋（403）。
    有 key：去 https://jina.ai/reader 拎免費 key，放喺環境變數
           WANDER_JINA_KEY。有 key 之後穩定好多。
    """
    h = {"User-Agent": _BROWSER_UA, "Accept": "text/plain,*/*"}
    key = os.environ.get("WANDER_JINA_KEY") or os.environ.get("JINA_API_KEY")
    if key:
        h["Authorization"] = f"Bearer {key}"
        h["X-Return-Format"] = "markdown"
    return h


def fetch_via_jina(url: str, timeout: int = 30) -> dict | None:
    """
    用 r.jina.ai 拎頁面內容（回傳 markdown 文字）。

    實測記錄（2026-10）：
      ✓ 第一次試：IG 貼文完全過到登入牆，拎到 caption 全文 + 創作者名
      ✗ 之後連續幾次：403 "Just a moment..."（Cloudflare rate limit）
      → 所以呢個係「有機會得」而唔係「一定得」。

    兩個陷阱（踩過）：
      1. 用自訂 User-Agent（例如 "WanderBot/0.1"）一定 403，要用普通瀏覽器 UA
      2. 免費用戶有嚴格 rate limit，唔可以當佢係生產級方案

    回傳 {"title":…, "text":…, "markdown":…, "images":[…]} 或 None。
    """
    try:
        r = requests.get(JINA_READER + url, timeout=timeout, headers=_jina_headers())
        if r.status_code != 200 or not r.text.strip():
            return None
        raw = r.text
        if "<title>Just a moment" in raw[:400]:
            return None                 # Cloudflare 挑戰
    except requests.RequestException:
        return None

    out: dict = {"markdown": raw, "title": None, "text": raw, "images": []}

    m = re.search(r"^Title:\s*(.+)$", raw, re.M)
    if m:
        out["title"] = m.group(1).strip()

    m = re.search(r"^Markdown Content:\s*$", raw, re.M)
    if m:
        out["text"] = raw[m.end():].strip()

    for m in re.finditer(r"!\[[^\]]*\]\((https?://[^)\s]+)\)", raw):
        out["images"].append(m.group(1))

    return out


def parse_instagram_via_reader(url: str) -> dict:
    """用 reader 服務解析 IG：抽出創作者 + caption。"""
    out = {"author": None, "caption": None, "image": None, "title_raw": None,
           "blocked": False, "method": "r.jina.ai"}
    res = fetch_via_jina(url)
    if not res:
        out["blocked"] = True
        return out

    title = res.get("title") or ""
    out["title_raw"] = title

    # 格式：`<創作者> on Instagram: "<caption 開始>`
    m = IG_CAPTION_RE.match(title)
    if m:
        out["author"] = m.group(1).strip()
        head = m.group(2).strip()
    else:
        head = title

    body = (res.get("text") or "").strip()
    # reader 回傳嘅 body 通常第一行就係 title，重複咗
    lines = body.split("\n")
    if lines and lines[0].strip().startswith("Title:"):
        lines = lines[1:]
    caption = "\n".join(lines).strip()

    if not caption and head:
        caption = head
    out["caption"] = caption or None
    if res.get("images"):
        out["image"] = res["images"][0]
    return out



IG_JUNK_TITLES = {"instagram", "login", "log in", "instagram • photos and videos",
                  "instagram photos and videos"}


def parse_instagram_html(html: str) -> dict:
    """
    由 IG 公開頁面抽資料。

    實情（2026-10 實測）：
      - server-side 請求一律 302 去 /accounts/login/，**完全冇 og:* 標籤**
      - 所以呢個函式多數會回傳 caption=None，然後由 reader 服務接手
      - 唯一例外：某啲地區／快取可能有 og:title

    回傳 caption 只會喺「真係似 caption」嘅情況 —— 唔可以將頁面標題
    「Instagram」當成 caption，否則會毒死後面成條 pipeline。
    """
    og = extract_og(html)
    title = (og.get("og:title") or og.get("_title") or "").strip()
    desc = (og.get("og:description") or "").strip()

    out: dict = {
        "image": og.get("og:image") or og.get("twitter:image"),
        "title_raw": title or None,
        "caption": None,
        "author": None,
        "blocked": False,
    }

    if title.lower() in IG_JUNK_TITLES or re.search(r"(log in|登入|login •)", title, re.I):
        out["blocked"] = True

    m = IG_CAPTION_RE.match(title)
    if m:
        out["author"] = m.group(1).strip()
        out["caption"] = m.group(2).strip()

    # og:description 有時有更多內容
    if desc:
        m2 = IG_CAPTION_RE.match(desc)
        cand = (m2.group(2) if m2 else desc).strip()
        if len(cand) > len(out["caption"] or "") and cand.lower() not in IG_JUNK_TITLES:
            out["caption"] = cand

    if not out["caption"]:
        out["blocked"] = True
    return out


def parse_oembed(url: str) -> dict | None:
    """用官方 oEmbed（免費、合法）。支援 YouTube / Vimeo / TikTok 等。"""
    endpoints = [
        ("https://www.youtube.com/oembed", "youtube"),
        ("https://vimeo.com/api/oembed.json", "vimeo"),
        ("https://www.tiktok.com/oembed", "tiktok"),
    ]
    host = urlparse(url).hostname or ""
    for base, key in endpoints:
        if key not in host:
            continue
        try:
            r = session.get(base, params={"url": url, "format": "json"}, timeout=8)
            if r.status_code == 200:
                d = r.json()
                return {
                    "name": d.get("title"),
                    "image": d.get("thumbnail_url"),
                    "author": d.get("author_name"),
                    "caption": d.get("title"),
                }
        except Exception:
            return None
    return None


def _maybe_reverse_geocode(item, trace: list, log) -> None:
    """
    有座標但冇地區 → 用 Nominatim 反查補上。

    ⚠️ 真實需要：Google Maps 短連結解析完只有店名 + 座標，
       URL 入面完全冇「神奈川県」或「鶴見区」。
    """
    if item.lat is None or item.lng is None or item.district or item.city:
        return
    try:
        from .lookup import apply_reverse_geocode
        apply_reverse_geocode(item, verbose=True)
        if item.district or item.city:
            log("REVERSE_GEOCODE", item.location_display,
                "有座標冇地區 → 反查（Nominatim，免費）")
            from .caption import CaptionParser
            CaptionParser._score(item, {"location": 88})
    except Exception as e:                      # 反查失敗唔可以影響其他資料
        log("REVERSE_GEOCODE_FAIL", f"{type(e).__name__}: {e}"[:60],
            "反查失敗，唔影響其他欄位")


def fetch_item(url: str, *, respect_robots: bool = True,
               caption_override: str | None = None):
    """
    主入口：抓一個 URL，回傳 (Item, 過程記錄, 原始 meta)。

    流程：
      0. robots.txt 檢查（可選）
      1. 短連結 → 跟 redirect
      2. 重新分類（redirect 之後可能唔同咗）
      3. 按來源揀策略：
         - Google Maps → 直接結構解析（唔使抓 HTML）
         - YouTube / TikTok → oEmbed（免費官方）
         - IG → 抓 HTML 抽 og:*（會受登入牆影響）
         - 其他網站 → 抓 HTML 抽 JSON-LD + og:*
      4. 將抽出嘅文字餵俾 CaptionParser
      5. 用 JSON-LD 嘅結構化欄位補強（地址、電話、時間、座標）
    """
    from .caption import CaptionParser
    from .links import classify, parse_gmaps
    from .models import Item

    trace: list[dict[str, str]] = []
    raw_meta: dict = {}
    final_url = url

    def log(rule: str, match: str, note: str) -> None:
        trace.append({"rule": rule, "match": match[:300], "note": note})

    log("INPUT", url, "輸入 URL")

    if respect_robots:
        allowed = check_robots(url)
        log("ROBOTS", {True: "允許", False: "禁止", None: "查唔到"}[allowed],
            "robots.txt 檢查")
        if allowed is False:
            item = Item(source="blocked", source_name="被 robots.txt 禁止", url=url)
            item.notes.append("robots.txt 唔准抓取，已停止")
            return item, trace, raw_meta

    # ① 短連結
    from .links import is_short_link
    if is_short_link(url):
        final_url = resolve_short_url(url)
        log("REDIRECT", final_url, "跟蹤短連結")
        if final_url != url and "google" in final_url and "/maps" in final_url:
            item, _ = parse_gmaps(final_url)
            item.url = url
            item.notes.append(f"短連結展開 → {final_url}")
            trace.extend(item.rules_matched)
            log("GMAPS_FROM_SHORT", final_url, "展開後直接結構解析成功")
            # ⚠️ 短連結呢條路徑都要做座標反查，否則會冇地區
            _maybe_reverse_geocode(item, trace, log)
            return item, trace, raw_meta

    kind = classify(final_url)
    log("CLASSIFY", kind["name"], f"來源：{kind['id']}（{kind['host']}）")

    # ② Google Maps：唔使抓 HTML
    if kind["id"] == "gmaps":
        item, steps = parse_gmaps(final_url)
        item.url = url
        trace.extend(steps)
        # ⚠️ Maps link 好多時只有座標冇地區名 → 反查補上
        _maybe_reverse_geocode(item, trace, log)
        return item, trace, raw_meta

    # ③ 官方 oEmbed（YouTube / TikTok）
    if kind["id"] in ("youtube", "tiktok"):
        oe = parse_oembed(final_url)
        if oe:
            raw_meta["oembed"] = oe
            log("OEMBED", oe.get("name") or "", "官方 oEmbed 成功（免費）")
            text = "\n".join(filter(None, [oe.get("name"), oe.get("caption")]))
            item = CaptionParser().parse(text, source=kind["id"], source_name=kind["name"],
                                         url=url, raw_image=oe.get("image"))
            item.raw_title = oe.get("name")
            item.rules_matched = trace + item.rules_matched
            return item, trace, raw_meta

    # ④ 小紅書：唔嘗試繞過，直接引導
    if kind["id"] == "xiaohongshu":
        item = Item(source="xiaohongshu", source_name="小紅書", url=url)
        item.notes.append("反爬嚴格，唔會嘗試繞過。請用戶貼 caption 文字或上傳截圖。")
        log("XHS_SKIP", kind["host"], "建議改用「貼文字」或「截圖上傳」")
        item.rules_matched = trace
        return item, trace, raw_meta

    # ⑤ 抓 HTML
    html, got_url, status = get_html(final_url)
    log("HTTP", f"{status}", f"抓取完成（{len(html)} bytes）")
    if html:
        raw_meta["html_len"] = len(html)

    # ⑥ JSON-LD（最高價值）
    ld_fields: dict = {}
    if html:
        blocks = extract_jsonld(html)
        if blocks:
            log("JSONLD", f"{len(blocks)} 個 block",
                "網站自願公開俾搜尋引擎嘅結構化資料（合法、最準）")
            ld_fields = jsonld_to_fields(blocks, got_url)
            raw_meta["jsonld"] = ld_fields
            if ld_fields.get("name"):
                log("JSONLD_NAME", str(ld_fields["name"]), "由 JSON-LD 抽到名")
            if ld_fields.get("address"):
                log("JSONLD_ADDR", str(ld_fields["address"]), "由 JSON-LD 抽到地址")
        else:
            log("JSONLD", "(無)", "呢個網站冇結構化資料")

    # ⑦ og:* / IG 特化
    text_for_parser = ""
    img = None
    item_author: str | None = None
    item_needs_caption = False
    if html:
        if kind["id"] == "instagram":
            ig = parse_instagram_html(html)
            raw_meta["instagram"] = ig
            got_caption = bool(ig.get("caption"))

            # ⚠️ 實測（2026-10）：IG 而家對所有未登入嘅 server-side 請求
            #    一律 redirect 去 /accounts/login/，完全冇 og:* 標籤。
            #    所以一定要有 fallback，否則 IG 等於完全冇用。
            if not got_caption or ig.get("blocked"):
                log("IG_WALL", "登入牆 / 無 og 標籤",
                    "IG 唔俾未登入用戶睇內容 → 轉用 reader 服務")
                rd = parse_instagram_via_reader(final_url)
                if rd.get("caption"):
                    ig = rd
                    got_caption = True
                    raw_meta["instagram"] = rd
                    log("IG_READER", (rd.get("author") or "")[:40],
                        "r.jina.ai reader 成功繞過（第三方免費服務）")
                else:
                    # ⚠️ 第二條路：第三方抓取服務（要用戶自己配置 API key）
                    #    「點解人哋啲 app 做到？」→ 佢哋俾錢買呢啲服務。
                    #    冇配置就完全唔會行（維持免費）。
                    from .igprovider import fetch_post, is_configured
                    got_third = None
                    if is_configured():
                        res = fetch_post(final_url)
                        if res and res.get("caption"):
                            got_third = res
                    if got_third:
                        ig = {"caption": got_third["caption"],
                              "author": got_third.get("author")}
                        got_caption = True
                        raw_meta["instagram"] = ig
                        log("IG_PROVIDER", got_third.get("source", ""),
                            "第三方服務成功繞過（用家自己配置嘅 API key）")
                    else:
                        log("IG_READER_FAIL", "自動抓取全部失敗 → 交俾用戶貼 caption",
                            "IG 登入牆完全封死。可以用書籤小工具，或者配置 "
                            "WANDER_IG_KEY 用第三方服務")
                        item_needs_caption = True

            if ig.get("caption"):
                log("IG_CAPTION", ig["caption"][:120], "抽到 caption 全文")
                text_for_parser = ig["caption"]
            if ig.get("author"):
                item_author = ig["author"]
                raw_meta["author"] = item_author
            if ig.get("image"):
                img = ig["image"]
                log("OG_IMAGE", img[:80], "封面圖")
        else:
            og = extract_og(html)
            raw_meta["og"] = og
            parts = [og.get("og:title"), og.get("og:description")]
            text_for_parser = "\n".join(p for p in parts if p)
            img = og.get("og:image") or og.get("twitter:image")
            if og.get("og:title"):
                log("OG_TITLE", og["og:title"][:120], "og:title")
            if og.get("og:description"):
                log("OG_DESC", og["og:description"][:120], "og:description")
            if img:
                log("OG_IMAGE", img[:80], "封面圖")

    # 用戶自己貼嘅 caption 優先（法律最乾淨、資料最齊）
    if caption_override:
        text_for_parser = caption_override
        log("CAPTION_OVERRIDE", caption_override[:120], "用咗用戶提供嘅文字")

    # ⑧ 文字解析
    text_for_parser = (text_for_parser or "").strip()
    if text_for_parser:
        item = CaptionParser().parse(text_for_parser, source=kind["id"],
                                     source_name=kind["name"], url=url, raw_image=img)
    else:
        item = Item(source=kind["id"], source_name=kind["name"], url=url, raw_image=img)
        item.notes.append("抓唔到可用文字（可能要登入，或者係純圖／JS 網站）")

    item.raw_title = (raw_meta.get("og", {}).get("og:title")
                      or raw_meta.get("instagram", {}).get("title_raw")
                      or raw_meta.get("oembed", {}).get("name"))

    # ⑨ 用 JSON-LD 結構化欄位補強（比 regex 可靠，所以優先）
    boost: dict[str, int] = {}
    if ld_fields:
        if ld_fields.get("name") and (not item.name or len(str(ld_fields["name"])) > 2):
            item.name = str(ld_fields["name"]).strip()
            item.name_method = "JSON-LD 結構化資料"
            boost["name"] = 98
            log("MERGE_LD_NAME", item.name, "用 JSON-LD 名稱覆蓋（更準）")
        if ld_fields.get("address"):
            item.address = str(ld_fields["address"]).strip()
            boost["address"] = 96
            # 地址再跑一次地名匹配（用同一個 parser 實例）
            parser = CaptionParser()
            parser._parse_address(item.address, "JSON-LD 地址", item, lambda *a: None)
            log("MERGE_LD_ADDR", item.address, "用 JSON-LD 地址覆蓋")
        if ld_fields.get("phone"):
            item.phone = str(ld_fields["phone"]).strip()
            boost["phone"] = 96
        if ld_fields.get("hours"):
            item.hours = str(ld_fields["hours"]).strip()[:80]
            boost["hours"] = 92
        if ld_fields.get("price"):
            item.price = str(ld_fields["price"]).strip()
            boost["price"] = 90
        if ld_fields.get("category"):
            item.category = ld_fields["category"]
            item.category_label = item.category_label or None
            boost["category"] = 96
        if ld_fields.get("image"):
            item.raw_image = ld_fields["image"]
        if ld_fields.get("rating"):
            item.tags.append(f"⭐ {ld_fields['rating']}")
        if ld_fields.get("lat") and ld_fields.get("lng"):
            item.lat, item.lng = ld_fields["lat"], ld_fields["lng"]
            boost["location"] = 98
            log("MERGE_LD_GEO", f"{item.lat},{item.lng}", "由 JSON-LD 抽到座標")

    # ⑨b IG 封鎖 → 標記要用戶貼 caption
    if item_needs_caption:
        item.needs_input = "caption"
        item.blocked_reason = "instagram_login_wall"
        item.notes.append(
            "IG 封鎖咗自動讀取（回傳登入頁，零資料）。"
            "請喺 IG 撳「⋯」→「複製文字」，再貼落嚟。")
        # 信心歸零 —— 因為真係乜都抽唔到
        item.confidence = 0
        item.needs_review = True

    # ⑩ 補充來源資訊
    if item_author:
        item.notes.append(f"創作者：{item_author}")
    if kind["id"] == "instagram":
        # 提醒 app 層：呢個結果可能係第三方 reader 拎到，要標明
        if raw_meta.get("instagram", {}).get("method") == "r.jina.ai":
            item.notes.append("caption 經第三方 reader 服務取得（可能有 rate limit）")

    # ⑪ 由網站標題補地區
    #    Tabelog / ホットペッパー / Retty 嘅標題格式係「店名 (最寄駅/類別)」，
    #    個「最寄駅」其實就係地區資訊，而 JSON-LD 嘅地址未必對得上詞典。
    enrich_from_title(item, raw_meta, log)

    # ⑫ 一致性檢查：地址同座標係咪同一地方
    #     ⚠️ 真實案例：Google Maps link 可以俾到「福岡地址 + 東京座標」。
    #        唔檢查就會令用戶搭幾個鐘車去錯地方。
    try:
        from .consistency import apply_consistency_check
        before = len(item.notes)
        apply_consistency_check(item)
        if len(item.notes) > before:
            log("CONSISTENCY_WARN", item.notes[-1][:110],
                "地址同座標唔一致 → 已標記，要人手確認")
    except Exception as e:
        log("CONSISTENCY_FAIL", f"{type(e).__name__}"[:50], "檢查失敗，唔影響其他資料")

    # ⑬ 重新計分
    if boost:
        CaptionParser._score(item, boost)

    item.rules_matched = trace + item.rules_matched
    return item, trace, raw_meta


def enrich_from_title(item, raw_meta: dict, log) -> None:
    """由 og:title / oembed title 補地區同分類。"""
    title = (item.raw_title
             or raw_meta.get("og", {}).get("og:title")
             or raw_meta.get("instagram", {}).get("title_raw")
             or raw_meta.get("oembed", {}).get("name")
             or "")
    if not title:
        return

    # 「官兵衛うどん (長者原/うどん)」→ 長者原 + うどん
    m = re.search(r"[（(]([^/）)]+)\s*/\s*([^）)]+)[）)]", title)
    if m:
        area, kind_word = m.group(1).strip(), m.group(2).strip()
        if area and not item.district and 1 <= len(area) <= 8:
            item.district = area
            item.notes.append(f"地區由網站標題推定：{area}（最寄駅／町名）")
            log("TITLE_AREA", area, f"由標題「({area}/{kind_word})」抽出地區")
        if kind_word and not item.category:
            from .caption import CaptionParser
            tmp = Item()
            CaptionParser._extract_category(kind_word, tmp, lambda *a: None)
            if tmp.category:
                item.category = tmp.category
                item.category_label = tmp.category_label
                item.category_why = kind_word
                log("TITLE_CATEGORY", kind_word, f"由標題類別抽出分類：{tmp.category}")

    # 地址排版：日本地址黐埋一齊難睇，插入分隔
    if item.address:
        addr = re.sub(r"(県|縣|都|道|府)(?=[^\s])", r"\1 ", item.address)
        addr = re.sub(r"(郡)(?=[^\s])", r"\1 ", addr)
        addr = re.sub(r"(市|区|區|町|村)(?=[^\s])", r"\1 ", addr)
        addr = re.sub(r"\s{2,}", " ", addr).strip()
        item.address = addr

        # ⚠️ 排版之後一定要重算 address_tail —— 加咗空格之後，
        #    tail_address 會行另一條 code path（最後一段），結果唔同。
        #    呢個 bug 令「番地」錯誤顯示成完整地址。
        from .lexicon import tail_address
        new_tail = tail_address(addr)
        if new_tail:
            item.address_tail = new_tail
            log("ADDR_TAIL_REFRESH", new_tail, "地址排版後重算番地")
