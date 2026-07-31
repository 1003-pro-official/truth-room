# Railway · docker-compose · Cloudflare Containers
FROM python:3.11-slim-bookworm

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    API_URL=http://127.0.0.1:8000 \
    CORS_ALLOW_ALL=1 \
    PORT=8080 \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

RUN apt-get update && apt-get install -y --no-install-recommends \
      curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements-llm.txt ./
RUN pip install --upgrade pip \
 && pip install -r requirements.txt -r requirements-llm.txt \
 && pip install "streamlit>=1.40.0"

COPY . .
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh \
 && mkdir -p /app/runs

# Railway는 $PORT 주입 · 로컬 기본 8080
EXPOSE 8080

# HEALTHCHECK는 railway.toml healthcheckPath 사용 (Railway 빌더 호환)

CMD ["/entrypoint.sh"]
