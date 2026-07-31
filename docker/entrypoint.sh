#!/bin/sh
set -eu

cd /app

# Railway injects PORT; local/compose default 8080
PORT="${PORT:-8080}"
export PORT
export API_URL="${API_URL:-http://127.0.0.1:8000}"
export CORS_ALLOW_ALL="${CORS_ALLOW_ALL:-1}"

echo "[truth-room] starting FastAPI on 127.0.0.1:8000"
python3 -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 &
API_PID=$!
trap 'kill "$API_PID" 2>/dev/null || true' EXIT

# API 헬스 대기 (최대 ~90s)
i=0
while [ "$i" -lt 90 ]; do
  if curl -fsS http://127.0.0.1:8000/health >/dev/null 2>&1; then
    echo "[truth-room] API ready"
    break
  fi
  i=$((i + 1))
  sleep 1
done

echo "[truth-room] starting Streamlit on 0.0.0.0:${PORT} (API_URL=${API_URL})"
exec python3 -m streamlit run app.py \
  --server.port="${PORT}" \
  --server.address=0.0.0.0 \
  --server.headless=true \
  --browser.gatherUsageStats=false
