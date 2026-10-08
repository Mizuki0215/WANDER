"""
wander.zones — 分區行程規劃
============================

用戶要求（原文）：
    「like 分區 plan 行程時幫你分好啲區」

即係：你入咗一堆地址／景點，App 幫你按**地理位置**分組，
然後建議「第一日去呢一區，第二日去嗰一區」。

⚠️ 為咩唔用 AI：
   分區係**幾何問題**，唔係語意問題。
   兩個地方距離 300 米就係同一區，距離 8 公里就唔係 —— 純數學。
   用 Haversine + 貪心聚類，100% 可預測、可測試、離線都用得。

⚠️ 為咩唔用 k-means：
   k-means 要你事先指定「分幾多區」，而且結果唔穩定
   （同一個 input 跑兩次可能唔同，因為初始中心隨機）。
   行程規劃唔可以咁 —— 用戶撳一次同撳兩次要一樣。
   所以用**確定性貪心聚類**：由最密集嘅點開始，掃描半徑內嘅所有點。
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Iterable, Optional

# ── 聚類參數 ──
#   走路 12-15 分鐘 ≈ 1100m。所以同一區嘅定義係「互相 1100m 內」。
#   ⚠️ 原本用 800m，結果「博多駅」同「中洲」分開咗兩區 ——
#      但對旅客嚟講佢哋係同一區（行得到）。1100m 啱啲。
ZONE_RADIUS_M = 1100
#   兩區距離超過呢個數就唔應該排同一日（的士太貴／太遠）
FAR_APART_M = 4000


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """兩點距離（米）。標準 Haversine 公式。"""
    R = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = (math.sin(dp / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2)
    return 2 * R * math.asin(math.sqrt(min(1.0, a)))


@dataclass
class Place:
    """要分區嘅一個點。"""
    id: str
    name: str = ""
    lat: Optional[float] = None
    lng: Optional[float] = None
    district: Optional[str] = None
    city: Optional[str] = None
    category: Optional[str] = None
    duration: Optional[int] = None      # 分鐘
    raw: dict = field(default_factory=dict)

    @property
    def has_coords(self) -> bool:
        return self.lat is not None and self.lng is not None


@dataclass
class Zone:
    """一區。"""
    key: str
    label: str                          # 顯示名（地區名或「第N區」）
    district: Optional[str] = None
    places: list[Place] = field(default_factory=list)
    lat: Optional[float] = None         # 中心
    lng: Optional[float] = None
    spread_m: float = 0.0               # 區內最遠兩點距離
    total_minutes: int = 0

    @property
    def count(self) -> int:
        return len(self.places)

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "label": self.label,
            "district": self.district,
            "count": self.count,
            "lat": self.lat,
            "lng": self.lng,
            "spread_m": round(self.spread_m),
            "total_minutes": self.total_minutes,
            "places": [
                {"id": p.id, "name": p.name, "lat": p.lat, "lng": p.lng,
                 "district": p.district, "category": p.category,
                 "duration": p.duration}
                for p in self.places
            ],
        }


def _centroid(places: list[Place]) -> tuple[float, float]:
    lats = [p.lat for p in places if p.has_coords]
    lngs = [p.lng for p in places if p.has_coords]
    return (sum(lats) / len(lats), sum(lngs) / len(lngs))


def _max_spread(places: list[Place]) -> float:
    """區內最遠兩點距離（衡量「呢區大唔大」）。"""
    pts = [p for p in places if p.has_coords]
    if len(pts) < 2:
        return 0.0
    worst = 0.0
    for i, a in enumerate(pts):
        for b in pts[i + 1:]:
            d = haversine_m(a.lat, a.lng, b.lat, b.lng)
            if d > worst:
                worst = d
    return worst


def build_zones(items: Iterable, *,
                radius_m: float = ZONE_RADIUS_M) -> list[Zone]:
    """
    將景點分成地理區。

    演算法（確定性，唔用隨機）：
      ① 有座標嘅 → 貪心聚類：
         由最密集嘅點開始做種子，吸納 radius 內所有未分組嘅點。
      ② 冇座標但有地區名嘅 → 按地區名分組。
      ③ 完全冇資料嘅 → 全部塞落一個「未定位」區。

    排序：多人嘅區排前面（行程通常先去重點區）。
    """
    items = list(items)
    places: list[Place] = []
    for it in items:
        if isinstance(it, Place):
            places.append(it)
            continue
        d = it if isinstance(it, dict) else getattr(it, "__dict__", {})
        get = (d.get if isinstance(d, dict) else lambda k, _d=d: getattr(_d, k, None))
        places.append(Place(
            id=str(get("id") or ""),
            name=get("name") or "",
            lat=get("lat"), lng=get("lng"),
            district=get("district"), city=get("city"),
            category=get("category"), duration=get("duration"),
            raw=dict(d) if isinstance(d, dict) else {},
        ))

    located = [p for p in places if p.has_coords]
    named = [p for p in places if not p.has_coords and (p.district or p.city)]
    unknown = [p for p in places if not p.has_coords and not (p.district or p.city)]

    zones: list[Zone] = []

    # ── ① 座標聚類 ──
    remaining = list(located)
    while remaining:
        # 揀最密集嘅點做種子：數下每個點 radius 內有幾多鄰居
        best_seed, best_score = None, -1
        for cand in remaining:
            n = sum(1 for o in remaining
                    if haversine_m(cand.lat, cand.lng, o.lat, o.lng) <= radius_m)
            if n > best_score:
                best_seed, best_score = cand, n
        seed = best_seed

        group = [o for o in remaining
                 if haversine_m(seed.lat, seed.lng, o.lat, o.lng) <= radius_m]
        for g in group:
            remaining.remove(g)

        clat, clng = _centroid(group)
        district = _dominant_district(group)
        zones.append(Zone(
            key=f"geo{len(zones)}",
            label=district or f"第 {len(zones) + 1} 區",
            district=district,
            places=sorted(group, key=lambda p: p.name or ""),
            lat=round(clat, 5), lng=round(clng, 5),
            spread_m=_max_spread(group),
            total_minutes=sum(p.duration or 0 for p in group),
        ))

    # ── ①b 合併孤兒區 ──
    #     ⚠️ 為咩要呢步：
    #        「博多駅」離中洲 1.13km，啱啱超出 1100m 半徑 →
    #        自己變成一區，得 1 個景點。但 1 個景點嘅「區」
    #        對行程規劃冇意義（唔會為咗一個站排一日）。
    #        所以：細區（< 3 個景點）距離大區夠近就併入去。
    zones = _merge_small_zones(zones, radius_m * 1.6)

    # ── ② 按地區名分組 ──
    by_name: dict[str, list[Place]] = {}
    for p in named:
        by_name.setdefault(p.district or p.city, []).append(p)
    for name, group in by_name.items():
        zones.append(Zone(
            key=f"name:{name}", label=name, district=name,
            places=sorted(group, key=lambda p: p.name or ""),
            total_minutes=sum(p.duration or 0 for p in group),
        ))

    # ── ③ 未定位 ──
    if unknown:
        zones.append(Zone(
            key="unknown", label="未定位", places=unknown,
            total_minutes=sum(p.duration or 0 for p in unknown),
        ))

    # 多人嘅區排前面
    #   ⚠️「未定位」永遠排最後 —— 佢係「仲要處理」嘅嘢，
    #      唔應該同真正嘅分區混埋一齊排。
    zones.sort(key=lambda z: (z.key == "unknown", -z.count, z.label))
    return zones


def _merge_small_zones(zones: list[Zone], merge_radius_m: float,
                       min_size: int = 3) -> list[Zone]:
    """
    將「孤兒區」（景點太少）併入附近嘅大區。

    規則：
      · 大區（>= min_size 個景點）唔會被合併
      · 細區距離某個大區中心 <= merge_radius_m → 併入該大區
      · 細區同細區之間都會合併（如果夠近）
      · 合併後重新計中心同範圍
    """
    if len(zones) <= 1:
        return zones

    big = [z for z in zones if z.count >= min_size and z.lat is not None]
    small = [z for z in zones if z.count < min_size or z.lat is None]
    if not big:
        return zones

    leftovers: list[Zone] = []
    for z in small:
        if z.lat is None:
            leftovers.append(z)
            continue
        # 搵最近嘅大區
        near = min(big, key=lambda b: haversine_m(z.lat, z.lng, b.lat, b.lng))
        d = haversine_m(z.lat, z.lng, near.lat, near.lng)
        if d <= merge_radius_m:
            near.places.extend(z.places)
            near.places.sort(key=lambda p: p.name or "")
            near.total_minutes += z.total_minutes
            # 重算中心同範圍
            near.lat, near.lng = (round(v, 5) for v in _centroid(near.places))
            near.spread_m = _max_spread(near.places)
        else:
            leftovers.append(z)

    # 剩返嘅細區：如果互相夠近就合併
    merged: list[Zone] = []
    for z in leftovers:
        if z.lat is None:
            merged.append(z)
            continue
        hit = None
        for m in merged:
            if m.lat is None:
                continue
            if haversine_m(z.lat, z.lng, m.lat, m.lng) <= merge_radius_m:
                hit = m
                break
        if hit:
            hit.places.extend(z.places)
            hit.places.sort(key=lambda p: p.name or "")
            hit.total_minutes += z.total_minutes
            hit.label = f"{hit.label}・{z.label}"
            hit.lat, hit.lng = (round(v, 5) for v in _centroid(hit.places))
            hit.spread_m = _max_spread(hit.places)
        else:
            merged.append(z)

    return big + merged


def _dominant_district(places: list[Place]) -> Optional[str]:
    """區入面最常見嘅地區名。"""
    counts: dict[str, int] = {}
    for p in places:
        d = p.district or p.city
        if d:
            counts[d] = counts.get(d, 0) + 1
    if not counts:
        return None
    return max(counts.items(), key=lambda kv: (kv[1], kv[0]))[0]


@dataclass
class DayPlan:
    day: int
    zones: list[Zone]
    label: str
    travel_minutes: int = 0
    places: list[Place] = field(default_factory=list)
    warning: str = ""                  # 「呢日要跨區，車程較長」之類

    def to_dict(self) -> dict:
        return {
            "day": self.day,
            "label": self.label,
            "zones": [z.key for z in self.zones],
            "travel_minutes": self.travel_minutes,
            "count": len(self.places),
            "place_ids": [p.id for p in self.places],
            "warning": self.warning,
        }


def plan_days(zones: list[Zone], days: int, *,
              max_minutes_per_day: int = 480) -> list[DayPlan]:
    """
    將區分配到日子。

    ⚠️ 用**評分制**而唔係硬規則。原本用「太遠就搵另一日」嘅硬規則，
       結果搵唔到替代嗰陣會照塞落去（真實 bug：太宰府同博多排同一日，
       相距 7.9km，但因為冇更好選擇就照塞）。

       評分制：為每一日計「加咗呢一區之後嘅總車程 + 負載懲罰」，
       揀最低分嗰日。永遠都有答案，而且一定係最合理嗰個。

    規則（用戶角度）：
      · 一日盡量去一區 —— 唔使搭車走嚟走去
      · 一區太大（行程超過 max_minutes）就切開兩日
      · 距離越遠分數越差（但唔會硬性禁止，因為有啲地方真係要一日）
    """
    days = max(1, days)

    # 展開：如果一區嘅行程時間超上限，就切開
    units: list[tuple[Zone, list[Place]]] = []
    for z in zones:
        if z.total_minutes <= max_minutes_per_day or z.count <= 1:
            units.append((z, list(z.places)))
            continue
        #   ⚠️ 切開之後要改 label —— 否則兩日都顯示「天神」，
        #      用戶唔知邊日去邊度。
        parts: list[list[Place]] = []
        cur: list[Place] = []
        acc = 0
        for p in z.places:
            m = p.duration or 60
            if cur and acc + m > max_minutes_per_day:
                parts.append(cur)
                cur, acc = [], 0
            cur.append(p)
            acc += m
        if cur:
            parts.append(cur)
        for i, part in enumerate(parts):
            if i == 0:
                units.append((z, part))
            else:
                units.append((Zone(
                    key=f"{z.key}#{i + 1}",
                    label=f"{z.label}（續 {i + 1}）",
                    district=z.district, places=part,
                    lat=z.lat, lng=z.lng, spread_m=z.spread_m,
                    total_minutes=sum(p.duration or 0 for p in part),
                ), part))

    plans = [DayPlan(day=i + 1, zones=[], label="") for i in range(days)]

    def cost(pl: DayPlan, zone: Zone, group: list[Place]) -> float:
        """加呢一區落呢一日嘅「代價」。越低越好。"""
        c = 0.0
        # ① 車程：同已有區嘅距離總和（公里）
        if zone.lat is not None:
            for ez in pl.zones:
                if ez.lat is None:
                    continue
                km = haversine_m(zone.lat, zone.lng, ez.lat, ez.lng) / 1000
                # 超過 4km 之後懲罰加重（唔想一日走兩個遠區）
                c += km if km <= FAR_APART_M / 1000 else km * 3
        # ② 負載平衡：已經多人嘅日唔好再加
        c += len(pl.places) * 1.5
        # ③ 完全空白嘅日有少少優惠（平均分佈）
        if not pl.zones:
            c -= 1.0
        return c

    # 人多嘅區先分配（佢哋最影響結果）
    for zone, group in sorted(units, key=lambda u: -u[0].count):
        target = min(plans, key=lambda pl: cost(pl, zone, group))
        target.zones.append(zone)
        target.places.extend(group)

    for pl in plans:
        pl.places.sort(key=lambda p: p.name or "")
        pl.label = " + ".join(z.label for z in pl.zones) or "自由活動"
        mins = 0
        for i, z in enumerate(pl.zones):
            for z2 in pl.zones[i + 1:]:
                if z.lat is not None and z2.lat is not None:
                    d = haversine_m(z.lat, z.lng, z2.lat, z2.lng)
                    mins += max(10, round(d / 1000 * 3))   # 約 20km/h 市區
        pl.travel_minutes = mins
        # 跨區太遠就提醒用戶
        for i, z in enumerate(pl.zones):
            for z2 in pl.zones[i + 1:]:
                if z.lat is None or z2.lat is None:
                    continue
                km = haversine_m(z.lat, z.lng, z2.lat, z2.lng) / 1000
                if km > FAR_APART_M / 1000:
                    pl.warning = (f"「{z.label}」同「{z2.label}」相距 "
                                  f"{km:.1f}km，建議安排半日以上")
                    break
            if pl.warning:
                break
    return plans


def suggest(items: Iterable, days: int, **kw) -> dict:
    """一次過做晒：分區 + 排日子。"""
    zones = build_zones(items, **kw)
    plans = plan_days(zones, days)
    return {
        "zones": [z.to_dict() for z in zones],
        "days": [p.to_dict() for p in plans],
        "summary": {
            "zones": len(zones),
            "located": sum(1 for z in zones for p in z.places if p.has_coords),
            "unlocated": sum(len(z.places) for z in zones if z.key == "unknown"),
        },
    }


def travel_order(places: list[Place]) -> list[Place]:
    """
    同一區入面嘅遊覽次序 —— 最近鄰居法（greedy nearest neighbour）。

    ⚠️ 唔係最優（TSP 係 NP-hard），但對 5-10 個點嚟講已經好夠，
       而且結果穩定、0ms、唔使 AI。
    """
    pts = [p for p in places if p.has_coords]
    rest = [p for p in places if not p.has_coords]
    if len(pts) < 3:
        return pts + rest

    out = [pts[0]]
    left = pts[1:]
    while left:
        last = out[-1]
        nxt = min(left, key=lambda p: haversine_m(last.lat, last.lng, p.lat, p.lng))
        out.append(nxt)
        left.remove(nxt)
    return out + rest
