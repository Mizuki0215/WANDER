import { useEffect, useRef, useState } from 'react'
import { api, iconFor, confClass } from '../lib/api'
import { toast, Empty } from '../lib/ui'

/**
 * 地圖顯示所有有座標嘅收藏。
 * ⚠️ 用 Leaflet + OpenStreetMap 圖磚 —— 完全免費、免 API key、免信用卡。
 *    （Google Maps JS API 要綁卡，唔符合「免費版」要求）
 */
export default function MapView({ items, stops = [], onRefresh, onEditItem }) {
  const boxRef = useRef(null)
  const mapRef = useRef(null)
  const layerRef = useRef(null)
  const [sel, setSel] = useState(null)
  const [ready, setReady] = useState(!!window.L)

  const pinned = items.filter(i => i.lat != null && i.lng != null)
  // 有座標嘅城市（用戶設定目的地時自動 geocode）
  const cities = (stops || []).filter(s => s.lat != null && s.lng != null)

  // 動態載入 Leaflet（避免打包體積）
  useEffect(() => {
    if (window.L) { setReady(true); return }
    const css = document.createElement('link')
    css.rel = 'stylesheet'
    css.href = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css'
    document.head.appendChild(css)
    const s = document.createElement('script')
    s.src = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js'
    s.onload = () => setReady(true)
    s.onerror = () => toast('地圖載入失敗（要上網）')
    document.head.appendChild(s)
  }, [])

  useEffect(() => {
    if (!ready || !boxRef.current || mapRef.current) return
    const L = window.L
    const map = L.map(boxRef.current, { zoomControl: true, attributionControl: true })
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '© OpenStreetMap',
    }).addTo(map)
    // ⚠️ 起始視圖：有設定城市就飛去嗰度，冇就用預設（福岡）
    if (cities.length === 1) {
      map.setView([cities[0].lat, cities[0].lng], 12)
    } else if (cities.length > 1) {
      map.fitBounds(cities.map(c => [c.lat, c.lng]), { padding: [50, 50], maxZoom: 12 })
    } else {
      // ⚠️⚠️ 原本死寫福岡 —— 用戶開香港 trip 見到福岡地圖，
      //    以為我哋搞錯咗佢個行程。
      //
      //    而家：冇座標嘅時候**唔假設任何地方**，
      //    用一個中立嘅世界視角，並且顯示提示叫用戶設定城市。
      //    寧願乜都唔顯示，都唔好顯示一個錯嘅城市。
      map.setView([20, 0], 2)
    }
    mapRef.current = map
    layerRef.current = L.layerGroup().addTo(map)
    setTimeout(() => map.invalidateSize(), 120)
  }, [ready])

  useEffect(() => {
    if (!ready || !mapRef.current || !layerRef.current) return
    const L = window.L
    layerRef.current.clearLayers()
    if (pinned.length === 0) return

    pinned.forEach(it => {
      const icon = L.divIcon({
        className: '',
        html: `<div style="font-size:22px;line-height:1;filter:drop-shadow(0 0 6px #a855f7)">${iconFor(it)}</div>`,
        iconSize: [22, 22], iconAnchor: [11, 20],
      })
      L.marker([it.lat, it.lng], { icon })
        .addTo(layerRef.current)
        .bindPopup(`<b>${escapeHtml(it.name || '（未有名稱）')}</b><br>
          <span style="opacity:.75">${escapeHtml(it.location_display || '')}</span><br>
          <span style="opacity:.6;font-size:11px">信心 ${it.confidence}%</span>`)
        .on('click', () => setSel(it))
    })

    // ── 城市標記（比較大、有名字）──
    cities.forEach((c, i) => {
      const html = `<div style="
        display:flex;align-items:center;gap:5px;
        background:linear-gradient(100deg,#a855f7,#22d3ee);
        color:#0b0518;font-weight:900;font-size:11px;
        padding:4px 10px;border-radius:99px;white-space:nowrap;
        box-shadow:0 2px 10px rgba(168,85,247,.5);
        border:1px solid rgba(11,5,24,.35);
      ">📍 ${c.city}<span style="opacity:.65;font-weight:700">${c.days}日</span></div>`
      L.marker([c.lat, c.lng], {
        icon: L.divIcon({ className: '', html, iconSize: [0, 0], iconAnchor: [0, 0] }),
        zIndexOffset: 1000,
      }).addTo(layerRef.current)
        .bindPopup(`<b>📍 ${c.city}</b><br>
          <span style="opacity:.75">${c.days} 日</span>
          ${c.country ? `<br><span style="opacity:.6;font-size:11px">${c.country}</span>` : ''}`)
    })

    // ── 自動 fit：包括城市同景點 ──
    const all = [...cities.map(c => [c.lat, c.lng]), ...pinned.map(i => [i.lat, i.lng])]
    if (all.length === 1) {
      mapRef.current.setView(all[0], 13)
    } else if (all.length > 1) {
      mapRef.current.fitBounds(L.latLngBounds(all),
        { padding: [46, 46], maxZoom: cities.length && !pinned.length ? 13 : 15 })
    }
    setTimeout(() => mapRef.current?.invalidateSize(), 120)
  }, [ready, items, stops])

  async function vote(it) {
    try { await api.vote(it.id); await onRefresh() } catch (e) { toast(e.message) }
  }

  return (
    <div className="screen">
      <div className="h1">地圖</div>
      <div className="sub">
        {cities.length > 0 && (
          <span>{cities.map(c => `${c.city} ${c.days}日`).join(' → ')} · </span>
        )}
        {pinned.length} 個地方有座標（總共 {items.length} 個收藏）
      </div>

      {cities.length > 0 && (
        <div className="scroll-x" style={{ marginTop: 10 }}>
          {cities.map((c, i) => (
            <button key={c.city + i} className="chip"
              onClick={() => {
                if (mapRef.current) mapRef.current.setView([c.lat, c.lng], 13)
                setSel(null)
              }}>
              📍 {c.city}
            </button>
          ))}
          {pinned.length > 0 && (
            <button className="chip" onClick={() => {
              const L = window.L
              if (mapRef.current && L) {
                const all = [...cities.map(c => [c.lat, c.lng]), ...pinned.map(i => [i.lat, i.lng])]
                if (all.length) mapRef.current.fitBounds(L.latLngBounds(all), { padding: [46, 46], maxZoom: 15 })
              }
            }}>全部</button>
          )}
        </div>
      )}

      <div style={{ height: 12 }} />

      {!ready && <div className="card" style={{ textAlign: 'center' }}>地圖載入中…</div>}
      <div ref={boxRef} className="map wide" style={{ display: ready ? 'block' : 'none' }} />

      {pinned.length === 0 && ready && (
        <Empty icon="🗺" title="仲未有座標" hint="貼 Google Maps link 就會即刻出 pin" />
      )}

      {sel && (
        <div className="card glow" style={{ marginTop: 12 }}>
          <div className="row">
            <div style={{ minWidth: 0 }}>
              <div style={{ fontWeight: 900, fontSize: 14 }}>{iconFor(sel)} {sel.name || '（未有名稱）'}</div>
              <div className="sub">{(sel.location_path || []).join(' › ') || '未分類'}</div>
            </div>
            <span className={`conf ${confClass(sel.confidence)}`}>{sel.confidence}%</span>
          </div>
          {sel.address && <div className="sub" style={{ marginTop: 6 }}>{sel.address}</div>}
          <div style={{ display: 'flex', gap: 7, marginTop: 10 }}>
            <button className="btn sm" onClick={() => vote(sel)}>▲ 投票 {sel.votes || 0}</button>
            {sel.google_maps_url && (
              <a className="btn sm ghost" href={sel.google_maps_url} target="_blank" rel="noreferrer">開 Google Maps</a>
            )}
            <button className="btn sm ghost" onClick={() => setSel(null)}>關閉</button>
          </div>
        </div>
      )}
    </div>
  )
}

function escapeHtml(s) {
  return String(s || '').replace(/[&<>"']/g, c =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]))
}
