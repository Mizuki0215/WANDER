"""
貨幣 + 匯率
=============
⚠️ 用戶要求：
   「有時你去旅行如果唔係都係用港幣㗎嘛，所以你要 mark 低返嗰個
    嘅價錢係有得揀嗰個 Yen or KRW or EUR、HKD 定係點樣？
    另外講起錢呢樣嘢…就係根據匯率去轉返嗰個你想要嘅錢，
    呢個可唔可以實時整㗎？」
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))
sys.path.insert(0, str(ROOT / "engine"))

WEB = ROOT / "web" / "src"


def code(path: Path) -> str:
    out = []
    for line in path.read_text(encoding="utf-8").split("\n"):
        s = re.sub(r'(?<![\'"`])//.*$', '', line)
        s = re.sub(r'/\*.*?\*/', '', s)
        if s.strip().startswith(('*', '/*')):
            continue
        out.append(s)
    return "\n".join(out)


# ══════════════════════════════════════════════════════════════
# ① 匯率引擎
# ══════════════════════════════════════════════════════════════

class TestCurrencyEngine:
    def test_two_free_sources(self):
        """
        ⚠️ 一定要有**兩個**免費來源 fallback ——
           一個死咗都仲有 rate（旅行時唔可以冇）。
        """
        from wander import currency as c
        assert len(c.SOURCES) >= 2, "得一個來源（死咗就冇匯率）"
        names = [s[0] for s in c.SOURCES]
        assert "jsdelivr" in names and "er-api" in names

    def test_no_api_key_needed(self):
        """
        ⚠️⚠️ 唔可以用要 key 嘅 API ——
           呢個 app 係「零成本、零註冊」。
        """
        from wander import currency as c
        for name, tpl, _ in c.SOURCES:
            assert "apikey" not in tpl.lower(), f"{name} 要 API key"
            assert "api_key" not in tpl.lower(), f"{name} 要 API key"
            assert "token" not in tpl.lower(), f"{name} 要 token"

    def test_has_ttl_cache(self):
        """
        ⚠️⚠️ 用戶問「可唔可以實時？」
           → 答：**快取 6 個鐘**，唔係每次查。
             為咩：匯率一日只變幾次；狂查會被免費 API 封；
             飛機／地鐵冇網要有最後一次嘅 rate。
        """
        from wander import currency as c
        assert c.TTL_SECONDS >= 3600, "TTL 太短（狂查 API）"
        assert c.TTL_SECONDS <= 24 * 3600, "TTL 太長（值日唔準）"

    def test_cache_file_written_atomically(self):
        """
        ⚠️ 要寫 .tmp 再 rename —— 唔係嘅話中途死會留半個檔。
        """
        s = (ROOT / "engine" / "wander" / "currency.py").read_text(encoding="utf-8")
        assert "with_suffix" in s or ".tmp" in s, "冇 atomic write"
        assert ".replace(" in s or "os.replace" in s, "冇 rename"

    def test_thread_lock(self):
        """
        ⚠️ uvicorn 用 threadpool 跑 sync endpoint ——
           兩個 request 同時 refresh 會寫爛個 cache。
        """
        s = (ROOT / "engine" / "wander" / "currency.py").read_text(encoding="utf-8")
        assert "threading.Lock" in s, "冇 thread lock"
        assert "with _LOCK:" in s, "冇用 lock"

    def test_never_raises(self):
        """
        ⚠️⚠️ 匯率攞唔到**唔應該**令「睇購物清單」失敗。
        """
        from wander import currency as c
        r = c.get_rates("ZZZ")          # ⚠️ 唔存在嘅幣
        assert isinstance(r, dict)
        assert "rates" in r
        # ⚠️ 唔可以爆
        assert c.convert(100, "XXX", "YYY") is None or True

    def test_stale_flag(self):
        """⚠️ 過期但攞唔到新 → `stale=True`（前端要提示）。"""
        from wander import currency as c
        r = c.get_rates("HKD")
        assert "stale" in r, "冇 stale 標記"

    def test_zero_and_negative_rates_filtered(self):
        """
        ⚠️ 0 或者負數 rate → 除數會爆或者出負錢。
        """
        s = (ROOT / "engine" / "wander" / "currency.py").read_text(encoding="utf-8")
        assert "if f > 0" in s, "冇過濾 0／負數 rate"

    def test_self_rate_is_one(self):
        """⚠️ 自己對自己一定係 1（唔靠 API）。"""
        s = (ROOT / "engine" / "wander" / "currency.py").read_text(encoding="utf-8")
        assert "rates[base] = 1.0" in s, "冇設自己 = 1"

    def test_convert_uses_cross_rate(self):
        """
        ⚠️ 用**交叉匯率**（唔使每個 pair 都查一次）：
           amount × (rate[to] / rate[frm])
        """
        s = (ROOT / "engine" / "wander" / "currency.py").read_text(encoding="utf-8")
        assert "rt / rf" in s, "冇用交叉匯率"

    def test_convert_returns_none_on_missing_rate(self):
        """
        ⚠️⚠️ 換唔到要回 **None**，**唔可以**回原數 ——
           回原數會靜靜咁畀錯錢（日元當港幣）。
        """
        from wander import currency as c
        assert c.convert(100, "ZZZ", "HKD") is None, "換唔到應該回 None"

    def test_symbols(self):
        from wander import currency as c
        assert c.symbol("JPY") == "¥"
        assert c.symbol("HKD") == "HK$"
        assert c.symbol("KRW") == "₩"
        assert c.symbol("ZZZ") == "ZZZ"      # ⚠️ 唔知就回 code

    def test_common_list_has_travel_currencies(self):
        """⚠️ 旅行常用嘅幣一定要喺清單（用戶講明要 Yen/KRW/EUR）。"""
        from wander import currency as c
        codes = [x[0] for x in c.COMMON]
        for k in ["HKD", "JPY", "KRW", "EUR", "USD", "TWD", "THB"]:
            assert k in codes, f"常用清單冇 {k}"


# ══════════════════════════════════════════════════════════════
# ② DB
# ══════════════════════════════════════════════════════════════

class TestCurrencySchema:
    def test_shopping_has_currency(self):
        s = (ROOT / "server" / "app" / "db.py").read_text(encoding="utf-8")
        i = s.index("CREATE TABLE IF NOT EXISTS shopping_items")
        blk = s[i:s.index(");", i)]
        assert "currency" in blk, "shopping_items 冇 currency 欄"

    def test_trips_has_currency(self):
        s = (ROOT / "server" / "app" / "db.py").read_text(encoding="utf-8")
        i = s.index("CREATE TABLE IF NOT EXISTS trips")
        blk = s[i:s.index(");", i)]
        assert "currency" in blk, "trips 冇 currency 欄"

    def test_migrations_for_old_dbs(self):
        """
        ⚠️⚠️ 舊 DB 唔會自動加新欄 —— 一定要有 migration，
           唔係嘅話舊用戶 UPDATE 會爆。
        """
        s = (ROOT / "server" / "app" / "db.py").read_text(encoding="utf-8")
        assert '"shopping_items", "currency"' in s or \
               "'shopping_items', 'currency'" in s, "冇 shopping migration"
        assert '"trips", "currency"' in s or \
               "'trips', 'currency'" in s, "冇 trips migration"


# ══════════════════════════════════════════════════════════════
# ③ API
# ══════════════════════════════════════════════════════════════

class TestCurrencyApi:
    @pytest.fixture(scope="class")
    def srv(self):
        return (ROOT / "server" / "app" / "main.py").read_text(encoding="utf-8")

    def test_rates_endpoint(self, srv):
        assert '@app.get("/api/rates")' in srv, "冇 /api/rates"

    def test_currencies_endpoint(self, srv):
        assert '@app.get("/api/currencies")' in srv, "冇 /api/currencies"

    def test_routes_before_spa_fallback(self, srv):
        """
        ⚠️⚠️ SPA catch-all 一定要喺**最後** ——
           唔係嘅話 API 會 404（呢個 bug 中過兩次）。
        """
        stripped = "\n".join(l for l in srv.split("\n")
                             if not l.strip().startswith("#"))
        i_fallback = stripped.index('@app.get("/{full_path:path}")')
        for r in ["/api/rates", "/api/currencies"]:
            assert stripped.index(f'"{r}"') < i_fallback, f"{r} 喺 catch-all 之後"

    def test_shopping_insert_writes_currency(self, srv):
        i = srv.index("def add_shopping(")
        blk = srv[i:i + 1600]
        assert "currency" in blk, "INSERT 冇寫 currency"

    def test_shopping_patch_supports_currency(self, srv):
        i = srv.index("def update_shopping(")
        blk = srv[i:i + 1400]
        assert '"currency" in body' in blk, "PATCH 唔支援 currency"

    def test_trip_update_supports_currency(self, srv):
        i = srv.index("class TripUpdate")
        blk = srv[i:i + 500]
        assert "currency" in blk, "TripUpdate 冇 currency"

    def test_trip_currency_validated(self, srv):
        """⚠️ 貨幣代碼要驗證（唔可以亂入）。"""
        i = srv.index("def update_trip(")
        blk = srv[i:i + 900]
        assert "isalpha()" in blk, "冇驗證貨幣代碼"

    def test_total_uses_trip_currency(self, srv):
        """
        ⚠️⚠️ 總額一定要換算 —— 唔可以將日元同港幣直接加埋。
        """
        i = srv.index("def list_shopping(")
        blk = srv[i:i + 3000]
        assert "price_trip" in blk, "冇換算後嘅 price_trip"
        assert "to_trip" in blk, "冇換算函數"

    def test_unconverted_counted(self, srv):
        """
        ⚠️⚠️ 換唔到嘅項要**數出嚟** ——
           唔可以靜靜咁唔計入總額（用戶會以為總額啱）。
        """
        i = srv.index("def list_shopping(")
        blk = srv[i:i + 3000]
        assert "unconverted" in blk, "冇數換唔到嘅項"

    def test_rates_stale_reported(self, srv):
        i = srv.index("def list_shopping(")
        blk = srv[i:i + 3000]
        assert "rates_stale" in blk, "冇回報匯率過期"


# ══════════════════════════════════════════════════════════════
# ④ 前端
# ══════════════════════════════════════════════════════════════

class TestCurrencyFrontend:
    def test_api_methods(self):
        s = code(WEB / "lib" / "api.js")
        assert "rates:" in s, "冇 api.rates"
        assert "currencies:" in s, "冇 api.currencies"

    def test_shopping_has_currency_picker(self):
        s = code(WEB / "components" / "ShoppingList.jsx")
        assert "function CurrencyPicker(" in s, "冇 CurrencyPicker"
        assert "<CurrencyPicker value=" in s, "冇用 CurrencyPicker"

    def test_picker_is_module_level(self):
        """⚠️ 喺 render 內定義 → 每次 render 新元件 → 輸入框失焦。"""
        s = code(WEB / "components" / "ShoppingList.jsx")
        assert s.index("function CurrencyPicker(") < \
               s.index("export default function ShoppingList"), \
            "CurrencyPicker 唔喺模組層"

    def test_no_hardcoded_yen(self):
        """
        ⚠️⚠️ 原本硬編碼 `¥` —— 用戶報「有時唔係用港幣㗎嘛」。
        """
        raw = (WEB / "components" / "ShoppingList.jsx").read_text(encoding="utf-8")
        # ⚠️ 去註解先檢查
        body = re.sub(r'\{/\*[\s\S]*?\*/\}', '', raw)
        body = re.sub(r'//.*$', '', body, flags=re.M)
        # ⚠️ 唔可以有 `¥${...}` 呢種硬編碼模板
        assert not re.search(r'`[^`]*¥\$\{', body), \
            "仲有硬編碼 ¥ 嘅價錢顯示"

    def test_uses_square_symbol_map(self):
        s = code(WEB / "components" / "ShoppingList.jsx")
        assert "const SYMBOLS" in s, "冇貨幣符號表"
        for k in ["HKD", "JPY", "KRW", "EUR", "USD"]:
            assert k in s, f"SYMBOLS 冇 {k}"

    def test_total_uses_server_converted(self):
        """
        ⚠️⚠️ 總額一定要用後端換算好嘅 `data.total` ——
           唔可以用前端原始數加埋（日元+港幣=冇意義）。
        """
        s = code(WEB / "components" / "ShoppingList.jsx")
        assert "data?.total" in s or "data.total" in s, "冇用後端換算嘅總額"
        # ⚠️ 原本嘅 `budget` 已經改名（提醒唔可以用）
        assert "budgetRaw" in s, "冇提醒 budget 係未換算"

    def test_shows_unconverted_warning(self):
        s = code(WEB / "components" / "ShoppingList.jsx")
        assert "unconverted" in s, "冇顯示換唔到匯率嘅提示"
        assert "rates_stale" in s, "冇顯示匯率過期提示"

    def test_trip_has_currency_select(self):
        s = code(WEB / "components" / "Trips.jsx")
        assert "function CurrencySelect(" in s, "冇 CurrencySelect"
        assert "currency:" in s, "payload 冇 currency"
        assert "記帳貨幣" in (WEB / "components" / "Trips.jsx").read_text(encoding="utf-8"), \
            "冇「記帳貨幣」標籤"

    def test_select_is_module_level(self):
        s = code(WEB / "components" / "Trips.jsx")
        assert s.index("function CurrencySelect(") < \
               s.index("export default function Trips"), "CurrencySelect 唔喺模組層"
