# 팀 프로젝트 Kickoff · 제출 마스터 체크리스트

> 일정: [PROJECT_SCHEDULE.md](PROJECT_SCHEDULE.md) · 역할: [docs/ROLES.md](docs/ROLES.md)  
> **DLthon2:** [PROJECT_SCHEDULE.md § DLthon2](PROJECT_SCHEDULE.md#dlthon2--완성-전략--4일-마일스톤) — Day 1~4 Task는 **변동 가능**

---

## 발표일 · 일정 (Day 0)

- [ ] **발표일 (D-0):** `YYYY-MM-DD`
- [ ] [PROJECT_SCHEDULE.md](PROJECT_SCHEDULE.md) 날짜 열 작성
- [ ] DLthon2 Day 1~4 마일스톤 합의 (변경 시 일정표 갱신)
- [ ] 합의: **D-3 Code Freeze** · **D-2 자료** · **D-1 연습** (발표 역산이 있을 때)

---

## Phase 0 — 레포 · 팀

- [ ] GitHub 레포 push (`truth-room`)
- [ ] [docs/ROLES.md](docs/ROLES.md) 담당 · GitHub ID
- [ ] `cp .env.example .env` · OPENAI_API_KEY
- [ ] `configs/*.example` → `configs/*.yaml`
- [ ] `.github/CODEOWNERS` 갱신
- [ ] `main` PR 필수 · Smoke CI 녹색
- [ ] [AI_CONVENTION.md](AI_CONVENTION.md) · [TECH_SPEC.md](TECH_SPEC.md) 팀 리뷰

---

## Phase 1a — Data / Scenario

- [ ] `case_01` 시나리오 · 용의자 3 페르소나
- [ ] raw 증거 샘플 (messenger / logs / corporate_card / **network**)
- [ ] `data/tools/` CCTV·포렌식 페이로드 (해당 시)
- [ ] `python3 ingest.py` → `runs/ingest/` · `data/processed/chunks.jsonl`
- [ ] Data PR merge

---

## Phase 1b — RAG

- [ ] `python3 build_index.py`
- [ ] Baseline `rag_pipeline.py --mode baseline`
- [ ] Advanced (hybrid/RRF 또는 Self-RAG) 1회 이상
- [ ] README 비교 표 초안
- [ ] RAG PR merge

---

## Phase 1c — Agent

- [ ] LangGraph 노드 연결 (심문·검색·대질·엔딩)
- [ ] `python3 agent_graph.py --smoke`
- [ ] Agent PR merge

---

## Phase 1d — Eval

- [ ] `python3 evaluate.py` (RAGAS 또는 루브릭)
- [ ] 데모 스크립트 완주 테스트
- [ ] Eval PR merge

---

## Phase 2 — API

- [ ] session / ask / search / accuse
- [ ] Swagger `/docs` 확인
- [ ] `pytest tests/smoke`

---

## Phase 3 — Demo

- [ ] Streamlit「진실의 방」· API only
- [ ] 5분 데모 리허설

---

## 제출

- [ ] README 메트릭 채움
- [ ] [docs/PEER_REVIEW.md](docs/PEER_REVIEW.md) → 과제 경로 복사
- [ ] [PRESENTATION.md](PRESENTATION.md) 슬라이드화
- [ ] D-3 Freeze
