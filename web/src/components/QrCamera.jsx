import { useEffect, useRef, useState } from 'react'
import { api } from '../lib/api'
import { toast } from '../lib/ui'

/**
 * 📷 用相機掃 QR Code
 * =====================
 *
 * ⚠️⚠️ 用戶要求：
 *   「另外就係加朋友嗰個，除咗我哋 upload 人哋嘅 QR code 之外，
 *    我仲想用開 Camera 嘅方式，例如係 scan QR code 影低佢」
 *
 * ⚠️⚠️ 為咩唔用 `BarcodeDetector`：
 *   · Chrome / Edge 有，**Safari 同 Firefox 冇**
 *   · 用戶用 iPhone（Safari）→ 一定唔 work
 *
 * ✅ 所以：開相機 → **每 800ms 影一格** → 送去後端
 *    `/api/qr/decode`（後端已經有 OpenCV，經實測）
 *
 * ⚠️ 為咩要 throttle（800ms）：
 *   唔 throttle 嘅話一秒送 60 張 → 手機發熱 + 後端爆。
 *   QR 唔會一瞬間出現，800ms 好夠。
 *
 * ⚠️ `getUserMedia` **一定要 HTTPS**（或者 localhost）。
 *   經 cloudflared tunnel 嘅話係 HTTPS ✓
 */

const INTERVAL_MS = 800

export default function QrCamera({ onFound, onClose }) {
  const videoRef = useRef(null)
  const canvasRef = useRef(null)
  const streamRef = useRef(null)
  const timerRef = useRef(null)
  const busyRef = useRef(false)
  const [err, setErr] = useState('')
  const [hint, setHint] = useState('將 QR Code 放喺框入面…')

  useEffect(() => {
    let dead = false

    async function start() {
      // ⚠️ 一定要 check 支援 —— 舊瀏覽器冇
      if (!navigator.mediaDevices?.getUserMedia) {
        setErr('呢個瀏覽器唔支援相機。可以用「揀一張圖」代替。')
        return
      }
      try {
        // ⚠️ `facingMode: 'environment'` = 後置鏡頭（掃 QR 一定用後置）
        const stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: { ideal: 'environment' }, width: { ideal: 1280 } },
          audio: false,
        })
        if (dead) { stream.getTracks().forEach(t => t.stop()); return }
        streamRef.current = stream
        if (videoRef.current) {
          videoRef.current.srcObject = stream
          await videoRef.current.play().catch(() => {})
        }
        timerRef.current = setInterval(tick, INTERVAL_MS)
      } catch (e) {
        // ⚠️ 分清「用戶拒絕」同「冇相機」—— 提示要唔同
        const denied = /NotAllowed|Permission/i.test(e.name || '')
        setErr(denied
          ? '你拒絕咗相機權限。要喺瀏覽器設定開啟，或者用「揀一張圖」。'
          : `開唔到相機：${e.message}。可以用「揀一張圖」代替。`)
      }
    }

    /** ⚠️ 影一格 → 縮圖 → 送後端解。 */
    async function tick() {
      // ⚠️ 一定要防止重疊 —— 上一次仲未返就唔好再送
      if (busyRef.current) return
      const v = videoRef.current, c = canvasRef.current
      if (!v || !c || !v.videoWidth) return
      busyRef.current = true
      try {
        // ⚠️ 縮到最長邊 900px —— 夠解 QR，但細好多（快 5–10 倍）
        const max = 900
        const scale = Math.min(1, max / Math.max(v.videoWidth, v.videoHeight))
        const w = Math.round(v.videoWidth * scale)
        const h = Math.round(v.videoHeight * scale)
        c.width = w; c.height = h
        c.getContext('2d').drawImage(v, 0, 0, w, h)
        const data = c.toDataURL('image/jpeg', 0.75)

        const r = await api.decodeQr(data)
        if (r?.username) {
          stop()
          onFound?.(r.username)
          return
        }
        // ⚠️ 解到 QR 但唔係 Wander 嘅 → 話俾用戶知（唔好靜靜唔動）
        if (r?.text) setHint(`解到「${r.text.slice(0, 22)}」但唔係 Wander QR`)
      } catch {
        // ⚠️ 解唔到係**正常**（大多數 frame 都冇 QR）—— 唔好嘈
      } finally {
        busyRef.current = false
      }
    }

    function stop() {
      if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null }
      streamRef.current?.getTracks().forEach(t => t.stop())
      streamRef.current = null
    }

    start()
    return () => { dead = true; stop() }
  }, [onFound])

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 200, background: '#000',
      display: 'flex', flexDirection: 'column',
    }}>
      <div className="row" style={{ padding: '10px 12px', alignItems: 'center', gap: 8 }}>
        <div style={{ flex: 1, fontWeight: 900, fontSize: 14, color: '#fff' }}>
          📷 掃 QR Code
        </div>
        <button className="btn sm ghost" style={{ color: '#fff' }}
          onClick={onClose}>✕ 閂</button>
      </div>

      <div style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>
        <video ref={videoRef} playsInline muted
          style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
        {/* ⚠️ 對準框 —— 正方形，四角有角標 */}
        <div style={{
          position: 'absolute', inset: 0, display: 'grid', placeItems: 'center',
          pointerEvents: 'none',
        }}>
          <div style={{
            width: 'min(68vw, 300px)', aspectRatio: '1',
            border: '3px solid rgba(255,255,255,.9)', borderRadius: 18,
            boxShadow: '0 0 0 9999px rgba(0,0,0,.45)',
          }} />
        </div>
        <canvas ref={canvasRef} style={{ display: 'none' }} />
        {err && (
          <div style={{
            position: 'absolute', inset: 0, display: 'grid', placeItems: 'center',
            padding: 24, textAlign: 'center', color: '#fff', fontSize: 13,
            background: 'rgba(0,0,0,.8)', lineHeight: 1.9,
          }}>{err}</div>
        )}
      </div>

      <div style={{ padding: '10px 14px 22px', color: '#fff', fontSize: 11.5,
                    textAlign: 'center', lineHeight: 1.9 }}>
        {hint}
        <br />
        <span style={{ opacity: .6 }}>
          ⚠️ 要 HTTPS 先開到相機（tunnel 就係 HTTPS）
        </span>
      </div>
    </div>
  )
}
