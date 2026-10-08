import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import { registerSW } from './lib/pwa'
import './styles.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
)

// PWA：註冊 service worker（離線支援 + 地圖圖磚快取）
// ⚠️ 只有 https 或 localhost 先註冊得到 → 手機連區網 IP 要「加到主畫面」
registerSW()
