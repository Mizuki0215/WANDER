"""
wander.caption — 文字解析引擎（rule-based）

呢個係整個系統最重要嘅一個模組。

設計哲學：
  1. 規則為先（rule-based first）—— 因為解釋性好、零成本、快、可審計。
     用戶可以睇到「點解抽出呢個答案」，調參數亦即刻見到效果。
  2. LLM 係 fallback，唔係主力 —— 規則 miss 先用，控制成本。
  3. 保留原文 —— 所有 raw_* 都唔會掉，方便日後 re-parse。

已知限制（要老實講）：
  - 只覆蓋日本（福岡為主）、香港、韓國、台灣嘅地名詞典。
    其他國家要靠 OSM Nominatim 或 LLM。
  - 「品牌來源 vs 實際位置」靠店名關鍵字（福岡／博多／九州），唔係語意理解。
    日文店名冇呢啲字就會 miss。
"""
from __future__ import annotations

import re
from typing import Optional

from .lexicon import (
    KOREAN_ALIAS,
    ALL_DISTRICT_WORDS, CATEGORY_RULES, CITY_COUNTRY_HINTS, CITY_LEVEL_WORDS,
    FACILITY, GENERIC_NAME, GROUP_COUNTRY, GROUP_TO_PREFECTURE,
    JP_PREFECTURE_HINTS, KOREAN_CITY_HINTS, NAME_BLACKLIST_PATTERNS, NAME_HINT,
    TAIWAN_CITY_HINTS, WARD_SUFFIXES, match_region, sorted_places, tail_address,
)
from .models import DateRange, Item

# ══════════════════════════════════════════════════════════════
# 前置處理
# ══════════════════════════════════════════════════════════════

# ⚠️⚠️ 呢個 dict 嘅用途要非常小心。
#    原本設計係「漢數字 → 阿拉伯」方便處理日期，但咁樣會**破壞店名**：
#        一蘭本社総本店  →  1蘭本社総本店   ❌
#        三代目        →  3代目          ❌
#        十二社        →  12社           ❌
#    店名嘅漢數字係名字嘅一部分，唔可以當數值處理。
#
#    所以：**只轉換「明確係數值」嘅情況**（見下面正則），唔會全句掃。
_JP_NUM = {"〇": "0", "零": "0"}


def _fullwidth_to_ascii(s: str) -> str:
    out = []
    for ch in s:
        o = ord(ch)
        if 0xFF01 <= o <= 0xFF5E:          # 全形 ASCII
            out.append(chr(o - 0xFEE0))
        elif ch == "\u3000":               # 全形空格
            out.append(" ")
        else:
            out.append(ch)
    return "".join(out)


def normalize(text: str) -> str:
    """
    正規化：全形→半形、全形空格、波紋線→「至」。

    ⚠️⚠️ 呢度踩過一個嚴重嘅坑：
        最初會將所有漢數字轉阿拉伯（一→1、二→2…），
        結果 **「一蘭本社総本店」變成「1蘭本社総本店」** ——
        店名壞咗，之後所有搜尋都會搵唔到。

        教訓：店名入面嘅漢數字係**名字嘅一部分**，唔係數值。
        所以而家**只喺明確係數值嘅上下文**先轉：
          · 〇/零 → 0（幾乎唔會出現喺店名）
          · 「三丁目」「二街」呢類地址後綴（見 _NUM_IN_ADDR）
        其餘一律保留原文。
    """
    s = _fullwidth_to_ascii(text)
    s = re.sub(r"[〇零]", lambda m: _JP_NUM[m.group()], s)
    _NUM_IN_ADDR = r"(?<=[一二三四五六七八九十])"
    s = s.replace("～", "至").replace("~", "至").replace("〜", "至")
    return s



# ══════════════════════════════════════════════════════════════
# 郵便番号 / 郵遞區號
# ══════════════════════════════════════════════════════════════

def parse_postal_code(text: str) -> Optional[str]:
    """
    由文字抽郵便番号／郵遞區號。

    ⚠️ 實測坑：並唔係個個來源都有 hyphen。
        Tabelog（JSON-LD）：「8112317」← 7 位冇 hyphen
        一般日文地址：    「〒810-0801」← 有 hyphen
        韓國：           「06236」
        台灣：           「106」
        香港：           （冇）

    所以一定要兩種格式都收，而且**統一正規化成「XXX-XXXX」**，
    否則同一個地方會有兩種寫法，去重同比對都會爆。
    """
    if not text:
        return None
    # ⚠️ 防呆：電話號碼唔係郵便番号。有電話字眼就直接放棄。
    if re.search(r"電話|TEL|Tel|tel|☎|📞|FAX", text):
        return None
    # 日本：〒810-0801 或 8112317
    m = re.search(r"〒\s*(\d{3})-?(\d{4})(?!\d)", text)
    if m:
        return f"{m.group(1)}-{m.group(2)}"
    # 「810-0801」冇 〒
    m = re.search(r"(?<!\d)(\d{3})-(\d{4})(?![\d\-])", text)
    if m:
        return f"{m.group(1)}-{m.group(2)}"
    # ⚠️ 日本郵便番号係 7 位數字，好多來源（Tabelog JSON-LD）會寫成
    #    「8112317」冇 hyphen 冇 〒。一定要收，否則 Tabelog 嘅地址會冇咗郵便番号。
    #    ⚠️ 但 7 位數字亦可能係電話（「092-938-4051」被拆成「9384051」），
    #       所以只接受喺**字串開頭**嘅裸 7 位數字。Tabelog 就係呢個格式。
    m = re.match(r"^\s*(\d{3})(\d{4})(?!\d)", text)
    if m:
        return f"{m.group(1)}-{m.group(2)}"
    return None


def _country_of(text: str) -> Optional[str]:
    """
    國別快篩：由地址文字判斷國家。

    ⚠️ 存在原因（真實 bug）：
        「ソウル特別市 城東区 聖水洞二街 315-71」
        「城東区」同時存在於 大阪府 同 韓國 → 冇快篩就會歸類成大阪 ❌
    """
    for hints, ctry in KOREAN_CITY_HINTS:
        if any(h in text for h in hints):
            return ctry
    for hints, ctry in TAIWAN_CITY_HINTS:
        if any(h in text for h in hints):
            return ctry
    if re.search(r"[가-힣]", text):
        return "韓國"
    return None




# ══════════════════════════════════════════════════════════════
# 一帖多店（清單式 caption）
# ══════════════════════════════════════════════════════════════

# 「01｜店名」/「02 | 店名」—— 全形同半形直線都要收
_VENUE_HEAD_RE = re.compile(r"^\s*[\u200b\u2060\ufeff]*\d{1,2}\s*[｜|]\s*(.+?)\s*$")

# 「🗺️ エリア：明洞」/「エリア: 弘大」/「📍地區：明洞」
_AREA_RE = re.compile(r"(?:🗺️?|📍|🧭)?\s*(?:エリア|地區|地区|지역|area)\s*[:：]\s*(.+?)\s*$",
                      re.IGNORECASE)

# 「⏰ 7:30〜10:30 / 11:30〜23:00」
_TIME_LINE_RE = re.compile(r"(?:⏰|🕐|🕒|時間|営業時間)\s*[:：]?\s*([^\n]+)")

# 「📝 推しメニュー：冷麺」
_MENU_RE = re.compile(r"(?:📝|🍽️?)?\s*(?:推しメニュー|推薦|おすすめ|메뉴)\s*[:：]\s*(.+?)\s*$")


def split_into_venues(text: str) -> list[dict]:
    """
    將「清單式」caption 切成一間間店。

    支援嘅格式（用戶真實例子）：
        ┈┈┈┈┈┈┈┈┈┈┈┈
        ⏰ 7:30〜10:30 / 11:30〜23:00
        🗺️ エリア：明洞
        📝 推しメニュー：冷麺

        02｜プルトゥンヌンテジ 풀뜯는돼지
        ┈┈┈┈┈┈┈┈┈┈┈┈┈┈
        ⏰ 11:00〜22:00
        🗺️ エリア：弘大
        📝 推しメニュー：ミナリサムギョプサル

    回傳 [{"name":…, "area":…, "hours":…, "menu":…, "raw":…}, …]

    ⚠️ 注意：每個 block 嘅「エリア / 時間 / メニュー」係**屬於上一間店**嘅
       （即係喺下一個店名**之前**）。所以要先掃 metadata 再撞到下一個店名。
    """
    lines = text.split("\n")
    venues: list[dict] = []
    cur: Optional[dict] = None

    for ln in lines:
        m = _VENUE_HEAD_RE.match(ln)
        if m:
            if cur:
                venues.append(cur)
            cur = {"name": m.group(1).strip(), "area": None, "hours": None,
                   "menu": None, "raw": []}
            continue
        # ⚠️ 「01」好多時冇標題（直接由 metadata 開始），所以要開一個匿名 block
        if cur is None:
            if _AREA_RE.search(ln) or _TIME_LINE_RE.search(ln) or _MENU_RE.search(ln):
                cur = {"name": None, "area": None, "hours": None,
                       "menu": None, "raw": []}
            else:
                continue
        cur["raw"].append(ln)
        ma = _AREA_RE.search(ln)
        if ma and not cur["area"]:
            cur["area"] = ma.group(1).strip()
            continue
        mt = _TIME_LINE_RE.search(ln)
        if mt and not cur["hours"]:
            cur["hours"] = mt.group(1).strip()
            continue
        mm = _MENU_RE.search(ln)
        if mm and not cur["menu"]:
            cur["menu"] = mm.group(1).strip()

    if cur:
        venues.append(cur)
    for v in venues:
        v["raw"] = "\n".join(v["raw"]).strip()
    # 匿名 block（冇標題）只保留喺有實質資料嘅情況
    venues = [v for v in venues
              if v["name"] or v["area"] or v["hours"] or v["menu"]]
    return venues


# ══════════════════════════════════════════════════════════════
# 主解析器
# ══════════════════════════════════════════════════════════════

class CaptionParser:
    """將一段文字（caption / 網頁正文）解析成 Item。"""

    def __init__(self, home_country: str | None = None):
        # home_country 用嚟做「品牌來源」判斷：
        # 如果用戶係香港人，見到「福岡」字眼而實際位置喺香港，就標 brand_from。
        self.home_country = home_country

    # ── 對外接口 ─────────────────────────────────────────────
    def parse(
        self,
        text: str,
        *,
        source: str = "caption",
        source_name: str = "文字",
        url: str | None = None,
        raw_title: str | None = None,
        raw_image: str | None = None,
        extra_confidence: dict[str, int] | None = None,
        area_hint: str | None = None,
    ) -> Item:
        item = Item(
            source=source, source_name=source_name, url=url,
            raw_title=raw_title, raw_image=raw_image, raw_caption=text,
        )
        rules: list[dict[str, str]] = []
        raw = text or ""
        T = normalize(raw)

        def log(rule: str, match: str, note: str) -> None:
            rules.append({"rule": rule, "match": match, "note": note})

        # ── 0. 電話（一定要喺「時間」之前，否則 10:00-23:00 會被當電話）──
        self._extract_phone(T, item, log)

        # ── 1. 地址 ──
        addr_line, addr_how = self._find_address_line(T, log)
        if addr_line:
            self._parse_address(addr_line, addr_how, item, log)
        # ⚠️ 條件係「仲未有地區」，唔係「冇地址行」。
        #    真實 bug：標題「首爾明洞必食」被 _find_address_line 當成地址行
        #    （因為含「明洞」），但 _parse_address 嘅國別守衛又掃唔到韓國地名，
        #    結果 district 永遠 None。所以冇地區就要再試。
        # ⚠️ 亦要處理「現有 district 只係街名」嘅情況：
        #    地址「서울 성동구 연무장길 47」→ district = 연무장길（街名）
        #    但標題寫「聖水洞必去」→ 地區名更有用（用戶要知喺邊區）
        if not (item.district or item.city) or self._is_street(item.district):
            self._parse_location_fallback(T, item, log, replace_street=True)

        # ── 2. 名稱 ──
        self._extract_name(raw, T, addr_line, item, log)

        # ── 3. 品牌來源 vs 實際位置 ──
        self._extract_origin(T, item, log)

        # ── 4. 日期 ──
        self._extract_dates(T, item, log)

        # ── 5. 時間 ──
        self._extract_hours(T, item, log)

        # ── 6. 價錢 ──
        self._extract_price(T, item, log)

        # ── 7. 分類 ──
        self._extract_category(T, item, log)

        # ── 8. Hashtag ──
        self._extract_tags(raw, item, log)

        # ── 8.5 地區提示有最高優先權 ──
        #      「🗺️ エリア：弘大」係明確標示，唔可以被地址推斷覆蓋
        if area_hint:
            item._area_hint = area_hint
            item.district = area_hint
            item.field_confidence["location"] = 82
            rules.append({"rule": "AREA_HINT", "match": area_hint,
                          "note": "「エリア」明確標示，優先於地址推斷"})

        # ── 9. 信心分數 ──
        self._score(item, extra_confidence)
        item.rules_matched = rules
        return item

    # ══════════════════════════════════════════════════════════
    # 0. 電話
    # ══════════════════════════════════════════════════════════
    @staticmethod
    def _extract_phone(T: str, item: Item, log) -> None:
        pats = [
            r"(?:電話|TEL|Tel|tel|☎️?|📞)\s*[:：]?\s*(\d{2,4}-\d{2,4}-[\dXxｘ×]{3,4})",
            r"(\d{2,4}-\d{2,4}-[\dXxｘ×]{3,4})",
            r"(0\d{1,3}-\d{1,4}-\d{3,4})",
        ]
        for p in pats:
            m = re.search(p, T)
            if m:
                item.phone = m.group(1).strip()
                masked = bool(re.search(r"[Xxｘ×]", item.phone))
                log("PHONE_MASK" if masked else "PHONE", item.phone,
                    "原文用 X 遮蔽，只有部分號碼" if masked else "電話號碼")
                return

    # ══════════════════════════════════════════════════════════
    # 1. 地址
    # ══════════════════════════════════════════════════════════
    @staticmethod
    def _find_address_line(T: str, log) -> tuple[Optional[str], str]:
        """回傳 (地址行, 點樣搵到)。"""
        # 1a 明確標籤
        m = re.search(r"(?:🔸|📍|▪️|🔹)?\s*(?:地址|住址|住所|Address|address)\s*[:：]?\s*(.+)", T)
        if m:
            line = m.group(1).split("\n")[0].strip()
            # 防呆：要似地址（有數字 或 含已知地區）
            if len(line) <= 80 and (any(c.isdigit() for c in line)
                                    or any(w in line for w in ALL_DISTRICT_WORDS)):
                return line, "有明確「地址／住所」標籤"

        # 1b 逐行偵測
        for raw_ln in T.split("\n"):
            ln = raw_ln.strip()
            if not ln:
                continue
            # (1) 有郵便番号
            if "〒" in ln:
                return ln, "偵測到郵便番号 〒"
            # (2) 都道府縣 + 市區町村
            if re.search(r"(都|道|府|県|縣)[^\s]{1,6}(市|区|區)", ln):
                return ln, "偵測到都道府縣＋市區格式"
            # (3) 有 📍 等 marker
            if re.match(r"^[📍🔸🔹▪️]", ln):
                no_emoji = re.sub(r"^[📍🔸🔹▪️🚇🕐💰☎️📞\s]+", "", ln).strip()
                if no_emoji:
                    mr = match_region(no_emoji)
                    return (mr[1] if mr and mr[2] <= 2 else no_emoji), "偵測到 📍 標記行"
            # (4) 外國地址格式（韓國「特別市/道」+「区/洞」、台灣「市/區」）
            #     唔可以靠詞典，因為每個國家嘅行政區名都唔同
            #
            # ⚠️⚠️ 呢度踩過一個極陰險嘅 regex 坑：
            #     r"(特別市|廣域市)[^\s]{0,6}(区|區|市|郡)"
            #     唔會 match「ソウル特別市 城東区」！
            #
            #     原因：{0,6} 呢個 quantifier **最左最短優先**，會先試 0 個字元，
            #           跟住要求下一個字係「区」，但實際撞到空格 → 失敗，
            #           而且唔會擴展再試（冇嘢逼佢回溯）。
            #           改 1..6 就得，或者用「.」（. 可以食空格）。
            #
            #     教訓：凡係「中間可能夾住空格」嘅位，唔可以用 [^\s]{0,6}。
            if re.search(r"(?:特別市|特別自治市|廣域市|道).{0,6}(?:区|區|市|郡)", ln) \
                    or re.search(r"[가-힣]{2,}\s*[가-힣]*\s*\d", ln) \
                    or re.search(r"[\u4e00-\u9fff]{2,4}(?:市|縣|县).{0,4}(?:區|区|鄉|鎮)", ln):
                return ln, "偵測到韓國／台灣／外國行政區格式"
            # (4b) 純地區名行（例如「在 #銅鑼灣利園 就吃得到，」）
            #     ⚠️ 一樣要做國別快篩，否則「ソウル…城東区」會被當成大阪嘅城東区
            if len(ln) <= 60 and not re.search(r"[。！？!?]$", ln):
                words = ALL_DISTRICT_WORDS
                cf = _country_of(ln)
                if cf:
                    from .lexicon import DISTRICTS
                    words = sorted_places(
                        {w for g, ws in DISTRICTS.items()
                         if GROUP_COUNTRY.get(g) == cf for w in ws})
                mr = match_region(ln, words)
                if mr:
                    return mr[1], f"偵測到行內地區名「{mr[0]}」"
        return None, ""

    # 街名後綴 —— 呢啲係「街道」唔係「地區」，做行程規劃冇用
    #   （用戶要知「喺聖水洞」，唔係「喺연무장길」）
    STREET_SUFFIXES = ("길", "로", "거리", "通り", "通", "街", "路", "大馬路",
                       "筋",          # 大阪「心齋橋筋」「御堂筋」係街名
                       "street", "road", "avenue", "st", "ave", "rd")

    @classmethod
    def _is_street(cls, s: Optional[str]) -> bool:
        if not s:
            return False
        low = s.strip().lower()
        return any(low.endswith(x) for x in cls.STREET_SUFFIXES)

    def _parse_location_fallback(self, T: str, item: Item, log,
                                 replace_street: bool = False) -> None:
        """
        冇地址行時，喺標題／內文搵地區名。

        ⚠️ 為咩要呢個：
           好多 caption 根本冇地址，地區淨係喺標題度：
             「首爾明洞必食」「福岡博多嘅拉麵」「大阪道頓堀たこ焼き」
           冇呢一步 → district 永遠 None → 地圖定位唔到、城市衝突偵測唔到。

        ⚠️ 保守原則：只掃頭 3 行（標題區），只收「詞典有嘅地名」，
           而且唔會覆蓋已經有嘅值（地址行嘅結果永遠優先）。
        """
        from .lexicon import DISTRICTS
        # 已經有「非街名」嘅地區 → 唔覆蓋
        if (item.district or item.city) and not (
                replace_street and self._is_street(item.district) and not item.city):
            return

        head = "\n".join(T.split("\n")[:3])
        if not head.strip():
            return
        # 國別快篩（同 _parse_address 一致）
        cf = _country_of(head)

        best = None   # (長度, 地名, 群組)
        for group, words in DISTRICTS.items():
            # ⚠️ 呢度**唔可以**跳過「福岡市」！
            #    _parse_address 跳過佢係因為有另一個 block 專門處理；
            #    fallback 冇嗰個 block，跳過就會令「博多」「天神」永遠搵唔到。
            if cf and GROUP_COUNTRY.get(group) != cf:
                continue
            if not cf and GROUP_COUNTRY.get(group) in ("韓國", "台灣") \
                    and not re.search(r"[가-힣]|台北|臺北|台中|高雄|台南|首爾|明洞|弘大", head):
                continue
            for d in words:
                if not d or d not in head:
                    continue
                # ⚠️ 排除街名（연무장길 / ○○通り）—— 用戶要知「喺邊區」，
                #    唔係「喺邊條街」。街名通常最長，唔排除就會搶走地區名。
                if self._is_street(d):
                    continue
                # 越長越具體（「聖水洞」好過「聖水」）
                if best is None or len(d) > best[0]:
                    best = (len(d), d, group)

        if not best:
            return
        _, d, group = best
        country = GROUP_COUNTRY.get(group)
        canonical = KOREAN_ALIAS.get(d, d)
        # ⚠️ 唔可以喺呢度 return —— 因為 best 係「最長嘅地名」，
        #    而街名通常最長（연무장길 4 字 vs 聖水 2 字），
        #    所以會攞到街名然後放棄，連地區名都冇。要在上面 loop 揀嗰陣就排除。
        if country == "日本":
            item.country = item.country or "日本"
            item.prefecture = item.prefecture or GROUP_TO_PREFECTURE.get(group)
            if d.endswith(WARD_SUFFIXES) or d in CITY_LEVEL_WORDS:
                item.city = item.city or d
            else:
                item.district = canonical
        else:
            item.district = canonical
            item.country = item.country or country
        log("GEO_FALLBACK", canonical,
            f"標題區（頭 3 行）搵到地區「{canonical}」，群組 {group}"
            + ("（取代原本嘅街名）" if replace_street else ""))

    def _parse_address(self, addr_line: str, how: str, item: Item, log) -> None:
        prefix = ("ADDR_LABEL" if "標籤" in how
                  else "ADDR_POSTAL" if "郵便" in how
                  else "ADDR_DETECT")
        log(prefix, addr_line, how)

        # 郵便番号
        pc = parse_postal_code(addr_line)
        if pc:
            item.postal_code = pc
            log("POSTAL_JP", f"〒{pc}", "日本郵便番号 → 可精準定位")

        # 逐個群組做地名匹配
        #
        # ⚠️⚠️ 一定要先判斷國別！真實 bug：
        #   「ソウル特別市 城東区 聖水洞二街 315-71」
        #   「城東区」同時存在於「大阪府」同韓國 → 字典順序決定結果，
        #   結果首爾地址被歸類成「日本 › 大阪府 › 城東区」❌
        #
        #   解法：先做一次「國別快篩」，命中就只掃該國嘅群組。
        from .lexicon import DISTRICTS
        country_filter: Optional[str] = _country_of(addr_line)
        if country_filter:
            log("COUNTRY_PREFILTER", country_filter,
                "地址有該國特徵 → 只掃該國地名，避免同名地區撞板")

        for group, words in DISTRICTS.items():
            if group in ("福岡市",):
                continue
            if country_filter and GROUP_COUNTRY.get(group) != country_filter:
                continue
            # 日文地址（有 〒 / 都道府縣）就唔應該掃韓國／台灣群組
            # ⚠️ 呢個 regex 要夠闊 —— 唔可以只靠諺文，因為韓國地名
            #    好多時寫漢字（明洞、弘大、聖水洞、梨泰院…）
            if not country_filter and GROUP_COUNTRY.get(group) in ("韓國", "台灣") \
                    and not re.search(
                        r"[가-힣]|台北|臺北|台中|高雄|台南|首爾|明洞|弘大|江南|"
                        r"聖水|梨泰院|東大門|新村|狎鷗亭|海雲台|南浦|甘川|廣安里",
                        addr_line):
                continue
            for d in sorted_places(words):
                if d not in addr_line:
                    continue
                country = GROUP_COUNTRY.get(group)
                pref = GROUP_TO_PREFECTURE.get(group)

                if country == "日本":
                    item.country = "日本"
                    if pref:
                        item.prefecture = item.prefecture or pref
                    else:
                        # 「其他日本」冇明確都道府縣，用 keyword 推斷
                        for hint, hint_pref in JP_PREFECTURE_HINTS:
                            if hint in addr_line:
                                item.prefecture = item.prefecture or hint_pref
                                break
                    # 區／市／郡／町級 → city；其他町名 → district
                    #    ⚠️ 如果 city 已經有市級名（「福岡市」）而又撞到「博多区」，
                    #       就要將舊嘅降級去 prefecture，唔係就會兩個都塞落 city
                    # 「郡」後面嘅「町／村」係市級行政體（日本地址係 郡 › 町 › 地区）
                    #   例：糟屋郡粕屋町長者原東 → city = 粕屋町
                    is_municipality = (
                        d.endswith(WARD_SUFFIXES)
                        or d in CITY_LEVEL_WORDS
                        or (d.endswith(("町", "村"))
                            and addr_line[:addr_line.find(d)].rstrip().endswith("郡"))
                    )
                    if is_municipality:
                        if item.city and item.city != d and item.city.endswith("市") \
                                and d.endswith(("区", "區")):
                            item.district = item.district or d
                        else:
                            item.city = item.city or d
                    else:
                        item.district = item.district or d
                else:
                    # 香港 / 韓國 / 台灣：一律當地區
                    #   ⚠️ 韓國地址常用諺文（성수동），詞典用漢字（聖水洞）。
                    #      統一存漢字寫法，否則同一個地方會有兩個名，去重會爆。
                    canonical = KOREAN_ALIAS.get(d, d)
                    item.district = item.district or canonical
                    item.country = item.country or country
                log("GEO_MATCH", d, f"地址命中詞典：{group}")
                break

        # 福岡市內嘅區／町名
        #
        # ⚠️⚠️ 唔可以 `break`！真實 bug：
        #   「〒810-0801 福岡県福岡市博多区中洲5-3-2」
        #   sorted_places 由長到短排 → 先撞到「博多区」（3 字）就 break，
        #   「中洲」（2 字）永遠唔會被檢查 → district 永遠 None。
        #   正確做法：區名做 city，町名做 district，兩者都要收。
        if "福岡" in addr_line or item.prefecture == "福岡縣":
            for d in sorted_places(DISTRICTS["福岡市"]):
                if d not in addr_line:
                    continue
                if d.endswith("区"):
                    if item.city and item.city.endswith("市"):
                        item.city = d
                    else:
                        item.city = item.city or d
                    item.country = item.country or "日本"
                    item.prefecture = item.prefecture or "福岡縣"
                    log("GEO_FUKUOKA", d, "福岡市內區名 → city")
                else:
                    # ⚠️ 町名（中洲、天神）一定贏過「區名」（中央区、博多区）。
                    #    真實 bug：通用 loop 會將「中央区」塞落 district，
                    #    然後 `if not item.district` 就唔會收「天神」→
                    #    district 變咗「中央区」（區名，做行程規劃冇用）。
                    if not item.district or item.district.endswith(("区", "區")):
                        item.district = d
                        item.country = item.country or "日本"
                        item.prefecture = item.prefecture or "福岡縣"
                        log("GEO_FUKUOKA", d, "福岡市內町名 → district")

        # 番地
        tail = tail_address(addr_line)
        if tail:
            item.address_tail = tail
            log("ADDR_TAIL", tail, "町名番地，可直接餵地圖 API")

        # 國家補充判定
        if item.postal_code and not item.country:
            item.country = "日本"
            log("COUNTRY_JP", "郵便番号格式", "判定為日本")
        if "香港" in addr_line:
            item.country = "香港"
        for hint, ctry in CITY_COUNTRY_HINTS:
            if hint in addr_line:
                item.country = ctry

        clean = re.sub(r"〒?\s*\d{3}-?\d{4}", "", addr_line)
        clean = re.sub(r"^[：:\s]+", "", clean).strip()
        item.address = clean or addr_line

    # ══════════════════════════════════════════════════════════
    # 2. 名稱
    # ══════════════════════════════════════════════════════════
    @staticmethod
    def _is_generic(s: str) -> bool:
        t = (s or "").strip()
        if len(t) < 2:
            return True
        if t in GENERIC_NAME:
            return True
        return any(p in t for p in NAME_BLACKLIST_PATTERNS)

    # 行政區名：唔可以當店名（「城東区」「福岡市」唔係店）
    ADMIN_NAME_RE = re.compile(r"(?:都|道|府|県|縣|市|区|區|郡|町|村|洞|街|路|号|號)$")

    @classmethod
    def _valid(cls, s: str) -> bool:
        t = (s or "").strip()
        if not t or cls._is_generic(t) or len(t) < 2:
            return False
        # 純行政區名（例如「城東区」「聖水洞二街」）唔係店名
        if cls.ADMIN_NAME_RE.search(t) and len(t) <= 6:
            return False
        return True

    @staticmethod
    def _venue_from_address(addr: str) -> Optional[str]:
        """由地址欄抽場地名：最後一段冇數字但含設施詞嘅。"""
        if not addr:
            return None
        parts = [p for p in re.split(r"[\s\u3000]+", addr) if p]
        for p in reversed(parts):
            p = p.strip("（）()「」【】〖〗").strip()
            if not p or any(c.isdigit() for c in p):
                continue
            if any(f in p for f in FACILITY) and len(p) >= 3:
                return p
        return None

    # ── 語言／腳本偵測 ─────────────────────────────────
    @staticmethod
    def _scripts(text: str) -> set:
        """偵測文字用咩腳本（cjk / kana / hangul / latin）。"""
        out = set()
        if not text:
            return out
        if re.search(r"[\u3040-\u30ff]", text):
            out.add("kana")
        if re.search(r"[\uac00-\ud7af]", text):
            out.add("hangul")
        if re.search(r"[\u4e00-\u9fff]", text):
            out.add("cjk")
        if re.search(r"[A-Za-z]{3,}", text):
            out.add("latin")
        return out

    @classmethod
    def _looks_like_name(cls, s: str) -> bool:
        """
        判斷一段字係唔係「店名」。
        ⚠️ 一定要語言中立 —— 用戶明確話資料唔一定係中文。

        接受：
            一蘭本社総本店 / 카페 어니언 / Bills Fukuoka / 波止場食堂
        拒絕：
            〒810-0801 / 福岡県福岡市博多区 / 11:00 / 2027年8月 / 電話番号
        """
        t = (s or "").strip()
        if len(t) < 2 or len(t) > 42:
            return False
        # ⚠️ 含 # 嘅唔係店名（hashtag 喺 rule 5 已經剝走 # 先傳入嚟）
        if "#" in t or "＃" in t:
            return False
        if cls._is_generic(t):
            return False
        # ⚠️ 純 metadata 用字唔係店名（「分鐘」「出口」「人均」…）
        from .lexicon import METADATA_WORDS
        if t in METADATA_WORDS:
            return False
        # 全部由 metadata 字組成（去標點後）都唔係店名
        stripped = re.sub(r"[\s\d\-–—:：()（）\[\]【】、，,。.]", "", t)
        if stripped and all(
                stripped == w or stripped.startswith(w) or stripped.endswith(w)
                for w in [stripped]) and stripped in METADATA_WORDS:
            return False
        # 唔可以有地址／數值特徵
        if re.search(r"〒|\d{3}-\d{4}", t):
            return False
        if re.search(r"(?:都|道|府|県|縣)[^\s]{0,4}(?:市|区|區|郡|町|村)", t):
            return False
        if re.fullmatch(r"[\d\s:：\-–—〜~至年月日.]+", t):
            return False
        if re.search(r"(?:電話|TEL|tel|住所|地址|料金|営業|予算|エリア|住所)", t):
            return False
        if re.search(r"\d{1,2}[:：]\d{2}", t):
            return False
        # 文章句子唔係店名
        if cls._looks_like_prose(t):
            return False
        # ⚠️ 節慶／活動名唔係店名（「彼岸節」「花火大会」「〇〇祭」）
        #    呢啲係「主題」，用戶去旅行唔會「去呢間店」
        from .lexicon import EVENT_SUFFIXES
        if len(t) <= 8 and t.endswith(EVENT_SUFFIXES) \
                and not any(h.lower() in t.lower() for h in NAME_HINT):
            return False
        # 要有一種「名字」嘅特徵
        sc = cls._scripts(t)
        if not sc:
            return False
        # 連續 3 個以上拉丁字母（大寫開頭）= 可能係英文店名
        if sc == {"latin"}:
            return bool(re.search(r"\b[A-Z][a-zA-Z]{2,}", t))
        return True

    @staticmethod
    def _clean_name(s: str) -> str:
        """
        清走店名尾嘅雜訊（樓層／房號／括號補充）。
        ⚠️ 但要保留分店資訊（本店／支店／○○店），因為佢哋係名字一部分。
        """
        t = (s or "").strip()
        # 樓層／房號：1階 / 2F / B1 / 地下1階 / 3樓 / 5号室
        t = re.sub(r"[\s,、，]*"
                   r"(?:[BbＢ]?\d{1,2}\s*[階楼樓層]|\d{1,2}\s*[FfＦ]|"
                   r"地下\d{1,2}階?|\d{1,3}\s*[号號]室?)\s*$", "", t)
        # 括號補充（分店除外）
        t = re.sub(r"[\s]*[（(][^）)]{1,20}[）)]\s*$",
                   lambda m: "" if not re.search(r"店|本店|支店", m.group(0)) else m.group(0), t)
        return t.strip()

    @staticmethod
    def _is_location_only(s: str) -> bool:
        """
        係唔係純地區（唔可以當店名）。

        ⚠️ 除咗 LOCATION_HASHTAGS，仲要查埋 DISTRICTS ——
           否則「宮若市」「粕屋町」呢類會通過。
        """
        from .lexicon import DISTRICTS, LOCATION_HASHTAGS
        t = (s or "").strip().lstrip("#＃").strip()
        if not t:
            return True
        low = t.lower()
        if low in {h.lower() for h in LOCATION_HASHTAGS}:
            return True
        for ws in DISTRICTS.values():
            if t in ws:
                return True
        # 行政區後綴（單獨一個「○○市」「○○町」唔係店名）
        if len(t) <= 5 and t.endswith(("市", "区", "區", "町", "村", "県", "縣", "郡", "洞", "동")):
            return True
        return len(t) <= 2

    @classmethod
    def _name_from_address_line(cls, line: str) -> Optional[str]:
        """
        由「地址行」抽出店名。

        ⚠️⚠️ 呢度踩過幾個大坑：
          1. 原本將成句當場地名 → 抽出「🔸住所：〒810-0801 …一蘭本社総本店」成句 ❌
          2. 純地區 hashtag 行（「#福岡 #博多 #美食」）被當地址 → 抽出「#美食」❌
          3. 只攞最右一個 token → 「一蘭 本社総本店」只得「本社総本店」❌

        正確做法：
          ① 剝標籤 → 去郵便番号
          ② **由右邊連續收集**「似名」嘅 token，撞到地址 token 就停
          ③ 拒絕任何「地區限定」或「#」開頭嘅結果
        """
        t = line.strip()
        t = re.sub(r"^[\s🔸🔹📍▪️#＃]*", "", t)
        t = re.sub(r"^(?:住所|住址|地址|Address|address|주소|所在地)\s*[:：]?\s*", "", t)
        t = re.sub(r"^[\s:：]+", "", t)
        t = re.sub(r"〒?\s*\d{3}-?\d{4}\s*", "", t).strip()
        t = re.sub(r"\s+", " ", t)
        if not t:
            return None

        from .lexicon import LOCATION_HASHTAGS
        loc_set = {x.lower() for x in LOCATION_HASHTAGS}

        def is_admin_token(tok: str) -> bool:
            x = tok.strip(" ,、，.")
            if not x:
                return True
            # 純番地
            if re.fullmatch(r"[\d\-–—ー]+(?:[階F地下B]|丁目|番地|番|号|號|chome)?", x):
                return True
            # ⚠️⚠️ 地址 token 可以好長！
            #    「福岡県福岡市博多区中洲5-3-2」有 15 個字，
            #    原本用 len<=9 做守衛 → 認唔到 → 被當成店名收集 → 抽出成串地址 ❌
            #    所以：先用「結構特徵」判斷，唔可以用長度。
            if re.search(r"(?:都|道|府|県|縣)[^\s]{0,8}(?:市|区|區|郡|町|村)", x):
                return True                      # 県+市 結構 = 一定係地址
            if re.search(r"\d+\s*[-–—ー]\s*\d+", x) and \
                    re.search(r"(?:市|区|區|郡|町|村|県|縣|道|府|洞|街|路)", x):
                return True                      # 有番地 + 行政區 = 地址
            # 短嘅純行政後綴
            #    ⚠️ 韓國行政後綴一定要齊：구(區) 동(洞) 시(市) 군(郡) 읍 면 리
            #       漏咗「구」就會將「성동구」當成店名。
            if len(x) <= 9 and re.search(
                    r"(?:都|道|府|県|縣|市|区|區|郡|町|村|洞|街|路"
                    r"|가|로|길|구|동|시|군|읍|면|리|대로|거리)$", x) \
                    and not any(h.lower() in x.lower() for h in NAME_HINT):
                # 例外：「祇園町南側」呢類含町但係地名；如果含店名特徵字就唔當 admin
                return True
            # 羅馬字地址後綴
            if re.search(r"(-ku|-shi|-chome|-dori|-machi|-gun|-cho|-gu|-dong|-ro|-gil)$", x, re.I):
                return True
            # 地區名
            if x.lower().strip(",. ") in loc_set:
                return True
            # 逗號／純標點
            if re.fullmatch(r"[,.、，\-–—/]+", x):
                return True
            return False

        tokens = [tk for tk in t.split(" ") if tk]
        collected: list[str] = []
        for tok in reversed(tokens):
            if is_admin_token(tok):
                if collected:
                    break            # 已經收集到名，遇到地址就停
                continue             # 未收集到 → 跳過地址
            collected.insert(0, tok)
            # 收集到「含店名特徵字」嘅已經夠
            if any(h.lower() in tok.lower() for h in NAME_HINT):
                # 再向左睇一個 token，如果佢都似名就一齊收（「一蘭 本社総本店」）
                continue

        cand = " ".join(collected).strip()

        # 冇空格嘅整串地址 → 用 admin prefix 切
        if len(tokens) == 1:
            cand = cls._cut_admin_prefix(t)

        # ②b 剝走開頭嘅地區名
        #     ⚠️ 真實 bug：「大阪・道頓堀で外せない」被當成店名。
        #        原因：_find_address_line 見到「道頓堀」就當佢係地址行，
        #        而 _name_from_address_line 又冇剝走開頭嘅「大阪・」地區前綴。
        if cand:
            cand = cls._strip_leading_places(cand)

        if cand:
            # ③ 拒絕條件（⚠️ 次序好重要：一定要喺 strip 之前檢查 #）
            if re.match(r"^[#＃]", cand.strip()):
                return None
            cand = cand.strip(" ,、，.")
            if cand.startswith("#") or cand.startswith("＃"):
                return None
            if cand.lower() in loc_set:
                return None
            # ④ 仲有番地 = 其實係地址尾巴（「中洲5-3-2」），唔係店名
            if re.search(r"\d+\s*[-–—ー]\s*\d+", cand) and \
                    not any(h.lower() in cand.lower() for h in NAME_HINT):
                return None
            # ④b 尾隨純數字都係地址尾巴（「大黒ふ頭15」）唔係店名
            #     ⚠️ 實測：橫濱地址「神奈川県横浜市鶴見区大黒ふ頭15」冇店名，
            #        但抽咗「大黒ふ頭15」出嚟 → 搶走正確嘅「波止場食堂 レストハウス店」
            if re.search(r"\d+$", cand) and \
                    not any(h.lower() in cand.lower() for h in NAME_HINT):
                return None
            if not cls._looks_like_name(cand):
                return None
            return cand

        # ④ 最後：喺行尾搵「含 NAME_HINT 嘅連續段」
        for h in NAME_HINT:
            idx = t.rfind(h)
            if idx < 0:
                continue
            seg = t[max(0, idx - 14): idx + len(h)]
            seg = re.sub(r"^[\s\d\-–—ー/,]+", "", seg).strip()
            seg = re.sub(r"^[^\s]*?[都道府県縣市区區郡町村](?=[^\s])", "", seg)
            if cls._looks_like_name(seg) and not re.match(r"^[#＃]", seg):
                return seg
        return None

    # 日文格助詞 —— 出現通常代表「呢句係文章」，唔係地址或店名
    _JP_PARTICLES = ("で", "を", "に", "は", "が", "も", "と", "へ", "や",
                     "から", "まで", "より", "ので", "けど", "たら")
    # 句尾動詞／語尾
    _PROSE_ENDINGS = ("ない", "ます", "です", "ました", "でした", "する",
                      "した", "ある", "いる", "なる", "たい", "でしょう",
                      "嘅", "咗", "㗎", "啦", "喇")

    @classmethod
    def _looks_like_prose(cls, t: str) -> bool:
        """判斷一段字係唔係「文章句子」而唔係店名。"""
        if not t:
            return False
        if any(t.endswith(e) for e in cls._PROSE_ENDINGS):
            return True
        # 中間夾住格助詞（前面要有 >= 2 個字，避免誤殺「木の花」）
        for pt in cls._JP_PARTICLES:
            i = t.find(pt)
            if 2 <= i <= len(t) - 2:
                return True
        return False

    @staticmethod
    def _is_real_address(line: str) -> bool:
        """
        判斷一行係唔係「真地址」。

        ⚠️ 為咩要呢個：
           _find_address_line 見到「道頓堀」就當「大阪・道頓堀で外せない」
           係地址行 → 跟住 _name_from_address_line 抽出「で外せない」做店名 ❌

           真地址一定有：郵便番号 〒 / 數字（番地）/ 都道府縣。
           標題通常冇。
        """
        if not line:
            return False
        if re.search(r"〒|\d", line):
            return True
        if re.search(r"(?:都|道|府|県|縣)[^\s]{0,6}(?:市|区|區|郡|町|村)", line):
            return True
        return False

    @classmethod
    def _strip_leading_places(cls, t: str) -> str:
        """
        剝走字串開頭嘅地區名（連分隔符）。

        例：
          「大阪・道頓堀で外せない」 → 「で外せない」→ 之後 _looks_like_name 會 reject
          「首爾明洞餃子」           → 「餃子」
          「福岡博多一蘭本社」        → 「一蘭本社」
        """
        from .lexicon import DISTRICTS, LOCATION_HASHTAGS
        places = set(LOCATION_HASHTAGS)
        for ws in DISTRICTS.values():
            places.update(ws)
        # 由長到短試，避免「聖水」先過「聖水洞」
        ordered = sorted((p for p in places if p), key=len, reverse=True)
        out = t.strip()
        for _ in range(4):              # 最多剝 4 層（國 › 縣 › 市 › 區）
            before = out
            for pl in ordered:
                if not out.startswith(pl):
                    continue
                rest = out[len(pl):]
                # 一定要有分隔符，或者剩返嘅部分仲夠長（「首爾明洞餃子」）
                if rest[:1] in ("・", "·", " ", "　", "-", "—", ",", "，", "/") or len(rest) >= 3:
                    out = rest.lstrip("・· 　-—,，/")
                    break
            if out == before:
                break
        return out.strip()

    @staticmethod
    def _cut_admin_prefix(t: str) -> str:
        """由一串冇空格嘅地址右邊切走行政區，剩返店名。"""
        out = t
        # 由最左邊開始剝（都道府県 → 市 → 区 → 郡 → 町 → 村）
        for _ in range(6):
            before = out
            out = re.sub(r"^(?:北海道|東京都|大阪府|京都府|[^\s]{2,3}[県縣府])", "", out, count=1)
            out = re.sub(r"^[^\s]{1,4}(?:市|区|區|郡|町|村)", "", out, count=1)
            if out == before:
                break
        # 去番地
        out = re.sub(r"^[\d\-–—ー]+(?:丁目|番地|番)?", "", out)
        return out.strip()

    def _extract_name(self, raw: str, T: str, addr_line: Optional[str],
                      item: Item, log) -> None:
        """
        抽出店名。

        ⚠️ 優先次序好重要（改動前睇清楚）：
            1. 明確標籤「店名：」          最可信
            2. 清單標題「NN｜店名」          IG 整理帖
            3. 〖#店名〗 / 【店名】           IG 常見格式
            4. 「店名」引號
            5. hashtag（**要剔走純地區 hashtag**）
            6. 由地址行右邊切
            7. 由含店名特徵字嘅行抽
        """
        cand: Optional[tuple[str, str]] = None

        # ── 1. 明確標籤（多語言）──
        m = re.search(r"(?:店名|店鋪|店舖|名稱|Name|name|가게\s*이름)\s*[:：]\s*([^\n]{2,42})", T)
        if m:
            nm = m.group(1).strip()
            if self._looks_like_name(nm):
                cand = (nm, "明確「店名：」標籤")

        # ── 2. 清單標題「NN｜店名」──
        if not cand:
            for m in _VENUE_HEAD_RE.finditer(raw):
                nm = m.group(1).strip()
                if self._looks_like_name(nm):
                    cand = (nm, "清單標題「NN｜店名」")
                    break

        # ── 3. 〖〗 【】 標記 ──
        if not cand:
            for pat in (r"〖\s*#?([^〗〖]{2,42})\s*〗", r"【([^】]{2,42})】"):
                m = re.search(pat, raw)
                if not m:
                    continue
                nm = m.group(1).lstrip("#＃").strip()
                if self._looks_like_name(nm):
                    cand = (nm, "〖〗／【】標記")
                    break

        # ── 3b. 由「真地址行」右邊切 ──
        #     ⚠️⚠️ 一定要排喺「」引號**之前**！
        #        原設計意圖（保留至今）：引號內容多數係主題詞，唔係店名。
        #        真實 bug：彼岸花 caption 嘅「彼岸節」「彼岸花」「蔓珠沙華」
        #        全部係引號，但真店名（犬鳴川河川公園）喺地址行尾巴。
        #        如果引號先行，就會抽出「彼岸節」❌
        #
        #     ⚠️ 只有「真地址行」先可以用呢招 ——
        #        「大阪・道頓堀で外せない」呢種標題含地區名但唔係地址，
        #        用咗就會抽出文章碎片（見 _is_real_address）。
        if not cand and addr_line and self._is_real_address(addr_line):
            nm = self._name_from_address_line(addr_line)
            if nm and self._looks_like_name(nm) and not self._looks_like_prose(nm):
                cand = (nm, "由地址行切出店名")

        # ── 4. 「」引號 ──
        #     ⚠️ 唔可以堅持「一定要有店名特徵字」——
        #        好多真店名冇任何特徵字：
        #          「本家大たこ」（たこ唔係特徵字）
        #          「Blue Bottle」
        #        反而「」引號本身已經係好強嘅「呢個係名」信號。
        #        所以改成：有特徵字 → 一定收；冇特徵字但要通過嚴格檢查先收。
        if not cand:
            for m in re.finditer(r"[「『]([^」』]{2,42})[」』]", raw):
                c = m.group(1).strip()
                if not self._looks_like_name(c):
                    continue
                has_hint = any(h.lower() in c.lower() for h in NAME_HINT)
                if has_hint:
                    cand = (c, "「」引號內容（含店名特徵字）")
                    break
                # 冇特徵字：要唔係地區、唔係通用詞、唔係文章句子
                if self._is_location_only(c) or self._is_generic(c):
                    continue
                if self._looks_like_prose(c):
                    continue
                # ⚠️ 長度同標點限制 —— 實測踩過：
                #    「「花開時不長葉，葉長時花就凋謝」」被當成店名 ❌
                #    店名唔會有句讀號，而且通常短。
                if re.search(r"[，。！？；：、]", c):
                    continue
                if len(c) > 16:
                    continue
                # 純拉丁要有大寫字（「Blue Bottle」得，「hello world」唔得）
                sc = self._scripts(c)
                if sc == {"latin"} and not re.search(r"\b[A-Z][a-zA-Z]{2,}", c):
                    continue
                cand = (c, "「」引號內容（無特徵字但似店名）")
                break

        # ── 5. hashtag（⚠️ 一定要剔走純地區 hashtag）──
        if not cand:
            for m in re.finditer(r"#([^\s#\[\]【】〖〗｜|，,。！!？?）)］」』🍤☕]+)", raw):
                h = m.group(1).strip()
                if self._is_location_only(h):
                    continue
                if not self._looks_like_name(h):
                    continue
                # hashtag 要含店名特徵字，或者夠長（>=4）而且唔似地區
                if any(k.lower() in h.lower() for k in NAME_HINT) or len(h) >= 5:
                    cand = (h, "hashtag 店名")
                    break

        # ── 6. ⭐ 由「含店名特徵字嘅非地址行」抽（最實用）
        #     ⚠️ 一定要排喺「地址行切名」之前 —— 因為「波止場食堂 レストハウス店」
        #        呢種第一行就係店名嘅情況，比由地址行猜可靠得多。
        if not cand:
            for ln in raw.split("\n")[:6]:
                line = ln.strip()
                if not line or len(line) > 60:
                    continue
                if re.match(r"^[#＃📍🔸🔹▪️⏰🕐🗺️📝☑︎〒🚇🚌🚕🚗🚶💰🎫📞🌐]", line):
                    continue
                # 地址行唔喺呢度處理
                _stripped = re.sub(
                    r"^[\s🔸🔹📍▪️]*(?:住所|住址|地址|Address|address|주소|所在地)\s*[:：]?\s*",
                    "", line)
                if re.search(r"〒|\d{3}-\d{4}", line) or _stripped != line:
                    continue
                if re.search(r"(?:都|道|府|県|縣)[^\s]{0,4}(?:市|区|區|郡|町|村)", line):
                    continue
                if not any(h.lower() in line.lower() for h in NAME_HINT):
                    continue
                # ⚠️ 分隔符一定要包括「」—— 否則 line = "「咖啡」" 會
                #    seg = "「咖啡」"，令 _is_generic 認唔到「咖啡」
                seg = re.split(r"[｜|，,。！!？?、；;（(【〖\[\]「」『』]", line)[0].strip()
                seg = re.sub(r"^[\s\-–—・•·:：]+", "", seg)
                seg = re.sub(r"[\s\-–—・•·:：]+$", "", seg)
                if self._looks_like_name(seg):
                    cand = (seg, "由含店名特徵字嘅行抽取")
                    break

        # ── 8. 最後防線：地址場地名 ──
        # ── 8b. ⭐ 「名 + 地區」連埋一齊嘅標題
        #     好多 caption 冇地址行，名同地區都喺標題：
        #       「首爾明洞必食」「福岡博多嘅拉麵」「大阪道頓堀たこ焼き」
        #     做法：搵標題入面「最深層嘅地區名」，抽佢前面嘅部分做店名。
        if not cand:
            from .lexicon import DISTRICTS
            for ln in raw.split("\n")[:4]:
                line = ln.strip()
                if not line or len(line) > 44:
                    continue
                # hashtag 行唔會係「店名 + 地區」標題，跳過
                if line.startswith("#") or line.startswith("＃") or line.count("#") >= 2:
                    continue
                if not any(h.lower() in line.lower() for h in NAME_HINT):
                    continue
                best = None
                for grp, names in DISTRICTS.items():
                    for nm in names:
                        if not nm or nm not in line:
                            continue
                        # 要喺標題中間或開頭（唔可以係最尾一個字，否則唔似店名）
                        i = line.index(nm)
                        tail = line[i + len(nm):]
                        if tail and len(tail) <= 12:
                            best = (nm, i, tail)
                            break
                    if best:
                        break
                if best:
                    # 店名 = 地區名前面嘅部分
                    head = line[:best[1]].strip(" ・·,，-—【】〖〗「」『』#＃")
                    # ⚠️ 一定要夠長同唔可以係地區名本身。
                    #    否則「#首爾 #聖水洞 #cafe」會抽出「#首爾 #」。
                    if (self._looks_like_name(head)
                            and not self._is_location_only(head)
                            and len(head) >= 2):
                        cand = (head, f"標題「{best[0]}」之前嘅部分")
                        break

        if not cand and addr_line:
            v = self._venue_from_address(addr_line)
            if v and self._looks_like_name(v):
                cand = (v, "由地址欄抽出場地名（最後防線）")

        if cand:
            nm = self._clean_name(cand[0])
            if nm and self._looks_like_name(nm):
                item.name, item.name_method = nm, cand[1]
                log("NAME", item.name, cand[1])
            else:
                item.name_method = "抽唔到可靠名稱（可能係主題帖，唔係特定店舖）"
        else:
            item.name_method = "抽唔到可靠名稱（可能係主題帖，唔係特定店舖）"

    # ══════════════════════════════════════════════════════════
    # 3. 品牌來源
    # ══════════════════════════════════════════════════════════
    @staticmethod
    def _extract_origin(T: str, item: Item, log) -> None:
        name = item.name or ""
        name_has_home = bool(re.search(r"福岡|博多|天神|中洲|九州", name))
        if name_has_home and item.country and item.country != "日本":
            item.brand_from = "福岡"
            log("ORIGIN_SPLIT", "店名含福岡字眼",
                f"實際位置＝{item.country}{' ' + item.district if item.district else ''}；"
                f"品牌來源＝福岡。⚠️ 唔可以歸入福岡行程！")
        if not item.brand_from and item.country == "日本":
            m = re.search(r"從\s*#?(福岡|東京|大阪|京都|首爾|台灣|日本)\s*(?:漂洋過海|空運|直送|來)", T)
            if m:
                item.brand_from = m.group(1)
                log("ORIGIN_TEXT", m.group(1), "文中提到「從…來」")

    # ══════════════════════════════════════════════════════════
    # 4. 日期
    # ══════════════════════════════════════════════════════════
    @staticmethod
    def _extract_dates(T: str, item: Item, log) -> None:
        blob_parts: list[str] = []
        m = re.search(r"🔸?\s*日期\s*[:：]?\s*([\s\S]{0,220}?)(?=\n\s*🔸|\n\s*[^\s]*時間|$)", T)
        if m:
            blob_parts.append(m.group(1))
        else:
            for ln in T.split("\n"):
                if re.search(r"\d{1,2}\s*月\s*\d{1,2}\s*日", ln):
                    blob_parts.append(ln)
        blob = " ".join(blob_parts)

        found: list[DateRange] = []

        # 範圍：9月24日至10月8日
        for m in re.finditer(r"(\d{1,2})\s*月\s*(\d{1,2})?\s*日?\s*至\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日", blob):
            found.append(DateRange(
                raw=m.group(0).strip(),
                date_from=f"{int(m.group(1))}/{int(m.group(2))}",
                date_to=f"{int(m.group(3))}/{int(m.group(4))}",
                kind="range",
            ))

        # 單日／時段：10月4日、9月中、10月初
        period_map = {"初": "上旬", "上旬": "上旬", "中": "中旬", "中旬": "中旬",
                      "下旬": "下旬", "底": "下旬", "末": "下旬"}
        for m in re.finditer(r"(\d{1,2})\s*月\s*(?:(\d{1,2})\s*日|(上旬|中旬|下旬|初|中|底|末))", T):
            if m.start() > 0 and T[m.start() - 1] == "年":
                continue                      # 排除「2026年10月」
            raw = m.group(0).strip()
            if any(raw in f.raw or f.raw in raw for f in found):
                continue
            if m.group(2):
                found.append(DateRange(raw=raw, date_from=f"{int(m.group(1))}/{int(m.group(2))}", kind="day"))
            else:
                label = f"{int(m.group(1))}月{period_map.get(m.group(3), m.group(3))}"
                found.append(DateRange(raw=raw, date_from=label, kind="period"))

        # 去重 + 範圍優先
        seen: set[str] = set()
        uniq: list[DateRange] = []
        for f in found:
            if f.raw in seen:
                continue
            seen.add(f.raw)
            uniq.append(f)
        uniq.sort(key=lambda d: 0 if d.kind == "range" else 1)
        item.dates = uniq
        if uniq:
            log("DATE", " / ".join(d.raw for d in uniq), f"抽到 {len(uniq)} 個日期")

    # ══════════════════════════════════════════════════════════
    # 5. 時間
    # ══════════════════════════════════════════════════════════
    @staticmethod
    def _conv_time(s: str) -> str:
        s = re.sub(r"(上午|早上|凌晨)", "AM", s)
        s = re.sub(r"(下午|晚上|夜晚|中午)", "PM", s)
        s = re.sub(r"(\d{1,2})\s*時", r"\1:00", s)
        return s

    def _extract_hours(self, T: str, item: Item, log) -> None:
        raw = None
        m = re.search(r"(?:營業時間|開放時間|時間|営業時間|🕐|🕒)\s*[:：]?\s*([^\n]{0,80})", T)
        if m:
            raw = m.group(1)
        if not raw:
            m = re.search(r"(\d{1,2}\s*[:：]\s*\d{2}\s*至\s*\d{1,2}\s*[:：]\s*\d{2})", T)
            if m:
                raw = m.group(1)
        if raw:
            h = self._conv_time(raw)
            h = re.sub(r"[（(][^）)]*[）)]", "", h).strip()
            if re.fullmatch(r"\d{1,2}:\d{2}\s*至\s*\d{1,2}:\d{2}", h):
                h = h.replace("至", "-")
            if len(h) > 60:
                h = h[:60]
            item.hours = h
            log("HOURS", h, "時間表達式正規化")

        # 「下午3時至晚上8時」冇標籤
        if not item.hours:
            m = re.search(r"(?:下午|晚上|上午|早上)[^\n]{0,4}?\d{1,2}\s*時\s*至\s*(?:下午|晚上|上午|早上)?[^\n]{0,4}?\d{1,2}\s*時", T)
            if m:
                item.hours = self._conv_time(m.group(0)).strip()
                log("HOURS_CN", item.hours, "中文時間（下午X時至晚上Y時）")

        # 清理：由活動名之中抽純時間
        if item.hours:
            m = re.search(r"(?:AM|PM)?\d{1,2}(?::\d{2})?\s*[-至]\s*(?:AM|PM)?\d{1,2}(?::\d{2})?", item.hours)
            if m and m.group(0) != item.hours and len(item.hours) > len(m.group(0)) + 8:
                item.hours = m.group(0).replace("至", "-")
                log("HOURS_TRIM", item.hours, "由活動名之中抽出純時間")
            item.hours = re.sub(r"^[^\dAMPM]+", "", item.hours).strip()

    # ══════════════════════════════════════════════════════════
    # 6. 價錢
    # ══════════════════════════════════════════════════════════
    @staticmethod
    def _extract_price(T: str, item: Item, log) -> None:
        pats = [
            r"(?:人均|予算|預算|費用|價錢|💰)\s*[:：]?\s*([^\n]{0,30})",
            r"([¥₩$]\s?[\d,]{2,9}(?:\s*[～至~-]\s*[¥₩$]?\s?[\d,]{2,9})?)",
            r"(\d[\d,]*)\s*円",
        ]
        for p in pats:
            m = re.search(p, T)
            if m:
                item.price = re.sub(r"\s+", " ", m.group(1)).strip()
                log("PRICE", item.price, "價錢／預算")
                return

    # ══════════════════════════════════════════════════════════
    # 7. 分類
    # ══════════════════════════════════════════════════════════
    @staticmethod
    def _extract_category(T: str, item: Item, log) -> None:
        low = T.lower()
        for rule in CATEGORY_RULES:
            for w in rule["words"]:
                if w.lower() in low:
                    item.category = rule["key"]
                    item.category_label = rule["label"]
                    item.category_why = w
                    log("CATEGORY", w, f"命中「{w}」→ {rule['key']} / {rule['label']}")
                    return

    # ══════════════════════════════════════════════════════════
    # 8. Hashtag
    # ══════════════════════════════════════════════════════════
    @staticmethod
    def _extract_tags(raw: str, item: Item, log) -> None:
        tags: list[str] = []
        for m in re.finditer(r"#([^\s#\[\]【】〖〗｜|，,。！!？?）)］」』🍤☕]+)", raw):
            t = m.group(1).strip()
            if 2 <= len(t) <= 16 and t not in tags:
                tags.append(t)
        item.tags = tags[:12]
        if item.tags:
            log("HASHTAG", " ".join(item.tags), "抽到 hashtag 做標籤")

    # ══════════════════════════════════════════════════════════
    # 9. 信心分數
    # ══════════════════════════════════════════════════════════
    @staticmethod
    def _score(item: Item, extra: dict[str, int] | None = None) -> None:
        nm = item.name_method or ""
        if not item.name:
            c_name = 0
        # ⚠️ Google Maps / JSON-LD 係「權威來源」—— 名直接由佢哋嚟，
        #    唔應該同「由引號猜」同一級。之前漏咗，令 Maps 結果由 93% 跌到 73%。
        elif any(k in nm for k in ("Google Maps", "JSON-LD", "清單標題", "用戶提供")):
            c_name = 98
        elif "店名：" in nm:
            c_name = 96
        elif "〖〗" in nm:
            c_name = 92
        elif "標題" in nm:
            c_name = 88
        elif "引號" in nm:
            c_name = 86
        elif "地址" in nm:
            c_name = 82
        elif "hashtag" in nm:
            c_name = 80
        else:
            c_name = 70

        c_addr = 0
        if item.address:
            c_addr = 96 if item.postal_code else (86 if item.address_tail else 74)

        if item.district or item.city:
            c_loc = 92 if item.address else 70
        else:
            c_loc = 0

        C = {
            "name": c_name,
            "location": c_loc,
            "address": c_addr,
            "category": 78 if item.category else 0,
            "dates": 88 if item.dates else 0,
            "hours": 72 if item.hours else 0,
            "price": 84 if item.price else 0,
            "phone": 90 if item.phone else 0,
        }
        if extra:
            for k, v in extra.items():
                C[k] = max(C.get(k, 0), v)

        weights = [("name", 0.32), ("location", 0.26), ("address", 0.16),
                   ("category", 0.14), ("dates", 0.06), ("hours", 0.03), ("price", 0.03)]
        total = sum(C.get(k, 0) * w for k, w in weights)

        item.field_confidence = C
        item.confidence = round(total)
        item.needs_review = item.confidence < 70 or not item.name or not (item.district or item.city)


# ── 方便呼叫 ─────────────────────────────────────────────
_default = CaptionParser()


def parse_caption(text: str, **kw) -> Item:
    """快捷函式：將一段 caption 解析成 Item。"""
    return _default.parse(text, **kw)


# ══════════════════════════════════════════════════════════════
# 公開 API
# ══════════════════════════════════════════════════════════════

def parse_caption_multi(text: str, *, source: str = "caption",
                        source_name: str = "文字",
                        url: str | None = None) -> list[Item]:
    """
    解析一段 caption，可以回傳**多個** Item。

    點解要咁：IG / 小紅書好興一帖列 10 間店（用戶真實例子：
    「02｜プルトゥンヌンテジ / 03｜チャドルバキンチュクミ …」）。
    如果當佢係一間店，就會錯得好離譜。

    回傳：
        清單式 caption → 每間店一個 Item（帶地區提示）
        普通 caption   → 一個 Item 嘅 list
    """
    venues = split_into_venues(text)
    parser = CaptionParser()

    if len(venues) >= 2:
        items: list[Item] = []
        for v in venues:
            # 將「地區」「時間」「推介菜」餵埋俾 parser，等佢抽得更準
            chunk_parts = [v["name"]] if v["name"] else []
            if v["area"]:
                chunk_parts.append(f"🗺️ エリア：{v['area']}")
            if v["hours"]:
                chunk_parts.append(f"⏰ {v['hours']}")
            if v["menu"]:
                chunk_parts.append(f"📝 推しメニュー：{v['menu']}")
            it = parser.parse("\n".join(chunk_parts), source=source,
                              source_name=source_name, url=url,
                              area_hint=v["area"])
            if v["name"]:
                it.name = v["name"]           # 標題行嘅名最準
                it.name_method = "清單標題「NN｜店名」"
            if v["area"]:
                it._area_hint = v["area"]
                it.district = it.district or v["area"]
            if v["menu"]:
                it.tags.append(f"推介：{v['menu']}")
            if v["hours"]:
                it.hours = it.hours or v["hours"]
            CaptionParser._score(it)
            it.field_confidence["name"] = 92
            items.append(it)
        return items

    # 普通單店 caption
    item = parser.parse(text, source=source, source_name=source_name, url=url)
    # 抽「地區」提示（唔覆蓋已有嘅 district，除非 district 係空）
    ma = _AREA_RE.search(text)
    if ma:
        area = ma.group(1).strip()
        item._area_hint = area
        if not item.district and area:
            item.district = area
            item.field_confidence["location"] = max(
                item.field_confidence.get("location", 0), 74)
            log = list(item.rules_matched)
            log.append({"rule": "AREA_HINT", "match": area,
                        "note": "由「エリア」標示抽出地區"})
            item.rules_matched = log
            CaptionParser._score(item)
    return [item]
