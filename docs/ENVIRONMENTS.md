# 개발·실행 환경 (Environments) — 진실의 방으로

> **정본:** `.py` + `configs/*.yaml` · 비밀값 `.env`  
> **관련:** [WORKFLOW.md](WORKFLOW.md) · [ROLES.md](ROLES.md) · [../TECH_SPEC.md](../TECH_SPEC.md)

---

## 1. 팀원 환경 표 (kickoff)

| 팀원 | OS | 비고 |
| :--- | :--- | :--- |
| 최승현 | | Agent · API · [@toryhyeon80](https://github.com/toryhyeon80) |
| 최병철 | | Scenario · raw · [@choi0310](https://github.com/choi0310) |
| 박성우 | | Prompt · [@parkjw8](https://github.com/parkjw8) |
| 이근목 | | RAG · tools · [@snarmse](https://github.com/snarmse) |
| 천세문 | | Streamlit · 데모 · [@1003-pro-official](https://github.com/1003-pro-official) |

공통: Python 3.9+ · `pip install -r requirements.txt -r requirements-llm.txt` · UI는 `streamlit`

---

## 2. 최초 세팅 (macOS / Windows / Linux 공통)

```bash
cd truth-room
python3 -m venv .venv
# mac/linux: source .venv/bin/activate
# windows: .venv\Scripts\activate

pip install -r requirements.txt -r requirements-llm.txt
pip install streamlit
cp .env.example .env   # OPENAI_API_KEY
```

`streamlit` / `uvicorn`이 PATH에 없으면:

```bash
python3 -m uvicorn backend.main:app --port 8000
python3 -m streamlit run app.py
```

---

## 3. Colab (선택)

- 무거운 RAG 실험만 Colab에서 가능
- 코드 변경은 **GitHub PR**로만 합류 ([INTEGRATION.md](INTEGRATION.md))
- `localhost` API는 Colab에서 불가 → 데모는 로컬 또는 ngrok

---

## 3b. 클라우드 데모 (선택)

- **Railway (추천):** [DEPLOY_RAILWAY.md](DEPLOY_RAILWAY.md)
- Cloudflare Containers (Paid): [DEPLOY_CLOUDFLARE.md](DEPLOY_CLOUDFLARE.md)

```bash
docker compose up --build          # http://localhost:8080
# Railway: GitHub 연동 또는 npx @railway/cli up
```

---

## 4. 트러블슈팅

| 증상 | 조치 |
| :--- | :--- |
| `command not found: streamlit` | `python3 -m streamlit run app.py` |
| API Connection refused | `python3 -m uvicorn backend.main:app --port 8000` 후 UI 새로고침 |
| chunks 없음 | `python3 ingest.py` → `python3 build_index.py` |
| Docker missing | Docker Desktop 설치 후 `docker info` 확인 |
| Railway healthcheck 실패 | 로그에서 API/Streamlit 기동 확인 · `healthcheckTimeout` 증가 |
