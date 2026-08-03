# ARCHITECTURE — 팀 OS (진실의 방으로)

> **`README.md` = 결과 분석 리포트**  
> **실행 가이드** → [GETTING_STARTED.md](GETTING_STARTED.md)  
> **Peer Review** → [docs/PEER_REVIEW.md](docs/PEER_REVIEW.md)  
> **제품 계획** → [MASTER_PLAN.md](MASTER_PLAN.md) · **기술** → [TECH_SPEC.md](TECH_SPEC.md) · **코딩** → [AI_CONVENTION.md](AI_CONVENTION.md)  
> **문서 인덱스** → [docs/README.md](docs/README.md)

Interactive Mystery · Advanced RAG · Multi-Agent(AutoGen 심문) DLthon 프로젝트입니다.

---

## 포함 문서

| 경로 | 내용 |
| :--- | :--- |
| [docs/ROLES.md](docs/ROLES.md) | 5인 역할 |
| [docs/TEAM_HANDOFF.md](docs/TEAM_HANDOFF.md) | 팀원 온보딩 · 구현 현황 · 코드 맵 |
| [docs/CONVERSATION_LOG.md](docs/CONVERSATION_LOG.md) | 실서버 심문 로그 → 말투 재학습 · 안정장치 |
| [docs/ROADMAP_EXPANSION.md](docs/ROADMAP_EXPANSION.md) | 중장기: 진범 랜덤 · 용의자 확장 · 발표 Q&A |
| [TEAM_KICKOFF_CHECKLIST.md](TEAM_KICKOFF_CHECKLIST.md) | 시작~제출 체크리스트 |
| [PROJECT_SCHEDULE.md](PROJECT_SCHEDULE.md) | DLthon2 4일 + 발표 역산 |
| [PRESENTATION.md](PRESENTATION.md) | 발표 초안 |
| [docs/WORKFLOW.md](docs/WORKFLOW.md) | Git · 파이프라인 |
| [docs/INTEGRATION.md](docs/INTEGRATION.md) | PR → main |
| [docs/ENVIRONMENTS.md](docs/ENVIRONMENTS.md) | 로컬·Colab 환경 |
| [docs/ANTIPATTERNS.md](docs/ANTIPATTERNS.md) | Only Me · API 우회 등 |
| [docs/PEER_REVIEW.md](docs/PEER_REVIEW.md) | AIFFEL PRT |

---

## Phase 파이프라인

```
[Data]   scenarios · personas · raw(4소스) → ingest
            ↓
[RAG]    build_index (runs/rag/index) → baseline / advanced
            ↓
[Agent]  LangGraph StateGraph (`lib/langgraph_runtime.py`) + AutoGen ask + Function Calling
            ↓
[Eval]   evaluate (로컬 Faith) · RAGAS py3.12 n=30 · `scripts/plot_metrics.py`
            ↓
[Service] FastAPI 세션/search/tool/ask/accuse → **React UI** (`web/game`, API only) · Streamlit `app.py` 백업
            · Langfuse 관측 보드 (사이드바「관측」· opt-in)
            ↓
[Deploy] Railway `/` 인트로 · `/game` React 플레이
            ↓
[Docs]   README · PRT · 발표 · Notion
```

**UI:** Streamlit → React 전환. **직접 원인** — Streamlit 한계로 상태·다이얼로그·리렌더 **오류가 반복**. 부가 — 게임 UX 정밀도·API only. 상세 [README.md §5](README.md).  
**관측:** [docs/LANGFUSE.md](docs/LANGFUSE.md)

**라이브:** https://web-production-072b8.up.railway.app

---

## 폴더 구조

```
truth-room/
├── MASTER_PLAN.md · TECH_SPEC.md · AI_CONVENTION.md · CLAUDE.md
├── README.md · ARCHITECTURE.md
├── ingest.py · build_index.py · rag_pipeline.py · agent_graph.py · evaluate.py
├── lib/          # langgraph_runtime · autogen_runtime · rag_core · tools · …
├── backend/ · app.py
├── configs/ · data/ · runs/ · report/assets/ · docs/ · tests/smoke/ · notebooks/
└── .github/
```

---

## 새 팀원 온보딩

1. [TEAM_KICKOFF_CHECKLIST.md](TEAM_KICKOFF_CHECKLIST.md) Phase 0
2. `cp .env.example .env` · configs
3. [docs/ROLES.md](docs/ROLES.md) 본인 행 · GitHub ID
4. `python3 -m pytest tests/smoke -q` (API 기동 시)
5. 맡은 Phase 게이트 산출물만 PR

---

## Organization 체크리스트

- [x] GitHub 레포 push · 팀원 초대
- [ ] Branch protection on `main`
- [x] CODEOWNERS 실 ID
- [x] Smoke CI 녹색
- [x] Phase 0~3 개발 게이트 · Railway 라이브 데모
