"""
分區行程規劃測試
================
⚠️ 為咩係純數學而唔用 AI：
   分區係**幾何問題**。兩個地方距離 300 米就係同區，
   距離 8 公里就唔係 —— 純數學，唔需要「理解」。

   用 AI 做呢件事有三個問題：
     ① 唔穩定 —— 同一 input 兩次可能唔同答案
     ② 慢 + 要錢
     ③ 冇得測 —— 你唔可以 assert「AI 應該話係同一區」
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "engine"))

from wander.zones import (  # noqa: E402
    Place, build_zones, haversine_m, plan_days, suggest, travel_order,
)

# ══ 真實福岡座標（實測過）══
FUKUOKA = [
    ("博多駅", 33.5897, 130.4207, "博多", 30),
    ("一蘭本社総本店", 33.5935, 130.4056, "中洲", 60),
    ("中洲屋台", 33.5910, 130.4060, "中洲", 90),
    ("キャナルシティ博多", 33.5896, 130.4110, "博多", 120),
    ("櫛田神社", 33.5935, 130.4100, "博多", 45),
    ("天神地下街", 33.5900, 130.4000, "天神", 90),
    ("大濠公園", 33.5862, 130.3790, "大濠", 90),
    ("福岡タワー", 33.5934, 130.3516, "百道", 60),
    ("太宰府天満宮", 33.5213, 130.5353, "太宰府", 120),
]


def mk(rows=FUKUOKA):
    return [{"id": f"p{i}", "name": n, "lat": la, "lng": ln,
             "district": d, "duration": m}
            for i, (n, la, ln, d, m) in enumerate(rows)]


class TestHaversine:
    def test_same_point_is_zero(self):
        assert haversine_m(33.59, 130.40, 33.59, 130.40) == 0

    def test_known_distance(self):
        """福岡駅 → 太宰府 ≈ 13km（實測 13.1km）。"""
        d = haversine_m(33.5897, 130.4207, 33.5213, 130.5353)
        assert 12000 < d < 14000, f"{d:.0f}m"

    def test_short_distance(self):
        """博多駅 → 中洲 ≈ 1.46km（行路約 20 分鐘）。"""
        d = haversine_m(33.5897, 130.4207, 33.5935, 130.4056)
        assert 1300 < d < 1600, f"{d:.0f}m"

    def test_symmetric(self):
        a = haversine_m(33.59, 130.40, 35.68, 139.76)
        b = haversine_m(35.68, 139.76, 33.59, 130.40)
        assert abs(a - b) < 0.001


class TestZoneBuilding:
    def test_groups_nearby(self):
        zones = build_zones(mk())
        # 博多駅 + 中洲 + 天神 應該同一區（合併後）
        central = [z for z in zones if "博多駅" in [p.name for p in z.places]]
        assert central, "博多駅 應該被分到某區"
        assert central[0].count >= 5, f"市中心應該有 >=5 個，實際 {central[0].count}"

    def test_keeps_far_places_separate(self):
        zones = build_zones(mk())
        taizaifu = [z for z in zones if "太宰府天満宮" in [p.name for p in z.places]]
        assert taizaifu
        assert taizaifu[0].count == 1, "太宰府應該自己一區（13km 外）"

    def test_no_zone_mixes_far_places(self):
        """⚠️ 任何一區嘅內部範圍都唔應該超過合理走路距離。"""
        for z in build_zones(mk()):
            if z.count > 1:
                assert z.spread_m < 3500, \
                    f"「{z.label}」範圍 {z.spread_m:.0f}m 太大 —— 唔似同一區"

    def test_unlocated_grouped_last(self):
        items = mk() + [{"id": "x", "name": "冇座標", "district": None}]
        zones = build_zones(items)
        assert zones[-1].key == "unknown"
        assert zones[-1].count == 1

    def test_named_without_coords_grouped_by_name(self):
        items = [
            {"id": "a", "name": "A", "district": "博多", "duration": 60},
            {"id": "b", "name": "B", "district": "博多", "duration": 60},
            {"id": "c", "name": "C", "district": "天神", "duration": 60},
        ]
        zones = build_zones(items)
        labels = {z.label: z.count for z in zones}
        assert labels.get("博多") == 2
        assert labels.get("天神") == 1

    def test_deterministic(self):
        """⚠️ 同一 input 一定要同一 output（唔可以有隨機）。"""
        a = [(z.label, z.count) for z in build_zones(mk())]
        b = [(z.label, z.count) for z in build_zones(mk())]
        assert a == b

    def test_empty_input(self):
        assert build_zones([]) == []

    def test_all_same_point(self):
        items = [{"id": str(i), "name": f"P{i}", "lat": 33.59, "lng": 130.40}
                 for i in range(5)]
        zones = build_zones(items)
        assert len(zones) == 1
        assert zones[0].count == 5


class TestDayPlanning:
    def test_every_place_scheduled(self):
        """⚠️ 最重要：唔可以漏咗任何景點。"""
        data = suggest(mk(), 4)
        planned = {pid for d in data["days"] for pid in d["place_ids"]}
        allids = {i["id"] for i in mk()}
        assert planned == allids, f"漏咗 {allids - planned}"

    def test_day_count_matches(self):
        data = suggest(mk(), 5)
        assert len(data["days"]) == 5
        assert [d["day"] for d in data["days"]] == [1, 2, 3, 4, 5]

    def test_prefers_one_zone_per_day(self):
        """一日盡量去一區。"""
        data = suggest(mk(), 4)
        multi = [d for d in data["days"] if len(d["zones"]) > 1]
        # 容許最多一日跨兩區（4 日 4 區）
        assert len(multi) <= 1, f"太多日跨區: {multi}"

    def test_warns_when_crossing_far_zones(self):
        """⚠️ 跨區太遠一定要提醒用戶。"""
        # 得 1 日但要處理兩個相距 13km 嘅區 → 一定要 warn
        data = suggest(mk(), 1)
        day1 = data["days"][0]
        assert day1["count"] == len(FUKUOKA)
        assert day1.get("warning"), "1 日跨 13km 應該有 warning"
        assert "km" in day1["warning"]

    def test_no_warning_within_same_area(self):
        """同區（< 4km）唔應該 warn —— 否則用戶會唔信個警告。"""
        items = [
            {"id": "a", "name": "博多駅", "lat": 33.5897, "lng": 130.4207},
            {"id": "b", "name": "中洲", "lat": 33.5935, "lng": 130.4056},
        ]
        data = suggest(items, 1)
        assert not data["days"][0].get("warning")

    def test_no_warning_when_no_crossing(self):
        data = suggest(mk(), 6)   # 6 日 4 區 → 唔使跨區
        assert not any(d.get("warning") for d in data["days"])

    def test_more_days_than_zones(self):
        data = suggest(mk(), 20)
        assert len(data["days"]) == 20
        planned = {pid for d in data["days"] for pid in d["place_ids"]}
        assert planned == {i["id"] for i in mk()}

    def test_one_day(self):
        data = suggest(mk(), 1)
        assert len(data["days"]) == 1

    def test_zero_days_becomes_one(self):
        data = suggest(mk(), 0)
        assert len(data["days"]) == 1

    def test_split_large_zone_has_distinct_labels(self):
        """⚠️ 一區要分兩日，兩日嘅 label 唔可以一樣（用戶唔知邊日去邊）。"""
        # 10 個景點 × 120 分鐘 = 1200 分鐘 > 480 上限 → 要切
        items = [{"id": str(i), "name": f"P{i}", "lat": 33.59 + i * 0.0005,
                  "lng": 130.40, "duration": 120} for i in range(10)]
        data = suggest(items, 3)
        labels = [d["label"] for d in data["days"] if d["count"]]
        assert len(labels) == len(set(labels)), f"重複 label: {labels}"

    def test_empty_input_still_returns_days(self):
        data = suggest([], 3)
        assert len(data["days"]) == 3
        assert all(d["count"] == 0 for d in data["days"])


class TestTravelOrder:
    def test_nearest_neighbour_reduces_travel(self):
        """最近鄰居法應該比原本次序短（或者一樣）。"""
        pts = [Place(id=str(i), name=n, lat=la, lng=ln)
               for i, (n, la, ln, _d, _m) in enumerate(FUKUOKA)]
        ordered = travel_order(pts)
        assert len(ordered) == len(pts)

        def total(seq):
            return sum(haversine_m(seq[i].lat, seq[i].lng,
                                   seq[i + 1].lat, seq[i + 1].lng)
                       for i in range(len(seq) - 1))
        # 由同一個起點出發，比原本次序好
        assert total(ordered) <= total(pts) + 1

    def test_small_input_unchanged(self):
        pts = [Place(id="a", lat=1.0, lng=1.0), Place(id="b", lat=2.0, lng=2.0)]
        assert [p.id for p in travel_order(pts)] == ["a", "b"]

    def test_places_without_coords_go_last(self):
        pts = [Place(id="a", lat=1.0, lng=1.0),
               Place(id="x", name="no coords"),
               Place(id="b", lat=2.0, lng=2.0),
               Place(id="c", lat=3.0, lng=3.0)]
        out = travel_order(pts)
        assert out[-1].id == "x"
