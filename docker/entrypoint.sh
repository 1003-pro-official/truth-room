#!/bin/sh
set -eu

cd /app

PORT="${PORT:-8080}"
export PORT
export API_URL="${API_URL:-http://127.0.0.1:8000}"
export ASSET_PUBLIC_URL="${ASSET_PUBLIC_URL:-/assets}"
export CORS_ALLOW_ALL="${CORS_ALLOW_ALL:-1}"

if [ ! -f runs/rag/index/vectors.json ] || [ ! -f data/processed/chunks.jsonl ]; then
  echo "[truth-room] building RAG index from data/raw (ingest + build_index)"
  python3 ingest.py
  python3 build_index.py
fi

sed "s/listen       8080;/listen       ${PORT};/" /app/docker/nginx.conf > /tmp/nginx.conf

echo "[truth-room] starting FastAPI on 127.0.0.1:8000"
python3 -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 &
API_PID=$!

# Streamlit은 /game-streamlit 백업용 (본편 /game 은 React dist)
if [ "${ENABLE_STREAMLIT_BACKUP:-0}" = "1" ]; then
  echo "[truth-room] starting Streamlit backup on 127.0.0.1:8501"
  python3 -m streamlit run app.py \
    --server.port=8501 \
    --server.address=127.0.0.1 \
    --server.headless=true \
    --browser.gatherUsageStats=false &
  ST_PID=$!
else
  ST_PID=""
fi

cleanup() {
  kill "$API_PID" ${ST_PID:+$ST_PID} 2>/dev/null || true
}
trap cleanup EXIT

i=0
while [ "$i" -lt 90 ]; do
  if curl -fsS http://127.0.0.1:8000/health >/dev/null 2>&1; then
    echo "[truth-room] API ready"
    break
  fi
  i=$((i + 1))
  sleep 1
done

if [ ! -f /app/web/game/dist/index.html ]; then
  echo "[truth-room] WARNING: web/game/dist missing — /game will 404"
fi

echo "[truth-room] starting nginx on 0.0.0.0:${PORT}"
exec nginx -c /tmp/nginx.conf -g "daemon off;"
