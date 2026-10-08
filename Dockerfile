# ⚠️⚠️ Wander —— 單一容器（後端 serve 前端 build 出嚟嘅檔案）
#
#   為咩要呢個：Fly.io / Render / Railway 之類嘅 host 都食 Dockerfile。
#   ⚠️ 冇 Dockerfile 就得自己寫 build script → 好易漏 build 前端。

# ── ① 砌前端 ──
FROM node:22-slim AS web
WORKDIR /w
COPY web/package*.json ./
# ⚠️ 用 `npm ci`（要 package-lock.json）而唔係 `install` ——
#    保證 build 出嚟嘅嘢同你本機一樣。
RUN npm ci
COPY web/ ./
RUN npm run build

# ── ② 跑後端 ──
FROM python:3.12-slim
WORKDIR /app

# ⚠️ 系統依賴：
#    libgl1 / libglib2.0-0 → OpenCV（QR 解碼）需要
#    (唔裝嘅話 `import cv2` 會爆，QR 掃描功能死)
RUN apt-get update && apt-get install -y --no-install-recommends \
      libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY server/requirements.txt /app/server/
RUN pip install --no-cache-dir -r /app/server/requirements.txt

COPY engine/ /app/engine/
COPY server/ /app/server/
# ⚠️ 前端 build 出嚟嘅嘢一定要 copy —— 後端就係 serve 佢
COPY --from=web /w/dist /app/web/dist
COPY run.sh /app/

# ⚠️⚠️ 資料庫要放喺**可以寫**嘅地方，而且**唔可以**包入 image。
#    用 volume mount（見 fly.toml / render.yaml）。
ENV WANDER_DB=/data/wander.db
RUN mkdir -p /data

# ⚠️ 大部分 host 用 $PORT
ENV WANDER_PORT=8787
EXPOSE 8787

# ⚠️⚠️ 一定要 `--host 0.0.0.0` ——
#    預設綁 127.0.0.1 嘅話外面連唔到（容器外）。
WORKDIR /app/server
CMD ["python", "-m", "app"]
