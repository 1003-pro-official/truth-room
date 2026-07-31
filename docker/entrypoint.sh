#!/bin/sh
set -eu

cd /app

# Railway injects PORT; nginx listens on 8080 by default then we rewrite config if needed
PORT="${PORT:-8080}"
export PORT
export API_URL="${API_URL:-http://127.0.0.1:8000}"
# 브라우저용 정적 에셋 (루프백 API_URL과 분리 — nginx /assets)
export ASSET_PUBLIC_URL="${ASSET_PUBLIC_URL:-/assets}"
export CORS_ALLOW_ALL="${CORS_ALLOW_ALL:-1}"

# 이미지에 runs/·processed 미포함 → 최초 기동 시 raw에서 인덱스 구축
if [ ! -f runs/rag/index/vectors.json ] || [ ! -f data/processed/chunks.jsonl ]; then
  echo "[truth-room] building RAG index from data/raw (ingest + build_index)"
  python3 ingest.py
  python3 build_index.py
fi

# nginx listen 포트를 $PORT 에 맞춤
sed "s/listen       8080;/listen       ${PORT};/" /app/docker/nginx.conf > /tmp/nginx.conf

echo "[truth-room] starting FastAPI on 127.0.0.1:8000"
python3 -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 &
API_PID=$!

echo "[truth-room] starting Streamlit on 127.0.0.1:8501 (baseUrlPath=game)"
python3 -m streamlit run app.py \
  --server.port=8501 \
  --server.address=127.0.0.1 \
  --server.baseUrlPath=game \
  --server.headless=true \
  --browser.gatherUsageStats=false &
ST_PID=$!

cleanup() {
  kill "$API_PID" "$ST_PID" 2>/dev/null || true
}
trap cleanup EXIT

# API 헬스 대기
i=0
while [ "$i" -lt 90 ]; do
  if curl -fsS http://127.0.0.1:8000/health >/dev/null 2>&1; then
    echo "[truth-room] API ready"
    break
  fi
  i=$((i + 1))
  sleep 1
done

echo "[truth-room] starting nginx on 0.0.0.0:${PORT}"
exec nginx -c /tmp/nginx.conf -g "daemon off;"
