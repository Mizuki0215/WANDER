"""pytest 測試 — 用真實 caption 同真實 URL 做 regression test。

跑法：
    cd engine && python -m pytest ../tests -v
或唔想裝 pytest：
    cd engine && python -m wander selftest
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "engine"))

from wander import CaptionParser, parse_caption, parse_gmaps, parse_url_offline  # noqa: E402
from wander.caption import parse_postal_code  # noqa: E402
from wander.models import Item  # noqa: E402

# ══════════════════════════════════════════════════════════════
# 真實 caption（用戶提供，唔可以改 —— 呢啲係 golden test）
# ══════════════════════════════════════════════════════════════

CAP_HIGANBANA = """曲「蔓珠沙華」大家都已熟能詳，
大家可知道「蔓珠沙華」在日本又名為「彼岸花」。
在秋分前後七天，
是為日本傳統祭祖的佛教節日「彼岸節」，
「彼岸花」也在此時長花ー「花開時不長葉，葉長時花就凋謝」，
富有生生不息的象徵意義。
迎接「宮若市」市成立20年，「犬鳴川綠之協會」30周年，
每年除了提供夜間點燈觀賞外，
在10月初更續辦去年大受好評的「放天燈（ランタンリリース），
🔸地址：〒823-0003　福岡縣宮若市本城65-1　犬鳴川河川公園
🔸日期：一般觀賞 9月中至10月初
晚間點燈 9月24日至10月8日
「彼岸花祭2026」10月4日
🔸營業時間：「彼岸花祭2026」下午3時至晚上8時"""

CAP_TEMPURA = """【開幕快將滿一年！座落銅鑼灣正宗〖#長岡博多天婦羅〗🍤】
正宗鮮製現炸天婦羅在哪吃？
在 #銅鑼灣利園 就吃得到，
從 #福岡 漂洋過海來的 #休閒式天婦羅店 ー長岡博多天婦羅（ #天ぷらながおか）。
午市提供廚師發辦或精選午餐選擇，
晚市則提供廚師發辦或A la Carte。"""

CAP_OSAKA = """大阪・道頓堀で外せないたこ焼きの名店
「本家大たこ 道頓堀店」
住所：〒542-0071 大阪府大阪市中央区道頓堀1-5-10
電話：06-6211-XXXX
営業時間：10:00〜23:00（年中無休）
予算：500〜1,000円
ミシュラン掲載店"""

CAP_SEOUL = """首爾聖水洞必去！☕
📍地址：서울 성동구 연무장길 47
🚇 2號線聖水站 3號出口行 5 分鐘
🕐 11:00 - 22:00（逢星期一休息）
💰 人均 ₩12,000
#首爾 #聖水洞 #cafe"""


# ══════════════════════════════════════════════════════════════
# 文字解析
# ══════════════════════════════════════════════════════════════

class TestHiganbana:
    """彼岸花 caption：郵便番号 + 完整地址 + 多個日期。

    Regression 重點：
      - 唔可以將「蔓珠沙華」當成店名（引號內容多數係主題詞）
      - 唔可以將「20年10月初」誤認做日期
    """
    @pytest.fixture(scope="class")
    @staticmethod
    def item() -> Item:
        return CaptionParser().parse(CAP_HIGANBANA)

    def test_name_from_address_not_quote(self, item):
        assert item.name == "犬鳴川河川公園"
        assert "地址" in (item.name_method or "")

    def test_postal_code(self, item):
        assert item.postal_code == "823-0003"

    def test_location_hierarchy(self, item):
        assert item.country == "日本"
        assert item.prefecture == "福岡縣"
        assert item.city == "宮若市"

    def test_address(self, item):
        assert "本城65-1" in item.address

    def test_category_flower(self, item):
        assert item.category == "play"
        assert item.category_label == "花季"

    def test_dates(self, item):
        raws = [d.raw for d in item.dates]
        assert "9月24日至10月8日" in raws
        assert "10月4日" in raws
        # 「20年10月初」唔應該出現
        assert not any("20年" in r for r in raws)

    def test_hours_trimmed(self, item):
        assert item.hours == "PM3:00-PM8:00"

    def test_high_confidence(self, item):
        assert item.confidence >= 80
        assert item.needs_review is False


class TestTempura:
    """銅鑼灣天婦羅：驗證「品牌來源 vs 實際位置」分離。

    呢個係整個引擎最重要嘅防錯機制 —— 如果傻更更見到「博多」
    就歸類福岡，用戶去到銅鑼灣就撲空。
    """
    @pytest.fixture(scope="class")
    @staticmethod
    def item() -> Item:
        return CaptionParser().parse(CAP_TEMPURA)

    def test_name(self, item):
        assert item.name == "長岡博多天婦羅"

    def test_actual_location_is_hongkong(self, item):
        assert item.country == "香港"
        assert item.district == "銅鑼灣"
        assert item.prefecture is None

    def test_brand_origin_separated(self, item):
        assert item.brand_from == "福岡"

    def test_category(self, item):
        assert item.category == "food"
        assert item.category_label == "天婦羅"

    def test_not_placed_in_fukuoka(self, item):
        """最關鍵嘅斷言：佢唔可以出現喺福岡嘅行程分類之下。"""
        assert "福岡" not in item.location_path


class TestOsaka:
    """日文 blog 風格：都道府縣 + 市 + 區 + 町名四層拆解。"""
    @pytest.fixture(scope="class")
    @staticmethod
    def item() -> Item:
        return CaptionParser().parse(CAP_OSAKA)

    def test_name_with_japanese_quotes(self, item):
        assert item.name == "本家大たこ 道頓堀店"

    def test_prefecture_and_district(self, item):
        assert item.prefecture == "大阪府"
        assert item.district == "道頓堀"

    def test_postal_and_phone(self, item):
        assert item.postal_code == "542-0071"
        assert item.phone == "06-6211-XXXX"

    def test_hours_and_price(self, item):
        assert item.hours and "10:00" in item.hours
        assert item.price and "500" in item.price

    def test_category_snack(self, item):
        assert item.category == "food"
        assert item.category_label == "小食"


class TestSeoul:
    """冇店名嘅帖：要老實承認抽唔到，唔可以亂猜。

    呢個 case 證明「第四層 fallback」係設計而唔係失敗。
    """
    @pytest.fixture(scope="class")
    @staticmethod
    def item() -> Item:
        return CaptionParser().parse(CAP_SEOUL)

    def test_no_name(self, item):
        assert item.name is None

    def test_country_detected(self, item):
        assert item.country == "韓國"

    def test_flags_for_review(self, item):
        assert item.needs_review is True
        assert item.confidence < 70

    def test_still_extracts_what_it_can(self, item):
        assert item.hours
        assert item.price
        assert item.category == "food"


# ══════════════════════════════════════════════════════════════
# URL 結構解析
# ══════════════════════════════════════════════════════════════

class TestGoogleMaps:
    def test_place_path(self):
        url = ("https://www.google.com/maps/place/Ichiran+Hakata+Shop/"
               "@33.5897,130.4207,17z/data=!3d33.5897!4d130.4207")
        item, _ = parse_gmaps(url)
        assert item.name == "Ichiran Hakata Shop"
        assert abs(item.lat - 33.5897) < 0.001
        assert abs(item.lng - 130.4207) < 0.001
        assert item.confidence >= 80

    def test_query_param(self):
        url = "https://www.google.com/maps/search/?api=1&query=Canal+City+Hakata"
        item, _ = parse_gmaps(url)
        assert item.name == "Canal City Hakata"

    def test_exact_coords_preferred_over_view_coords(self):
        """!3d!4d 係店舖本身，@ 只係視窗中心 —— 一定要優先 !3d!4d。"""
        url = ("https://www.google.com/maps/place/X/@1.0,2.0,17z/"
               "data=!3d33.111!4d130.222")
        item, _ = parse_gmaps(url)
        assert abs(item.lat - 33.111) < 0.001
        assert abs(item.lng - 130.222) < 0.001


class TestClassification:
    @pytest.mark.parametrize("url,source", [
        ("https://www.instagram.com/p/ABC123/", "instagram"),
        ("https://www.instagram.com/reel/ABC123/", "instagram"),
        ("https://www.xiaohongshu.com/explore/abc", "xiaohongshu"),
        ("https://www.youtube.com/watch?v=abc", "youtube"),
        ("https://tabelog.com/fukuoka/A4001/A400101/40001234/", "tabelog"),
        ("https://www.tripadvisor.com/Restaurant_Review-x.html", "tripadvisor"),
        ("https://example.com/blog/fukuoka-ramen", "web"),
    ])
    def test_source_detection(self, url, source):
        assert parse_url_offline(url).source == source

    def test_short_link_needs_redirect(self):
        item = parse_url_offline("https://maps.app.goo.gl/xK9mQ2vLp8TnR4wY7")
        assert item.source == "gmaps"
        assert item.confidence == 0
        assert any("redirect" in n.lower() or "短連結" in n for n in item.notes)


# ══════════════════════════════════════════════════════════════
# Item 合併（Google Maps 座標 + IG caption 圖文）
# ══════════════════════════════════════════════════════════════

class TestMerge:
    def test_merge_fills_gaps_without_overwriting_coords(self):
        gmaps, _ = parse_gmaps(
            "https://www.google.com/maps/place/Ichiran/"
            "@33.5897,130.4207,17z/data=!3d33.5897!4d130.4207")
        cap = CaptionParser().parse(
            "博多一蘭拉麵 本店\n📍地址：福岡縣福岡市博多区博多駅前1-1-1\n💰 人均 ¥1,000")

        merged = gmaps.merge(cap)
        # 座標唔可以被蓋走
        assert abs(merged.lat - 33.5897) < 0.001
        # 由 caption 補到嘅嘢
        assert merged.category == "food"
        assert merged.address
        assert merged.price
        # 信心提升
        assert merged.confidence >= gmaps.confidence

    def test_merge_handles_caption_with_image_only(self):
        a = Item(source="gmaps", name="Test Place", lat=1.0, lng=2.0, confidence=90)
        b = Item(source="instagram", raw_image="https://img/x.jpg", confidence=20)
        a.merge(b)
        assert a.raw_image == "https://img/x.jpg"
        assert a.name == "Test Place"
        assert a.confidence == 90


# ══════════════════════════════════════════════════════════════
# 郵便番号解析
# ══════════════════════════════════════════════════════════════

class TestPostalCode:
    """
    ⚠️ 呢個欄位看似簡單，但踩過三個坑：
       1. Tabelog JSON-LD 用「8112317」冇 hyphen，唔可以用死板 regex
       2. 一定要正規化成「XXX-XXXX」，否則同一個地方有兩種寫法
       3. 電話號碼「092-938-4051」會被誤認（要防呆）
    """

    @pytest.mark.parametrize("text,want", [
        ("〒810-0801 福岡市", "810-0801"),
        ("〒542-0071 大阪府", "542-0071"),
        ("810-0801 福岡市", "810-0801"),
        ("8112317 福岡県 糟屋郡 粕屋町", "811-2317"),   # Tabelog 格式
        ("8180117", "818-0117"),
    ])
    def test_valid_formats(self, text, want):
        assert parse_postal_code(text) == want

    @pytest.mark.parametrize("text", [
        "電話 092-938-4051",
        "TEL 06-6211-1234",
        "☎ 092-938-4051",
        "서울 성동구 연무장길 47",
        "冇任何號碼",
        "",
    ])
    def test_rejects_non_postal(self, text):
        assert parse_postal_code(text) is None

    def test_phone_not_mistaken_for_postal(self):
        """電話「092-938-4051」唔可以被當成「938-4051」。"""
        assert parse_postal_code("店家電話：092-938-4051") is None

    def test_normalizes_consistently(self):
        """唔同寫法要收斂成同一個值，否則去重會爆。"""
        a = parse_postal_code("〒811-2317 福岡県")
        b = parse_postal_code("8112317 福岡県")
        assert a == b == "811-2317"


# ══════════════════════════════════════════════════════════════
# 用戶真實數據（2026-10 提供）—— 全部係 golden test
# ══════════════════════════════════════════════════════════════

CAP_YOKOHAMA = """波止場食堂 レストハウス店
〒230-0054 神奈川県横浜市鶴見区大黒ふ頭１５"""

CAP_SEOUL2 = """ソウル特別市 城東区 聖水洞二街 315-71
︎︎︎︎☑︎11:00〜24:00(LO.23:00)"""

CAP_KOREA_LIST = """⏰ 7:30〜10:30 / 11:30〜23:00
🗺️ エリア：明洞
📝 推しメニュー：冷麺

02｜プルトゥンヌンテジ 풀뜯는돼지
⏰ 11:00〜22:00
🗺️ エリア：弘大
📝 推しメニュー：ミナリサムギョプサル

03｜チャドルバキンチュクミ 명동점 차돌박힌쭈꾸미 명동점
⏰ 11:00〜15:00 / 17:00〜22:00
🗺️ エリア：明洞
📝 推しメニュー：チャチュクイ"""


class TestYokohamaVenue:
    """横浜：神奈川県嘅地名詞典（原本只有福岡，會 miss）。"""

    @pytest.fixture(scope="class")
    @staticmethod
    def item() -> Item:
        return CaptionParser().parse(CAP_YOKOHAMA)

    def test_name_from_first_line(self, item):
        assert item.name == "波止場食堂 レストハウス店"

    def test_kanagawa_hierarchy(self, item):
        assert item.country == "日本"
        assert item.prefecture == "神奈川縣"
        assert item.city == "鶴見区"
        assert item.district == "大黒ふ頭"

    def test_postal_and_tail(self, item):
        assert item.postal_code == "230-0054"
        assert item.address_tail == "大黒ふ頭15"

    def test_full_width_number_normalized(self, item):
        """「大黒ふ頭１５」嘅全形數字要變半形。"""
        assert "15" in (item.address or "")
        assert "１５" not in (item.address or "")


class TestSeoulJapaneseAddress:
    """首爾用日文寫法。

    Regression 重點：「城東区」同時存在於大阪府同韓國，
    冇國別快篩就會歸類成「日本 › 大阪府 › 城東区」❌
    """

    @pytest.fixture(scope="class")
    @staticmethod
    def item() -> Item:
        return CaptionParser().parse(CAP_SEOUL2)

    def test_country_is_korea_not_japan(self, item):
        assert item.country == "韓國"
        assert item.prefecture is None

    def test_district_seongsu(self, item):
        assert item.district == "聖水洞"

    def test_hours(self, item):
        assert item.hours and "11:00" in item.hours

    def test_house_number_kept_whole(self, item):
        """「315-71」唔可以被砍成「315-7」。"""
        assert item.address_tail == "315-71"


class TestKoreanRestaurantList:
    """一帖多店 —— IG 整理帖最常見嘅格式。

    呢個係最重要嘅新功能：如果當佢係一間店，結果會錯得好離譜。
    """

    def test_splits_into_three_venues(self):
        from wander import parse_caption_multi
        items = parse_caption_multi(CAP_KOREA_LIST)
        assert len(items) == 3

    def test_named_venues(self):
        from wander import parse_caption_multi
        items = parse_caption_multi(CAP_KOREA_LIST)
        names = [i.name for i in items]
        assert "プルトゥンヌンテジ 풀뜯는돼지" in names
        assert any("チャドルバキンチュクミ" in (n or "") for n in names)

    def test_area_hint_applied(self):
        from wander import parse_caption_multi
        items = parse_caption_multi(CAP_KOREA_LIST)
        by_name = {i.name: i for i in items if i.name}
        assert by_name["プルトゥンヌンテジ 풀뜯는돼지"].district == "弘大"

    def test_each_venue_gets_its_own_area(self):
        """地區提示一定要配對返正確嗰間店，唔可以全部變成明洞。"""
        from wander import parse_caption_multi
        items = parse_caption_multi(CAP_KOREA_LIST)
        areas = {i.name: i.district for i in items if i.name}
        assert areas["プルトゥンヌンテジ 풀뜯는돼지"] == "弘大"
        assert areas["チャドルバキンチュクミ 명동점 차돌박힌쭈꾸미 명동점"] == "明洞"

    def test_menu_becomes_tag(self):
        from wander import parse_caption_multi
        items = parse_caption_multi(CAP_KOREA_LIST)
        for i in items:
            if i.name == "プルトゥンヌンテジ 풀뜯는돼지":
                assert any("ミナリサムギョプサル" in t for t in i.tags)

    def test_single_venue_returns_one(self):
        from wander import parse_caption_multi
        items = parse_caption_multi("官兵衛うどん\n営業時間：10:00〜23:00")
        assert len(items) == 1


class TestCountryPrefilter:
    """同名地區唔可以撞板。"""

    @pytest.mark.parametrize("addr,want_country,want_place", [
        ("ソウル特別市 城東区 聖水洞二街 315-71", "韓國", "聖水洞"),
        ("〒542-0071 大阪府大阪市中央区道頓堀1-5-10", "日本", "道頓堀"),
        ("서울 성동구 성수동2가 315-71", "韓國", "聖水洞"),
        ("台北市大安區永康街 12 號", "台灣", "大安區"),
    ])
    def test_country_detection(self, addr, want_country, want_place):
        item = CaptionParser().parse(addr)
        assert item.country == want_country
        assert want_place in item.location_path


class TestSuffixSpecificity:
    """同名長度時，後綴更具體嘅要贏。

    Regression：「糟屋郡」同「粕屋町」都係 3 個字，
    字典順序令「糟屋郡」贏 → city 錯。
    """

    def test_town_beats_county(self):
        item = CaptionParser().parse("住所：〒811-2317 福岡県糟屋郡粕屋町長者原東1-12-15")
        assert item.city == "粕屋町"
        assert item.prefecture == "福岡縣"

    def test_place_sort_key_orders_by_specificity(self):
        from wander.lexicon import sorted_places
        order = sorted_places(["糟屋郡", "粕屋町", "福岡市"])
        assert order.index("粕屋町") < order.index("糟屋郡")


class TestTailAddressFormats:
    """真實地址格式（跨國家）。"""

    @pytest.mark.parametrize("addr,want", [
        ("大阪府大阪市中央区道頓堀1-5-10", "道頓堀1-5-10"),
        ("東京都中央区銀座4-6-16", "銀座4-6-16"),
        ("神奈川県横浜市鶴見区大黒ふ頭15", "大黒ふ頭15"),
        ("福岡県糟屋郡粕屋町長者原東1-12-15", "長者原東1-12-15"),
        ("ソウル特別市 城東区 聖水洞2街 315-71", "315-71"),
        ("서울 성동구 연무장길 47", "47"),
        ("銅鑼灣利園", ""),
    ])
    def test_tail(self, addr, want):
        from wander.lexicon import tail_address
        assert tail_address(addr) == want


# ══════════════════════════════════════════════════════════════
# 跨語言店名抽取
#   ⚠️ 用戶明確指出：「information 唔一定係中文，可以係其他 language」
#      所以日文 / 韓文 / 英文 / 中文 全部都要認得。
# ══════════════════════════════════════════════════════════════

class TestMultilingualNames:
    """店名抽取要語言中立。"""

    # ── 日文 ──
    @pytest.mark.parametrize("text,want", [
        ("🔸住所：〒810-0801 福岡県福岡市博多区中洲5-3-2 一蘭本社総本店", "一蘭本社総本店"),
        ("住所：〒810-0801 福岡県福岡市博多区中洲5-3-2 一蘭 本社総本店", "一蘭 本社総本店"),
        ("📍住所：〒818-0056 福岡県筑紫野市紫二丁目 イオンモール筑紫野1階", "イオンモール筑紫野"),
        ("住所：〒810-0001 福岡県福岡市中央区天神1-1-1 一蘭天神支店", "一蘭天神支店"),
        ("波止場食堂 レストハウス店\n〒230-0054 神奈川県横浜市鶴見区大黒ふ頭15",
         "波止場食堂 レストハウス店"),
    ])
    def test_japanese(self, text, want):
        assert CaptionParser().parse(text).name == want

    # ── 韓文 ──
    @pytest.mark.parametrize("text,want", [
        ("🔹주소：서울 성동구 연무장길 47 어니언 성수", "어니언"),
        ("📍주소：부산 해운대구 해운대해변로 264 씨클라우드 호텔", "씨클라우드 호텔"),
    ])
    def test_korean(self, text, want):
        assert CaptionParser().parse(text).name == want

    # ── 英文 ──
    def test_english_hashtag(self):
        it = CaptionParser().parse("#BillsFukuoka #福岡 世界一の朝食")
        assert it.name == "BillsFukuoka"

    # ── 唔可以亂抽 ──
    @pytest.mark.parametrize("text", [
        "#福岡 #博多 #美食",                       # 全部係地區 hashtag
        "#首爾 #聖水洞 #cafe",                     # 全部係地區 + 通用詞
        "首爾聖水洞必去！☕\n📍地址：서울 성동구 연무장길 47\n🕐 11:00 - 22:00",
    ])
    def test_rejects_location_only(self, text):
        """純地區／通用詞唔可以當店名。"""
        assert CaptionParser().parse(text).name is None


class TestNumeralNotCorrupted:
    """
    ⚠️⚠️ Regression：曾經將漢數字全部轉阿拉伯，
       令「一蘭本社総本店」變成「1蘭本社総本店」—— 店名壞晒。
    """

    def test_ichi_ran_preserved(self):
        from wander.caption import normalize
        assert normalize("一蘭本社総本店") == "一蘭本社総本店"

    @pytest.mark.parametrize("text", [
        "三代目 鳥メロ", "十二社", "一風堂", "二◯加屋長介", "九州一番星",
    ])
    def test_names_with_kanji_numbers(self, text):
        from wander.caption import normalize
        assert normalize(text) == text

    def test_still_normalizes_fullwidth(self):
        from wander.caption import normalize
        assert normalize("１２３") == "123"

    def test_still_normalizes_tilde(self):
        from wander.caption import normalize
        assert normalize("11:00〜23:00") == "11:00至23:00"


class TestNameFromAddressLine:
    """由地址行切店名 —— 唔可以攞成句。"""

    @pytest.mark.parametrize("line,want", [
        ("🔸住所：〒810-0801 福岡県福岡市博多区中洲5-3-2 一蘭本社総本店", "一蘭本社総本店"),
        ("〒230-0054 神奈川県横浜市鶴見区大黒ふ頭15 波止場食堂", "波止場食堂"),
    ])
    def test_cuts_admin_prefix(self, line, want):
        assert CaptionParser._name_from_address_line(line) == want

    @pytest.mark.parametrize("line", [
        "#福岡 #博多 #美食",
        "〒810-0801 福岡県福岡市博多区中洲5-3-2",
        "서울 성동구 연무장길 47",
    ])
    def test_rejects_pure_address(self, line):
        got = CaptionParser._name_from_address_line(line)
        assert got is None or CaptionParser._looks_like_name(got) is False


# ══════════════════════════════════════════════════════════════
# 標題地區抽取（冇地址行嘅情況）
#   ⚠️ 真實問題：好多 caption 根本冇地址行，地區淨係喺標題：
#      「首爾明洞必食」「福岡博多嘅拉麵」「大阪道頓堀たこ焼き」
#      冇呢一步 → district 永遠 None → 地圖定位唔到、衝突偵測唔到。
# ══════════════════════════════════════════════════════════════

class TestTitleDistrict:
    @pytest.mark.parametrize("text,want_district", [
        ("首爾明洞必食\n「明洞餃子」", "明洞"),
        ("福岡博多嘅拉麵\n「一蘭本社総本店」", "博多"),
        ("大阪・道頓堀で外せない\n「本家大たこ」", "道頓堀"),
        ("銅鑼灣利園\n「長岡博多天婦羅」", "銅鑼灣"),
        ("東京新宿嘅咖啡店\n「Blue Bottle」", "新宿"),
        ("福岡天神嘅百貨\n「岩田屋」", "天神"),
    ])
    def test_district_from_title(self, text, want_district):
        it = CaptionParser().parse(text)
        assert it.district == want_district, f"抽到 {it.district!r}"

    @pytest.mark.parametrize("text,want_name,want_district", [
        ("首爾明洞必食\n「明洞餃子」", "明洞餃子", "明洞"),
        ("福岡博多嘅拉麵\n「一蘭本社総本店」", "一蘭本社総本店", "博多"),
    ])
    def test_name_not_the_title(self, text, want_name, want_district):
        """店名要係「」入面嗰個，唔係成個標題。"""
        it = CaptionParser().parse(text)
        assert it.name == want_name


class TestStreetVsDistrict:
    """
    ⚠️ 街名唔可以當地區。
       用戶要知「喺聖水洞」，唔係「喺연무장길」。
       연무장길（4 字）比 聖水（2 字）長，所以「攞最長」會攞錯。
    """

    def test_prefers_neighbourhood_over_street(self):
        it = CaptionParser().parse(
            "首爾聖水洞必去！☕\n📍地址：서울 성동구 연무장길 47")
        assert it.district == "聖水洞", f"抽到街名 {it.district!r}"

    @pytest.mark.parametrize("s", ["연무장길", "江南大路", "心齋橋筋", "Main Street", "5th Avenue"])
    def test_is_street_detects(self, s):
        assert CaptionParser._is_street(s) is True

    @pytest.mark.parametrize("s", ["明洞", "聖水洞", "博多", "銅鑼灣", "中央区"])
    def test_is_street_rejects(self, s):
        assert CaptionParser._is_street(s) is False


class TestWardVsTown:
    """
    ⚠️ 日本地址「福岡市中央区天神」有兩個層級：
         中央区 = 區名（行政）
         天神   = 町名（用戶想去嘅地方）
       做行程規劃要町名。真實 bug：sorted_places 由長到短排，
       「博多区」先撞到就 break，「中洲」永遠搵唔到。
    """

    @pytest.mark.parametrize("text,want_district,want_city", [
        ("📍地址：〒810-0801 福岡県福岡市博多区中洲5-3-2", "中洲", "博多区"),
        ("📍地址：〒810-0001 福岡県福岡市中央区天神2-4-12", "天神", "中央区"),
        ("📍住所：〒810-0051 福岡県福岡市中央区大濠公園1-2", "大濠", "中央区"),
    ])
    def test_town_beats_ward(self, text, want_district, want_city):
        it = CaptionParser().parse(text)
        assert it.district == want_district, f"district={it.district!r}"
        assert it.city == want_city, f"city={it.city!r}"


class TestNoFalseNames:
    """
    ⚠️ 擴充 NAME_HINT 時踩過嘅坑 —— 有啲字太通用，
       會令普通句子被當成店名。
    """

    def test_subway_direction_not_a_name(self):
        """「2號線聖水站 3號出口行 5 分鐘」唔係店名。"""
        it = CaptionParser().parse(
            "首爾聖水洞必去！☕\n📍地址：서울 성동구 연무장길 47\n"
            "🚇 2號線聖水站 3號出口行 5 分鐘\n🕐 11:00 - 22:00")
        assert it.name is None, f"抽到 {it.name!r}"

    @pytest.mark.parametrize("text", ["#首爾 #聖水洞 #cafe", "#福岡 #博多 #美食"])
    def test_location_hashtags_not_names(self, text):
        assert CaptionParser().parse(text).name is None

    def test_looks_like_name_rejects_hashtag(self):
        assert CaptionParser._looks_like_name("#首爾 #") is False

    @pytest.mark.parametrize("bad_char", ["號", "行"])
    def test_dangerous_chars_not_in_name_hints(self, bad_char):
        """
        ⚠️ 「號」「行」呢類字太通用，唔可以做店名特徵字。
           實測踩過：「2號線聖水站 3號出口行 5 分鐘」被當成店名。
           （「號」出現喺 號線／出口號；「行」出現喺 出口行／銀行）
        """
        from wander.lexicon import NAME_HINT
        assert bad_char not in NAME_HINT, f"「{bad_char}」唔應該喺 NAME_HINT"

    @pytest.mark.parametrize("text", [
        "🚇 2號線聖水站 3號出口行 5 分鐘",
        "💰 人均 ₩12,000",
        "🕐 11:00 - 22:00（逢星期一休息）",
    ])
    def test_plain_metadata_lines_not_names(self, text):
        """呢啲係 metadata 行，唔可以抽成店名。"""
        it = CaptionParser().parse(text)
        assert it.name is None, f"抽到 {it.name!r}"


class TestProseNotName:
    """
    ⚠️ 文章句子唔可以當店名。
       實測踩過：「「花開時不長葉，葉長時花就凋謝」」被當成店名 ❌
    """

    @pytest.mark.parametrize("text", [
        "「花開時不長葉，葉長時花就凋謝」",
        "「彼岸節」",
        "「宮若市」",
        "「彼岸花」好靚",
    ])
    def test_prose_or_location_not_name(self, text):
        assert CaptionParser().parse(text).name is None

    def test_higanbana_address_wins_over_quotes(self):
        """真店名喺地址行尾巴，引號內容係主題詞 → 地址行要贏。"""
        from test_parser import CAP_HIGANBANA
        it = CaptionParser().parse(CAP_HIGANBANA)
        assert it.name == "犬鳴川河川公園"


class TestQuoteNamesWithoutHints:
    """
    ⚠️ 唔可以堅持「引號內容一定要有店名特徵字」——
       好多真店名冇特徵字：「本家大たこ」「Blue Bottle」。
    """

    @pytest.mark.parametrize("text,want", [
        ("大阪・道頓堀で外せない\n「本家大たこ」", "本家大たこ"),
        ("東京新宿嘅咖啡店\n「Blue Bottle」", "Blue Bottle"),
    ])
    def test_quote_name_without_hint(self, text, want):
        assert CaptionParser().parse(text).name == want

    @pytest.mark.parametrize("text", ["「hello world」", "「咖啡」"])
    def test_rejects_non_names(self, text):
        assert CaptionParser().parse(text).name is None


class TestAddressTailNotName:
    """地址尾巴（大黒ふ頭15）唔可以當店名，否則搶走真正嘅第一行店名。"""

    def test_yokohama(self):
        it = CaptionParser().parse(
            "波止場食堂 レストハウス店\n〒230-0054 神奈川県横浜市鶴見区大黒ふ頭15")
        assert it.name == "波止場食堂 レストハウス店"

    @pytest.mark.parametrize("line", [
        "〒230-0054 神奈川県横浜市鶴見区大黒ふ頭15",
        "〒810-0801 福岡県福岡市博多区中洲5-3-2",
        "서울 성동구 연무장길 47",
    ])
    def test_pure_address_has_no_name(self, line):
        got = CaptionParser._name_from_address_line(line)
        assert got is None, f"抽出咗 {got!r}"
