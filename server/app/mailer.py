"""
Wander 後端 — 寄信
==================

支援真實 email 寄送，唔再只係印喺 console。

設定（放喺 server/.env 或者環境變數）：

    # 方法 1：Gmail（最簡單，用 App Password）
    WANDER_SMTP_HOST=smtp.gmail.com
    WANDER_SMTP_PORT=587
    WANDER_SMTP_USER=yourname@gmail.com
    WANDER_SMTP_PASS=abcd efgh ijkl mnop     # Gmail App Password（16 位）
    WANDER_MAIL_FROM=Wander <yourname@gmail.com>

    # 方法 2：Resend（唔使自己開 SMTP，有免費額度）
    WANDER_RESEND_KEY=re_xxxxxxxx

⚠️ Gmail App Password 唔係你嘅登入密碼。
   要去 https://myaccount.google.com/apppasswords 產生
   （要先開兩步驗證）。
   普通密碼係唔會 work 嘅 —— Google 已經封鎖咗。

⚠️ 安全：.env 唔可以 commit 入 git（已經喺 .gitignore）。
"""
from __future__ import annotations

import os
import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path
from typing import Optional

ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


def load_env() -> None:
    """讀 .env（簡單 parser，唔加 dependency）。"""
    if not ENV_FILE.exists():
        return
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip().strip('"').strip("'")
        # 唔覆蓋已經有嘅環境變數（env 優先）
        os.environ.setdefault(k, v)


load_env()


def _cfg(key: str, default: Optional[str] = None) -> Optional[str]:
    v = os.environ.get(key)
    return v if v else default


def smtp_configured() -> bool:
    return bool(_cfg("WANDER_SMTP_HOST") and _cfg("WANDER_SMTP_USER")
                and _cfg("WANDER_SMTP_PASS"))


def resend_configured() -> bool:
    return bool(_cfg("WANDER_RESEND_KEY"))


def mail_configured() -> bool:
    return smtp_configured() or resend_configured()


def mail_status() -> dict:
    """
    俾前端 / console 顯示目前用邊個方法。

    ⚠️ 加 `from` / `to` 係為咗後台 ——
       用戶要求：「我真係想我 email 收到呢一封」→
       要一眼睇到「寄件人」同「測試會寄去邊」。
    """
    frm = _cfg("WANDER_MAIL_FROM")
    if smtp_configured():
        user = _cfg("WANDER_SMTP_USER")
        return {"mode": "smtp", "host": _cfg("WANDER_SMTP_HOST"),
                "user": user, "from": frm or user,
                # ⚠️ 測試信預設寄去登入嗰個 email（通常就係自己）
                "to": user}
    if resend_configured():
        return {"mode": "resend",
                "from": frm or "onboarding@resend.dev",
                "to": frm or None}
    return {"mode": "console",
            "hint": "未設定 SMTP → 驗證碼只會印喺 console"}


# ══════════════════════════════════════════════════════════════
# 寄信
# ══════════════════════════════════════════════════════════════

def _html_code(code: str, ttl: int) -> str:
    return f"""<!DOCTYPE html>
<html><body style="margin:0;padding:0;background:#0b0518;font-family:-apple-system,system-ui,'Noto Sans TC',sans-serif">
  <div style="max-width:460px;margin:0 auto;padding:36px 24px">
    <div style="text-align:center;margin-bottom:26px">
      <div style="font-size:34px;line-height:1">✦</div>
      <div style="color:#a855f7;font-weight:900;letter-spacing:.22em;font-size:13px;margin-top:10px">WANDER</div>
    </div>
    <div style="background:#160d2e;border:1px solid #3a2570;border-radius:14px;padding:26px;text-align:center">
      <div style="color:#9d8fc4;font-size:12.5px;margin-bottom:16px">你嘅登入驗證碼</div>
      <div style="font-family:ui-monospace,monospace;font-size:34px;font-weight:900;letter-spacing:9px;color:#efeaff">{code}</div>
      <div style="color:#9d8fc4;font-size:11.5px;margin-top:18px">{ttl} 分鐘內有效</div>
    </div>
    <div style="color:#6b5c96;font-size:11px;text-align:center;margin-top:22px;line-height:1.7">
      如果唔係你本人要求，可以忽略呢封郵件。<br>
      冇人會要你提供驗證碼 —— 唔好轉發俾任何人。
    </div>
  </div>
</body></html>"""


def _plain_code(code: str, ttl: int) -> str:
    return (f"Wander 登入驗證碼：{code}\n\n"
            f"{ttl} 分鐘內有效。\n"
            f"如果唔係你本人要求，可以忽略呢封郵件。\n")


def _send(to_email: str, subject: str, body_text: str, body_html: str) -> dict:
    """
    通用寄信（Resend → SMTP → console fallback）。

    ⚠️ 永遠唔會 raise。三個層級：
       ① Resend（HTTP API，唔使開 SMTP）
       ② Gmail SMTP（要 App Password）
       ③ console（印喺 server 終端機）
    """
    # ① Resend
    if resend_configured():
        try:
            import requests
            r = requests.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {_cfg('WANDER_RESEND_KEY')}"},
                json={
                    "from": _cfg("WANDER_MAIL_FROM") or "Wander <onboarding@resend.dev>",
                    "to": [to_email],
                    "subject": subject,
                    "text": body_text,
                    "html": body_html,
                }, timeout=20)
            if r.status_code < 300:
                return {"sent": True, "mode": "resend", "error": None}
            detail = ""
            try:
                detail = (r.json().get("message") or "")[:120]
            except Exception:
                detail = r.text[:120]
            return {"sent": False, "mode": "resend",
                    "error": f"Resend {r.status_code}: {detail}"}
        except Exception as e:
            return {"sent": False, "mode": "resend", "error": f"{type(e).__name__}: {e}"}

    # ② SMTP
    host = _cfg("WANDER_SMTP_HOST")
    if host:
        import smtplib
        from email.message import EmailMessage
        user = _cfg("WANDER_SMTP_USER")
        pwd = _cfg("WANDER_SMTP_PASS")
        port = int(_cfg("WANDER_SMTP_PORT", "587") or 587)
        sender = _cfg("WANDER_MAIL_FROM") or user

        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = sender
        msg["To"] = to_email
        msg.set_content(body_text)
        msg.add_alternative(body_html, subtype="html")
        try:
            ctx = ssl.create_default_context()
            if port == 465:
                with smtplib.SMTP_SSL(host, port, timeout=20, context=ctx) as srv:
                    srv.login(user, pwd)
                    srv.send_message(msg)
            else:
                with smtplib.SMTP(host, port, timeout=20) as srv:
                    srv.ehlo()
                    srv.starttls(context=ctx)
                    srv.ehlo()
                    srv.login(user, pwd)
                    srv.send_message(msg)
            return {"sent": True, "mode": "smtp", "error": None}
        except smtplib.SMTPAuthenticationError as e:
            return {"sent": False, "mode": "smtp",
                    "error": ("Gmail 認證失敗 —— 要用 App Password，唔係登入密碼。"
                              "去 https://myaccount.google.com/apppasswords 產生。"
                              f"（{e.smtp_code}）")}
        except Exception as e:
            return {"sent": False, "mode": "smtp", "error": f"{type(e).__name__}: {e}"}

    # ③ console
    return {"sent": False, "mode": "console", "error": None}


def send_code_email(to_email: str, code: str, ttl_minutes: int = 10) -> dict:
    """寄驗證碼。回傳 {"sent", "mode", "error"}。"""
    subject = f"Wander 登入驗證碼：{code}"
    return _send(to_email, subject,
                 _plain_code(code, ttl_minutes), _html_code(code, ttl_minutes))


def send_friend_invite(to_email: str, *, from_name: str, url: str,
                       note: str = "") -> dict:
    """
    寄交友邀請 email。

    ⚠️ 同驗證碼一樣：**永遠唔會拋錯**。
       寄唔到就回一個有 error 嘅 dict，由 caller 決定點顯示。
       原因：email 寄唔到唔應該令「加朋友」呢個動作失敗 ——
       邀請本身已經建立咗，對方用連結或者代碼一樣加到。
    """
    subject = f"{from_name} 想喺 Wander 加你做朋友"
    body_text = (
        f"{from_name} 想喺 Wander 加你做朋友，一齊計劃旅行。\n\n"
        + (f"佢留咗句話：{note}\n\n" if note else "")
        + f"撳呢條連結接受：\n{url}\n\n"
        "Wander 係一個旅行規劃 app —— 貼 link、分區排行程、分帳、購物清單。\n"
        "如果唔想加，忽略呢封 email 就得。"
    )
    body_html = f"""<!DOCTYPE html><html><body style="margin:0;padding:24px;
background:#0b0518;font-family:-apple-system,'Noto Sans TC',sans-serif">
<div style="max-width:520px;margin:0 auto;background:#160d2e;border-radius:18px;
padding:28px;border:1px solid #a855f733">
  <div style="font-size:26px;font-weight:900;letter-spacing:4px;
background:linear-gradient(100deg,#a855f7,#22d3ee);-webkit-background-clip:text;
-webkit-text-fill-color:transparent;background-clip:text">WANDER</div>
  <p style="color:#efeaff;font-size:15px;line-height:1.85;margin:20px 0 8px">
    <b style="color:#22d3ee">{from_name}</b> 想加你做朋友，一齊計劃旅行。
  </p>
  {f'<p style="color:#a99cd0;font-size:13px;line-height:1.8;margin:8px 0;padding:10px 14px;background:#1e1440;border-radius:10px;border-left:3px solid #a855f7">「{note}」</p>' if note else ''}
  <a href="{url}" style="display:inline-block;margin:22px 0 10px;padding:14px 30px;
background:linear-gradient(100deg,#a855f7,#22d3ee);color:#0b0518;font-weight:900;
text-decoration:none;border-radius:11px;font-size:15px">接受邀請 →</a>
  <p style="color:#6b5f96;font-size:11.5px;line-height:1.8;margin-top:22px">
    或者複製呢條連結：<br>
    <span style="color:#22d3ee;word-break:break-all">{url}</span>
  </p>
  <p style="color:#4a3d70;font-size:11px;margin-top:18px;line-height:1.7">
    唔想加？忽略呢封 email 就得，唔會再收到通知。
  </p>
</div></body></html>"""
    return _send(to_email, subject, body_text, body_html)


def _html_welcome(name: str) -> str:
    return f"""<!doctype html><html><body style="margin:0;background:#0b0518;
font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif">
<div style="max-width:520px;margin:0 auto;padding:32px 22px;color:#efeaff">
  <div style="font-size:26px;font-weight:900;letter-spacing:-.5px">Wander</div>
  <div style="height:3px;background:linear-gradient(90deg,#a855f7,#22d3ee);
       margin:14px 0 26px;border-radius:2px"></div>
  <div style="font-size:19px;font-weight:800;margin-bottom:14px">
    歡迎，{name} 👋
  </div>
  <div style="font-size:14px;line-height:1.9;color:#c9c0e8">
    你嘅 Wander 帳號已經開好。<br>
    而家可以去<b>旅程</b>開一個，貼啲 link 入嚟，就開始計劃啦。
  </div>
  <div style="margin-top:26px;padding:16px;background:#160d2e;
       border-left:3px solid #a855f7;border-radius:6px;font-size:13px;
       line-height:1.9;color:#c9c0e8">
    💡 貼一條 Google Maps 或 IG link，Wander 會自動幫你抽出
    地址、座標、分區。
  </div>
  <div style="margin-top:30px;font-size:11px;color:#6b5f8a">
    呢封信係系統自動寄出，唔使回覆。
  </div>
</div></body></html>"""


def _plain_welcome(name: str) -> str:
    return (f"歡迎，{name}！\n\n"
            "你嘅 Wander 帳號已經開好。\n"
            "去「旅程」開一個，貼啲 link 入嚟，就開始計劃啦。\n\n"
            "（呢封信係系統自動寄出，唔使回覆。）")


def send_welcome_email(to_email: str, name: str = "") -> dict:
    """
    寄歡迎信（註冊成功之後）。

    ⚠️⚠️ 用戶要求：
       「我係真係想我 email 收到有呢一封嘅 email。」
       → 註冊完要真係收到一封。

    ⚠️ 同其他一樣：**永遠唔會 raise** ——
       email 寄唔到唔應該令「註冊」失敗（帳號已經開好）。
    """
    who = (name or "").strip() or "朋友"
    return _send(to_email, "歡迎嚟到 Wander ✦",
                 _plain_welcome(who), _html_welcome(who))


def send_test_email(to_email: str) -> dict:
    """
    寄一封測試信（後台「測試寄信」掣用）。

    ⚠️ 為咩要呢個：
       設定 SMTP 之後最怕「以為設定好但其實寄唔到」。
       撳一下就即刻知 —— 唔使等真有註冊先發現。
    """
    st = mail_status()
    body = (f"Wander 寄信測試\n\n"
            f"如果你收到呢封信，代表寄信設定正常 ✓\n\n"
            f"模式：{st.get('mode')}\n"
            f"（呢封信係系統自動寄出，唔使回覆。）")
    html = f"""<!doctype html><html><body style="margin:0;background:#0b0518;
font-family:-apple-system,sans-serif">
<div style="max-width:480px;margin:0 auto;padding:30px 20px;color:#efeaff">
  <div style="font-size:22px;font-weight:900">Wander ✦ 寄信測試</div>
  <div style="height:3px;background:linear-gradient(90deg,#a855f7,#22d3ee);
       margin:12px 0 22px;border-radius:2px"></div>
  <div style="font-size:15px;line-height:1.9;color:#c9c0e8">
    ✅ 你收到呢封信 → 寄信設定<b>正常</b>。
  </div>
  <div style="margin-top:16px;font-size:12px;color:#6b5f8a">
    模式：{st.get('mode')}
  </div>
</div></body></html>"""
    return _send(to_email, "Wander 寄信測試 ✓", body, html)
