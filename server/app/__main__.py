"""
啟動伺服器：
    cd server && python -m app

會自動：
  1. 建立 SQLite schema
  2. 綁 0.0.0.0（等手機連同一個 WiFi 都開得）
  3. 印出本機 + 區網 URL
"""
from __future__ import annotations

import socket
import subprocess

import uvicorn

PORT = 8787


def _is_private(ip: str) -> bool:
    """只接受真正嘅區網 IP（排除 link-local / 公網 / VPN 內部）。"""
    return (ip.startswith("192.168.") or ip.startswith("10.")
            or ip.startswith("172.16.") or ip.startswith("172.17.")
            or ip.startswith("172.18.") or ip.startswith("172.19.")
            or any(ip.startswith(f"172.{n}.") for n in range(20, 32)))


def lan_ips() -> list[str]:
    """
    攞所有可能嘅區網 IP。

    ⚠️⚠️ 踩過嘅大坑：最初用 `socket.connect(('8.8.8.8', 80))` 攞 IP，
       結果攞到 **VPN 嘅 utun 介面 IP**（10.2.0.2），唔係 WiFi 嘅
       192.168.1.100。用戶照住印出嘅 URL 用手機連 → 永遠連唔到。

    教訓：macOS 有 VPN / iCloud Private Relay 嘅時候，
         「route 去 8.8.8.8 用邊個介面」唔等於「手機連得到嘅介面」。

    正確做法：直接問網絡介面（en0/en1 = WiFi/Ethernet），
             過濾走 utun（VPN）、bridge、awdl、llw。
    """
    out: list[str] = []
    try:
        raw = subprocess.run(["ifconfig"], capture_output=True, text=True, timeout=5).stdout
        cur = ""
        for line in raw.splitlines():
            if line and not line[0].isspace():
                cur = line.split(":")[0]
                continue
            if "inet " not in line:
                continue
            # ⚠️ 排除 VPN / bridge / awdl / llw / lo
            if cur.startswith(("utun", "bridge", "awdl", "llw", "lo", "gif", "stf", "ipsec")):
                continue
            ip = line.split("inet ")[1].split()[0]
            if _is_private(ip) and ip not in out:
                out.append(ip)
    except Exception:
        pass

    # 後備：用 UDP trick（可能攞到 VPN IP，但至少有嘢）
    if not out:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            if ip != "127.0.0.1":
                out.append(ip)
        except Exception:
            pass
    return out


def main() -> None:
    from .db import DB_PATH, init_db

    init_db()
    ips = lan_ips()

    print(f"""
  ┌─ Wander ─────────────────────────────────────────────
  │  資料庫   {DB_PATH}
  │
  │  電腦     http://127.0.0.1:{PORT}
  │  手機     {f"http://{ips[0]}:{PORT}" if ips else "（搵唔到區網 IP，睇下面）"}
  │
  │  ⚠️ 手機要連同一個 WiFi
  │  ⚠️ 登入驗證碼會印喺呢個 console
  │  ⚠️ 手機想有離線功能 → 撳「分享 → 加到主畫面」
  │     （http:// 區網 IP 唔係 secure context，註冊唔到 service worker）
  └────────────────────────────────────────────────────────""")
    if len(ips) > 1:
        print("  │  其他介面：" + "  ".join(f"http://{ip}:{PORT}" for ip in ips[1:]))
    if not ips:
        print("  │  ⚠️ 搵唔到區網 IP —— 檢查 WiFi 有冇連線")
    print()

    uvicorn.run("app.main:app", host="0.0.0.0", port=PORT, reload=False)


if __name__ == "__main__":
    main()
