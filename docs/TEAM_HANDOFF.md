# 팀 핸드오프 — 지금까지 구현 · 코드 보는 법

> **대상:** collaborator 전원 (`parkjw8` · `1003-pro-official` · `choi0310` · `snarmse` · owner `toryhyeon80`)  
> **레포:** https://github.com/toryhyeon80/truth-room  
> **목적:** 각자 PC에서 clone 한 뒤, **어디를 보면 되는지** · **무엇이 이미 되는지** 를 빠르게 파악

관련: [GETTING_STARTED.md](../GETTING_STARTED.md) · [ROLES.md](ROLES.md) · [INTEGRATION.md](INTEGRATION.md) · [GAME_RULES.md](GAME_RULES.md)

---

## 1. 5분 안에 코드 보기

```bash
git clone https://github.com/toryhyeon80/truth-room.git
cd truth-room
git pull origin main
```

| 보고 싶은 것 | 열 파일 |
| :--- | :--- |
| 사건·승패 | `data/scenarios/case_01.yaml` |
| 용의자 페르소나·공개 프로필 | `data/personas/suspect_*.yaml` |
| 게임 룰 (3-Out·스태미나·조합 지목) | `docs/GAME_RULES.md` · `lib/game_rules.py` |
| API 세션/심문/검색/지목/프로필 | `backend/main.py` · `backend/game_engine.py` |
| Streamlit UI (초상·인벤·프로필 팝업·타이머) | `app.py` |
| API 계약 | `TECH_SPEC.md` §4 |
| 역할·GitHub ID | `docs/ROLES.md` |

Swagger로 API 목록: `uvicorn` 기동 후 http://localhost:8000/docs

---

## 2. 로컬에서 데모 켜기 (최소)

```bash
cp .env.example .env   # OPENAI_API_KEY 등 — .env 는 절대 커밋 금지
pip install -r requirements.txt -r requirements-llm.txt
pip install streamlit

# 터미널 1
python3 -m uvicorn backend.main:app --host 127.0.0.1 --port 8000

# 터미널 2
python3 -m streamlit run app.py
```

1. 사이드바 **새 수사 개시**
2. 용의자 ○/● 선택 → **심문** / **증거 수색** / **최종 지목**
3. **프로필** → 전신·페르소나·사건개요 (열리면 타이머 일시정지)

인덱스/RAG까지 돌리려면: [GETTING_STARTED.md](../GETTING_STARTED.md) 의 `ingest` → `build_index` → `rag_pipeline`

---

## 3. 지금까지 main에 들어간 것 (요약)

| 영역 | 상태 | 핵심 경로 |
| :--- | :---: | :--- |
| 샘플 시나리오 · 페르소나 3 · raw 코퍼스 | ✅ | `data/` |
| 게임 룰 문서 · stamina · 조합 지목(용의자+증거 2) | ✅ | `docs/GAME_RULES.md`, `lib/game_rules.py` |
| FastAPI 세션 / ask / search / tool / accuse / pass_turn | ✅ | `backend/` |
| 공개 프로필 · 사건개요 API | ✅ | `GET .../suspects/{id}/profile`, `GET .../case` |
| Streamlit: 초상 선택 · 인벤 · 단서 · 타임어택 · 프로필 dialog | ✅ | `app.py`, `assets/suspects/` |
| 프로필 열 때 타이머 pause / 닫으면 resume | ✅ | `app.py` (`_pause_timer` / `on_dismiss`) |
| Smoke 테스트 | ✅ | `tests/smoke/` |
| RAG baseline/advanced · Hit@5 **4/4** · soft routing · eval/RAGAS · 그래프 | ✅ | `runs/rag/` · `runs/eval/` · `report/assets/` · `scripts/plot_metrics.py` |
| **LangGraph** StateGraph smoke | ✅ | `lib/langgraph_runtime.py` · `agent_graph.py --smoke` |
| **AutoGen** ask 본선 | ✅ | `lib/autogen_runtime.py` · `scripts/smoke_autogen_ask.py` |
| 로컬 LoRA ladder (≤3B) · 7B memory_limit | ✅ | `runs/sft/local_lora_qwen*` |
| GM LLM 알리바이 판정 · Judge | ✅/⏳ | 로컬 판정 + 프롬프트 · live LLM 고도화는 선택 |

최근 커밋 예:

- `31b048e` — 게임 룰 · stamina/combo accuse · 수사 UI
- `697708c` — 프로필 dossier · 전신 에셋 · 타이머 pause

---

## 4. 역할별로 “내 코드” 어디?

| 담당 | GitHub | 주로 보는/고치는 곳 | 브랜치 예 |
| :--- | :--- | :--- | :--- |
| 최승현 (Agent·PM) | `toryhyeon80` | `agent_graph.py`, `lib/langgraph_runtime.py`, `lib/autogen_runtime.py`, `configs/agent.yaml`, `backend/`, 문서 | `feature/agent-*` |
| 최병철 (Scenario) | `choi0310` | `data/scenarios/`, `data/raw/` | `feature/data-*` |
| 박성우 (Prompt) | `parkjw8` | `data/personas/`, 시스템 프롬프트 | `feature/data-*` |
| 이근목 (RAG·Tools) | `snarmse` | `ingest.py`, `build_index.py`, `rag_pipeline.py`, `lib/`, `evaluate.py` | `feature/rag-*` |
| 천세문 (Service·QA) | `1003-pro-official` | `app.py`, `backend/`, `configs/api.yaml` | `feature/service-*` |

> **안티패턴:** UI에서 LLM 직결 · `culprit_id` 클라이언트 노출 · `.env` 커밋 · `main` 직푸시  
> 상세: [ANTIPATTERNS.md](ANTIPATTERNS.md)

---

## 5. 팀원 → main 합류 (필수)

```bash
git checkout main && git pull origin main
git checkout -b feature/<role>-<topic>
# 작업…
git add <변경 파일만>
git commit -m "feat(…): …"
git push -u origin HEAD
# GitHub에서 Pull Request → 리뷰 → merge
```

정본: [INTEGRATION.md](INTEGRATION.md)

같은 레포에 push/PR 하면 **owner 레포(`toryhyeon80/truth-room`)에 그대로 반영**됩니다. fork 불필요.

---

## 6. API 한눈에 (구현된 것)

| Method | Path | 설명 |
| :--- | :--- | :--- |
| `POST` | `/api/v1/session` | 새 수사 |
| `GET` | `/api/v1/session/{id}` | 공개 상태 |
| `POST` | `/api/v1/session/{id}/ask` | 심문 |
| `POST` | `/api/v1/session/{id}/search` | 증거 RAG |
| `POST` | `/api/v1/session/{id}/tool` | CCTV / forensic |
| `POST` | `/api/v1/session/{id}/pass_turn` | 타임아웃 턴 패스 |
| `POST` | `/api/v1/session/{id}/accuse` | 조합 지목 `{suspect_id, evidence_ids[2]}` |
| `GET` | `/api/v1/session/{id}/suspects/{sid}/profile` | 공개 프로필 (+ 사건개요) |
| `GET` | `/api/v1/session/{id}/case` | 공개 사건개요 |

`secrets` · `role` · `culprit_id` 는 프로필/상태 API에 **안 내려갑니다**.

---

## 7. 다음에 손대기 좋은 것 (역할 힌트)

| 우선 | 내용 | 담당 힌트 |
| :--- | :--- | :--- |
| Golden Route UI 연출 · 5분 데모 리허설 | Streamlit · 라이브 URL | Service · PM |
| 페르소나·알리바이 대사 폴리싱 | `system_prompt` / mental_break | Prompt |
| PRT · 발표 슬라이드 확정 | `docs/PEER_REVIEW.md`, `PRESENTATION.md` | PM |
| (선택) 32GB+/QLoRA로 7B LoRA 재시도 | `scripts/local_lora_persona.py` | Agent |

질문·이슈는 GitHub Issues 또는 팀 채널에, 코드 변경은 **PR**로.

---

## 8. 클라우드 데모

- **라이브 (Railway):** https://web-production-072b8.up.railway.app
- 가이드: [DEPLOY_RAILWAY.md](DEPLOY_RAILWAY.md)
- Cloudflare Containers (Paid): [DEPLOY_CLOUDFLARE.md](DEPLOY_CLOUDFLARE.md)

