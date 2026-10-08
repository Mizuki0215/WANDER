"""
wander.models — 統一資料模型

所有來源（Google Maps link、IG caption、Tabelog HTML、用戶手動輸入）
最後都收斂成同一個 Item 物件。咁 app 層只需要識一種資料結構。

呢個檔係整個系統嘅「合約」，所以改動要小心。
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Literal, Optional

# ── 分類：永遠儲英文 enum，顯示時先翻譯 ──────────────────────
Category = Literal["food", "shopping", "play", "stay", "transport", "other"]

CATEGORY_LABELS: dict[str, dict[str, str]] = {
    "food":      {"zh_HK": "美食",   "zh_CN": "美食",   "en": "Food",       "ja": "グルメ"},
    "shopping":  {"zh_HK": "購物",   "zh_CN": "购物",   "en": "Shopping",   "ja": "ショッピング"},
    "play":      {"zh_HK": "玩樂",   "zh_CN": "玩乐",   "en": "Activities", "ja": "遊び"},
    "stay":      {"zh_HK": "住宿",   "zh_CN": "住宿",   "en": "Stay",       "ja": "宿泊"},
    "transport": {"zh_HK": "交通",   "zh_CN": "交通",   "en": "Transport",  "ja": "交通"},
    "other":     {"zh_HK": "其他",   "zh_CN": "其他",   "en": "Other",      "ja": "その他"},
}

CATEGORY_ICONS = {
    "food": "🍜", "shopping": "🛍", "play": "🎡",
    "stay": "🏨", "transport": "🚇", "other": "📍",
}


@dataclass
class DateRange:
    """日期。單日 = to 為 None；範圍 = 兩個都有。"""
    raw: str                      # 原文，例如 "9月24日至10月8日"
    date_from: str                # 正規化，例如 "9/24" 或 "10月上旬"
    date_to: Optional[str] = None
    kind: str = "day"             # day | range | period

    @property
    def display(self) -> str:
        if self.kind == "range" and self.date_to:
            return f"{self.date_from} – {self.date_to}"
        return self.date_from


@dataclass
class Item:
    """
    一個收藏項目。所有解析結果最後都變成佢。

    raw_* 欄位一定要保留：將來改進算法時，可以將所有舊 link 重新跑一次，
    唔會蝕資料。呢個係做 data product 最重要嘅習慣。
    """
    # ── 來源 ──
    source: str = "manual"            # gmaps | instagram | xiaohongshu | web | caption | manual
    source_name: str = ""
    url: Optional[str] = None
    raw_title: Optional[str] = None
    raw_caption: Optional[str] = None
    raw_image: Optional[str] = None

    # ── 名稱 ──
    name: Optional[str] = None
    name_method: Optional[str] = None

    # ── 位置 ──
    country: Optional[str] = None
    prefecture: Optional[str] = None
    city: Optional[str] = None
    district: Optional[str] = None
    address: Optional[str] = None
    postal_code: Optional[str] = None
    address_tail: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    brand_from: Optional[str] = None   # 「品牌來自」，例如銅鑼灣店但係福岡品牌
    _area_hint: Optional[str] = None   # 「🗺️ エリア：明洞」呢種地區提示
    # 需要用戶補資料嘅提示（例如 IG 封鎖 → 要貼 caption）
    #   "caption" = 要用戶貼 caption 文字
    needs_input: Optional[str] = None
    blocked_reason: Optional[str] = None

    # ── 分類 ──
    category: Optional[Category] = None
    category_label: Optional[str] = None
    category_why: Optional[str] = None

    # ── 詳情 ──
    dates: list[DateRange] = field(default_factory=list)
    hours: Optional[str] = None
    phone: Optional[str] = None
    price: Optional[str] = None
    tags: list[str] = field(default_factory=list)

    # ── 品質 ──
    confidence: int = 0
    field_confidence: dict[str, int] = field(default_factory=dict)
    needs_review: bool = True
    rules_matched: list[dict[str, str]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    parsed_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )

    # ── 衍生屬性 ──
    @property
    def location_path(self) -> list[str]:
        """用嚟做 group 內自動分類，例如 ['日本','福岡縣','宮若市']"""
        out = []
        for v in (self.country, self.prefecture, self.city, self.district):
            if v and v not in out and v != "（日本）":
                out.append(v)
        return out

    @property
    def location_display(self) -> str:
        return " › ".join(self.location_path) if self.location_path else "未分類"

    @property
    def category_display(self) -> str:
        if not self.category:
            return "未分類"
        icon = CATEGORY_ICONS.get(self.category, "📍")
        label = self.category_label or CATEGORY_LABELS.get(self.category, {}).get("zh_HK", self.category)
        return f"{icon} {label}"

    @property
    def has_coords(self) -> bool:
        return self.lat is not None and self.lng is not None

    @property
    def google_maps_url(self) -> Optional[str]:
        if self.has_coords:
            return f"https://www.google.com/maps/search/?api=1&query={self.lat},{self.lng}"
        if self.name and self.address:
            from urllib.parse import quote
            return f"https://www.google.com/maps/search/?api=1&query={quote(self.name + ' ' + self.address)}"
        return None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["location_path"] = self.location_path
        d["location_display"] = self.location_display
        d["category_display"] = self.category_display
        d["google_maps_url"] = self.google_maps_url
        return d

    def merge(self, other: "Item") -> "Item":
        """
        合併兩個 Item（例如 Google Maps link + IG caption）。

        規則：唔覆蓋已經有嘅值，只填補空缺。座標永遠優先保留。
        confidence 取較高者。
        """
        coords_kept = self.has_coords
        # 保護：唔可以俾 None 清走已有嘅值
        protected = {k: v for k, v in asdict(self).items() if v not in (None, "", [], {})}
        for f in self.__dataclass_fields__:
            if f in ("parsed_at", "rules_matched", "notes", "dates", "tags",
                     "field_confidence", "confidence", "needs_review", "source", "source_name"):
                continue
            cur = getattr(self, f)
            new = getattr(other, f)
            if (cur is None or cur == "") and new:
                setattr(self, f, new)

        # 保險：任何原本有值嘅欄位，如果變成空，就還原
        for k, v in protected.items():
            if k in ("parsed_at", "rules_matched", "notes", "tags", "field_confidence"):
                continue
            if getattr(self, k, None) in (None, "", [], {}):
                setattr(self, k, v)

        # 列表類：聯集
        for d in other.dates:
            if not any(x.raw == d.raw for x in self.dates):
                self.dates.append(d)
        for t in other.tags:
            if t not in self.tags:
                self.tags.append(t)

        # 規則紀錄合併
        seen = {(r.get("rule"), r.get("match")) for r in self.rules_matched}
        for r in other.rules_matched:
            if (r.get("rule"), r.get("match")) not in seen:
                self.rules_matched.append(r)

        if other.confidence > self.confidence:
            self.confidence = other.confidence
        for k, v in other.field_confidence.items():
            self.field_confidence[k] = max(self.field_confidence.get(k, 0), v)

        src = f"{self.source_name or self.source}+{other.source_name or other.source}"
        self.source_name = src
        self.needs_review = self.confidence < 70 or not self.name
        return self
