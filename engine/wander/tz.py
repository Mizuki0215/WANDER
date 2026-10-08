"""
時區估算（Timezone）
=====================

⚠️⚠️ 為咩需要呢個 —— 旅行 app 最易出錯嘅位：

   用戶問：
     「呢個時間係點樣抽取㗎？如果我正常去旅行我就會帶手機啦，
      咁係手機顯示咩時間你就顯示咩時間，定係點樣？
      因為你去旅行嘅話就會入唔同嘅時區呀嘛。」

   ⚠️ 正確答案係「**兩個都要**」：

     ① **手機時間**（`new Date()`）—— 你身處邊度嘅時間。
        手機自己會跟網絡／GPS 調整，所以喺東京會自動變 UTC+9。
        ✅ 呢個係「我而家幾點」。

     ② **目的地時間** —— 旅程城市嘅時間。
        ⚠️ 呢個**手機唔會話你知**：
           · 你喺香港計劃去東京 → 你想知東京而家幾點（排行程）
           · 你喺東京想打返香港 → 你想知香港而家幾點（唔好半夜打）
           · 你喺東京但行程寫「Day 3」→ 係東京嘅 Day 3

   ⚠️⚠️ 而且仲有一個更隱蔽嘅問題：**日期唔可以因為時區而偏移**。
      `new Date('2026-11-19')` 喺 JS 會當做 **UTC 午夜**，
      喺 UTC-5 嘅機 `toLocaleDateString()` 會顯示 **11-18**！
      所以日期一定要當做「**日曆日**」（冇時區），
      用 `new Date(y, m-1, d)` 解析（見 web/src/lib/dates.js）。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
點樣由城市座標搵到 IANA 時區（唔用外部 library）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚠️ 為咩唔用 `timezonefinder`：
   佢要一個 ~50MB 嘅邊界資料庫。對我哋嘅用途（顯示多個時鐘）
   唔值。而且我哋已經有**國家代碼**（geocoding 已經回傳），
   覆蓋率足夠。

三層策略：
  ① 單一時區國家 → 查表（最準）
  ② 多時區國家（美／加／澳／俄／巴西／印尼／墨西哥）→ 按**經度**分帶
  ③ 未知國家 → 經度估算（nautical time zone，誤差通常 ±1 鐘）
"""

from __future__ import annotations

# ══════════════════════════════════════════════════════════════════
# ① 單一時區國家／地區
# ══════════════════════════════════════════════════════════════════

COUNTRY_TZ: dict[str, str] = {
    # ── 東亞 ──
    "HK": "Asia/Hong_Kong",
    "MO": "Asia/Macau",
    "TW": "Asia/Taipei",
    "JP": "Asia/Tokyo",
    "KR": "Asia/Seoul",
    "CN": "Asia/Shanghai",      # ⚠️ 全中國用一個時區（雖然地理上橫跨 5 個）
    "MN": "Asia/Ulaanbaatar",
    # ── 東南亞 ──
    "SG": "Asia/Singapore",
    "MY": "Asia/Kuala_Lumpur",
    "TH": "Asia/Bangkok",
    "VN": "Asia/Ho_Chi_Minh",
    "PH": "Asia/Manila",
    "KH": "Asia/Phnom_Penh",
    "LA": "Asia/Vientiane",
    "MM": "Asia/Yangon",
    "BN": "Asia/Brunei",
    # ── 南亞 / 中亞 ──
    "IN": "Asia/Kolkata",       # ⚠️ UTC+5:30（半個鐘）
    "NP": "Asia/Kathmandu",     # ⚠️ UTC+5:45（離奇嘅 45 分）
    "LK": "Asia/Colombo",
    "BD": "Asia/Dhaka",
    "PK": "Asia/Karachi",
    "KZ": "Asia/Almaty",
    "UZ": "Asia/Tashkent",
    # ── 中東 ──
    "AE": "Asia/Dubai",
    "SA": "Asia/Riyadh",
    "QA": "Asia/Qatar",
    "KW": "Asia/Kuwait",
    "BH": "Asia/Bahrain",
    "OM": "Asia/Muscat",
    "IL": "Asia/Jerusalem",
    "JO": "Asia/Amman",
    "LB": "Asia/Beirut",
    "TR": "Europe/Istanbul",
    # ── 歐洲 ──
    "GB": "Europe/London",
    "IE": "Europe/Dublin",
    "FR": "Europe/Paris",
    "DE": "Europe/Berlin",
    "IT": "Europe/Rome",
    "ES": "Europe/Madrid",
    "PT": "Europe/Lisbon",
    "NL": "Europe/Amsterdam",
    "BE": "Europe/Brussels",
    "CH": "Europe/Zurich",
    "AT": "Europe/Vienna",
    "GR": "Europe/Athens",
    "PL": "Europe/Warsaw",
    "CZ": "Europe/Prague",
    "HU": "Europe/Budapest",
    "SE": "Europe/Stockholm",
    "NO": "Europe/Oslo",
    "DK": "Europe/Copenhagen",
    "FI": "Europe/Helsinki",
    "IS": "Atlantic/Reykjavik",
    "HR": "Europe/Zagreb",
    "RO": "Europe/Bucharest",
    # ── 非洲 ──
    "EG": "Africa/Cairo",
    "ZA": "Africa/Johannesburg",
    "KE": "Africa/Nairobi",
    "ET": "Africa/Addis_Ababa",
    "MA": "Africa/Casablanca",
    "NG": "Africa/Lagos",
    "GH": "Africa/Accra",
    "TZ": "Africa/Dar_es_Salaam",
    # ── 大洋洲（單一時區）──
    "NZ": "Pacific/Auckland",
    "FJ": "Pacific/Fiji",
    "GU": "Pacific/Guam",
    # ── 美洲（單一時區）──
    "AR": "America/Argentina/Buenos_Aires",
    "CL": "America/Santiago",
    "PE": "America/Lima",
    "CO": "America/Bogota",
    "VE": "America/Caracas",
    "EC": "America/Guayaquil",
    "CU": "America/Havana",
    "CR": "America/Costa_Rica",
    "PA": "America/Panama",
    "UY": "America/Montevideo",
    "BO": "America/La_Paz",
}

# ══════════════════════════════════════════════════════════════════
# ② 多時區國家 —— 按經度分帶
# ══════════════════════════════════════════════════════════════════
# ⚠️ 每個 list 係 [(經度上界, IANA), ...]，由西向東檢查。
#    ⚠️ 用**經度**而唔係州份 —— 因為我哋只有 lat/lng，冇行政區資料。
#       經度分帶對主要城市夠準（例如 LA -118 → 西岸、NY -74 → 東岸）。

MULTI_TZ: dict[str, list[tuple[float, str]]] = {
    # ── 美國（本土 + 東岸）──
    #   ⚠️⚠️ 每個 tuple 係 (該帶嘅**東邊界經度**, IANA)。
    #      由西向東排，條件 `lng < upper` → 命中第一條。
    #      ⚠️ 第一版寫成西邊界（-124, -114…）→ 全部向東串移一格，
    #         紐約變咗 Halifax、芝加哥變咗紐約。
    #      ⚠️ 最後一條一定要係**大正數**（東邊盡頭），
    #         唔可以係 -999（咁樣永遠命中最後一條）。
    "US": [
        (-114.0, "America/Los_Angeles"),   # 西岸（-125 ~ -114）
        (-109.0, "America/Phoenix"),       # ⚠️ 亞利桑那唔跟夏令時間
        (-102.0, "America/Denver"),        # 山地
        (-87.0, "America/Chicago"),        # 中部
        (-65.0, "America/New_York"),       # 東岸
        (999.0, "America/Halifax"),        # 大西洋
    ],
    "CA": [
        (-114.0, "America/Vancouver"),
        (-102.0, "America/Edmonton"),
        (-88.0, "America/Winnipeg"),
        (-68.0, "America/Toronto"),
        (999.0, "America/Halifax"),
    ],
    "AU": [
        (129.0, "Australia/Perth"),        # 西澳 UTC+8
        (141.0, "Australia/Adelaide"),     # ⚠️ 南澳 UTC+9:30（半個鐘）
        (999.0, "Australia/Sydney"),       # 東岸 UTC+10/+11
    ],
    "RU": [
        (60.0, "Europe/Moscow"),
        (85.0, "Asia/Yekaterinburg"),
        (100.0, "Asia/Krasnoyarsk"),
        (120.0, "Asia/Irkutsk"),
        (999.0, "Asia/Vladivostok"),
    ],
    "BR": [
        (-50.0, "America/Manaus"),
        (-42.0, "America/Sao_Paulo"),
        (999.0, "America/Fortaleza"),
    ],
    "ID": [
        (115.0, "Asia/Jakarta"),
        (130.0, "Asia/Makassar"),
        (999.0, "Asia/Jayapura"),
    ],
    "MX": [
        (-106.0, "America/Tijuana"),
        (-93.0, "America/Mexico_City"),
        (999.0, "America/Cancun"),
    ],
    "ES": [  # ⚠️ 加那利群島（UTC+0）同本土（UTC+1）唔同
        (-10.0, "Atlantic/Canary"),
        (999.0, "Europe/Madrid"),
    ],
    "PT": [  # ⚠️ 亞速爾群島（UTC-1）
        (-18.0, "Atlantic/Azores"),
        (999.0, "Europe/Lisbon"),
    ],
}

# ══════════════════════════════════════════════════════════════════
# ③ 經度估算（fallback）
# ══════════════════════════════════════════════════════════════════
# ⚠️ 呢個係「航海時區」（nautical time zone）：每 15° 一個鐘。
#    實際上政治時區唔跟經度（例如西班牙地理上喺 UTC+0 但用 UTC+1），
#    所以只用喺**查唔到國家**嘅情況，而且標明係「估算」。

def _by_longitude(lng: float) -> str:
    """
    經度 → `Etc/GMT±N`。

    ⚠️⚠️ `Etc/GMT` 嘅**正負號係反轉**嘅！
       `Etc/GMT-9` = UTC+9（東京）
       `Etc/GMT+5` = UTC-5（紐約）
       呢個係 POSIX 遺留嘅約定，好易寫錯。
    """
    n = int(round(lng / 15.0))
    n = max(-12, min(14, n))
    if n == 0:
        return "Etc/GMT"
    # UTC+9 → "Etc/GMT-9"（負號）
    return f"Etc/GMT{-n:+d}"


# ══════════════════════════════════════════════════════════════════
# 對外 API
# ══════════════════════════════════════════════════════════════════

def lookup(lat: float | None, lng: float | None,
           cc: str | None = None) -> dict:
    """
    由座標 + 國家代碼估算 IANA 時區。

    回傳 {"tz": "Asia/Tokyo", "source": "country|longitude|none",
          "confident": bool}

    ⚠️ `confident=False` 代表係**估算** —— 前端應該顯示「約」
       而唔係當佢準（例如西班牙用 UTC+1 但經度係 0°）。
    """
    cc = (cc or "").strip().upper()

    # ① 多時區國家 → 按經度分帶（要先檢查，因為有啲國家同時喺兩個表）
    if cc in MULTI_TZ and lng is not None:
        for upper, tz in MULTI_TZ[cc]:
            if lng < upper:
                return {"tz": tz, "source": "country", "confident": True}
        return {"tz": MULTI_TZ[cc][-1][1], "source": "country", "confident": True}

    # ② 單一時區國家
    if cc in COUNTRY_TZ:
        return {"tz": COUNTRY_TZ[cc], "source": "country", "confident": True}

    # ③ 經度估算
    if lng is not None:
        return {"tz": _by_longitude(lng), "source": "longitude", "confident": False}

    return {"tz": None, "source": "none", "confident": False}


def stats() -> dict:
    return {
        "countries": len(COUNTRY_TZ),
        "multi": len(MULTI_TZ),
        "total": len(set(COUNTRY_TZ.values()) | {
            tz for bands in MULTI_TZ.values() for _, tz in bands}),
    }


if __name__ == "__main__":
    # 自我測試
    cases = [
        (35.69, 139.69, "JP", "Asia/Tokyo"),
        (37.57, 126.98, "KR", "Asia/Seoul"),
        (25.05, 121.53, "TW", "Asia/Taipei"),
        (22.28, 114.17, "HK", "Asia/Hong_Kong"),
        (13.75, 100.50, "TH", "Asia/Bangkok"),
        (51.51, -0.13, "GB", "Europe/London"),
        (40.71, -74.01, "US", "America/New_York"),
        (34.05, -118.24, "US", "America/Los_Angeles"),
        (41.88, -87.63, "US", "America/Chicago"),
        (-33.87, 151.21, "AU", "Australia/Sydney"),
        (49.25, -123.12, "CA", "America/Vancouver"),
        (25.08, 55.31, "AE", "Asia/Dubai"),
        (19.43, -99.13, "MX", "America/Mexico_City"),
        (-23.55, -46.63, "BR", "America/Sao_Paulo"),
        (28.61, 77.21, "IN", "Asia/Kolkata"),
        (-41.29, 174.78, "NZ", "Pacific/Auckland"),
        (48.85, 2.35, "FR", "Europe/Paris"),
        (52.52, 13.40, "DE", "Europe/Berlin"),
        (55.75, 37.62, "RU", "Europe/Moscow"),
    ]
    ok = 0
    for lat, lng, cc, want in cases:
        got = lookup(lat, lng, cc)
        good = got["tz"] == want
        ok += good
        print(f"  {'✓' if good else '✗'} {cc} {lat:6.2f},{lng:8.2f} → "
              f"{got['tz']:32} (要 {want})")
    print(f"\n  {ok}/{len(cases)} 通過")
    print(f"  {stats()}")
