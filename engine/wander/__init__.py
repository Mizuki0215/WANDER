"""
Wander 解析引擎
================

由任何來源（Google Maps link、IG caption、Tabelog 網頁、用戶手打）
抽出一個結構化嘅「收藏項目」。

快速開始：
    from wander import parse_caption, parse_url_offline, fetch_item

    # 1. 純文字解析（唔使上網）
    item = parse_caption("地址：〒823-0003 福岡縣宮若市本城65-1 犬鳴川河川公園")
    print(item.name, item.location_display, item.confidence)

    # 2. 只靠 URL 結構解析（Google Maps 極準，唔使上網）
    item = parse_url_offline("https://www.google.com/maps/place/.../@33.59,130.42,17z")

    # 3. 真正抓網頁（要上網）
    item, trace, meta = fetch_item("https://tabelog.com/fukuoka/...")

    # 4. 由店名反查完整資料（截圖 OCR → 店名 → 乜都有）
    from wander import lookup_place
    item, log = lookup_place("一蘭 本社総本店", hint="博多")
    print(item.address, item.lat, item.lng, item.phone)
"""

from .models import (
    CATEGORY_ICONS, CATEGORY_LABELS, Category, DateRange, Item,
)
from . import zones  # noqa: F401
from . import settle  # noqa: F401
from .caption import (
    CaptionParser, normalize, parse_caption, parse_caption_multi,
    parse_postal_code, split_into_venues,
)
from .links import (
    SOURCE_CAPABILITY, classify, is_short_link, parse_gmaps, parse_url_offline,
)
from .fetch import fetch_item, get_html, extract_jsonld, extract_og, jsonld_to_fields
from .lookup import (
    PlaceCandidate, SearchHit, best_source_url, build_query,
    duckduckgo_search, enrich_caption_item, lookup_place,
    search_nominatim, search_photon,
)
from .ua import BROWSER_UA

__version__ = "0.1.0"

__all__ = [
    "Item", "DateRange", "Category",
    "CATEGORY_LABELS", "CATEGORY_ICONS",
    "CaptionParser", "parse_caption", "parse_caption_multi", "normalize",
    "split_into_venues", "parse_postal_code",
    "classify", "parse_gmaps", "parse_url_offline", "is_short_link",
    "SOURCE_CAPABILITY",
    "fetch_item", "get_html", "extract_og", "extract_jsonld", "jsonld_to_fields",
    # 由店名反查
    "lookup_place", "enrich_caption_item", "search_photon", "search_nominatim",
    "duckduckgo_search", "best_source_url", "build_query",
    "PlaceCandidate", "SearchHit", "BROWSER_UA",
    "__version__",
]
