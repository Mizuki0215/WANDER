/**
 * Wander 書籤小工具（Bookmarklet）
 * ================================
 *
 * ⚠️ 為咩要呢個（而唔係 WebView 偷 cookie）：
 *
 *   IG 對所有未登入嘅 server-side 請求回傳登入頁，零資料。
 *   網上有人教「WebView 偷 cookie 去爬」，但：
 *     · Web App 做唔到（Same-Origin Policy，讀唔到 instagram.com 嘅 cookie）
 *     · 原生 App 做到但會令**用戶帳號被鎖**（cookie 綁 IP + 裝置指紋）
 *     · 要儲存用戶 IG session → server 一被入侵就洩漏晒所有人帳號
 *     · 違反 IG ToS
 *
 *   正確做法：**用用戶自己嘅瀏覽器、自己嘅登入狀態，由用戶主動撳一下。**
 *   書籤小工具就係咁：
 *     · 用戶喺 IG 開住個帖（已經登入，見得到內容）
 *     · 撳一下書籤 → 喺**用戶自己嘅分頁**讀取 DOM
 *     · 抽到 caption + 圖片 + 原 link → 放入剪貼簿
 *     · 用戶去 Wander 貼上 → 完成
 *
 *   法律上等同「用戶自己選取文字複製」，完全乾淨。
 *   技術上唔需要任何 server-side 爬蟲、唔需要 cookie、唔需要 API key。
 *
 * ⚠️ 點解用剪貼簿而唔係直接開 Wander URL：
 *   書籤小工具跑喺 https://www.instagram.com，
 *   如果開 http://192.168.x.x:8787 會被 Chrome 當 mixed content 擋。
 *   所以最可靠係「複製 → 用戶貼上」。部署上 HTTPS 之後可以改成直接開。
 */

export const PAYLOAD_START = '---WANDER---'
export const PAYLOAD_END = '---WANDER-END---'

/** 書籤小工具嘅原始碼（會壓縮成一行）。 */
const BOOKMARKLET_SRC = `(function(){
  var host = location.hostname;
  var out = { url: location.href.split('?')[0], caption: '', image: '', author: '' };

  function txt(el){ return el ? (el.innerText || el.textContent || '').trim() : ''; }

  /* ══ Instagram ══ */
  if (/instagram\\.com$/.test(host)) {
    /* 主 caption */
    var h1 = document.querySelector('h1');
    if (h1) out.caption = txt(h1);
    if (!out.caption) {
      var meta = document.querySelector('meta[property="og:description"]');
      if (meta) out.caption = (meta.getAttribute('content') || '').trim();
    }
    /* 作者 */
    var a = document.querySelector('header a[href^="/"] span, a[href^="/"][role="link"] span');
    if (a) out.author = txt(a).replace(/^@/, '');
    /* 圖片 */
    var img = document.querySelector('article img[srcset], main img[srcset]');
    if (img) out.image = (img.getAttribute('src') || '').split('?')[0];
    /* 冇 h1 就試埋所有 span（IG 改版好頻） */
    if (!out.caption) {
      var cands = [].slice.call(document.querySelectorAll('div[dir="auto"], span[dir="auto"]'))
        .map(txt).filter(function(t){ return t.length > 30; });
      if (cands.length) out.caption = cands.sort(function(x,y){ return y.length - x.length; })[0];
    }
  }

  /* ══ 小紅書 ══ */
  else if (/xiaohongshu\\.com$/.test(host)) {
    var d = document.querySelector('#detail-desc, .desc, .note-content');
    out.caption = txt(d);
    if (!out.caption) {
      var m = document.querySelector('meta[name="description"], meta[property="og:description"]');
      if (m) out.caption = (m.getAttribute('content') || '').trim();
    }
    var im = document.querySelector('.swiper-slide img, .note-slider img');
    if (im) out.image = (im.getAttribute('src') || '').split('?')[0];
  }

  /* ══ 其他網站：og / 內文 ══ */
  else {
    var ogd = document.querySelector('meta[property="og:description"]');
    out.caption = (ogd && ogd.getAttribute('content')) || '';
    var ogi = document.querySelector('meta[property="og:image"]');
    if (ogi) out.image = ogi.getAttribute('content') || '';
    if (!out.caption) {
      var art = document.querySelector('article, main');
      out.caption = txt(art).slice(0, 1500);
    }
    var ogt = document.querySelector('meta[property="og:title"]');
    if (ogt) out.author = (ogt.getAttribute('content') || '').split('|')[0].trim();
  }

  out.caption = (out.caption || '').replace(/\\s+\\n/g, '\\n').trim().slice(0, 4000);

  if (!out.caption) {
    alert('Wander：喺呢一頁搵唔到內文。\\n\\n試下展開內文（撳「更多」）再撳一次書籤。');
    return;
  }

  var payload = '${PAYLOAD_START}\\n'
    + 'url: ' + out.url + '\\n'
    + (out.author ? 'author: ' + out.author + '\\n' : '')
    + (out.image ? 'image: ' + out.image + '\\n' : '')
    + 'caption: |\\n'
    + out.caption.split('\\n').map(function(l){ return '  ' + l; }).join('\\n')
    + '\\n${PAYLOAD_END}';

  function done(){
    var msg = document.createElement('div');
    msg.textContent = '✓ Wander：已複製內文 (' + out.caption.length + ' 字) — 去 Wander 貼上';
    msg.style.cssText = 'position:fixed;left:50%;top:24px;transform:translateX(-50%);'
      + 'z-index:2147483647;background:#a855f7;color:#0b0518;font-weight:800;'
      + 'font-size:14px;padding:12px 20px;border-radius:99px;'
      + 'box-shadow:0 8px 30px rgba(0,0,0,.4);font-family:system-ui,sans-serif';
    document.body.appendChild(msg);
    setTimeout(function(){ msg.remove(); }, 3200);
  }

  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(payload).then(done, function(){
      /* 剪貼簿唔得（權限）→ 彈出一個 textarea 俾用戶手動複製 */
      var ta = document.createElement('textarea');
      ta.value = payload;
      ta.style.cssText = 'position:fixed;left:10px;top:10px;width:90%;height:60%;'
        + 'z-index:2147483647;font-size:13px;padding:12px;border-radius:10px;'
        + 'border:2px solid #a855f7;background:#160d2e;color:#efeaff';
      document.body.appendChild(ta);
      ta.select();
      alert('Wander：請按 ⌘C / Ctrl+C 複製，再關閉呢個框，然後去 Wander 貼上。');
      ta.remove();
    });
  } else {
    var ta2 = document.createElement('textarea');
    ta2.value = payload;
    ta2.style.cssText = 'position:fixed;left:10px;top:10px;width:90%;height:60%;'
      + 'z-index:2147483647;font-size:13px;padding:12px;border-radius:10px;'
      + 'border:2px solid #a855f7;background:#160d2e;color:#efeaff';
    document.body.appendChild(ta2);
    ta2.select();
    alert('Wander：請按 ⌘C / Ctrl+C 複製，再關閉呢個框，然後去 Wander 貼上。');
    ta2.remove();
  }
})();`

/**
 * 壓成一行（bookmarklet 唔可以有換行）。
 *
 * ⚠️⚠️ 呢度踩過一個嚴重 bug：
 *    原本上面嘅原始碼用 `//` 行註解。壓縮成一行之後，
 *    個 `//` 會**吞掉成行後面所有程式碼** —— 成個書籤小工具直接壞掉
 *    （SyntaxError: Unexpected end of input），但**用戶唔會知係邊度壞**。
 *
 *    所以：書籤小工具嘅原始碼**一定唔可以用 `//` 註解**，只可以用 `/* *\/`。
 *    呢個 bug 係用 jsdom 真跑一次先發現 —— 淨係睇語法檢查唔會捉到。
 *    （見 tests/web/bookmarklet-dom.test.mjs）
 */
export function bookmarkletCode() {
  return 'javascript:' + BOOKMARKLET_SRC.replace(/\s*\n\s*/g, ' ').trim()
}

export const PAYLOAD_HINT = `貼上之後 Wander 會自動認得，抽出 caption、原 link、封面圖。`

/**
 * 解析書籤小工具嘅 payload。
 * 回傳 { url, author, image, caption } 或 null（唔係 payload）。
 */
export function parsePayload(text) {
  if (!text || !text.includes(PAYLOAD_START)) return null
  const start = text.indexOf(PAYLOAD_START) + PAYLOAD_START.length
  const end = text.indexOf(PAYLOAD_END)
  const body = text.slice(start, end < 0 ? undefined : end)

  const out = { url: null, author: null, image: null, caption: '' }
  const lines = body.split('\n')
  let inCaption = false
  const capLines = []
  for (const raw of lines) {
    const line = raw.replace(/\r$/, '')
    if (inCaption) {
      // caption 用 2 空格縮排
      capLines.push(line.replace(/^ {2}/, ''))
      continue
    }
    const m = /^(url|author|image|caption):\s*(.*)$/.exec(line.trim())
    if (!m) continue
    const [, key, val] = m
    if (key === 'caption' && val.trim() === '|') { inCaption = true; continue }
    if (key === 'url') out.url = val.trim()
    else if (key === 'author') out.author = val.trim()
    else if (key === 'image') out.image = val.trim()
    else if (key === 'caption') out.caption = val.trim()
  }
  if (inCaption) out.caption = capLines.join('\n').trim()
  return out.caption || out.url ? out : null
}
