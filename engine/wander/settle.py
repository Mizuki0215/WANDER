"""
wander.settle — 旅行分帳
=========================

用戶要求（原文）：
    「同程 做一個 function like sette uppp。咁 計錢」

即係：一班人去旅行，有人墊支，最後要計返邊個俾返幾多俾邊個。

⚠️ 為咩唔用 AI：
   分帳係**算術**。1 + 1 = 2，唔需要「理解」。
   用 AI 做算術係災難 —— 會出現「大概係 $523 左右」呢種答案，
   但分帳係要**準確到仙**嘅嘢（差一蚊都會嘈交）。

⚠️ 核心係「最少轉帳次數」：
   5 個人去完旅行，如果逐對逐對咁計要 20 次轉帳。
   但實際上通常 3-4 次就搞掂。
   呢個係經典嘅 debt settlement 問題，用貪心法已經好接近最優：
     每次攞「最大債仔」同「最大債主」配對，轉帳 min(欠, 應收)。
   結果：n 個人最多 n-1 次轉帳。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Optional

# 貨幣最小單位（用整數運算避免浮點誤差）
#   ⚠️ 分帳一定要用整數運算！
#      0.1 + 0.2 = 0.30000000000000004 喺浮點數係事實。
#      用 float 計錢會出現「明明應該 $0 但顯示 $0.0000001」→ 用戶唔信個 app。
#      所以內部全部用「仙」（最小單位）做整數運算。
CENT = 1


def to_cents(amount: float | int | str) -> int:
    """金額 → 仙（整數）。用 round 避免 0.1*100 = 10.000000000000002。"""
    if amount is None or amount == "":
        return 0
    return int(round(float(amount) * 100))


def from_cents(cents: int) -> float:
    return round(cents / 100, 2)


def fmt_money(cents: int, symbol: str = "$") -> str:
    """整數仙 → 顯示字串（負數都處理得好）。"""
    neg = cents < 0
    c = abs(int(cents))
    s = f"{symbol}{c // 100:,}.{c % 100:02d}"
    return f"-{s}" if neg else s


@dataclass
class Expense:
    """一筆開支。"""
    id: str
    title: str
    amount: float | int              # 總額（正數）
    payer: str                       # 邊個墊支
    participants: list[str] = field(default_factory=list)   # 邊幾個分
    category: str = "other"          # food / transport / stay / ticket / shop / other
    day_index: Optional[int] = None
    note: str = ""
    currency: str = "JPY"

    @property
    def cents(self) -> int:
        return to_cents(self.amount)

    @property
    def shares(self) -> list[str]:
        return self.participants or [self.payer]


@dataclass
class Share:
    """每人應付／已付。"""
    person: str
    paid: int = 0        # 已墊支（仙）
    owes: int = 0        # 應該分擔（仙）
    net: int = 0         # 已付 - 應付；正數 = 應該收返

    def to_dict(self, symbol: str = "$") -> dict:
        return {
            "person": self.person,
            "paid": from_cents(self.paid),
            "owes": from_cents(self.owes),
            "net": from_cents(self.net),
            "paid_text": fmt_money(self.paid, symbol),
            "owes_text": fmt_money(self.owes, symbol),
            "net_text": fmt_money(self.net, symbol),
        }


@dataclass
class Transfer:
    """一筆轉帳建議。"""
    frm: str
    to: str
    amount: int          # 仙

    def to_dict(self, symbol: str = "$") -> dict:
        return {
            "from": self.frm, "to": self.to,
            "amount": from_cents(self.amount),
            "amount_text": fmt_money(self.amount, symbol),
        }


def split_evenly(total_cents: int, people: list[str]) -> dict[str, int]:
    """
    平均分，**餘數要分配得好**，令總和一定等於總額。

    ⚠️ 呢度係最容易出錯嘅位：
       $100 / 3 = 33.333… → 如果每人都係 33.33，總和 = 99.99 ≠ 100
       差嗰 $0.01 去邊？唔可以「消失」，否則永遠對唔到數。

       做法：先每人攞 floor，餘數逐個派（每次 1 仙）。
       咁樣總和一定準確，而且分配係確定性嘅（同一個 input 同一個結果）。
    """
    n = len(people)
    if n == 0:
        return {}
    base, rem = divmod(total_cents, n)
    out: dict[str, int] = {}
    for i, p in enumerate(people):
        out[p] = base + (1 if i < rem else 0)
    return out


def compute(expenses: Iterable[Expense], members: Optional[list[str]] = None,
            *, symbol: str = "$") -> dict:
    """
    計分帳。

    回傳 { shares, transfers, total, per_category, balanced }
    """
    expenses = list(expenses)
    shares: dict[str, Share] = {}

    def get(p: str) -> Share:
        if p not in shares:
            shares[p] = Share(person=p)
        return shares[p]

    if members:
        for m in members:
            get(m)

    total = 0
    per_category: dict[str, int] = {}

    for e in expenses:
        cents = e.cents
        if cents <= 0:
            continue
        total += cents
        per_category[e.category] = per_category.get(e.category, 0) + cents

        payer = get(e.payer)
        payer.paid += cents

        # 分擔：平均分，餘數派落前面嘅人
        people = list(e.shares)
        for person, amt in split_evenly(cents, people).items():
            get(person).owes += amt

    for s in shares.values():
        s.net = s.paid - s.owes

    transfers = min_transfers(shares, symbol=symbol)

    return {
        "shares": [s.to_dict(symbol) for s in
                   sorted(shares.values(), key=lambda x: -x.net)],
        "transfers": [t.to_dict(symbol) for t in transfers],
        "total": from_cents(total),
        "total_text": fmt_money(total, symbol),
        "per_category": {k: from_cents(v) for k, v in
                         sorted(per_category.items(), key=lambda kv: -kv[1])},
        # 賬目一定平（因為 split_evenly 保證總和準確）
        "balanced": sum(s.net for s in shares.values()) == 0,
        "transfer_count": len(transfers),
    }


def min_transfers(shares: dict[str, Share], *,
                  symbol: str = "$") -> list[Transfer]:
    """
    最少轉帳次數。

    貪心法：
      ① 淨額 > 0 = 債主（應該收返）
      ② 淨額 < 0 = 債仔（應該俾返）
      ③ 每次攞最大債仔同最大債主配對，轉 min(|債仔|, 債主)
      ④ 重複直到冇

    結果：最多 n-1 次轉帳（n = 人數）。
    ⚠️ 貪心法唔一定係數學上最少，但對真實旅行人數（2-10 人）
       已經係最優或者差 1 次，而且**結果穩定可預測**。
    """
    creditors = sorted(((p, s.net) for p, s in shares.items() if s.net > 0),
                       key=lambda x: (-x[1], x[0]))
    debtors = sorted(((p, -s.net) for p, s in shares.items() if s.net < 0),
                     key=lambda x: (-x[1], x[0]))

    out: list[Transfer] = []
    ci = di = 0
    while ci < len(creditors) and di < len(debtors):
        cp, credit = creditors[ci]
        dp, debt = debtors[di]
        amt = min(credit, debt)
        if amt > 0:
            out.append(Transfer(frm=dp, to=cp, amount=amt))
        credit -= amt
        debt -= amt
        creditors[ci] = (cp, credit)
        debtors[di] = (dp, debt)
        if credit == 0:
            ci += 1
        if debt == 0:
            di += 1
    return out


def parse_expense(raw: dict) -> Expense:
    """由 API / DB dict 建立 Expense（容錯）。"""
    parts = raw.get("participants") or []
    if isinstance(parts, str):
        # 支援逗號分隔："alice,bob"
        parts = [p.strip() for p in parts.replace("，", ",").split(",") if p.strip()]
    return Expense(
        id=str(raw.get("id") or ""),
        title=(raw.get("title") or "").strip(),
        amount=raw.get("amount") or 0,
        payer=(raw.get("payer") or "").strip(),
        participants=list(parts),
        category=(raw.get("category") or "other").strip(),
        day_index=raw.get("day_index"),
        note=(raw.get("note") or "").strip(),
        currency=(raw.get("currency") or "JPY").strip(),
    )


CATEGORY_LABELS = {
    "food": "🍜 食",
    "transport": "🚕 交通",
    "stay": "🏨 住宿",
    "ticket": "🎫 門票",
    "shop": "🛍 購物",
    "other": "✦ 其他",
}


def summarize(expenses: Iterable[Expense], symbol: str = "$") -> dict:
    """快速摘要（俾行程頁顯示）。"""
    exps = list(expenses)
    res = compute(exps, symbol=symbol)
    return {
        **res,
        "count": len(exps),
        "per_category_labels": {
            CATEGORY_LABELS.get(k, k): v
            for k, v in res["per_category"].items()
        },
    }
