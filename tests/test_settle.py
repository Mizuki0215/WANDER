"""
分帳測試
========
⚠️ 為咩唔用 AI：
   分帳係**算術**。用 AI 做算術係災難 —— 會出現「大概 $523 左右」，
   但分帳要**準確到仙**（差一蚊都會嘈交）。

⚠️ 最重要嘅斷言：
   ① 分錢唔可以唔見咗一分（$100 / 3 一定要加返 = $100）
   ② 賬目一定要平（所有人淨額加起來 = 0）
   ③ 轉帳次數要接近理論下限 n-1
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "engine"))

from wander.settle import (  # noqa: E402
    Expense, compute, fmt_money, from_cents, min_transfers, parse_expense,
    split_evenly, summarize, to_cents,
)


class TestMoneyMath:
    """⚠️ 一定要用整數運算 —— 浮點數會出現 0.1+0.2=0.30000000000000004。"""

    @pytest.mark.parametrize("amount,want", [
        (100, 10000), (0.1, 10), (99.99, 9999), (1.005, 100),
        (0, 0), ("1234.56", 123456), (None, 0), ("", 0),
    ])
    def test_to_cents(self, amount, want):
        assert to_cents(amount) == want

    def test_to_cents_avoids_float_noise(self):
        """0.1 * 100 = 10.000000000000002 喺浮點數係事實。"""
        total = sum(to_cents(0.1) for _ in range(10))
        assert total == 100, f"10 × $0.10 應該 = $1.00，實際 {total} 仙"

    @pytest.mark.parametrize("cents,want", [
        (10000, "$100.00"), (9999, "$99.99"), (0, "$0.00"),
        (-5000, "-$50.00"), (123456, "$1,234.56"), (1, "$0.01"),
    ])
    def test_fmt_money(self, cents, want):
        assert fmt_money(cents) == want

    def test_roundtrip(self):
        for c in (0, 1, 99, 100, 12345, -500):
            assert to_cents(from_cents(c)) == c


class TestSplitEvenly:
    """
    ⚠️⚠️ 最重要：餘數唔可以「消失」。
       $100 / 3 = 33.333… → 每人都 33.33 就總和 99.99，差 $0.01。
       分帳 app 如果對唔到數，用戶永遠唔信。
    """

    @pytest.mark.parametrize("total,n", [
        (10000, 3), (9999, 7), (1, 3), (100, 6), (12345, 7),
        (10000, 1), (99999, 13), (5, 100),
    ])
    def test_sum_always_exact(self, total, n):
        people = [f"P{i}" for i in range(n)]
        parts = split_evenly(total, people)
        assert sum(parts.values()) == total, \
            f"{total} 仙 / {n} 人 = {sum(parts.values())} 仙（應該 {total}）"

    def test_all_people_get_share(self):
        parts = split_evenly(10000, ["a", "b", "c"])
        assert set(parts) == {"a", "b", "c"}

    def test_difference_at_most_one_cent(self):
        parts = split_evenly(10000, ["a", "b", "c"])
        vals = list(parts.values())
        assert max(vals) - min(vals) <= 1

    def test_empty(self):
        assert split_evenly(100, []) == {}

    def test_deterministic(self):
        a = split_evenly(9999, ["a", "b", "c", "d"])
        b = split_evenly(9999, ["a", "b", "c", "d"])
        assert a == b


# ══ 真實情境：4 人去福岡 ══
TRIP = [
    Expense("e1", "一蘭拉麵", 4800, "Alice", ["Alice", "Bob", "Carol", "Dave"], "food"),
    Expense("e2", "太宰府門票", 2400, "Bob", ["Alice", "Bob", "Carol", "Dave"], "ticket"),
    Expense("e3", "的士", 3200, "Carol", ["Alice", "Bob", "Carol"], "transport"),  # Dave 冇搭
    Expense("e4", "酒店", 48000, "Alice", ["Alice", "Bob", "Carol", "Dave"], "stay"),
    Expense("e5", "藥妝", 8600, "Dave", ["Dave", "Alice"], "shop"),
    Expense("e6", "屋台", 12000, "Bob", ["Alice", "Bob", "Carol", "Dave"], "food"),
]
MEMBERS = ["Alice", "Bob", "Carol", "Dave"]


class TestCompute:
    def test_balanced(self):
        """⚠️ 所有人淨額加起來一定要 = 0。"""
        r = compute(TRIP, MEMBERS)
        assert r["balanced"] is True
        total_net = sum(to_cents(s["net"]) for s in r["shares"])
        assert total_net == 0, f"淨額總和 {total_net} ≠ 0"

    def test_total(self):
        r = compute(TRIP, MEMBERS)
        assert r["total"] == 79000.0

    def test_everyone_listed(self):
        r = compute(TRIP, MEMBERS)
        assert {s["person"] for s in r["shares"]} == set(MEMBERS)

    def test_paid_matches_expenses(self):
        r = compute(TRIP, MEMBERS)
        by = {s["person"]: s for s in r["shares"]}
        assert to_cents(by["Alice"]["paid"]) == to_cents(4800 + 48000)
        assert to_cents(by["Carol"]["paid"]) == to_cents(3200)
        assert to_cents(by["Dave"]["paid"]) == to_cents(8600)

    def test_owes_is_correct(self):
        """Dave 冇搭的士 → 佢唔應該分擔的士錢。"""
        r = compute(TRIP, MEMBERS)
        by = {s["person"]: s for s in r["shares"]}
        # 的士 3200 / 3 人 = 1066.66…  → Dave 唔包括
        # 藥妝 8600 得 2 人分；其餘 4 筆 4 人分
        want = to_cents(8600) // 2 + (to_cents(4800) + to_cents(2400)
                                      + to_cents(48000) + to_cents(12000)) // 4
        assert abs(to_cents(by["Dave"]["owes"]) - want) <= 2

    def test_per_category(self):
        r = compute(TRIP, MEMBERS)
        assert r["per_category"]["food"] == 16800.0   # 4800 + 12000
        assert r["per_category"]["stay"] == 48000.0   # 48000

    def test_empty_expenses(self):
        r = compute([], MEMBERS)
        assert r["total"] == 0
        assert r["balanced"] is True
        assert r["transfers"] == []

    def test_ignores_zero_and_negative(self):
        exps = TRIP + [Expense("z", "免費", 0, "Alice", MEMBERS)]
        r = compute(exps, MEMBERS)
        assert r["total"] == 79000.0

    def test_single_person(self):
        exps = [Expense("e", "自己食", 1000, "Solo", ["Solo"], "food")]
        r = compute(exps, ["Solo"])
        assert r["balanced"] is True
        assert r["transfers"] == []


class TestMinTransfers:
    """
    ⚠️ 核心價值：4 個人互相欠，逐對計要 6 次轉帳，
       但實際上 n-1 = 3 次就搞掂。
    """

    def test_at_most_n_minus_1(self):
        r = compute(TRIP, MEMBERS)
        assert r["transfer_count"] <= len(MEMBERS) - 1, \
            f"應該 <= {len(MEMBERS)-1} 次，實際 {r['transfer_count']} 次"

    def test_transfers_settle_everything(self):
        """轉帳之後，所有人淨額應該變 0。"""
        r = compute(TRIP, MEMBERS)
        net = {s["person"]: to_cents(s["net"]) for s in r["shares"]}
        for t in r["transfers"]:
            amt = to_cents(t["amount"])
            net[t["from"]] += amt
            net[t["to"]] -= amt
        assert all(v == 0 for v in net.values()), f"仲有欠款: {net}"

    def test_transfer_amounts_positive(self):
        r = compute(TRIP, MEMBERS)
        assert all(to_cents(t["amount"]) > 0 for t in r["transfers"])

    def test_no_self_transfer(self):
        r = compute(TRIP, MEMBERS)
        assert all(t["from"] != t["to"] for t in r["transfers"])

    def test_two_people(self):
        exps = [
            Expense("a", "A 墊", 10000, "A", ["A", "B"], "food"),
            Expense("b", "B 墊", 4000, "B", ["A", "B"], "food"),
        ]
        r = compute(exps, ["A", "B"])
        assert r["transfer_count"] == 1
        t = r["transfers"][0]
        assert t["from"] == "B" and t["to"] == "A"
        assert to_cents(t["amount"]) == 300000    # (10000-4000)/2 = 3000

    def test_all_settled_no_transfers(self):
        exps = [
            Expense("a", "A 墊", 5000, "A", ["A", "B"], "food"),
            Expense("b", "B 墊", 5000, "B", ["A", "B"], "food"),
        ]
        r = compute(exps, ["A", "B"])
        assert r["transfer_count"] == 0

    def test_many_people_still_efficient(self):
        """10 個人隨機欠款，轉帳次數應該 <= 9。"""
        import random
        random.seed(42)          # 固定 seed → 可重現
        people = [f"P{i}" for i in range(10)]
        exps = [Expense(f"e{i}", f"item{i}", random.randint(1000, 50000),
                        random.choice(people),
                        random.sample(people, random.randint(2, 10)), "food")
                for i in range(20)]
        r = compute(exps, people)
        assert r["transfer_count"] <= 9, f"實際 {r['transfer_count']} 次"
        assert r["balanced"] is True


class TestParseExpense:
    def test_basic(self):
        e = parse_expense({"id": "x", "title": "T", "amount": 100,
                           "payer": "A", "participants": ["A", "B"]})
        assert e.payer == "A" and e.participants == ["A", "B"]

    def test_comma_string_participants(self):
        """支援逗號分隔字串（前端／API 都可能傳）。"""
        e = parse_expense({"id": "x", "title": "T", "amount": 1, "payer": "A",
                           "participants": "A, B, C"})
        assert e.participants == ["A", "B", "C"]

    def test_chinese_comma(self):
        e = parse_expense({"id": "x", "title": "T", "amount": 1, "payer": "A",
                           "participants": "A，B"})
        assert e.participants == ["A", "B"]

    def test_missing_fields_safe(self):
        e = parse_expense({})
        assert e.amount == 0 and e.participants == []
        assert e.category == "other"

    def test_shares_defaults_to_payer(self):
        e = parse_expense({"id": "x", "title": "T", "amount": 10, "payer": "A"})
        assert e.shares == ["A"]


class TestSummarize:
    def test_includes_labels(self):
        r = summarize(TRIP)
        assert "🍜 食" in r["per_category_labels"]
        assert "🏨 住宿" in r["per_category_labels"]
        assert r["count"] == 6
