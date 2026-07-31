# Cloudflare Containers 배포 — 진실의 방으로

> **방식 B:** Docker 이미지 + Worker가 Container로 프록시 (Streamlit UI · 내부 FastAPI)  
> **레포 경로:** `Dockerfile` · `docker-compose.yml` · `deploy/cloudflare/`

관련: [GETTING_STARTED.md](../GETTING_STARTED.md) · [TEAM_HANDOFF.md](TEAM_HANDOFF.md)

---

## 1. 아키텍처

```
Browser ──HTTPS──► Cloudflare Worker
                      │  Container.fetch() (WebSocket 포함)
                      ▼
              Container (linux/amd64)
           ┌─────────────────────────┐
           │ Streamlit :8080 (공개)  │
           │ FastAPI   :8000 (루프백)│  API_URL=http://127.0.0.1:8000
           └─────────────────────────┘
```

- UI만 Worker URL로 노출. API는 컨테이너 안에서만 호출.
- Streamlit WebSocket → Worker는 **`container.fetch()`** 사용 (`containerFetch` 금지).

---

## 2. 사전 요구

| 항목 | 설명 |
| :--- | :--- |
| Docker Desktop | `docker info` 성공해야 함 (`linux/amd64` 빌드) |
| Node 18+ | `deploy/cloudflare` 에서 wrangler |
| Cloudflare 계정 | Workers Paid 플랜에 Containers 포함 여부 확인 |
| 시크릿 | `OPENAI_API_KEY` (선택 — 스텁 모드면 없어도 데모 가능) |

---

## 3. 로컬 컨테이너 검증 (Cloudflare 없이)

```bash
cd truth-room
# .env 에 OPENAI_API_KEY 등 (선택)
docker compose up --build
```

브라우저: http://localhost:8080 → **새 수사 개시**

중지: `Ctrl+C` 또는 `docker compose down`

---

## 4. Cloudflare에 배포

```bash
cd deploy/cloudflare
npm install
npx wrangler login

# (선택) LLM 키
npx wrangler secret put OPENAI_API_KEY

# Docker Desktop 실행 중인 상태에서
npx wrangler deploy
```

성공 시 URL 예: `https://truth-room.<YOUR_SUBDOMAIN>.workers.dev`

상태 확인:

```bash
npx wrangler containers list
npx wrangler tail
```

---

## 5. 팀원 공유

1. Worker URL을 팀 채널에 공유
2. 첫 요청은 **cold start 수 초** 걸릴 수 있음 (`sleepAfter = 30m`)
3. 인메모리 세션 → 컨테이너 sleep/재시작 시 세션 초기 (데모 중이면 새 수사 개시)

---

## 6. 주의 · 제한

| 항목 | 내용 |
| :--- | :--- |
| 요금 | Containers는 실행 시간 과금 — 데모 후 `wrangler delete` 또는 대시보드에서 중지 검토 |
| 디스크 | sleep 후 ephemeral — `runs/` 영속 없음 |
| 아키텍처 | **amd64 only** (Apple Silicon은 Docker가 amd64 에뮬레이션) |
| `.env` | 이미지에 넣지 말 것 — `wrangler secret` / compose `env_file` |
| `culprit_id` | 클라이언트 미노출 유지 |

---

## 7. 파일 맵

| 경로 | 역할 |
| :--- | :--- |
| `Dockerfile` | 앱 이미지 (Streamlit+API) |
| `docker/entrypoint.sh` | API → Streamlit 기동 |
| `docker-compose.yml` | 로컬 검증 |
| `deploy/cloudflare/wrangler.toml` | Container · DO 바인딩 |
| `deploy/cloudflare/src/index.ts` | Worker 라우팅 |

대시보드: Cloudflare → Workers & Pages → Containers
