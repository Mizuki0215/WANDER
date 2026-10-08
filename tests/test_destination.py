"""
目的地 → 城市 自動推導測試
============================
⚠️⚠️ 呢個係真實用戶報嘅 bug：

   用戶開咗個 trip 叫「hk」，喺**目的地**欄打「香港」。
   但地圖顯示**福岡**。

   原因：地圖只讀 🧭「城市」編輯器（trip_stops 表），
        而佢冇填過嗰度 → 空 → 地圖跌落硬編碼 fallback（福岡）。

   ⚠️ 用戶嘅資料冇錯，係我哋冇將「目的地」當一回事。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))
sys.path.insert(0, str(ROOT / "engine"))


class TestGeocodeDestination:
    """目的地要查到座標。"""

    @pytest.mark.parametrize("dest,expect_country", [
        ("香港", "香港"),
        ("Hong Kong", "香港"),
        ("hongkong", "香港"),
        ("HK", "香港"),
        ("Seoul", "韓國"),
        ("首爾", "韓國"),
        ("東京", "日本"),
        ("Tokyo", "日本"),
        ("台北", "台灣"),
        ("大阪", "日本"),
        ("Bangkok", "泰國"),
        ("London", "英國"),
    ])
    def test_geocodes(self, dest, expect_country):
        """⚠️ 中／英／簡寫都要查到，而且**唔可以查錯國家**。"""
        from wander.lookup import geocode_city
        c = geocode_city(dest)
        assert c is not None, f"{dest} 查唔到座標"
        assert c.lat is not None, f"{dest} 冇 lat"
        assert c.country == expect_country, \
            f"{dest} 應該係 {expect_country}，實際 {c.country}"

    def test_hong_kong_not_fukuoka(self):
        """
        ⚠️⚠️ 呢個就係用戶報嘅 bug 嘅核心斷言。
        """
        from wander.lookup import geocode_city
        c = geocode_city("香港")
        assert c is not None
        # 香港喺北緯 22.15-22.56、東經 113.83-114.44
        assert 22.1 < c.lat < 22.6, f"lat={c.lat} 唔係香港"
        assert 113.8 < c.lng < 114.5, f"lng={c.lng} 唔係香港"
        # 福岡喺北緯 33.6 —— 明確唔可以係嗰度
        assert not (33 < c.lat < 34), "竟然查到福岡！"


class TestNoPhantomStop:
    """
    ⚠️ 唔可以「合成」一個冇座標嘅假城市。

    舊 code 咁做：
      if not rows and trip.get("destination"):
          rows = [{"id": None, "city": ..., }]     ← 冇 lat/lng

    兩個問題：
      ① `id: None` → React key 撞、撳刪除會亂、
         地圖 `filter(s => s.lat != null)` 剔走佢 → 地圖仍然冇中心
      ② 用戶見到城市名喺清單度，以為設定好咗 → 唔會知要再設定
    """

    @staticmethod
    def _code_only(path: Path) -> str:
        """
        ⚠️ 去咗**註解**先檢查 ——
           否則會 match 到我解釋緊呢個 bug 嘅那段註解
           （第一個版本嘅測試就係咁誤報）。
        """
        import re
        out = []
        for line in path.read_text(encoding="utf-8").split("\n"):
            # 去行尾註解（粗略但夠用：唔喺字串入面嘅 #）
            stripped = re.sub(r'(?<![\'"\"])\s*#.*$', '', line)
            if stripped.strip().startswith("#"):
                continue
            out.append(stripped)
        return "\n".join(out)

    def test_source_has_no_synthetic_stop(self):
        src = self._code_only(ROOT / "server" / "app" / "main.py")
        # 搵合成嘅假城市（dict 入面 id 係 None）
        assert '"id": None' not in src, \
            "仲有合成嘅假城市（id: None，冇座標）"
        assert "'id': None" not in src

    def test_get_stops_calls_ensure(self):
        """GET /stops 一定要叫 _ensure_stops_from_destination。"""
        src = (ROOT / "server" / "app" / "main.py").read_text(encoding="utf-8")
        i = src.index('def get_stops(')
        body = src[i:i + 1400]
        assert "_ensure_stops_from_destination" in body, \
            "GET /stops 冇由 destination 推導城市"

    def test_create_trip_calls_ensure(self):
        src = (ROOT / "server" / "app" / "main.py").read_text(encoding="utf-8")
        i = src.index('def create_trip(')
        body = src[i:i + 1400]
        assert "_ensure_stops_from_destination" in body, \
            "create_trip 冇由 destination 建城市"

    def test_map_has_no_hardcoded_city(self):
        """
        ⚠️⚠️ 地圖唔可以硬編碼任何城市做 fallback ——
           就係呢個（福岡）令用戶以為我哋搞錯佢個行程。
        """
        mv = (ROOT / "web" / "src" / "components" / "MapView.jsx").read_text(encoding="utf-8")
        import re
        # 搵 setView([數字, 數字] 嘅硬編碼座標
        for m in re.finditer(r"setView\(\[([\d.]+),\s*([\d.]+)\]", mv):
            lat, lng = float(m.group(1)), float(m.group(2))
            assert not (33 < lat < 34 and 130 < lng < 131), \
                f"地圖仍然硬編碼福岡座標 {lat},{lng}"
