/**
 * 圖片處理工具
 * ============
 * ⚠️ 為咩一定要前端縮圖：
 *    手機影相郁啲就 4MB。base64 之後變 5.3MB，上傳要十幾秒。
 *    縮到最長邊 1200px + JPEG 0.82 → 通常 150-350KB，快 15 倍。
 *    而且購物清單嘅相只係用嚟認貨，唔需要原相。
 */

/** 由檔案讀成 data URL，同時縮圖。 */
export function readAndResize(file, { maxSize = 1200, quality = 0.82 } = {}) {
  return new Promise((resolve, reject) => {
    if (!file) return reject(new Error('冇檔案'))
    if (!/^image\//.test(file.type)) return reject(new Error('唔係圖片'))
    if (file.size > 25 * 1024 * 1024) return reject(new Error('原圖太大（>25MB）'))

    const reader = new FileReader()
    reader.onerror = () => reject(new Error('讀唔到檔案'))
    reader.onload = () => {
      const img = new Image()
      img.onerror = () => reject(new Error('唔係有效圖片'))
      img.onload = () => {
        const { width: w, height: h } = img
        const scale = Math.min(1, maxSize / Math.max(w, h))
        const cw = Math.max(1, Math.round(w * scale))
        const ch = Math.max(1, Math.round(h * scale))

        const cv = document.createElement('canvas')
        cv.width = cw; cv.height = ch
        const ctx = cv.getContext('2d')
        ctx.fillStyle = '#fff'          // PNG 透明底轉 JPEG 會變黑
        ctx.fillRect(0, 0, cw, ch)
        ctx.drawImage(img, 0, 0, cw, ch)
        resolve({
          data: cv.toDataURL('image/jpeg', quality),
          width: cw, height: ch,
          original: { width: w, height: h, bytes: file.size },
        })
      }
      img.src = reader.result
    }
    reader.readAsDataURL(file)
  })
}

/** 粗略檔案大小（由 data URL 估）。 */
export function dataUrlBytes(dataUrl) {
  const i = (dataUrl || '').indexOf(',')
  if (i < 0) return 0
  return Math.round((dataUrl.length - i - 1) * 3 / 4)
}

export function fmtBytes(n) {
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} KB`
  return `${(n / 1024 / 1024).toFixed(1)} MB`
}


/**
 * 讀圖俾 QR 解碼用。
 *
 * ⚠️⚠️ 唔可以用 readAndResize 嘅參數！
 *    QR 解碼最怕**壓縮失真** —— 原本 1200px / JPEG 0.82 會令
 *    細格嘅 QR 糊成一團，OpenCV 就解唔到。
 *
 *    呢個版本：最長邊 1600px（保留多啲格）、PNG（無損）、
 *    而且**唔加白底**（QR 自己已經有白邊）。
 */
export function readForQr(file, { maxSize = 1600 } = {}) {
  return new Promise((resolve, reject) => {
    if (!file) return reject(new Error('冇檔案'))
    if (!/^image\//.test(file.type)) return reject(new Error('唔係圖片'))
    if (file.size > 25 * 1024 * 1024) return reject(new Error('原圖太大'))

    const reader = new FileReader()
    reader.onerror = () => reject(new Error('讀唔到檔案'))
    reader.onload = () => {
      const img = new Image()
      img.onerror = () => reject(new Error('唔係有效圖片'))
      img.onload = () => {
        const { width: w, height: h } = img
        const scale = Math.min(1, maxSize / Math.max(w, h))
        const cw = Math.max(1, Math.round(w * scale))
        const ch = Math.max(1, Math.round(h * scale))
        const cv = document.createElement('canvas')
        cv.width = cw; cv.height = ch
        const ctx = cv.getContext('2d')
        ctx.drawImage(img, 0, 0, cw, ch)
        // PNG 無損 —— QR 唔可以失真
        resolve({ data: cv.toDataURL('image/png'), width: cw, height: ch })
      }
      img.src = reader.result
    }
    reader.readAsDataURL(file)
  })
}
