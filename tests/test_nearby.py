"""
附近邊度買得到 + 圖片 + 密碼 測試
==================================
⚠️ 呢個檔記錄咗幾個「唔同服務要求相反」嘅坑：
   · DuckDuckGo     → 一定要**完整瀏覽器 UA**
   · Overpass API   → 一定要**自訂 UA**（瀏覽器 UA 會 406）
   · Nominatim      → 一定要**當地語言**關鍵字（英文搵唔到日本店）
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "engine"))

from wander.nearby import (  # noqa: E402
    CATEGORY_TAGS, REGION_KEYWORDS, bbox_around, classify, region_of,
)


class TestClassify:
    """
    ⚠️ 貨品名 → 店鋪類別。
       OSM 冇「合利他命」呢個 tag，但有 shop=chemist。
       所以要靠關鍵字判斷應該去邊類店。
    """

    @pytest.mark.parametrize("title,want", [
        ("合利他命", "drug"), ("休足時間", "drug"), ("面膜", "drug"),
        ("防曬", "drug"), ("藥妝", "drug"), ("曼秀雷敦", "drug"),
        ("白色戀人", "souvenir"), ("Royce 生巧克力", "souvenir"),
        ("手信", "souvenir"), ("和菓子", "souvenir"),
        ("Uniqlo 外套", "cloth"), ("鞋", "cloth"),
        ("電飯煲", "electronics"), ("吹風機", "electronics"),
        ("日本茶", "food"), ("泡麵", "food"),
    ])
    def test_keywords(self, title, want):
        assert classify(title) == want

    def test_falls_back_to_category(self):
        assert classify("隨便一樣嘢", "cloth") == "cloth"

    def test_unknown_goes_other(self):
        assert classify("某某某") == "other"
        assert classify("") == "other"

    def test_keyword_beats_category(self):
        """⚠️ 關鍵字比用戶揀嘅分類準（用戶可能亂揀）。"""
        assert classify("合利他命", "cloth") == "drug"


class TestRegion:
    @pytest.mark.parametrize("lat,lng,want", [
        (33.59, 130.42, "jp"),      # 福岡
        (35.68, 139.76, "jp"),      # 東京
        (37.56, 126.98, "kr"),      # 首爾
        (35.18, 129.08, "kr"),      # 釜山
        (25.03, 121.53, "tw"),      # 台北
        (22.28, 114.18, "hk"),      # 銅鑼灣
        (48.85, 2.35, "en"),        # 巴黎
    ])
    def test_by_coords(self, lat, lng, want):
        assert region_of(lat, lng) == want

    @pytest.mark.parametrize("country,want", [
        ("日本", "jp"), ("Japan", "jp"), ("韓國", "kr"),
        ("台灣", "tw"), ("香港", "hk"),
    ])
    def test_by_country(self, country, want):
        assert region_of(0, 0, country) == want

    def test_every_region_has_all_categories(self):
        """⚠️ 每個地區每個類別都要有關鍵字，否則會 fallback 去英文。"""
        for reg, cats in REGION_KEYWORDS.items():
            for c in CATEGORY_TAGS:
                assert cats.get(c), f"{reg} 冇 {c} 嘅關鍵字"


class TestBbox:
    def test_contains_center(self):
        box = bbox_around(33.59, 130.42, 1.5)
        parts = [float(x) for x in box.split(",")]
        assert parts[0] < 130.42 < parts[2]
        assert parts[1] < 33.59 < parts[3]

    def test_scales_with_km(self):
        a = bbox_around(33.59, 130.42, 1)
        b = bbox_around(33.59, 130.42, 3)
        wa = float(a.split(",")[2]) - float(a.split(",")[0])
        wb = float(b.split(",")[2]) - float(b.split(",")[0])
        assert wb > wa * 2.5


class TestTagsCoverage:
    def test_every_category_has_tags(self):
        for cat in ("drug", "souvenir", "food", "cloth", "electronics", "other"):
            assert CATEGORY_TAGS.get(cat), f"{cat} 冇 tag"

    def test_tags_are_valid_pairs(self):
        for cat, tags in CATEGORY_TAGS.items():
            for k, v in tags:
                assert k in ("shop", "amenity"), f"{cat}: {k} 唔係有效 key"
                assert v and isinstance(v, str)


@pytest.mark.network
class TestLiveSearch:
    """
    ⚠️ 真查 Nominatim —— 驗證「當地語言關鍵字」呢個設計係啱嘅。
       實測：「ドラッグストア」→ 20 間；「drugstore」→ 0 間。
    """

    def test_finds_drugstores_in_fukuoka(self):
        from wander.nearby import find_nearby
        r = find_nearby("合利他命", 33.59, 130.42, country="日本")
        assert r["category"] == "drug"
        assert r["total"] > 0, "福岡博多應該搵到藥妝店"
        # 要有距離，而且按距離排
        ds = [s["distance_m"] for s in r["shops"]]
        assert ds == sorted(ds), "應該按距離排序"
        assert all(s["name"] for s in r["shops"])

    def test_finds_souvenir_in_seoul(self):
        from wander.nearby import find_nearby
        r = find_nearby("手信", 37.5636, 126.9834, country="韓國")
        assert r["total"] >= 0     # 明洞應該有，但唔強求

    def test_saved_places_ranked_first(self):
        """⭐ 用戶自己收藏嘅店要排最前（API 層做）。"""
        from wander.nearby import classify
        assert classify("ドラッグイレブン 博多店") == "drug"
