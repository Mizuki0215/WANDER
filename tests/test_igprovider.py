"""
IG 第三方抓取服務測試
====================
⚠️ 呢個檔存在嘅原因：要老實面對「IG 封鎖」呢個硬事實。

   用戶問：「點解人哋啲 app 可以直程 copy 到 IG？」
   答案：佢哋俾錢買第三方抓取服務。呢啲服務自己養住宅代理 +
        帳號池 + 反偵測，成本轉嫁落用家身上。

   所以 Wander 提供**可選**支援：
     · 唔配置 → 完全免費（書籤小工具／貼 caption）
     · 配置咗 → IG link 一貼就自動抽出

   最重要嘅斷言：**唔配置就絕對唔會用**（唔可以偷偷俾錢）。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "engine"))

from wander import igprovider  # noqa: E402


class TestDefaultsOff:
    """
    ⚠️ 最重要：預設一定要關閉。
       唔可以喺用戶冇同意嘅情況吓用收費服務。
    """

    def test_not_configured_by_default(self, monkeypatch):
        monkeypatch.delenv("WANDER_IG_PROVIDER", raising=False)
        monkeypatch.delenv("WANDER_IG_KEY", raising=False)
        assert igprovider.is_configured() is False
        assert igprovider.configured() is None

    def test_fetch_returns_none_when_unconfigured(self, monkeypatch):
        monkeypatch.delenv("WANDER_IG_PROVIDER", raising=False)
        monkeypatch.delenv("WANDER_IG_KEY", raising=False)
        # 完全冇網絡請求都應該安全回 None
        assert igprovider.fetch_post("https://www.instagram.com/p/ABC/") is None

    def test_status_lists_options_when_off(self, monkeypatch):
        monkeypatch.delenv("WANDER_IG_PROVIDER", raising=False)
        monkeypatch.delenv("WANDER_IG_KEY", raising=False)
        st = igprovider.status()
        assert st["enabled"] is False
        # 要列晒所有可選服務，等用戶自己決定
        assert len(st["providers"]) >= 3
        for name in ("scrapecreators", "socialfetch", "hikerapi"):
            assert name in st["providers"]
            assert st["providers"][name]["free"]      # 一定要講明免費額度
            assert st["providers"][name]["signup"]    # 一定要有註冊連結

    def test_partial_config_still_off(self, monkeypatch):
        """淨係填 provider 冇填 key → 唔算配置好。"""
        monkeypatch.setenv("WANDER_IG_PROVIDER", "scrapecreators")
        monkeypatch.delenv("WANDER_IG_KEY", raising=False)
        assert igprovider.is_configured() is False

        monkeypatch.setenv("WANDER_IG_KEY", "abc")
        monkeypatch.delenv("WANDER_IG_PROVIDER", raising=False)
        assert igprovider.is_configured() is False

    def test_unknown_provider_rejected(self, monkeypatch):
        monkeypatch.setenv("WANDER_IG_PROVIDER", "some_random_service")
        monkeypatch.setenv("WANDER_IG_KEY", "abc")
        assert igprovider.is_configured() is False


class TestConfigured:
    def test_recognises_known_providers(self, monkeypatch):
        for name in igprovider.PROVIDERS:
            monkeypatch.setenv("WANDER_IG_PROVIDER", name)
            monkeypatch.setenv("WANDER_IG_KEY", "test_key")
            assert igprovider.is_configured() is True
            assert igprovider.configured() == (name, "test_key")

    def test_status_shows_enabled(self, monkeypatch):
        monkeypatch.setenv("WANDER_IG_PROVIDER", "hikerapi")
        monkeypatch.setenv("WANDER_IG_KEY", "k")
        st = igprovider.status()
        assert st["enabled"] is True
        assert st["provider"] == "hikerapi"
        assert st["label"] == "HikerAPI"


class TestUrlDetection:
    @pytest.mark.parametrize("url", [
        "https://www.instagram.com/p/DcV-H82D9Rj/",
        "https://instagram.com/p/ABC123/",
        "https://www.instagram.com/reel/XYZ/",
        "https://www.instagram.com/tv/ABC/",
        "https://www.instagram.com/reels/ABC/",
    ])
    def test_is_instagram(self, url):
        assert igprovider.is_instagram(url) is True

    @pytest.mark.parametrize("url", [
        "https://maps.app.goo.gl/abc",
        "https://tabelog.com/fukuoka/A4001/",
        "https://www.xiaohongshu.com/explore/x",
        "", "instagram.com/p/ABC",          # 冇 scheme
    ])
    def test_not_instagram(self, url):
        assert igprovider.is_instagram(url) is False


class TestResponseParsing:
    """
    ⚠️ 唔同服務回傳唔同 schema，所以用「候選路徑」逐個試。
       呢啲測試確保任何一種 schema 都抽得到 caption。
    """

    @pytest.mark.parametrize("payload,want", [
        ({"caption": "一蘭拉麵"}, "一蘭拉麵"),
        ({"caption_text": "明洞餃子"}, "明洞餃子"),
        ({"data": {"caption": "本家大たこ"}}, "本家大たこ"),
        ({"data": {"edge_media_to_caption": {"edges": [{"node": {"text": "波止場食堂"}}]}}},
         "波止場食堂"),
        ({"items": [{"caption": {"text": "Blue Bottle"}}]}, "Blue Bottle"),
        ({"items": [{"caption": "官兵衛うどん"}]}, "官兵衛うどん"),
        ({"result": {"caption": "長岡博多天婦羅"}}, "長岡博多天婦羅"),
    ])
    def test_extracts_caption_from_various_schemas(self, payload, want):
        got = igprovider._first_str(payload, igprovider._CAPTION_PATHS)
        assert got == want

    @pytest.mark.parametrize("payload", [
        {}, {"data": {}}, {"items": []}, {"caption": ""}, {"caption": None},
        {"caption": "   "}, {"unexpected": "shape"},
    ])
    def test_no_caption_returns_none(self, payload):
        assert igprovider._first_str(payload, igprovider._CAPTION_PATHS) is None

    def test_dig_does_not_raise(self):
        """_dig 要對任何垃圾 input 都安全。"""
        assert igprovider._dig(None, ("a",)) is None
        assert igprovider._dig({}, ("a", "b")) is None
        assert igprovider._dig([], (0,)) is None
        assert igprovider._dig("string", ("a",)) is None
        assert igprovider._dig({"a": [1, 2]}, ("a", 5)) is None
        assert igprovider._dig({"a": {"b": "c"}}, ("a", "b")) == "c"

    @pytest.mark.parametrize("payload,want", [
        ({"owner": {"username": "foodie"}}, "foodie"),
        ({"username": "foodie2"}, "foodie2"),
        ({"data": {"owner": {"username": "foodie3"}}}, "foodie3"),
    ])
    def test_extracts_author(self, payload, want):
        assert igprovider._first_str(payload, igprovider._AUTHOR_PATHS) == want

    @pytest.mark.parametrize("payload,want", [
        ({"display_url": "https://cdn.ig/a.jpg"}, "https://cdn.ig/a.jpg"),
        ({"data": {"image_url": "https://cdn.ig/b.jpg"}}, "https://cdn.ig/b.jpg"),
    ])
    def test_extracts_image(self, payload, want):
        assert igprovider._first_str(payload, igprovider._IMAGE_PATHS) == want


class TestErrorHandling:
    """任何錯誤都要安全回傳，唔可以拋出去搞死成個 parse。"""

    def test_auth_error_is_reported_not_raised(self, monkeypatch):
        monkeypatch.setenv("WANDER_IG_PROVIDER", "scrapecreators")
        monkeypatch.setenv("WANDER_IG_KEY", "bad_key")

        class FakeResp:
            status_code = 401
        monkeypatch.setattr(igprovider.requests, "get",
                            lambda *a, **k: FakeResp())
        r = igprovider.fetch_post("https://www.instagram.com/p/ABC/")
        assert r is not None and r.get("error") == "auth"

    def test_quota_error_is_reported(self, monkeypatch):
        monkeypatch.setenv("WANDER_IG_PROVIDER", "scrapecreators")
        monkeypatch.setenv("WANDER_IG_KEY", "k")

        class FakeResp:
            status_code = 429
        monkeypatch.setattr(igprovider.requests, "get", lambda *a, **k: FakeResp())
        r = igprovider.fetch_post("https://www.instagram.com/p/ABC/")
        assert r.get("error") == "quota"

    def test_network_error_returns_none(self, monkeypatch):
        monkeypatch.setenv("WANDER_IG_PROVIDER", "scrapecreators")
        monkeypatch.setenv("WANDER_IG_KEY", "k")

        def boom(*a, **k):
            raise igprovider.requests.RequestException("network down")
        monkeypatch.setattr(igprovider.requests, "get", boom)
        assert igprovider.fetch_post("https://www.instagram.com/p/ABC/") is None

    def test_schema_change_is_reported(self, monkeypatch):
        """服務改咗 schema → 要明確講，唔可以靜靜當成功。"""
        monkeypatch.setenv("WANDER_IG_PROVIDER", "scrapecreators")
        monkeypatch.setenv("WANDER_IG_KEY", "k")

        class FakeResp:
            status_code = 200
            def json(self): return {"totally": "different"}
        monkeypatch.setattr(igprovider.requests, "get", lambda *a, **k: FakeResp())
        r = igprovider.fetch_post("https://www.instagram.com/p/ABC/")
        assert r.get("error") == "nocaption"
        assert "schema" in r.get("detail", "")
