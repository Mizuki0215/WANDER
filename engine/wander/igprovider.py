"""
wander.igprovider — 可選嘅第三方 IG 抓取服務
============================================

⚠️ 為咩要有呢個檔
----------------
IG 對**所有**未登入嘅 server 請求一律回傳 JS 空殼（零資料）。
我實測過嘅全部失敗：
    · 直接抓 HTML              → 302 /accounts/login/
    · /embed/captioned/        → 636KB JS 殼，冇 caption
    · /api/v1/oembed/          → 401
    · ?__a=1&__d=dis           → 404
    · api.instagram.com/oembed → JS 殼
    · graph.facebook.com/oembed→ 要 token
    · r.jina.ai reader         → 第一次得，之後 Cloudflare 403

「點解人哋啲 app 做到？」—— 因為佢哋**俾錢**買第三方抓取服務。
呢啲服務自己養住宅代理 + 帳號池 + 反偵測，成本轉嫁落你身上。

所以：呢個檔提供**可選**嘅支援。你唔配置就完全唔會用（維持免費）。
你配置咗 API key，就會自動抓，唔使貼 caption。

⚠️ 成本同法律
------------
    · 各服務都有免費額度（通常 100 次），之後要俾錢
    · 回傳嘅係「公開可見」內容，但**合規責任喺用家身上**
    · 呢啲服務全部喺 IG ToS 嘅灰色地帶（IG 明文禁止自動化存取）

    所以預設**關閉**，而且 UI 會清楚講明。
    想零成本零風險嘅話，用書籤小工具（見 lib/bookmarklet.js）。
"""
from __future__ import annotations

import os
import re
from typing import Any, Optional

import requests

from .ua import BROWSER_UA

# ══════════════════════════════════════════════════════════════
# 支援嘅服務
# ══════════════════════════════════════════════════════════════

PROVIDERS: dict[str, dict[str, Any]] = {
    "scrapecreators": {
        "label": "ScrapeCreators",
        "url": "https://api.scrapecreators.com/v1/instagram/post",
        "auth": "x-api-key",
        "param": "url",
        "free": "100 次免費（唔使信用卡）",
        "pricing": "約 $1.88 / 1000 次",
        "signup": "https://scrapecreators.com",
        "note": "最簡單嘅 REST，一個 GET 就搞掂",
    },
    "socialfetch": {
        "label": "Social Fetch",
        "url": "https://api.socialfetch.dev/v1/instagram/posts",
        "auth": "bearer",
        "param": "url",
        "free": "100 credits 免費（唔使信用卡）",
        "pricing": "約 $1.65 / 1000 次",
        "signup": "https://app.socialfetch.dev",
        "note": "多平台統一 schema",
    },
    "hikerapi": {
        "label": "HikerAPI",
        "url": "https://api.hikerapi.com/v1/media/info/by/url",
        "auth": "x-access-key",
        "param": "url",
        "free": "約 100 次（要自己確認）",
        "pricing": "約 $0.60–1.00 / 1000 次（最平）",
        "signup": "https://hikerapi.com",
        "note": "IG 專門，最便宜",
    },
}

# 由回應抽出 caption 嘅候選欄位（唔同服務唔同路徑）
_CAPTION_PATHS = [
    ("caption",), ("caption_text",), ("text",), ("description",),
    ("data", "caption"), ("data", "caption_text"), ("data", "text"),
    ("data", "edge_media_to_caption", "edges", 0, "node", "text"),
    ("items", 0, "caption", "text"),
    ("items", 0, "caption"),
    ("media", "caption"),
    ("result", "caption"),
    ("post", "caption"),
]

_AUTHOR_PATHS = [
    ("owner", "username"), ("username",), ("author",), ("user", "username"),
    ("data", "owner", "username"), ("data", "username"),
    ("items", 0, "owner", "username"), ("items", 0, "user", "username"),
]

_IMAGE_PATHS = [
    ("display_url",), ("image_url",), ("thumbnail_url",), ("image",),
    ("data", "display_url"), ("data", "image_url"), ("data", "thumbnail_url"),
    ("items", 0, "image_versions2", "candidates", 0, "url"),
    ("items", 0, "display_url"),
    ("media", "image"),
]


def _dig(obj: Any, path: tuple) -> Optional[Any]:
    """跟路徑搵值，搵唔到回 None（唔會拋錯）。"""
    cur = obj
    for k in path:
        try:
            if isinstance(k, int):
                if not isinstance(cur, (list, tuple)) or len(cur) <= k:
                    return None
                cur = cur[k]
            else:
                if not isinstance(cur, dict) or k not in cur:
                    return None
                cur = cur[k]
        except Exception:
            return None
    return cur


def _first_str(obj: Any, paths: list) -> Optional[str]:
    for p in paths:
        v = _dig(obj, p)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


def configured() -> Optional[tuple[str, str]]:
    """
    讀環境變數，回傳 (provider_name, api_key) 或 None。

        WANDER_IG_PROVIDER=scrapecreators
        WANDER_IG_KEY=your_key_here
    """
    name = (os.environ.get("WANDER_IG_PROVIDER") or "").strip().lower()
    key = (os.environ.get("WANDER_IG_KEY") or "").strip()
    if not name or not key:
        return None
    if name not in PROVIDERS:
        return None
    return name, key


def is_configured() -> bool:
    return configured() is not None


def status() -> dict:
    """俾 /api/health 同 UI 顯示用。"""
    c = configured()
    if not c:
        return {
            "enabled": False,
            "providers": {
                k: {"label": v["label"], "free": v["free"],
                    "pricing": v["pricing"], "signup": v["signup"], "note": v["note"]}
                for k, v in PROVIDERS.items()
            },
            "hint": "未配置第三方抓取服務 → IG 要用書籤小工具或貼 caption",
        }
    return {"enabled": True, "provider": c[0],
            "label": PROVIDERS[c[0]]["label"], "hint": f"已啟用 {PROVIDERS[c[0]]['label']}"}


def fetch_post(url: str, *, timeout: int = 30) -> Optional[dict]:
    """
    用第三方服務抓一個 IG 貼文。

    回傳 {"caption","author","image","source"} 或 None。
    ⚠️ 任何錯誤都唔會拋出去 —— 抓唔到就回 None，由上層 fallback。
    """
    c = configured()
    if not c:
        return None
    name, key = c
    spec = PROVIDERS[name]

    headers = {"User-Agent": BROWSER_UA, "Accept": "application/json"}
    if spec["auth"] == "bearer":
        headers["Authorization"] = f"Bearer {key}"
    else:
        headers[spec["auth"]] = key

    try:
        r = requests.get(spec["url"], params={spec["param"]: url},
                         headers=headers, timeout=timeout)
    except requests.RequestException:
        return None

    if r.status_code == 401 or r.status_code == 403:
        return {"error": "auth", "detail": f"{spec['label']} 拒絕個 API key（{r.status_code}）"}
    if r.status_code == 429:
        return {"error": "quota", "detail": f"{spec['label']} 額度用完（429）"}
    if r.status_code >= 400:
        return {"error": "http", "detail": f"{spec['label']} 回傳 {r.status_code}"}

    try:
        data = r.json()
    except Exception:
        return {"error": "json", "detail": f"{spec['label']} 回傳唔係 JSON"}

    caption = _first_str(data, _CAPTION_PATHS)
    if not caption:
        return {"error": "nocaption",
                "detail": f"{spec['label']} 回傳成功但搵唔到 caption（可能服務改咗 schema）"}

    return {
        "caption": caption,
        "author": _first_str(data, _AUTHOR_PATHS),
        "image": _first_str(data, _IMAGE_PATHS),
        "source": f"igprovider:{name}",
    }


def fetch_post_text(url: str) -> Optional[str]:
    """只要 caption 文字（俾 fetch.py 用）。"""
    r = fetch_post(url)
    if r and r.get("caption"):
        return r["caption"]
    return None


# ══════════════════════════════════════════════════════════════
# 判斷係唔係「需要第三方服務」嘅 IG URL
# ══════════════════════════════════════════════════════════════

IG_URL_RE = re.compile(
    r"^https?://(?:www\.)?instagram\.com/(?:p|reel|reels|tv)/[\w-]+", re.I)


def is_instagram(url: str) -> bool:
    return bool(IG_URL_RE.match(url or ""))
