"""
wander.ua — 共用 User-Agent
===========================

⚠️ 呢個檔存在嘅原因：踩過三次 UA 相關嘅坑。

實測記錄：
    "Wander/0.1"                          → Nominatim 403
    "...Chrome/124.0 Safari/537.36"       → html.duckduckgo.com 403
    "...Chrome/124.0.0.0 Safari/537.36"   → 全部 200 ✅
    "...Chrome/124.0 Safari/537.36"       → r.jina.ai 403（Cloudflare）

結論：**一定要用完整、標準嘅瀏覽器 UA 字串**。
     少一個 ".0.0" 都會被 bot detection 擋。
     呢個係做 scraping 最反直覺嘅坑之一。
"""

BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

# 如果將來要申請 API（Nominatim 政策建議），可以喺呢度加聯絡方式
CONTACT = "wander-app@example.com"


# ══════════════════════════════════════════════════════════════
# API 專用 User-Agent
# ══════════════════════════════════════════════════════════════
#
# ⚠️⚠️ 唔同服務嘅要求係**相反**嘅，呢個係踩過嘅坑：
#
#   DuckDuckGo HTML  → 一定要**完整瀏覽器 UA**（Chrome/124.0.0.0）
#                       用自訂 UA 會被 403
#
#   Overpass API     → 一定要**自訂 UA**，明確識別自己
#                       用瀏覽器 UA 會被 **406 Not Acceptable**
#                       （實測：BROWSER_UA → 406；"Wander/1.0" → 200）
#                       原因：佢哋要區分「真人瀏覽」同「程式查詢」，
#                       程式查詢要自報身份先可以封鎖濫用者。
#
#   所以唔可以一個 UA 走天涯。
API_UA = "Wander/1.0 (travel planner; +https://github.com/wander)"
