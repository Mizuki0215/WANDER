#!/usr/bin/env python3
"""
寄信設定工具
==============

⚠️⚠️ 點解要有呢個工具（而唔係叫你喺 chat 打密碼）：

   用戶要求：「我係真係想我 email 收到有呢一封嘅 email。」

   ⚠️ 但 App Password 等同你 Gmail 嘅**發信權**。
      如果喺 chat 打，佢會留喺**對話紀錄**（我哋兩邊都見到）。
      → 用呢個工具，密碼只會由你嘅鍵盤直接寫入 `server/.env`，
        **唔會經過任何對話**。

用法：
    cd server
    python tools/setup_mail.py

    # 之後即刻試寄一封：
    python tools/setup_mail.py --test 你@gmail.com
"""

from __future__ import annotations

import argparse
import getpass
import os
import re
import sys
from pathlib import Path

SERVER = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SERVER))
sys.path.insert(0, str(SERVER.parent / "engine"))

ENV_FILE = SERVER / ".env"

# ⚠️ 呢啲 key 由我哋管理 —— 設定之前先清走舊值，否則會殘留
OUR_KEYS = [
    "WANDER_SMTP_HOST", "WANDER_SMTP_PORT", "WANDER_SMTP_USER",
    "WANDER_SMTP_PASS", "WANDER_RESEND_KEY", "WANDER_MAIL_FROM",
]

METHODS = {
    "1": {
        "name": "Gmail App Password",
        "quota": "500 封/日",
        "need": "Google 帳號要開咗兩步驗證",
        "hint": "https://myaccount.google.com/apppasswords",
    },
    "2": {
        "name": "Resend",
        "quota": "100 封/日（3000/月）",
        "need": "⚠️ 未驗證網域之下，只可以寄去你自己註冊嘅 email",
        "hint": "https://resend.com/api-keys",
    },
    "3": {
        "name": "Brevo（可以寄去任何人）",
        "quota": "300 封/日",
        "need": "要驗證寄件人 email",
        "hint": "https://app.brevo.com → SMTP & API",
    },
}


def read_env() -> dict:
    if not ENV_FILE.exists():
        return {}
    out = {}
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        t = line.strip()
        if not t or t.startswith("#") or "=" not in t:
            continue
        k, v = t.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def write_env(pairs: dict) -> None:
    """
    寫入 `.env`。

    ⚠️ 一定要**保留**其他人寫嘅 key（例如 WANDER_ADMIN_EMAILS）——
       唔可以整份覆蓋。
    """
    lines = ENV_FILE.read_text(encoding="utf-8").splitlines() if ENV_FILE.exists() else []
    # 清走我哋要重設嘅 key（同埋舊註解）
    kept, skip_next_comment = [], False
    for ln in lines:
        t = ln.strip()
        if any(t.startswith(f"{k}=") for k in OUR_KEYS):
            continue
        kept.append(ln)
    # 補一個空行
    while kept and not kept[-1].strip():
        kept.pop()
    if kept:
        kept.append("")
    kept.append("# ── 寄信（由 tools/setup_mail.py 寫入）──")
    for k, v in pairs.items():
        kept.append(f"{k}={v}")
    ENV_FILE.write_text("\n".join(kept) + "\n", encoding="utf-8")
    try:
        os.chmod(ENV_FILE, 0o600)      # ⚠️ 只有你可以讀
    except Exception:
        pass


def ask(prompt: str, *, secret: bool = False, default: str = "") -> str:
    try:
        if secret:
            return getpass.getpass(prompt).strip()
        v = input(prompt).strip()
        return v or default
    except (EOFError, KeyboardInterrupt):
        print("\n  ✗ 取消")
        sys.exit(1)


def setup_gmail() -> dict:
    print()
    print("  ⚠️ 前提：你嘅 Google 帳號要開咗**兩步驗證**")
    print("     去 https://myaccount.google.com/apppasswords")
    print("     應用程式選「郵件」、裝置選「其他」→ 打「Wander」→ 產生")
    print("     會出一個 16 位密碼（例：abcd efgh ijkl mnop）")
    print()
    user = ask("  你嘅 Gmail：")
    if "@" not in user:
        print("  ✗ 唔似 email")
        sys.exit(1)
    pw = ask("  App Password（16 位，可以連空格貼）：", secret=True)
    # ⚠️ Google 顯示嗰陣有空格 → 一定要刪走
    pw = re.sub(r"\s+", "", pw)

    # ⚠️⚠️ 硬性檢查：Google App Password **一定係 16 個字**。
    #
    #    實測中招：用戶貼咗**自己嘅 Gmail 登入密碼**（11 個字）,
    #    然後寄信回 `SMTPServerDisconnected: Connection unexpectedly closed`
    #    —— 睇落似「網絡問題」，其實係「憑證唔啱」。
    #
    #    ⚠️ Gmail 唔接受普通密碼做 SMTP（除非開「低安全性應用程式」，
    #       而 Google 已經喺 2022 年停用咗）。
    if len(pw) != 16:
        print()
        print(f"  ✗✗ 你打咗 {len(pw)} 個字 —— App Password **一定係 16 個**。")
        print()
        print("     你可能貼咗：")
        print("       · 你嘅 **Gmail 登入密碼**（唔可以用嚟做 SMTP）")
        print("       · 或者貼嘅時候截斷咗")
        print()
        print("     正確做法：")
        print("       1. 去 https://myaccount.google.com/apppasswords")
        print("          ⚠️ 呢一頁**只有開咗兩步驗證**先會出現")
        print("       2. 應用程式：郵件 · 裝置：其他 → 打「Wander」")
        print("       3. 撳「產生」→ 出一個 **16 位**密碼")
        print("          （顯示嗰陣有空格，例如 `abcd efgh ijkl mnop`）")
        print("       4. 再跑一次呢個工具，貼嗰 16 位")
        print()
        if "--force" not in sys.argv:
            print("  ⚠️ 如果真係想照用（唔建議）：加 --force 再跑")
            sys.exit(1)
        print("  ⚠️ --force：照寫入（但寄信一定失敗）")
    return {
        "WANDER_SMTP_HOST": "smtp.gmail.com",
        "WANDER_SMTP_PORT": "587",
        "WANDER_SMTP_USER": user,
        "WANDER_SMTP_PASS": pw,
        "WANDER_MAIL_FROM": user,
    }


def setup_resend() -> dict:
    print()
    print("  去 https://resend.com/api-keys 產生一個 API key（re_ 開頭）")
    print("  ⚠️ 未驗證網域之下只可以寄去**你自己註冊嘅 email**")
    print()
    key = ask("  Resend API key：", secret=True)
    if not key.startswith("re_"):
        print("  ⚠️ Resend key 通常以 re_ 開頭")
    to = ask("  你自己註冊 Resend 嗰個 email：")
    return {
        "WANDER_RESEND_KEY": key,
        "WANDER_MAIL_FROM": "Wander <onboarding@resend.dev>",
        # ⚠️ 記住用途：未驗證網域只寄得去呢個
        "WANDER_MAIL_TO_SELF": to,
    }


def setup_brevo() -> dict:
    print()
    print("  去 https://app.brevo.com → SMTP & API → SMTP")
    print("  攞 login（通常係你 email）同 SMTP key")
    print()
    login = ask("  Brevo SMTP login：")
    key = ask("  Brevo SMTP key：", secret=True)
    frm = ask("  寄件人 email（要喺 Brevo 驗證過）：", default=login)
    return {
        "WANDER_SMTP_HOST": "smtp-relay.brevo.com",
        "WANDER_SMTP_PORT": "587",
        "WANDER_SMTP_USER": login,
        "WANDER_SMTP_PASS": key,
        "WANDER_MAIL_FROM": frm,
    }


def send_test(to: str) -> int:
    """
    ⚠️ 一定要**另開 process** 試 ——
       因為 `mailer` 喺 module 層讀 env（`_cfg`），
       同一個 process 改咗 `os.environ` 佢唔會重新讀。
    """
    print()
    print("=" * 64)
    print("  試寄一封…")
    print("=" * 64)
    from app import mailer
    st = mailer.mail_status()
    print(f"  模式：{st.get('mode')}")
    if st.get("mode") == "console":
        print("  ⚠️ 仲係 console 模式 —— 設定冇生效？")
        print("     （記得：改咗 .env 要**重啟 server**）")
        return 1
    r = mailer.send_test_email(to)
    if r.get("sent"):
        print(f"  ✅ 寄咗去 {to}")
        print("     ⚠️ 去收件箱**同 spam** 睇下有冇")
        return 0

    err = r.get("error") or "未知"
    print(f"  ✗ 寄唔到：{err}")
    # ⚠️ 翻譯最常見嘅誤導性錯誤
    print()
    if "SMTPServerDisconnected" in err or "Connection unexpectedly closed" in err:
        print("  ⚠️⚠️ 呢個錯誤訊息**完全誤導** ——")
        print("     睇落似「網絡問題」，其實係「**憑證唔啱**」。")
        print("     Gmail 收到錯嘅 App Password 唔會講「密碼錯」，")
        print("     佢直接切斷連線（防止暴力破解）。")
        print()
        print("     你嘅密碼係幾個字？App Password **一定係 16 個**。")
    elif "Authentication" in err or "535" in err:
        print("  ⚠️ 認證失敗 —— App Password 唔啱（或者被 revoke 咗）")
    elif "timed out" in err.lower() or "Timeout" in err:
        print("  ⚠️ 連線逾時 —— 可能係防火牆封咗 SMTP port")
    print()
    print("  👉 詳細診斷：python tools/setup_mail.py --doctor")
    return 1


def main() -> int:
    ap = argparse.ArgumentParser(description="寄信設定")
    ap.add_argument("--test", metavar="EMAIL", help="只寄測試信")
    ap.add_argument("--show", action="store_true", help="睇目前設定")
    ap.add_argument("--force", action="store_true", help="就算格式唔啱都照寫")
    ap.add_argument("--doctor", action="store_true", help="診斷寄信問題")
    a = ap.parse_args()

    if a.test:
        return send_test(a.test)

    if a.doctor:
        return doctor()

    if a.show:
        from app import mailer
        import json
        print(json.dumps(mailer.mail_status(), ensure_ascii=False, indent=2))
        env = read_env()
        for k in OUR_KEYS:
            if k in env:
                v = env[k]
                # ⚠️ 唔可以印密碼出嚟
                if "PASS" in k or "KEY" in k:
                    v = f"（已設定，{len(v)} 字）"
                print(f"  {k} = {v}")
        return 0

    print("=" * 64)
    print("  Wander 寄信設定")
    print("=" * 64)
    print()
    print("  ⚠️⚠️ 你嘅密碼只會由鍵盤直接寫入 server/.env，")
    print("      **唔會經過任何對話或者紀錄**。")
    print()
    for k, m in METHODS.items():
        print(f"  {k}. {m['name']:26} {m['quota']}")
        print(f"     {m['need']}")
        print(f"     {m['hint']}")
    print()
    choice = ask("  揀邊個？(1/2/3)：", default="1")

    if choice == "1":
        pairs = setup_gmail()
    elif choice == "2":
        pairs = setup_resend()
    elif choice == "3":
        pairs = setup_brevo()
    else:
        print("  ✗ 冇呢個選項")
        return 1

    write_env(pairs)
    print()
    print(f"  ✅ 寫入 {ENV_FILE}")
    print(f"     （權限設咗 600 —— 只有你讀得到）")
    print()
    print("  ⚠️⚠️ 記住：要**重啟 server** 先生效：")
    print("       Ctrl+C 停咗佢，再 ./run.sh")
    print()
    print("  之後試寄：")
    print(f"       python tools/setup_mail.py --test {pairs.get('WANDER_MAIL_FROM', '你@email')}")
    return 0




def doctor() -> int:
    """
    診斷寄信問題。

    ⚠️⚠️ 為咩要呢個：
       實測用戶見到 `SMTPServerDisconnected: Connection unexpectedly closed`
       —— 呢個錯誤訊息**完全誤導**：
         睇落似「網絡問題 / server 掛咗」，其實係「憑證唔啱」。

       Gmail 收到錯嘅 App Password 唔會講「密碼錯」，
       佢直接**切斷連線**（防止暴力破解）。

    ✅ 所以呢個工具逐步試，並且**翻譯**錯誤去人話。
    """
    import socket
    import smtplib

    env = read_env()
    print("=" * 70)
    print("  寄信診斷")
    print("=" * 70)

    host = env.get("WANDER_SMTP_HOST", "")
    port = env.get("WANDER_SMTP_PORT", "587")
    user = env.get("WANDER_SMTP_USER", "")
    pw = env.get("WANDER_SMTP_PASS", "")
    frm = env.get("WANDER_MAIL_FROM", "")
    rk = env.get("WANDER_RESEND_KEY", "")

    # ── ① 設定檢查 ──
    print("\n  ① 設定")
    if rk:
        print(f"     ✓ Resend key（{len(rk)} 字）")
        print("     → 用 Resend，唔使 SMTP")
        return _doctor_resend(rk, frm)
    if not host:
        print("     ✗ 冇 WANDER_SMTP_HOST")
        print("       → 跑 `python tools/setup_mail.py` 設定")
        return 1
    print(f"     host = {host}")
    print(f"     port = {port}")
    print(f"     user = {user or '（冇）'}")
    print(f"     from = {frm or '（冇）'}")
    print(f"     pass = （{len(pw)} 字）")

    problems = []
    if not user:
        problems.append("冇 WANDER_SMTP_USER")
    if not pw:
        problems.append("冇 WANDER_SMTP_PASS")
    # ⚠️ Gmail App Password 一定係 16 字
    if "gmail" in host and len(pw) != 16:
        problems.append(
            f"⚠️⚠️ Gmail App Password **一定係 16 個字**，但你係 {len(pw)} 個\n"
            f"         → 好可能貼咗 Gmail **登入密碼**（唔可以用嚟做 SMTP）\n"
            f"         → 去 https://myaccount.google.com/apppasswords 產生 16 位"
        )
    if pw and pw != re.sub(r"\s+", "", pw):
        problems.append("密碼中間有空格 —— 應該刪走")
    if problems:
        print("\n     ⚠️ 發現問題：")
        for x in problems:
            print(f"       · {x}")
        # ⚠️ 唔好即刻 return —— 繼續測連線，
        #    證明「唔關網絡事，係憑證問題」（用戶最容易誤會）
        print("\n     （照繼續測連線，證明唔關網絡事…）")
    else:
        print("     ✓ 格式睇落正確")

    # ── ② 連得到嗎？──
    print(f"\n  ② 連線 {host}:{port}")
    try:
        sock = socket.create_connection((host, int(port)), timeout=12)
        sock.close()
        print("     ✓ TCP 連得到（唔關網絡事）")
    except Exception as e:
        print(f"     ✗ 連唔到：{type(e).__name__}: {e}")
        print("       → 可能係防火牆／公司網絡封咗 SMTP port")
        print("       → 試下 port 465（SSL）")
        return 1

    # ── ③ TLS ──
    print("\n  ③ STARTTLS")
    try:
        sm = smtplib.SMTP(host, int(port), timeout=20)
        sm.ehlo()
        sm.starttls()
        sm.ehlo()
        print("     ✓ TLS 握手成功")
    except Exception as e:
        print(f"     ✗ {type(e).__name__}: {e}")
        return 1

    # ── ④ 登入（最常見嘅失敗點）──
    print("\n  ④ 登入")
    try:
        sm.login(user, pw)
        print("     ✓ 登入成功")
    except smtplib.SMTPAuthenticationError as e:
        print(f"     ✗ 認證失敗：{e}")
        print()
        print("       ⚠️ Gmail 嘅 App Password 一定要 16 個字。")
        print("          如果你用咗登入密碼 → 一定失敗。")
        print("          https://myaccount.google.com/apppasswords")
        return 1
    except smtplib.SMTPServerDisconnected:
        print("     ✗ Server 切斷連線（SMTPServerDisconnected）")
        print()
        print("       ⚠️⚠️ 呢個錯誤訊息**完全誤導** ——")
        print("          睇落似「網絡問題」，其實係「**憑證唔啱**」。")
        print("          Gmail 收到錯嘅 App Password 唔會講「密碼錯」，")
        print("          佢直接切斷連線（防止暴力破解）。")
        print()
        print(f"          你嘅密碼係 {len(pw)} 個字 —— Gmail App Password 一定係 **16 個**。")
        print("          去 https://myaccount.google.com/apppasswords 重新產生")
        return 1
    except Exception as e:
        print(f"     ✗ {type(e).__name__}: {e}")
        return 1

    print("\n  " + "=" * 66)
    print("  ✅ 全部正常 —— 寄信設定冇問題")
    print("  " + "=" * 66)
    print(f"\n  試寄：python tools/setup_mail.py --test {frm or user}")
    sm.quit()
    return 0


def _doctor_resend(key: str, frm: str) -> int:
    """檢查 Resend key。"""
    print("\n  ② 試 Resend API")
    try:
        import requests
        r = requests.get("https://api.resend.com/domains",
                         headers={"Authorization": f"Bearer {key}"}, timeout=15)
        if r.status_code == 200:
            print("     ✓ Key 有效")
            print(f"     ⚠️ 寄件人：{frm or 'onboarding@resend.dev'}")
            print("       未驗證網域之下只可以寄去你自己註冊嘅 email")
            return 0
        print(f"     ✗ HTTP {r.status_code}: {r.text[:160]}")
        return 1
    except Exception as e:
        print(f"     ✗ {type(e).__name__}: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
