# ARCHITECTURE — 팀 OS (진실의 방으로)

> **`README.md` = 결과 분석 리포트**  
> **실행 가이드** → [GETTING_STARTED.md](GETTING_STARTED.md)  
> **Peer Review** → [docs/PEER_REVIEW.md](docs/PEER_REVIEW.md)  
> **제품 계획** → [MASTER_PLAN.md](MASTER_PLAN.md) · **기술** → [TECH_SPEC.md](TECH_SPEC.md) · **코딩** → [AI_CONVENTION.md](AI_CONVENTION.md)  
> **문서 인덱스** → [docs/README.md](docs/README.md)

Interactive Mystery · Advanced RAG · Multi-Agent(역할 분리) DLthon 프로젝트입니다.

---

## 포함 문서

| 경로 | 내용 |
| :--- | :--- |
| [docs/ROLES.md](docs/ROLES.md) | 5인 역할 |
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
[Agent]  LangGraph-style 심문 루프 + Function Calling
            ↓
[Eval]   evaluate (Faithfulness · 루브릭)
            ↓
[Service] FastAPI 세션/search/tool → Streamlit UI
            ↓
[Docs]   README · PRT · 발표
```

---

## 폴더 구조

```
truth-room/
├── MASTER_PLAN.md · TECH_SPEC.md · AI_CONVENTION.md · CLAUDE.md
├── README.md · ARCHITECTURE.md
├── ingest.py · build_index.py · rag_pipeline.py · agent_graph.py · evaluate.py
├── lib/ · backend/ · app.py
├── configs/ · data/ · runs/ · docs/ · tests/smoke/ · notebooks/
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

- [ ] GitHub 레포 push · 팀원 초대
- [ ] Branch protection on `main`
- [ ] CODEOWNERS 실 ID
- [ ] Smoke CI 녹색
