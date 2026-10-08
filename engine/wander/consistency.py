"""
一致性檢查：地址文字 vs 座標，睇下係咪同一個地方。

⚠️ 真實案例（用戶提供）：
    店名  イオンモール筑紫野         → 暗示 福岡
    地址  福岡県筑紫野市立明寺434-1   → 福岡
    〒    110-0015                  → 東京都台東区
    座標  35.70982, 139.77868       → 東京都台東区東上野
    → 地址同座標係兩個唔同城市！用戶會去錯地方。
"""
from __future__ import annotations

from .caption import CaptionParser
from .lexicon import DISTRICTS, GROUP_COUNTRY, GROUP_TO_PREFECTURE, sorted_places
from .models import Item


def _hierarchy_from_text(text: str) -> dict:
    """由地址文字抽行政層級（唔用座標）。"""
    if not text:
        return {}
    probe = Item()
    CaptionParser()._parse_address(text, "consistency", probe, lambda *a: None)
    return {
        "country": probe.country,
        "prefecture": probe.prefecture,
        "city": probe.city,
        "district": probe.district,
        "postal_code": probe.postal_code,
    }


def check_coordinate_consistency(item: Item, *, reverse=True) -> dict:
    """
    檢查 item 嘅地址／郵便番号同座標係咪指向同一個地方。

    回傳：
        {"consistent": True/False/None, "issues": [...], "reverse": {...}}
        consistent=None 代表資料不足，判斷唔到。
    """
    issues: list[str] = []
    if item.lat is None or item.lng is None:
        return {"consistent": None, "issues": [], "reverse": None}

    from .lookup import reverse_geocode
    rev = reverse_geocode(item.lat, item.lng) if reverse else None
    rev_info = None
    if rev:
        rev_info = {"country": rev.country, "prefecture": rev.state,
                    "city": rev.city, "district": rev.district}

    # ── ① 由地址文字抽層級 ──
    addr_text = " ".join(filter(None, [item.address, item.postal_code]))
    text_h = _hierarchy_from_text(addr_text) if addr_text else {}

    # item 自己已經有嘅層級都要考慮（可能由 caption 抽到）
    own = {"country": item.country, "prefecture": item.prefecture,
           "city": item.city, "district": item.district}
    merged = {k: own.get(k) or text_h.get(k) for k in own}

    if not rev_info:
        return {"consistent": None, "issues": issues, "reverse": None,
                "text": merged}

    # ── ② 比對策略：保守評分制 ──
    #
    #    ⚠️⚠️ 呢度踩過兩個坑：
    #
    #    坑 1：Nominatim 對日本地址嘅欄位對應**唔一致**
    #          東京台東区   → city='台東区', state=None
    #          福岡市博多区 → city='福岡市',  state=None
    #          神奈川       → city='横浜市',  state='神奈川県'
    #          → 唔可以逐個欄位硬對，會誤報。
    #
    #    坑 2：用「共同 >=2 字前綴」做模糊比對太寬鬆
    #          地址「東上野」vs 反查「東上」→ 前綴相同但係唔同地方 → 誤配。
    #
    #    最終做法：**評分 + 保守**。只有明確冇任何一層對得上，
    #    或者郵便番号唔夾，先當衝突。寧願唔報，都唔好誤報
    #    （誤報會令用戶唔信任個警告）。

    def _chain(*vals) -> str:
        return " ".join(str(v) for v in vals if v)

    def _norm_place(x: str) -> str:
        return (x or "").replace("縣", "県").replace("區", "区") \
                        .replace("臺", "台").replace(" ", "").strip()

    def _exact(a: str, b: str) -> bool:
        return bool(a) and bool(b) and _norm_place(a) == _norm_place(b)

    def _contains(a: str, b: str) -> bool:
        """一個地名包含另一個（>=3 字先算，避免「東上」呢種短前綴誤配）。"""
        a, b = _norm_place(a), _norm_place(b)
        if len(a) < 3 or len(b) < 3:
            return False
        return a in b or b in a

    addr_parts = [x for x in [merged.get("prefecture"), merged.get("city"),
                              merged.get("district")] if x]
    rev_parts = [x for x in [rev.state, rev.city, rev.district] if x]

    # ⚠️ 要**分層**比對，唔可以將所有層級混一齊。
    #    真實案例：首爾地址「성동구 연무장길 47」
    #      地址層級 = ['성동구'(city), '연무장길'(district=街名)]
    #      反查層級 = ['서울특별시'(city), '성수2가3동'(district=洞名)]
    #    → 街名同洞名本質上唔同層次，混一齊比會誤報衝突。
    #    所以：**只用「地區／市」層比對，district 唔參與判定。**
    addr_top = [x for x in [merged.get("prefecture"), merged.get("city")] if x]
    rev_top = [x for x in [rev.state, rev.city] if x]

    def _match_top(a: list[str], b: list[str]) -> bool:
        return any(_exact(x, y) or _contains(x, y) for x in a for y in b)

    hits = 1 if (addr_top and rev_top and _match_top(addr_top, rev_top)) else 0

    addr_chain = _chain(*addr_parts)
    rev_chain = _chain(*rev_parts)

    # ── ③ 郵便番号（最強信號，日本前 3 位 = 地區）──
    pc = item.postal_code or text_h.get("postal_code")
    postal_bad = False
    if pc and rev.postcode:
        a, b = str(pc).replace("-", ""), str(rev.postcode).replace("-", "")
        if len(a) >= 3 and len(b) >= 3 and a[:3] != b[:3]:
            postal_bad = True

    # ── ④ 判定（保守）──
    #
    #    ⚠️ 郵便番号**唔可以單獨做證據**。實測：
    #       橫濱鶴見区大黒ふ頭（〒230-0054）嘅座標反查到 〒231-0017 ——
    #       同一區但唔同番号。所以 3 位比對會有誤報。
    #     → 郵便番号只可以做「加權」，唔可以單獨判衝突。
    if addr_top and rev_top and hits == 0:
        # 完全冇任何一層對得上 = 兩個唔同地方
        msg = f"地址寫「{addr_chain}」，但座標喺「{rev_chain}」"
        if postal_bad:
            msg += f"（郵便番号 〒{pc} vs 〒{rev.postcode} 亦唔夾）"
        issues.append(msg)
    elif postal_bad and hits == 0:
        # 只有郵便番号，而且兩邊資料都好少 → 只做提示，唔算硬衝突
        issues.append(
            f"郵便番号 〒{pc} 同座標反查嘅 〒{rev.postcode} 唔一致（資料不足，請人手確認）")

    return {
        "consistent": len(issues) == 0,
        "issues": issues,
        "reverse": rev_info,
        "text": merged,
        "postal_mismatch": any("郵便番号" in i for i in issues),
    }


def apply_consistency_check(item: Item, *, reverse=True) -> Item:
    """跑一致性檢查，將問題寫入 notes 同 flag。"""
    r = check_coordinate_consistency(item, reverse=reverse)
    if r["consistent"] is False:
        item.notes.append("⚠️ 地址同座標唔一致：" + "；".join(r["issues"]))
        # 唔自動改資料 —— 交俾用戶決定邊個對
        item.needs_review = True
        extra = getattr(item, "_consistency", None) or {}
        try:
            item.__dict__["_consistency"] = r
        except Exception:
            pass
    return item
