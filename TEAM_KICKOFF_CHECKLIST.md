# 팀 프로젝트 Kickoff · 제출 마스터 체크리스트

> 일정: [PROJECT_SCHEDULE.md](PROJECT_SCHEDULE.md) · 역할: [docs/ROLES.md](docs/ROLES.md)  
> **DLthon2:** [PROJECT_SCHEDULE.md § DLthon2](PROJECT_SCHEDULE.md#dlthon2--완성-전략--4일-마일스톤) — Day 1~4 Task는 **변동 가능**

---

## 발표일 · 일정 (Day 0) — **확정**

- [x] **발표일 (D-0):** **2026-08-11 14:00**
- [x] **발표 준비 (D-1):** **2026-08-10**
- [x] **당일 오전 리허설:** **2026-08-11 오전**
- [x] [PROJECT_SCHEDULE.md](PROJECT_SCHEDULE.md) — **확정 주간** (8/4~7 수집 · 8/7 LoRA · **8/9 시연 녹화** · 8/10 발표자·슬라이드 · 8/11 리허설 · **14:00 발표 15분**)
- [x] 수집: `scripts/auto_ask_collect.py` · `data/sft/auto_ask_questions.yaml` · **45+45+45+30 ≈165턴 · 변형 ON**
- [x] 8/4~7 일일 `auto_ask_collect` 실행 · 8/7 export+3B LoRA 완주 (**본선 ask 미적용**)
- [ ] **8/9** 시연 녹화 (발표 컷 B)
- [ ] D-1(8/10) 발표자·슬라이드 · D-0 오전(8/11) 리허설 · **14:00 발표**

---

## Phase 0 — 레포 · 팀

- [x] GitHub 레포 push (`truth-room`)
- [x] [docs/ROLES.md](docs/ROLES.md) 담당 · GitHub ID
- [x] `cp .env.example .env` · OPENAI_API_KEY
- [x] `configs/*.example` → `configs/*.yaml`
- [x] `.github/CODEOWNERS` 갱신
- [x] `main` PR 필수 · Smoke CI 녹색
- [x] [AI_CONVENTION.md](AI_CONVENTION.md) · [TECH_SPEC.md](TECH_SPEC.md) 팀 리뷰

---

## Phase 1a — Data / Scenario

- [x] `case_01` 시나리오 · 용의자 3 페르소나
- [x] raw 증거 샘플 (messenger / logs / corporate_card / **network**)
- [x] `data/tools/` CCTV·포렌식 페이로드 (해당 시)
- [x] `python3 ingest.py` → `runs/ingest/` · `data/processed/chunks.jsonl`
- [x] Data PR merge

---

## Phase 1b — RAG

- [x] `python3 build_index.py`
- [x] Baseline `rag_pipeline.py --mode baseline`
- [x] Advanced (hybrid/RRF 또는 Self-RAG) 1회 이상
- [x] README 비교 표 초안
- [x] RAG PR merge

---

## Phase 1c — Agent

- [x] LangGraph StateGraph (`lib/langgraph_runtime.py`) · 심문·검색·툴·대질·엔딩
- [x] `python3 agent_graph.py --smoke` (backend=`langgraph`)
- [x] AutoGen ask (`lib/autogen_runtime.py` · `scripts/smoke_autogen_ask.py`)
- [x] Agent PR merge

---

## Phase 1d — Eval

- [x] `python3 evaluate.py` (로컬 Faith)
- [x] `python3 scripts/eval_ragas.py` (RAGAS py3.12 · n=30)
- [x] `python3 scripts/plot_metrics.py` → `report/assets/`
- [x] 데모 스크립트 완주 테스트 (Golden Route UI)
- [x] Eval 수치 README 반영

---

## Phase 2 — API

- [x] session / ask / search / accuse
- [x] Swagger `/docs` 확인
- [x] `pytest tests/smoke`

---

## Phase 3 — Demo

- [x] **React**「진실의 방」· API only · Streamlit 백업
- [x] Railway 라이브 · 인트로(`/`) → 게임(`/game/`) · 새로고침 시 인트로 복귀
- [ ] 5분 데모 **발표** 리허설 (슬라이드·멘트)

---

## 제출

- [x] README 메트릭 채움
- [ ] [docs/PEER_REVIEW.md](docs/PEER_REVIEW.md) → 과제 경로 복사
- [ ] [PRESENTATION.md](PRESENTATION.md) 슬라이드화
- [ ] D-3 Freeze
