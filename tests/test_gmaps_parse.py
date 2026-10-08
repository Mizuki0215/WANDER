"""
Google Maps link 解析精準度
=============================

⚠️⚠️ 用戶報：「貼 Google Maps link 之後，解析得唔夠準」

⚠️ 實測捉到 5 個問題：
   ① 店名連埋地址一齊（`一蘭拉麵 本店, 1 Chome-1-1 ...`）
   ② 純座標當咗做店名（`35.6586,139.7454`）
   ③ `place_id:ChIJ...` 當咗做店名（係 Google 內部 ID）
   ④ `dir?destination=` 完全冇解析
   ⑤ 有座標但 country/city 都係 None
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import quote

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))
sys.path.insert(0, str(ROOT / "engine"))

from wander.links import parse_url_offline  # noqa: E402


def P(url: str):
    return parse_url_offline(url)


class TestNameAccuracy:
    """⚠️ ① 店名唔可以連埋地址。"""

    def test_splits_english_address(self):
        """
        ⚠️⚠️ 實測原本出：
           `'一蘭拉麵 本店, 1 Chome-1-1 Hakataekichuogai, Hakata Ward'`
        """
        url = ("https://www.google.com/maps/place/"
               + quote("一蘭拉麵 本店, 1 Chome-1-1 Hakataekichuogai, Hakata Ward")
               + "/@33.59,130.4,17z/data=!3m1!4b1!4m6!3m5!8m2!3d33.5901!4d130.4012")
        it = P(url)
        assert it.name == "一蘭拉麵 本店", f"店名唔啱: {it.name!r}"
        assert "Chome" in (it.address or ""), f"地址唔見咗: {it.address!r}"

    def test_splits_chinese_address(self):
        url = ("https://www.google.com/maps/place/"
               + quote("築地場外市場, 東京都中央区築地4-16-2")
               + "/@35.6654,139.7707,17z")
        it = P(url)
        assert it.name == "築地場外市場", f"店名唔啱: {it.name!r}"
        assert "東京都" in (it.address or ""), f"地址唔啱: {it.address!r}"

    def test_does_not_split_name_with_comma(self):
        """
        ⚠️ 唔可以見逗號就切 —— 有啲店名本身有逗號，
           而且第二段唔似地址。
        """
        url = ("https://www.google.com/maps/place/"
               + quote("Cafe, Bar & Grill") + "/@35.0,139.0,17z")
        it = P(url)
        assert it.name == "Cafe, Bar & Grill", f"唔應該切: {it.name!r}"


class TestNoGarbageNames:
    """⚠️ ②③ 唔可以攞座標或者 Google 內部 ID 做名。"""

    def test_pure_coords_not_a_name(self):
        """
        ⚠️⚠️ 實測原本出 `name='35.6586'`（拆咗做名+地址）。
        """
        it = P("https://www.google.com/maps/place/35.6586,139.7454/@35.6586,139.7454,17z")
        assert not it.name, f"座標唔應該當名: {it.name!r}"
        assert it.lat == pytest.approx(35.6586)
        assert it.lng == pytest.approx(139.7454)

    def test_query_coords_not_a_name(self):
        it = P("https://maps.google.com/?q=35.6586,139.7454")
        assert not it.name, f"座標唔應該當名: {it.name!r}"
        assert it.lat == pytest.approx(35.6586)

    def test_place_id_not_a_name(self):
        """
        ⚠️⚠️ 實測原本出 `name='place_id:ChIJN1t_tDeuEmsRUsoyG83frY4'`。
        """
        it = P("https://www.google.com/maps/place/?q=place_id:ChIJN1t_tDeuEmsRUsoyG83frY4")
        assert not it.name, f"place_id 唔應該當名: {it.name!r}"

    def test_bare_chij_not_a_name(self):
        it = P("https://www.google.com/maps/place/?q=ChIJN1t_tDeuEmsRUsoyG83frY4")
        assert not it.name, f"ChIJ id 唔應該當名: {it.name!r}"


class TestDestinationParam:
    """⚠️ ④ `dir?destination=` 之前完全冇解析。"""

    def test_destination_extracted(self):
        it = P("https://www.google.com/maps/dir/?api=1&destination=" + quote("成田機場"))
        assert it.name == "成田機場", f"冇抽到 destination: {it.name!r}"

    def test_origin_extracted_when_no_destination(self):
        it = P("https://www.google.com/maps/dir/?api=1&origin=" + quote("東京站"))
        assert it.name == "東京站", f"冇抽到 origin: {it.name!r}"


class TestReverseGeo:
    """⚠️ ⑤ 有座標但冇地名 → 用座標反查（本機 134k 城市庫）。"""

    def test_coords_give_country(self):
        it = P("https://www.google.com/maps/place/33.5901,130.4012/@33.59,130.4,17z")
        assert it.country == "日本", f"冇反查到國家: {it.country!r}"
        assert it.city, "冇反查到城市"

    def test_seoul_coords(self):
        it = P("https://www.google.com/maps/place/37.5636,126.9827/@37.56,126.98,17z")
        assert it.country == "韓國", f"國家錯: {it.country!r}"

    def test_london_coords(self):
        it = P("https://www.google.com/maps/place/51.5074,-0.1278/@51.5,-0.13,17z")
        assert it.country == "英國", f"國家錯: {it.country!r}"

    def test_ocean_coords_no_country(self):
        """⚠️ 太平洋中央唔應該亂認一個國家。"""
        it = P("https://www.google.com/maps/place/0.0,-140.0/@0,-140,5z")
        assert not it.country, f"海洋唔應該有國家: {it.country!r}"

    def test_nearest_helper_exists(self):
        from wander.localgeo import nearest
        r = nearest(35.6586, 139.7454)
        assert r and r.get("country") == "日本"
        assert r.get("km") is not None, "冇回距離（唔知可唔可靠）"


class TestCoordinatePriority:
    """⚠️ `!3d!4d`（店舖本身）一定要贏過 `@lat,lng`（視窗中心）。"""

    def test_exact_beats_viewport(self):
        url = ("https://www.google.com/maps/place/X/@1.0,2.0,17z/"
               "data=!3m1!4b1!8m2!3d33.5901!4d130.4012")
        it = P(url)
        assert it.lat == pytest.approx(33.5901), f"用咗視窗中心: {it.lat}"
        assert it.lng == pytest.approx(130.4012)

    def test_viewport_used_when_no_exact(self):
        it = P("https://www.google.com/maps/@35.6586,139.7454,15z")
        assert it.lat == pytest.approx(35.6586)


class TestShortLink:
    """⚠️ 短連結要跟 redirect（網絡步驟）—— 離線解析唔到係正常。"""

    def test_short_link_flagged(self):
        it = P("https://maps.app.goo.gl/AbCdEf123456")
        assert not it.name, "短連結唔應該有店名"
        assert any("短連結" in n for n in (it.notes or [])), \
            "冇標記「短連結要跟 redirect」"

    def test_short_link_detected(self):
        from wander.links import is_short_link
        assert is_short_link("https://maps.app.goo.gl/abc")
        assert is_short_link("https://goo.gl/maps/abc")
        assert not is_short_link("https://www.google.com/maps/place/X/@1,2,17z")


class TestURLEncoding:
    """⚠️ URL 編碼要解對（`%E4%B8%80` → 一）。"""

    def test_encoded_chinese_name(self):
        it = P("https://maps.google.com/?q=" + quote("東京鐵塔"))
        assert it.name == "東京鐵塔", f"編碼解錯: {it.name!r}"

    def test_plus_becomes_space(self):
        it = P("https://www.google.com/maps/place/teamLab+Planets/@35.6,139.7,17z")
        assert it.name == "teamLab Planets", f"+ 冇變空格: {it.name!r}"
