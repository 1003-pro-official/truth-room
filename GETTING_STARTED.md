# 시작 가이드 (Getting Started) — 진실의 방으로

> **온보딩 · 실행 명령** 문서입니다.  
> **결과 분석 리포트(GitHub 메인):** [README.md](README.md)  
> **계획·기술:** [MASTER_PLAN.md](MASTER_PLAN.md) · [TECH_SPEC.md](TECH_SPEC.md) · [ARCHITECTURE.md](ARCHITECTURE.md)

인터랙티브 텍스트 미스터리. 플레이어는 용의자 3명(김팀장·이대리·박신입)을 심문하고, 메신저·출입로그·법인카드·네트워크 증거를 Advanced RAG로 모으며, **공식 LangGraph** 상태머신(`lib/langgraph_runtime.py`)·**AutoGen** 심문(`lib/autogen_runtime.py`)·Function Calling으로 모순을 압박해 자백을 유도합니다.

**케이스:** `case_01` — 「진실의 방 — 100억의 야근자들」(Omega 가중치 유출)

```
심문 → 증거 수집(RAG / CCTV·포렌식 툴) → 압박/대질 → 지목/자백
```

---

## 0. 팀원이면 먼저

1. clone: `git clone https://github.com/toryhyeon80/truth-room.git`
2. **구현 현황·코드 맵:** [docs/TEAM_HANDOFF.md](docs/TEAM_HANDOFF.md)
3. 역할: [docs/ROLES.md](docs/ROLES.md) · PR 규칙: [docs/INTEGRATION.md](docs/INTEGRATION.md)

---

## 1. 빠른 시작

```bash
cd truth-room
cp .env.example .env          # OPENAI_API_KEY (AutoGen 심문 ask 본선)

pip install -r requirements.txt -r requirements-llm.txt

python3 ingest.py
python3 build_index.py
python3 rag_pipeline.py --mode baseline
python3 rag_pipeline.py --mode advanced
python3 agent_graph.py --smoke
python3 scripts/smoke_autogen_ask.py   # AutoGen 본선 ask 검증
python3 evaluate.py
python3 scripts/eval_ragas.py          # RAGAS · Python ≥3.10 · n=30 (선택)
python3 scripts/plot_metrics.py        # report/assets/ 그래프
python3 update_report.py          # runs/ → README.md 자동 반영
# Notion (선택): .env에 NOTION_TOKEN · NOTION_PAGE_ID
python3 update_notion.py
python3 -m uvicorn backend.main:app --port 8000
# 본선 UI: http://127.0.0.1:8000/ (인트로) · http://127.0.0.1:8000/game/ (React)
# 로컬 Vite 핫리로드(선택):
#   cd web/game && npm install && npm run dev  → http://127.0.0.1:5173/game/
```

**라이브 데모:** https://web-production-072b8.up.railway.app  
(`/` 인트로 브리핑 → `/game/` React 플레이 · `/game/` 새로고침 시 인트로로 복귀)

> **UI 전환:** 본선은 **React** (`web/game`). Streamlit `app.py`는 백업.  
> **이유:** Streamlit 한계(상태·다이얼로그·리렌더)로 **개발 중 오류가 반복**되어 본선 이전. 상세 [README.md §5](README.md) · [web/game/README.md](web/game/README.md).

---

## 1. 데이터 · 시나리오 경로

| 경로 | 내용 |
| :--- | :--- |
| `data/scenarios/` | 사건 YAML (승패 조건) |
| `data/personas/` | 용의자 페르소나 · 시스템 프롬프트 |
| `data/raw/messenger/` | 슬랙/메신저 |
| `data/raw/logs/` | 서버/출입 로그 |
| `data/raw/corporate_card/` | 법인카드 |
| `data/raw/network/` | Wi-Fi / 전송 로그 |
| `data/tools/` | CCTV · 포렌식 Function Calling 페이로드 |
| `data/processed/` | 청크 JSONL · eval 질문 |

스키마: [TECH_SPEC.md](TECH_SPEC.md) §2

---

## 2. 서비스 · 데모

| 구성 | 명령 | URL |
| :--- | :--- | :--- |
| API + 인트로 + React 빌드 | `python3 -m uvicorn backend.main:app --port 8000` | `/` 인트로 · `/game/` 플레이 · `/docs` |
| React 개발 서버 (선택) | `cd web/game && npm run dev` | http://127.0.0.1:5173/game/ |
| Streamlit 백업 (선택) | `python3 -m streamlit run app.py` | http://localhost:8501 |
| Docker/Railway | `docker compose up --build` | http://localhost:8080 (`/`→`/game/`) |

**단일 경로:** React(또는 Streamlit 백업) → FastAPI only ([docs/ANTIPATTERNS.md](docs/ANTIPATTERNS.md))  
**데모 게이트:** Phase 3 완료 — 심문 · 증거 책상 · 조합 지목 · Golden Route UI

**실서버 심문 로그 → 재학습:** 플레이 테스트 ask를 JSONL로 모아 말투 LoRA 후보로 쓴다.  
켜기: `CONVERSATION_LOG=1`. 안정장치·절차: [docs/CONVERSATION_LOG.md](docs/CONVERSATION_LOG.md)

**라이브 데모:** https://web-production-072b8.up.railway.app

---

## 3. 팀 · 일정

- **구현 현황·코드 맵 (팀원 필독):** [docs/TEAM_HANDOFF.md](docs/TEAM_HANDOFF.md)
- 역할: [docs/ROLES.md](docs/ROLES.md)
- Kickoff: [TEAM_KICKOFF_CHECKLIST.md](TEAM_KICKOFF_CHECKLIST.md)
- DLthon2 일정: [PROJECT_SCHEDULE.md](PROJECT_SCHEDULE.md)
- 발표: [PRESENTATION.md](PRESENTATION.md)
- PRT: [docs/PEER_REVIEW.md](docs/PEER_REVIEW.md)

---

## 4. 레포 구조 (요지)

```
truth-room/
├── README.md              # 결과 분석 리포트
├── GETTING_STARTED.md     # 본 문서
├── update_report.py       # runs/ → README.md
├── update_notion.py       # README.md → Notion (.env)
├── MASTER_PLAN.md · TECH_SPEC.md · AI_CONVENTION.md · CLAUDE.md
├── ingest.py · build_index.py · rag_pipeline.py · agent_graph.py · evaluate.py
├── lib/               # langgraph_runtime · autogen_runtime · rag_core · tools
├── backend/ · app.py      # app.py = Streamlit 백업
├── web/intro/ · web/game/ # 인트로 · React 본선 UI
├── configs/ · data/ · runs/ · report/assets/ · docs/ · notebooks/
└── .github/
```

### 리포트 · Notion · 메트릭 그래프

| 명령 | 역할 |
| :--- | :--- |
| `python3 update_report.py` | `runs/ingest` · `runs/rag/exp_*` · `runs/agent` · `runs/eval` → README `report:auto:*` |
| `python3 update_notion.py` | (기본) report 동기화 후 Notion 페이지 교체 |
| `python3 update_notion.py --dry-run` | API 없이 블록 수 확인 |
| `python3 update_notion.py --skip-report-sync` | README 원문만 업로드 |
| `python3 scripts/plot_metrics.py` | Hit@5·RAGAS·LoRA 등 → `report/assets/{eda,metrics}/` |
| `python3 scripts/eval_ragas.py` | RAGAS (Python ≥3.10 권장 · n=30) |

`.env`: `NOTION_TOKEN`, `NOTION_PAGE_ID` (Integration을 해당 페이지에 공유)