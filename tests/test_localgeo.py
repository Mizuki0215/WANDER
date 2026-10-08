"""
本地城市庫測試
==============
⚠️ 為咩要本地庫（用戶提議）：
   每次查 Photon 要 200–800ms 而且會 rate limit（實測連續查十幾個就冇反應）。
   世界重點城市座標唔會變 —— 冇理由每次上網查。

最重要嘅斷言：**唔可以攞錯同名地方**。
   「梅田」喺埼玉都有、「安平」喺河北都有、「祇園」喺広島都有。
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "engine"))

from wander.localgeo import lookup, norm, search, stats  # noqa: E402


class TestDatabase:
    def test_loaded(self):
        s = stats()
        assert s["cities"] > 100_000, f"城市庫太小: {s}"
        assert s["districts"] >= 100, f"地區庫太小: {s}"

    def test_fast(self):
        """本地查詢要快過 1ms（對比 Photon 200–800ms）。"""
        lookup("福岡")            # warm up
        t0 = time.perf_counter()
        for _ in range(100):
            lookup("福岡")
        dt = (time.perf_counter() - t0) / 100 * 1000
        assert dt < 2, f"太慢: {dt:.2f}ms"


class TestNormalization:
    @pytest.mark.parametrize("a,b", [
        ("Fukuoka", "fukuoka"),
        ("福岡", "福岡"),
        ("台北", "臺北"),          # 臺/台 統一
        ("香港島", "香港島"),
        ("New York", "newyork"),
    ])
    def test_same_key(self, a, b):
        assert norm(a) == norm(b)


class TestMajorCities:
    @pytest.mark.parametrize("city,country,lat,lng", [
        ("福岡", "日本", 33.6, 130.42),
        ("首爾", "韓國", 37.57, 126.98),
        ("서울", "韓國", 37.57, 126.98),
        ("Tokyo", "日本", 35.69, 139.69),
        ("Paris", "法國", 48.85, 2.35),
        ("London", "英國", 51.51, -0.13),
        ("台北", "台灣", 25.05, 121.53),
        ("曼谷", "泰國", 13.75, 100.50),
        ("雪梨", "澳洲", -33.87, 151.21),
        ("杜拜", "阿聯酋", 25.08, 55.31),
    ])
    def test_coords(self, city, country, lat, lng):
        r = lookup(city)
        assert r, f"搵唔到 {city}"
        assert r["country"] == country, f"{city} 國家錯: {r['country']}"
        assert abs(r["lat"] - lat) < 0.5, f"{city} 緯度偏差: {r['lat']}"
        assert abs(r["lng"] - lng) < 0.5, f"{city} 經度偏差: {r['lng']}"


class TestNoHomonymMixup:
    """
    ⚠️ 最重要：同名地方唔可以攞錯。

    呢啲全部係實測踩過嘅坑（Photon / GeoNames 攞錯城市）：
       梅田  → 埼玉縣嘅梅田      ❌ 應該係大阪
       安平  → 河北安平縣        ❌ 應該係台南
       祇園  → 広島附近嘅祇園町   ❌ 應該係福岡
       西門町 → 日本嘅西門町      ❌ 應該係台北
    """

    @pytest.mark.parametrize("name,country,lat,lng", [
        ("梅田", "日本", 34.70, 135.50),
        ("安平", "台灣", 23.00, 120.17),
        ("祇園", "日本", 33.59, 130.42),
        ("西門町", "台灣", 25.04, 121.51),
        ("心齋橋", "日本", 34.67, 135.50),
        ("明洞", "韓國", 37.56, 126.98),
        ("銅鑼灣", "香港", 22.28, 114.19),
    ])
    def test_correct_city(self, name, country, lat, lng):
        r = lookup(name)
        assert r, f"搵唔到 {name}"
        assert r["country"] == country, f"{name} 國家錯: {r['country']}"
        assert abs(r["lat"] - lat) < 0.1, f"{name} 緯度錯: {r['lat']}"
        assert abs(r["lng"] - lng) < 0.1, f"{name} 經度錯: {r['lng']}"


class TestFukuokaDistricts:
    """用戶主要用福岡，呢啲一定要準。"""

    @pytest.mark.parametrize("name", [
        "博多", "天神", "中洲", "大濠", "薬院", "住吉", "祇園",
        "箱崎", "西新", "大名", "今泉", "春吉", "渡辺通", "百道", "藤崎",
        "太宰府", "糸島", "柳川", "北九州", "小倉", "門司港", "久留米",
    ])
    def test_all_present_and_in_kyushu(self, name):
        r = lookup(name)
        assert r, f"搵唔到 {name}"
        assert r["country"] == "日本"
        # 全部應該喺九州範圍（福岡周邊）
        assert 32.5 < r["lat"] < 34.5, f"{name} 緯度唔似九州: {r['lat']}"
        assert 129.5 < r["lng"] < 131.5, f"{name} 經度唔似九州: {r['lng']}"


class TestSingleCharNames:
    """日文有單字地名（「栄」名古屋）。"""

    def test_sakae(self):
        r = lookup("栄")
        assert r, "「栄」搵唔到"
        assert r["country"] == "日本"

    def test_empty_returns_none(self):
        assert lookup("") is None
        assert lookup("   ") is None


class TestSearch:
    def test_prefix(self):
        rs = search("福岡", limit=5)
        assert rs
        assert any("Fukuoka" in r["query"] or "福岡" in r["query"] for r in rs)

    def test_single_char_works(self):
        """
        ⚠️ 單一個字**應該**有結果 —— 用戶要求：
           「你例如打某些字，咁然後就會出對應近似嘅答案俾你」

           一個中文字已經好有指向性（「香」→ 香港、「福」→ 福州／福岡）。
           原本 ≥2 個字先搜，但咁樣用戶打第一個字冇反應，會以為壞咗。
        """
        assert search("f"), "打一個英文字母應該有結果"
        assert search("香"), "打一個中文字應該有結果"
        assert search("福")

    def test_empty(self):
        assert search("") == []
        assert search("   ") == []

    def test_ranking_canonical_first(self):
        """
        ⚠️⚠️ 呢個係真實用戶問題：
           打 "hong" 應該出 **Hong Kong** 而唔係 Hangzhou。

           原因：索引包含**任何語言嘅別名**，
           Hangzhou 有韓文羅馬拼音別名 "hongchusu"，
           而佢人口仲多過香港 → 單靠人口排序就會出錯。
        """
        rs = search("hong", limit=5)
        assert rs, "應該有結果"
        assert rs[0]["query"] == "Hong Kong", \
            f"打 hong 應該出 Hong Kong，實際：{[r['query'] for r in rs]}"

    def test_ranking_chinese_query(self):
        """打中文都要出返對應城市。"""
        for q, want in [("香港", "Hong Kong"), ("東京", "Tokyo"), ("首爾", "Seoul"),
                        ("台北", "Taipei")]:
            rs = search(q, limit=5)
            assert rs, f"{q} 應該有結果"
            assert want in rs[0]["query"], \
                f"打「{q}」應該出 {want}，實際：{rs[0]['query']}"

    def test_returns_matched(self):
        """⚠️ 要回傳「匹配到嘅名」—— 用戶打「香港」但正名係 Hong Kong。"""
        rs = search("香港", limit=3)
        assert rs and rs[0].get("matched"), "應該有 matched 欄位"
        assert rs[0]["matched"] != rs[0]["query"] or rs[0]["matched"] == "香港"

    def test_population_present(self):
        rs = search("tokyo", limit=3)
        assert rs and rs[0]["population"] > 0

    def test_limit(self):
        assert len(search("san", limit=3)) <= 3
