"""
wander.qr — 純 Python QR Code 產生器（零依賴）
==============================================

⚠️ 為咩要自己寫而唔用 qrcode 套件：
   呢個專案嘅原則係**零依賴 + 離線可用**。
   加一個套件 = 用戶要 pip install = 多一個裝唔到嘅理由。
   QR Code 係 1994 年嘅公開標準，spec 好清楚，自己寫係啱嘅。

⚠️ 為咩要 QR Code：
   手機要用 `http://192.168.1.100:8787` —— 喺手機打呢串嘢好煩。
   喺電腦出個 QR，手機一掃就開到。

支援：
   · Byte mode（UTF-8，所以中文 URL 都得）
   · **EC level L**（最大容量）
       ⚠️ 誠實講：M / Q / H 未實作 —— 傳入會 raise ValueError。
          唔可以靜靜當 L，否則會出「format 話 M 但資料用 L」嘅壞 QR。
          URL 用途嚟講 L 最啱（裝得最多）。
   · Version 1–20（v20-L 可以裝 858 bytes）
   · 自動揀最細嘅 version
   · 自動揀最好嘅 mask（用 spec 嘅 penalty 評分）

輸出：
   · matrix()  → 二維 bool list（可以自己畫）
   · svg()     → SVG 字串（向量，任何 size 都清）
   · text()    → 用 █ / ░ 畫（terminal 睇）
"""
from __future__ import annotations

from typing import Optional

# ══════════════════════════════════════════════════════════════
# 規格表
# ══════════════════════════════════════════════════════════════

# 每個 version 嘅「資料碼字總數」（唔計 EC）
_TOTAL_CODEWORDS = {
    1: 26, 2: 44, 3: 70, 4: 100, 5: 134, 6: 172, 7: 196, 8: 242,
    9: 292, 10: 346, 11: 404, 12: 466, 13: 532, 14: 581, 15: 655,
    16: 733, 17: 815, 18: 901, 19: 991, 20: 1085,
}

# version → (EC codewords per block, group1 blocks, group1 data codewords,
#            group2 blocks, group2 data codewords)
#   只列 level L（最常用，容量最大）
_EC_L = {
    1:  (7, 1, 19, 0, 0),      2:  (10, 1, 34, 0, 0),
    3:  (15, 1, 55, 0, 0),     4:  (20, 1, 80, 0, 0),
    5:  (26, 1, 108, 0, 0),    6:  (18, 2, 68, 0, 0),
    7:  (20, 2, 78, 0, 0),     8:  (24, 2, 97, 0, 0),
    9:  (30, 2, 116, 0, 0),    10: (18, 2, 68, 2, 69),
    11: (20, 4, 81, 0, 0),     12: (24, 2, 92, 2, 93),
    13: (26, 4, 107, 0, 0),    14: (30, 3, 115, 1, 116),
    15: (22, 5, 87, 1, 88),    16: (24, 5, 98, 1, 99),
    17: (28, 1, 107, 5, 108),  18: (30, 5, 120, 1, 121),
    19: (28, 3, 113, 4, 114),  20: (28, 3, 107, 5, 108),
}

# 對齊圖案中心位置
_ALIGN = {
    1: [], 2: [6, 18], 3: [6, 22], 4: [6, 26], 5: [6, 30],
    6: [6, 34], 7: [6, 22, 38], 8: [6, 24, 42], 9: [6, 26, 46],
    10: [6, 28, 50], 11: [6, 30, 54], 12: [6, 32, 58], 13: [6, 34, 62],
    14: [6, 26, 46, 66], 15: [6, 26, 48, 70], 16: [6, 26, 50, 74],
    17: [6, 30, 54, 78], 18: [6, 30, 56, 82], 19: [6, 30, 58, 86],
    20: [6, 34, 62, 90],
}

_EC_LEVEL_BITS = {"L": 1, "M": 0, "Q": 3, "H": 2}


# ══════════════════════════════════════════════════════════════
# GF(256) 有限體運算（Reed-Solomon 要）
# ══════════════════════════════════════════════════════════════

_EXP = [0] * 512
_LOG = [0] * 256
_x = 1
for _i in range(255):
    _EXP[_i] = _x
    _LOG[_x] = _i
    _x <<= 1
    if _x & 0x100:
        _x ^= 0x11D          # 本原多項式 x^8+x^4+x^3+x^2+1
for _i in range(255, 512):
    _EXP[_i] = _EXP[_i - 255]


def _gf_mul(a: int, b: int) -> int:
    if a == 0 or b == 0:
        return 0
    return _EXP[_LOG[a] + _LOG[b]]


def _rs_generator(n: int) -> list[int]:
    """Reed-Solomon 生成多項式（degree n）。"""
    g = [1]
    for i in range(n):
        # 乘 (x - α^i)
        g2 = [0] * (len(g) + 1)
        for j, c in enumerate(g):
            g2[j] ^= c
            g2[j + 1] ^= _gf_mul(c, _EXP[i])
        g = g2
    return g


def _rs_encode(data: list[int], ec_len: int) -> list[int]:
    """為 data 計算 ec_len 個 EC 碼字。"""
    g = _rs_generator(ec_len)
    res = [0] * ec_len
    for byte in data:
        factor = byte ^ res[0]
        res = res[1:] + [0]
        if factor:
            for i in range(ec_len):
                res[i] ^= _gf_mul(g[i + 1], factor)
    return res


# ══════════════════════════════════════════════════════════════
# 資料編碼
# ══════════════════════════════════════════════════════════════

def _capacity(version: int, ec: str) -> int:
    """該 version/level 可以裝幾多個資料碼字。"""
    if ec != "L":
        raise ValueError(f"只支援 EC level L（收到 {ec!r}）")
    table = {"L": _EC_L}[ec]
    _, b1, d1, b2, d2 = table[version]
    return b1 * d1 + b2 * d2


def _pick_version(nbytes: int, ec: str) -> Optional[int]:
    """
    揀最細嘅 version。

    ⚠️ 要**精確**計所需 bit 數，唔可以粗略估。
       原本寫「nbytes + 3 <= 容量」→ 對 v1-L 嚟講太保守：
       v1-L 容量 19 碼字 = 152 bit，
       17 bytes 需要 4 + 8 + 17×8 = 148 bit → 其實裝得落，
       但粗略估 17+3=20 > 19 → 錯過咗，揀咗 v2（大 16%）。
    """
    for v in range(1, 21):
        cap_bits = _capacity(v, ec) * 8
        need = 4 + (8 if v <= 9 else 16) + nbytes * 8
        if need <= cap_bits:
            return v
    return None


def _encode_data(text: str, version: int, ec: str) -> list[int]:
    """Byte mode 編碼 → 碼字 list。"""
    payload = text.encode("utf-8")
    bits: list[int] = []

    def push(val: int, n: int):
        for i in range(n - 1, -1, -1):
            bits.append((val >> i) & 1)

    push(0b0100, 4)                       # byte mode
    nbits = 8 if version <= 9 else 16
    push(len(payload), nbits)
    for b in payload:
        push(b, 8)

    total = _capacity(version, ec) * 8
    # 終止符（最多 4 個 0）
    for _ in range(min(4, total - len(bits))):
        bits.append(0)
    # 補到 8 嘅倍數
    while len(bits) % 8:
        bits.append(0)

    out = [int("".join(map(str, bits[i:i + 8])), 2) for i in range(0, len(bits), 8)]
    # 補位元組 0xEC / 0x11 交替
    pad = [0xEC, 0x11]
    i = 0
    while len(out) < _capacity(version, ec):
        out.append(pad[i % 2])
        i += 1
    return out


def _interleave(blocks: list[list[int]], ec_blocks: list[list[int]]) -> list[int]:
    """按 spec 交錯資料同 EC 碼字。"""
    out: list[int] = []
    maxlen = max((len(b) for b in blocks), default=0)
    for i in range(maxlen):
        for b in blocks:
            if i < len(b):
                out.append(b[i])
    ecmax = max((len(b) for b in ec_blocks), default=0)
    for i in range(ecmax):
        for b in ec_blocks:
            if i < len(b):
                out.append(b[i])
    return out


def _split_and_ec(codewords: list[int], version: int, ec: str) -> list[int]:
    _, b1, d1, b2, d2 = {"L": _EC_L}[ec][version]
    ec_len = _EC_L[version][0]
    blocks, ecbs, pos = [], [], 0
    for _ in range(b1):
        d = codewords[pos:pos + d1]; pos += d1
        blocks.append(d); ecbs.append(_rs_encode(d, ec_len))
    for _ in range(b2):
        d = codewords[pos:pos + d2]; pos += d2
        blocks.append(d); ecbs.append(_rs_encode(d, ec_len))
    return _interleave(blocks, ecbs)


# ══════════════════════════════════════════════════════════════
# 模組放置
# ══════════════════════════════════════════════════════════════

def _new_matrix(size: int):
    """回傳 (modules, reserved)。reserved = 功能圖案（唔可以放資料）。"""
    m = [[0] * size for _ in range(size)]
    r = [[False] * size for _ in range(size)]
    return m, r


def _place_finder(m, r, row, col):
    for i in range(-1, 8):
        for j in range(-1, 8):
            rr, cc = row + i, col + j
            if not (0 <= rr < len(m) and 0 <= cc < len(m)):
                continue
            inside = 0 <= i <= 6 and 0 <= j <= 6
            border = i in (0, 6) or j in (0, 6)
            core = 2 <= i <= 4 and 2 <= j <= 4
            m[rr][cc] = 1 if (inside and (border or core)) else 0
            r[rr][cc] = True


def _place_alignment(m, r, version):
    size = len(m)
    for row in _ALIGN[version]:
        for col in _ALIGN[version]:
            # 跳過同 finder 重疊嘅位置
            if (row <= 8 and col <= 8) or (row <= 8 and col >= size - 9) \
                    or (row >= size - 9 and col <= 8):
                continue
            for i in range(-2, 3):
                for j in range(-2, 3):
                    on = max(abs(i), abs(j)) != 1
                    m[row + i][col + j] = 1 if on else 0
                    r[row + i][col + j] = True


def _place_timing(m, r):
    size = len(m)
    for i in range(8, size - 8):
        v = 1 if i % 2 == 0 else 0
        if not r[6][i]:
            m[6][i] = v; r[6][i] = True
        if not r[i][6]:
            m[i][6] = v; r[i][6] = True


def _reserve_format(m, r):
    size = len(m)
    for i in range(9):
        for (rr, cc) in ((8, i), (i, 8)):
            if 0 <= rr < size and 0 <= cc < size:
                r[rr][cc] = True
    for i in range(8):
        r[8][size - 1 - i] = True
        r[size - 1 - i][8] = True
    r[size - 8][8] = True
    # 固定暗模組
    m[size - 8][8] = 1


def _place_data(m, r, codewords: list[int]):
    """
    放置資料模組（zigzag，由右下向上）。

    ⚠️⚠️ 呢度踩過一個極隱蔽嘅 bug：
       原本會將 `r[row][c] = True`（標記已放置），
       但 `r` 係「功能圖案位置」map，之後 `_apply_mask` 靠佢判斷
       「邊啲格可以 mask」。放完資料之後成個 map 都變 True →
       **mask 完全冇應用到** → QR 掃唔到，但結構睇落完全正常。

       修法：用一個 local copy 做放置，唔好污染 caller 嘅 `r`。
    """
    size = len(m)
    filled = [row[:] for row in r]
    bits: list[int] = []
    for cw in codewords:
        for i in range(7, -1, -1):
            bits.append((cw >> i) & 1)

    idx = 0
    col = size - 1
    upward = True
    while col > 0:
        if col == 6:
            col -= 1
        rows = range(size - 1, -1, -1) if upward else range(size)
        for row in rows:
            for c in (col, col - 1):
                if not filled[row][c]:
                    m[row][c] = bits[idx] if idx < len(bits) else 0
                    filled[row][c] = True
                    idx += 1
        upward = not upward
        col -= 2


_MASKS = [
    lambda i, j: (i + j) % 2 == 0,
    lambda i, j: i % 2 == 0,
    lambda i, j: j % 3 == 0,
    lambda i, j: (i + j) % 3 == 0,
    lambda i, j: (i // 2 + j // 3) % 2 == 0,
    lambda i, j: (i * j) % 2 + (i * j) % 3 == 0,
    lambda i, j: ((i * j) % 2 + (i * j) % 3) % 2 == 0,
    lambda i, j: ((i + j) % 2 + (i * j) % 3) % 2 == 0,
]


def _apply_mask(m, r, mask_id: int) -> list[list[int]]:
    size = len(m)
    fn = _MASKS[mask_id]
    out = [row[:] for row in m]
    for i in range(size):
        for j in range(size):
            if not r[i][j] and fn(i, j):
                out[i][j] ^= 1
    return out


def _place_format(m, ec: str, mask_id: int):
    size = len(m)
    data = (_EC_LEVEL_BITS[ec] << 3) | mask_id
    # BCH(15,5)
    v = data << 10
    for i in range(4, -1, -1):
        if v & (1 << (i + 10)):
            v ^= 0b10100110111 << i
    bits = ((data << 10) | v) ^ 0b101010000010010

    # ⚠️⚠️⚠️ 呢度踩過最嚴重嘅 bug：**format info 位置 transpose 咗**。
    #
    #    自己寫 QR encoder 最易錯嘅位就係呢度 ——
    #    因為 format info 唔係簡單放喺一行，而係散喺兩條「L 形」上面，
    #    而且 row/col 嘅次序極易掉轉。
    #
    #    錯咗嘅後果：QR 結構睇落完全正常（finder/timing 都啱），
    #    但**掃唔到**。冇任何錯誤訊息 —— 只有「掃唔到」。
    #
    #    正確位置（對照 ISO/IEC 18004 同 qrcode 套件嘅實作）：
    #
    #    第一份（圍住左上 finder，L 形）：
    #      bits 0-5  → (0..5, 8)   垂直，行 0-5，第 8 列
    #      bit  6    → (7, 8)      跳過 timing 嘅 (6,8)
    #      bit  7    → (8, 8)
    #      bit  8    → (8, 7)
    #      bits 9-14 → (8, 5..0)   水平，第 8 行，向左
    #
    #    第二份：
    #      bits 0-7  → (8, size-1 .. size-8)   水平，第 8 行，由右邊數
    #      bits 8-14 → (size-7 .. size-1, 8)   垂直，第 8 列，貼底部
    for i in range(15):
        bit = (bits >> i) & 1
        # ── 第一份：垂直部分（第 8 列）──
        if i < 6:
            m[i][8] = bit
        elif i < 8:
            m[i + 1][8] = bit
        # ── 第一份：水平部分（第 8 行）──
        elif i == 8:
            m[8][7] = bit
        else:
            m[8][14 - i] = bit
        # ── 第二份 ──
        if i < 8:
            m[8][size - 1 - i] = bit
        else:
            m[size - 15 + i][8] = bit


def _penalty(m) -> int:
    """QR spec 定義嘅 mask 評分（越低越好）。"""
    size = len(m)
    score = 0
    # 規則 1：同色連續
    for line in list(m) + [list(c) for c in zip(*m)]:
        run, prev = 1, line[0]
        for v in line[1:]:
            if v == prev:
                run += 1
            else:
                if run >= 5:
                    score += 3 + (run - 5)
                run, prev = 1, v
        if run >= 5:
            score += 3 + (run - 5)
    # 規則 2：2×2 同色
    for i in range(size - 1):
        for j in range(size - 1):
            if m[i][j] == m[i][j + 1] == m[i + 1][j] == m[i + 1][j + 1]:
                score += 3
    # 規則 4：黑白平衡
    dark = sum(sum(row) for row in m)
    pct = dark * 100 // (size * size)
    score += abs(pct - 50) // 5 * 10
    return score


# ══════════════════════════════════════════════════════════════
# 公開 API
# ══════════════════════════════════════════════════════════════

def matrix(text: str, ec: str = "L") -> Optional[list[list[bool]]]:
    """產生 QR 矩陣。裝唔落 → None。"""
    if not text:
        return None
    if ec != "L":
        raise ValueError(f"只支援 EC level L（收到 {ec!r}）—— M/Q/H 未實作")
    version = _pick_version(len(text.encode("utf-8")), ec)
    if version is None:
        return None

    size = version * 4 + 17
    m, r = _new_matrix(size)
    _place_finder(m, r, 0, 0)
    _place_finder(m, r, 0, size - 7)
    _place_finder(m, r, size - 7, 0)
    _place_alignment(m, r, version)
    _place_timing(m, r)
    _reserve_format(m, r)

    cw = _encode_data(text, version, ec)
    final = _split_and_ec(cw, version, ec)
    _place_data(m, r, final)

    # 揀最好嘅 mask
    best, best_score = None, None
    for mid in range(8):
        cand = _apply_mask(m, r, mid)
        _place_format(cand, ec, mid)
        s = _penalty(cand)
        if best_score is None or s < best_score:
            best, best_score = cand, s
    return [[bool(v) for v in row] for row in best]


def svg(text: str, *, module: int = 8, border: int = 4,
        dark: str = "#0b0518", light: str = "#ffffff") -> str:
    """產生 SVG（向量，任何 size 都清）。"""
    mx = matrix(text)
    if mx is None:
        return ""
    n = len(mx)
    total = (n + border * 2) * module
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{total}" height="{total}" '
        f'viewBox="0 0 {total} {total}" shape-rendering="crispEdges">',
        f'<rect width="{total}" height="{total}" fill="{light}"/>',
    ]
    # 逐行合併連續黑格（檔案細啲）
    for y, row in enumerate(mx):
        x = 0
        while x < n:
            if row[x]:
                run = 1
                while x + run < n and row[x + run]:
                    run += 1
                parts.append(
                    f'<rect x="{(x + border) * module}" y="{(y + border) * module}" '
                    f'width="{run * module}" height="{module}" fill="{dark}"/>')
                x += run
            else:
                x += 1
    parts.append("</svg>")
    return "".join(parts)


def text_qr(text: str, *, quiet: bool = True) -> str:
    """用方塊字元畫（terminal 睇）。"""
    mx = matrix(text)
    if mx is None:
        return "（裝唔落）"
    n = len(mx)
    pad = 1 if quiet else 0
    lines = []
    for y in range(-pad, n + pad):
        line = []
        for x in range(-pad, n + pad):
            inside = 0 <= y < n and 0 <= x < n
            line.append("██" if inside and mx[y][x] else "  ")
        lines.append("".join(line))
    return "\n".join(lines)
