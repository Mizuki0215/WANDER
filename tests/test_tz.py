"""
時區測試
=========
⚠️⚠️ 用戶問：「呢個時間係點樣抽取㗎？…你去旅行嘅話就會入唔同嘅時區呀嘛。」

   呢個測試守住三件事：
     ① 城市座標 → 正確 IANA 時區
     ② 多時區國家（美／加／澳／俄）按經度分帶正確
     ③ `Etc/GMT` 嘅**正負號反轉**（POSIX 遺留陷阱）
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "engine"))

from wander.tz import COUNTRY_TZ, MULTI_TZ, lookup, stats, _by_longitude  # noqa: E402


class TestCountryLookup:
    """單一時區國家 —— 查表唔應該錯。"""

    @pytest.mark.parametrize("lat,lng,cc,want", [
        (35.69, 139.69, "JP", "Asia/Tokyo"),
        (37.57, 126.98, "KR", "Asia/Seoul"),
        (25.05, 121.53, "TW", "Asia/Taipei"),
        (22.28, 114.17, "HK", "Asia/Hong_Kong"),
        (22.20, 113.54, "MO", "Asia/Macau"),
        (13.75, 100.50, "TH", "Asia/Bangkok"),
        (1.35, 103.82, "SG", "Asia/Singapore"),
        (51.51, -0.13, "GB", "Europe/London"),
        (48.85, 2.35, "FR", "Europe/Paris"),
        (52.52, 13.40, "DE", "Europe/Berlin"),
        (41.90, 12.50, "IT", "Europe/Rome"),
        (25.08, 55.31, "AE", "Asia/Dubai"),
        (28.61, 77.21, "IN", "Asia/Kolkata"),
        (-41.29, 174.78, "NZ", "Pacific/Auckland"),
        (39.90, 116.40, "CN", "Asia/Shanghai"),
    ])
    def test_lookup(self, lat, lng, cc, want):
        r = lookup(lat, lng, cc)
        assert r["tz"] == want, f"{cc} 應該係 {want}，實際 {r['tz']}"
        assert r["confident"] is True, f"{cc} 應該係「確定」而唔係估算"

    def test_china_single_zone(self):
        """
        ⚠️ 中國地理上橫跨 5 個時區，但**政治上只用一個**（UTC+8）。
           用經度估算會錯得好厲害（烏魯木齊實際 87°E → 估 UTC+6）。
        """
        # 烏魯木齊（東經 87.6）
        r = lookup(43.83, 87.62, "CN")
        assert r["tz"] == "Asia/Shanghai", \
            f"中國要用單一時區，唔可以按經度分（實際 {r['tz']}）"


class TestMultiZone:
    """
    ⚠️⚠️ 多時區國家 —— 呢個 class 捉到一個真 bug。

       第一版將 `(西邊界, tz)` 寫成 `(東邊界, tz)`：
         "US": [(-124, LA), (-114, Phoenix), ...]
       條件 `lng < upper` → 全部向東串移一格：
         紐約（-74）→ Halifax ❌
         芝加哥（-87.6）→ 紐約 ❌
    """

    @pytest.mark.parametrize("lat,lng,cc,want", [
        # 美國
        (40.71, -74.01, "US", "America/New_York"),
        (41.88, -87.63, "US", "America/Chicago"),
        (39.74, -104.99, "US", "America/Denver"),
        (34.05, -118.24, "US", "America/Los_Angeles"),
        (33.45, -112.07, "US", "America/Phoenix"),
        (42.36, -71.06, "US", "America/New_York"),
        (47.61, -122.33, "US", "America/Los_Angeles"),
        # 加拿大
        (49.25, -123.12, "CA", "America/Vancouver"),
        (43.65, -79.38, "CA", "America/Toronto"),
        (45.50, -73.57, "CA", "America/Toronto"),
        # 澳洲
        (-31.95, 115.86, "AU", "Australia/Perth"),
        (-33.87, 151.21, "AU", "Australia/Sydney"),
        (-27.47, 153.03, "AU", "Australia/Sydney"),
        # 俄羅斯
        (55.75, 37.62, "RU", "Europe/Moscow"),
        (43.12, 131.89, "RU", "Asia/Vladivostok"),
        # 巴西
        (-23.55, -46.63, "BR", "America/Sao_Paulo"),
        (-3.12, -60.02, "BR", "America/Manaus"),
        # 墨西哥
        (19.43, -99.13, "MX", "America/Mexico_City"),
        # 西班牙（加那利群島）
        (28.29, -16.62, "ES", "Atlantic/Canary"),
        (40.42, -3.70, "ES", "Europe/Madrid"),
    ])
    def test_multi(self, lat, lng, cc, want):
        r = lookup(lat, lng, cc)
        assert r["tz"] == want, f"{cc} {lng} 應該係 {want}，實際 {r['tz']}"

    def test_bands_ordered_west_to_east(self):
        """
        ⚠️⚠️ 波段一定要**由西向東**排（遞增），
           而且最後一條要係**大正數**（東邊盡頭）。
           如果最後一條係細數（例如 -999）就永遠都會命中最後一條。
        """
        for cc, bands in MULTI_TZ.items():
            uppers = [u for u, _ in bands]
            assert uppers == sorted(uppers), f"{cc} 波段唔係遞增：{uppers}"
            assert uppers[-1] >= 180, \
                f"{cc} 最後一條上界 {uppers[-1]} 唔夠大（要 ≥180）"

    def test_all_iana_valid(self):
        """
        ⚠️ 所有時區名都要係**有效嘅 IANA 名** ——
           打錯字 `Intl.DateTimeFormat` 會拋 RangeError。
        """
        from zoneinfo import available_timezones
        valid = available_timezones()
        bad = []
        for cc, tz in COUNTRY_TZ.items():
            if tz not in valid:
                bad.append(f"{cc} → {tz}")
        for cc, bands in MULTI_TZ.items():
            for _, tz in bands:
                if tz not in valid:
                    bad.append(f"{cc} → {tz}")
        assert not bad, "無效嘅 IANA 時區名：\n  " + "\n  ".join(bad)


class TestLongitudeFallback:
    """
    ⚠️⚠️ `Etc/GMT` 嘅**正負號係反轉**嘅（POSIX 遺留約定）：
         Etc/GMT-9 = UTC+9（東京）
         Etc/GMT+5 = UTC-5（紐約）
       呢個好易寫錯，所以一定要測。
    """

    @pytest.mark.parametrize("lng,want", [
        (139.69, "Etc/GMT-9"),    # 東京 UTC+9
        (-74.01, "Etc/GMT+5"),    # 紐約 UTC-5
        (-0.13, "Etc/GMT"),       # 倫敦（0°）
        (151.21, "Etc/GMT-10"),   # 悉尼 UTC+10
        (-118.24, "Etc/GMT+8"),   # 洛杉磯 UTC-8
    ])
    def test_sign_inverted(self, lng, want):
        assert _by_longitude(lng) == want, \
            f"經度 {lng} 應該係 {want}（⚠️ Etc/GMT 正負號反轉）"

    def test_unknown_country_falls_back(self):
        r = lookup(35.0, 139.0, "ZZ")
        assert r["source"] == "longitude"
        assert r["confident"] is False, "估算唔可以當「確定」"
        assert r["tz"], "應該有 fallback"

    def test_no_coords(self):
        r = lookup(None, None, None)
        assert r["tz"] is None and r["confident"] is False


class TestStats:
    def test_coverage(self):
        s = stats()
        assert s["countries"] >= 60, f"只有 {s['countries']} 個國家"
        assert s["multi"] >= 6, f"只有 {s['multi']} 個多時區國家"
        assert s["total"] >= 80


class TestCountryCodePlumbing:
    """
    ⚠️⚠️ 時區要正確，**上游一定要傳到 ISO 國家碼**。

       呢個 class 捉到一個真 bug：
         「由布院」「鹿兒島」攞到 `Etc/GMT-9`（經度估算）
         而唔係 `Asia/Tokyo` —— 因為：
           ① 地區庫（districts.json）只存**中文國名**，冇 ISO 碼
           ② 快取係**舊版**寫落嘅，冇 `country_code` 欄位
              （快取命中率 >99% → 大部分查詢行呢條路）
           ③ Photon / Nominatim 路徑冇讀 `countrycode`
    """

    def test_districts_have_cc(self):
        """① 地區庫要有 ISO 碼（由中文國名反推）。"""
        from wander.localgeo import _zh_to_cc, lookup
        assert _zh_to_cc("日本") == "JP"
        assert _zh_to_cc("韓國") == "KR"
        assert _zh_to_cc("台灣") == "TW"
        assert _zh_to_cc("唔存在嘅國") is None
        r = lookup("天神")
        assert r, "搵唔到天神"
        assert r["country_code"] == "JP", \
            f"地區庫冇回 ISO 碼（{r['country_code']}）→ 時區會跌落估算"

    def test_cache_read_backfills_cc(self, monkeypatch):
        """
        ② 舊快取（冇 cc）讀返嗰陣要自動補。

        ⚠️ `geocode_city` 用**函數內部 import**
           （`from .localgeo import ... cache_get ...`）——
           所以一定要 patch `wander.localgeo`，patch `wander.lookup` 冇用
           （實測：AttributeError: module has no attribute 'cache_get'）。
        """
        from wander import localgeo, lookup as L
        old = {"lat": 33.26, "lng": 131.36, "country": "日本",
               "canonical": "由布院", "source": "photon_cached"}
        monkeypatch.setattr(localgeo, "lookup", lambda n, hint=None: None)
        monkeypatch.setattr(localgeo, "cache_get", lambda n: dict(old))
        monkeypatch.setattr(localgeo, "cache_put", lambda n, r: None)
        r = L.geocode_city("由布院ZZZ_唔喺本地庫")
        assert r is not None, "應該由快取攞到"
        assert r.cc == "JP", \
            f"舊快取冇 backfill ISO 碼（cc={r.cc}）→ 時區會變 Etc/GMT-9"

    def test_cache_write_includes_cc(self):
        """③ 寫快取一定要寫 cc（否則下一個人一樣中招）。"""
        src = (ROOT / "engine" / "wander" / "lookup.py").read_text(encoding="utf-8")
        assert '"country_code": best.cc' in src, \
            "寫快取冇寫 country_code → 下一個人一樣中招"

    def test_photon_nominatim_read_cc(self):
        """④ Photon 用 `countrycode`；Nominatim 用 `country_code`。"""
        src = (ROOT / "engine" / "wander" / "lookup.py").read_text(encoding="utf-8")
        assert 'p.get("countrycode")' in src, "Photon 冇讀 countrycode"
        assert 'a.get("country_code")' in src, "Nominatim 冇讀 country_code"

    @pytest.mark.parametrize("city,want", [
        ("福岡", "Asia/Tokyo"),
        ("熊本", "Asia/Tokyo"),
        ("別府", "Asia/Tokyo"),
        ("天神", "Asia/Tokyo"),
        ("首爾", "Asia/Seoul"),
        ("台北", "Asia/Taipei"),
    ])
    def test_end_to_end(self, city, want):
        """⑤ 由城市名一路到時區。"""
        from wander.lookup import geocode_city
        r = geocode_city(city)
        if r is None:
            pytest.skip(f"本地庫冇「{city}」（要上網）")
        got = lookup(r.lat, r.lng, r.cc)
        assert got["tz"] == want, f"{city} → {got['tz']}（要 {want}）"
        assert got["confident"] is True, \
            f"{city} 跌落估算（cc={r.cc}）"
