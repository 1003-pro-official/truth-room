# Railway 배포 — 진실의 방으로

> Streamlit + FastAPI 단일 Docker 이미지.  
> **본선 UI:** React (`web/game` 정적). Streamlit은 선택 백업.  
> UI 전환 이유: [README.md §5](../README.md).  
> Cloudflare Containers(Paid) 대신 **Railway** 권장 경로.

관련: [DEPLOY_CLOUDFLARE.md](DEPLOY_CLOUDFLARE.md) · [GETTING_STARTED.md](../GETTING_STARTED.md)

---

## 1. 아키텍처

```
Internet ──HTTPS──► Railway ($PORT)
                      │
              Container
         Streamlit :$PORT  (공개)
         FastAPI   :8000   (루프백, API_URL=http://127.0.0.1:8000)
```

---

## 2. 사전 준비

1. https://railway.app 가입 (GitHub 연동 권장)
2. 로컬(선택): `npm i -g @railway/cli` 또는 `npx @railway/cli`

---

## 3. 대시보드로 배포 (가장 단순)

1. [Railway New Project](https://railway.app/new) → **Deploy from GitHub repo**
2. `toryhyeon80/truth-room` 선택
3. Railway가 `Dockerfile` + `railway.toml` 자동 감지
4. **Variables** 에 추가:
   - `API_URL` = `http://127.0.0.1:8000`
   - `CORS_ALLOW_ALL` = `1`
   - `OPENAI_API_KEY` = (권장 · AutoGen 심문 ask 본선. 없으면 스텁 폴백)
5. **Settings → Networking → Generate Domain** (공개 URL)
6. Deploy 완료 후 접속 → **새 수사 개시**  
   **현 배포 URL:** https://web-production-072b8.up.railway.app  
   (신규 프로젝트는 `https://<project>.up.railway.app`)

첫 빌드는 pip 설치로 **수 분** 걸릴 수 있습니다.

---

## 4. CLI로 배포

```bash
cd truth-room
npx @railway/cli login
npx @railway/cli init          # 또는 link 기존 프로젝트
npx @railway/cli up            # Dockerfile 빌드·배포
npx @railway/cli domain        # 공개 도메인 발급
npx @railway/cli variables set CORS_ALLOW_ALL=1 API_URL=http://127.0.0.1:8000
# npx @railway/cli variables set OPENAI_API_KEY=sk-...
```

---

## 5. 로컬 검증 (배포 전)

```bash
docker compose up --build
# http://localhost:8080
```

---

## 6. 주의

| 항목 | 내용 |
| :--- | :--- |
| 세션 | 인메모리 — 재배포/슬립 시 세션 초기화 |
| 요금 | Hobby/Trial 한도 확인 · 데모 후 서비스 pause 가능 |
| `.env` | 레포에 커밋 금지 · Railway Variables 사용 |
| 포트 | Railway가 `PORT` 주입 — entrypoint가 자동 반영 |
| `/` vs `/game/` | `/` = 스크롤 인트로 · `/game/` = **React**. **F5 on `/game/` → `/`** (nginx HTML inject) |
| 에셋 | WebP 우선 (`assets/ui` · `suspects` · `intro` · `evidence_desk`) · `/assets/` 캐시 30d |

---

## 7. 파일

| 경로 | 역할 |
| :--- | :--- |
| `Dockerfile` | 앱 이미지 |
| `docker/entrypoint.sh` | API + Streamlit (`$PORT`) |
| `railway.toml` | Dockerfile 빌더 · healthcheck |
