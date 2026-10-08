"""
lookup 模組測試

分兩類：
  · 唔使上網嘅（一定跑）—— 查詢砌法、OSM 分類對照、URL 解包、快取
  · 要上網嘅（-m network）—— Photon / DuckDuckGo / 完整 pipeline

跑法：
    pytest tests -v                      # 只跑唔使上網嘅
    pytest tests -v -m network           # 連網絡測試都跑
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

try:
    from wander.lookup import DDG_RATE_LIMITED as _DDG_INITIAL  # noqa
except Exception:
    _DDG_INITIAL = False


def _ddg_guard() -> None:
    """
    如果 DuckDuckGo rate limit 咗就 skip 呢個測試。

    ⚠️⚠️ 為咩一定要**執行時**檢查，唔可以用 `@pytest.mark.skipif`：
       skipif 喺 **import 時**評估，但嗰陣 DDG_RATE_LIMITED 仲係 False
       （未開始查）。要真正查一次先知道俾唔俾 rate limit。

       DDG 冇 API key，所以會 bot 偵測。狂查十幾次之後回傳
       HTTP 202 + anomaly 頁 → 搜尋結果係空（唔係錯誤）。
       如果測試當佢係「功能壞咗」，就會報假失敗，令人以為有 regression。
    """
    import wander.lookup as L
    # 主動查一次，令 rate limit 狀態更新
    L.duckduckgo_search("wander rate limit probe")
    if getattr(L, "DDG_RATE_LIMITED", False):
        pytest.skip("DuckDuckGo rate limit 咗（HTTP 202 anomaly）→ 唔係程式問題")


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "engine"))

from wander.lookup import (  # noqa: E402
    PlaceCandidate, SearchHit, _clean_html, _osm_to_category, _unwrap_ddg_url,
    best_source_url, build_query,
)

# ══════════════════════════════════════════════════════════════
# 唔使上網
# ══════════════════════════════════════════════════════════════

class TestBuildQuery:
    def test_adds_hint(self):
        assert build_query("一蘭 本社総本店", "博多") == "一蘭 本社総本店 博多"

    def test_skips_duplicate_hint(self):
        """hint 已經喺名入面就唔好重複（「一蘭 博多」+ hint「博多」）。"""
        assert build_query("一蘭 博多", "博多") == "一蘭 博多"

    def test_handles_empty_hint(self):
        assert build_query("犬鳴川河川公園", None) == "犬鳴川河川公園"
        assert build_query("犬鳴川河川公園", "  ") == "犬鳴川河川公園"

    def test_strips_whitespace(self):
        assert build_query("  一蘭  ", " 博多 ") == "一蘭 博多"


class TestOsmCategory:
    @pytest.mark.parametrize("key,value,want", [
        ("amenity", "restaurant", "food"),
        ("amenity", "cafe", "food"),
        ("shop", "department_store", "shopping"),
        ("tourism", "hotel", "stay"),
        ("tourism", "museum", "play"),
        ("leisure", "park", "play"),
        ("amenity", "place_of_worship", "play"),
        ("railway", "station", "transport"),
    ])
    def test_known_tags(self, key, value, want):
        result = _osm_to_category(key, value)
        assert result is not None
        assert result[0] == want

    def test_unknown_returns_none(self):
        assert _osm_to_category("nonsense", "nonsense") is None
        assert _osm_to_category(None, None) is None

    def test_fallback_by_key(self):
        assert _osm_to_category("shop", "unknown_shop_type")[0] == "shopping"
        assert _osm_to_category("tourism", "unknown")[0] == "play"


class TestDdgHelpers:
    def test_unwrap_ddg_redirect(self):
        href = "//duckduckgo.com/l/?uddg=https%3A%2F%2Ftabelog.com%2Ffukuoka%2FA4001%2F"
        assert _unwrap_ddg_url(href) == "https://tabelog.com/fukuoka/A4001/"

    def test_passthrough_normal_url(self):
        assert _unwrap_ddg_url("https://example.com/a") == "https://example.com/a"

    def test_clean_html_strips_tags_and_entities(self):
        assert _clean_html("<b>一蘭</b> &amp; 天婦羅") == "一蘭 & 天婦羅"


class TestBestSourceUrl:
    def make(self, kind: str, url: str, score: float = 0) -> SearchHit:
        return SearchHit(title="t", url=url, source_kind=kind, score=score)

    def test_prefers_tabelog_over_official(self):
        hits = [self.make("official", "https://ichiran.com/", 20),
                self.make("tabelog", "https://tabelog.com/x/", 67)]
        assert best_source_url(hits) == "https://tabelog.com/x/"

    def test_falls_back_to_first_when_no_known_kind(self):
        hits = [self.make("other", "https://a.com/"), self.make("other", "https://b.com/")]
        assert best_source_url(hits) == "https://a.com/"

    def test_empty_list(self):
        assert best_source_url([]) is None


class TestPlaceCandidate:
    def test_address_line_joins_parts(self):
        c = PlaceCandidate(name="一蘭", postcode="8100801", state="福岡県",
                           city="福岡市", district="博多区", street="中洲5-3-2")
        assert c.address_line == "8100801 福岡県 福岡市 博多区 中洲5-3-2"

    def test_address_line_skips_missing(self):
        c = PlaceCandidate(name="X", city="福岡市", street="中洲5-3-2")
        assert c.address_line == "福岡市 中洲5-3-2"


# ══════════════════════════════════════════════════════════════
# 需要上網
# ══════════════════════════════════════════════════════════════

@pytest.mark.network
class TestPhoton:
    def test_finds_ichiran(self):
        from wander.lookup import search_photon
        cands = search_photon("一蘭 本社総本店 博多")
        if not cands:
            # Photon 係免費服務，會 rate limit。呢個唔係我哋嘅 bug，
            # 所以 skip 而唔係 fail（唔好因為第三方服務狀態而嚇自己）。
            pytest.skip("Photon 冇回應（可能 rate limit），跳過")
        assert cands
        c = cands[0]
        assert c.lat and c.lng
        # 一蘭本社総本店實測座標約 33.593, 130.405
        assert abs(c.lat - 33.593) < 0.05
        assert abs(c.lng - 130.405) < 0.05

    def test_nonsense_returns_empty(self):
        from wander.lookup import search_photon
        assert search_photon("zzzzqqqqxxxx不存在的地方999") == []


@pytest.mark.network
class TestDuckDuckGo:
    def test_finds_tabelog_for_ichiran(self):
        _ddg_guard()
        from wander.lookup import duckduckgo_search
        hits = duckduckgo_search("一蘭 本社総本店 博多")
        assert hits, "DDG 應該有結果（如果冇，好可能係 Accept-Language 又加返咗）"
        assert any(h.source_kind == "tabelog" for h in hits), \
            f"應該搵到 Tabelog，實際 kinds = {[h.source_kind for h in hits]}"


@pytest.mark.network
class TestLookupPipeline:
    def test_ichiran_full(self):
        _ddg_guard()
        from wander.lookup import lookup_place
        item, _ = lookup_place("一蘭 本社総本店", hint="博多")
        assert item.name
        assert item.lat and item.lng
        assert item.country == "日本"
        assert item.category == "food"
        # Tabelog 應該補到電話
        assert item.phone
        assert item.confidence >= 70

    def test_kanbee_udon_full(self):
        _ddg_guard()
        from wander.lookup import lookup_place
        item, _ = lookup_place("官兵衛うどん", hint="粕屋町")
        assert item.name
        assert item.lat and item.lng
        assert item.address and "粕屋町" in item.address
        # ⚠️ 郵便番号一定會正規化成「XXX-XXXX」——
        #    唔係嘅話 Tabelog（8112317）同地址（811-2317）會變成兩個唔同嘅值
        assert item.postal_code == "811-2317"
        assert item.category == "food"
        assert item.confidence >= 70

    def test_dazaifu_shrine(self):
        from wander.lookup import lookup_place
        item, _ = lookup_place("太宰府天満宮", hint="福岡")
        assert item.lat and item.lng
        assert item.category == "play"

    def test_enrich_caption_item(self):
        """完整用戶流程：caption → 抽店名 → 搜尋補完。"""
        from wander.caption import CaptionParser
        from wander.lookup import enrich_caption_item

        raw = """大阪・道頓堀で外せないたこ焼きの名店
「本家大たこ 道頓堀店」
営業時間：10:00〜23:00（年中無休）"""
        item = CaptionParser().parse(raw)
        assert item.name == "本家大たこ 道頓堀店"
        item, log = enrich_caption_item(item, verbose=True)
        assert log
        # 原本有嘅營業時間唔應該被覆蓋
        assert item.hours and "10:00" in item.hours
        # 應該補到座標
        assert item.lat and item.lng

    def test_enrich_without_name_does_nothing(self):
        from wander.caption import CaptionParser
        from wander.lookup import enrich_caption_item

        item = CaptionParser().parse("睇下有咩好玩啦")
        assert item.name is None
        item2, log = enrich_caption_item(item)
        assert item2.lat is None
        assert "冇店名" in log[0]


# ══════════════════════════════════════════════════════════════
# 座標反查
# ══════════════════════════════════════════════════════════════

class TestReverseGeocodeOffline:
    """唔使上網嘅部分。"""

    def test_skips_when_district_exists(self):
        """已經有地區就唔應該再反查（省 API 配額）。"""
        from wander.lookup import apply_reverse_geocode
        from wander.models import Item
        item = Item(lat=35.0, lng=139.0, district="鶴見区")
        assert apply_reverse_geocode(item) is item
        assert item.district == "鶴見区"

    def test_skips_without_coords(self):
        from wander.lookup import apply_reverse_geocode
        from wander.models import Item
        item = Item(name="測試")
        apply_reverse_geocode(item)
        assert item.country is None

    def test_nameless_lookup_does_not_search(self):
        """冇店名就唔可以亂搜尋 —— 否則會覆蓋已有嘅地區（真實 bug）。"""
        from wander.lookup import lookup_place
        item, log = lookup_place("", hint="聖水洞")
        assert item.lat is None
        assert any("冇店名" in l for l in log)


class TestMergeProtection:
    """merge 唔可以俾空值清走已有嘅資料。"""

    def test_merge_does_not_null_out_existing(self):
        from wander.models import Item
        a = Item(name="本來有名", district="聖水洞", country="韓國", confidence=50)
        b = Item(source="lookup")          # 全部係 None
        a.merge(b)
        assert a.name == "本來有名"
        assert a.district == "聖水洞"
        assert a.country == "韓國"


@pytest.mark.network
class TestReverseGeocodeNetwork:
    def test_yokohama_coords(self):
        """波止場食堂嘅真實座標 → 應該反查到神奈川県横浜市鶴見区。"""
        from wander.lookup import reverse_geocode
        c = reverse_geocode(35.4675145, 139.6912852)
        if c is None:
            pytest.skip("Nominatim 冇回應（可能 rate limit），跳過")
        assert c.state and "神奈川" in c.state
        assert c.city and "横浜" in c.city
        assert c.district and "鶴見" in c.district


# ══════════════════════════════════════════════════════════════
# IG 封鎖處理
#   ⚠️ 實測（2026-10）：IG 對所有未登入嘅 server-side 請求
#      一律 302 去 /accounts/login/，回傳 630KB JS 空殼，**零資料**
#      （連 og:image 都冇）。所有替代方法都試過，全部失敗：
#        · /embed/captioned/  → 只有 JS 殼
#        · /api/v1/oembed/    → 401
#        · ?__a=1&__d=dis     → 404
#        · r.jina.ai          → 第一次得，之後 Cloudflare 403
#      所以唯一可靠方法係「用戶自己貼 caption」。
# ══════════════════════════════════════════════════════════════

class TestInstagramWall:
    """唔使上網嘅部分：確認邏輯正確。"""

    def test_item_has_needs_input_field(self):
        from wander.models import Item
        it = Item(source="instagram")
        assert hasattr(it, "needs_input")
        assert hasattr(it, "blocked_reason")
        assert it.needs_input is None

    def test_needs_input_is_serialised(self):
        """to_dict() 一定要帶 needs_input，前端先睇得到。"""
        from wander.models import Item
        d = Item(source="instagram", needs_input="caption",
                 blocked_reason="instagram_login_wall").to_dict()
        assert d["needs_input"] == "caption"
        assert d["blocked_reason"] == "instagram_login_wall"


@pytest.mark.network
class TestInstagramWallLive:
    def test_detects_wall(self):
        """真 IG link 應該偵測到登入牆，並標記 needs_input。"""
        from wander.fetch import fetch_item
        item, trace, _ = fetch_item("https://www.instagram.com/p/DcV-H82D9Rj/",
                                    respect_robots=False)
        rules = [t["rule"] for t in trace]
        # 一定要有 IG_WALL（唔可以靜靜當成功）
        assert "IG_WALL" in rules, f"冇偵測到登入牆，rules={rules}"
        assert item.name is None
        assert item.confidence == 0
        # 冇 reader key 嘅話應該叫用戶貼 caption
        if item.needs_input:
            assert item.needs_input == "caption"
            assert item.blocked_reason == "instagram_login_wall"
            assert any("IG 封鎖" in n for n in item.notes)

    def test_caption_fallback_works(self):
        """貼 caption 之後應該抽到完整資料。"""
        from wander.caption import parse_caption_multi
        cap = """【開幕快將滿一年！座落銅鑼灣正宗〖#長岡博多天婦羅〗🍤】
在 #銅鑼灣利園 就吃得到，
從 #福岡 漂洋過海來的 #休閒式天婦羅店。"""
        it = parse_caption_multi(cap)[0]
        assert it.name == "長岡博多天婦羅"
        assert it.district == "銅鑼灣"
        assert it.country == "香港"
        assert it.brand_from == "福岡"      # ⚠️ 唔可以歸入福岡行程
        assert it.confidence >= 70
