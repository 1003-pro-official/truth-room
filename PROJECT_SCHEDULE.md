# 프로젝트 일정표 (PROJECT_SCHEDULE)

> **용도:** 발표일이 정해져 있을 때 **역산** 일정 · 마일스톤 · Code Freeze  
> **프로젝트:** 방구석 프로파일러: 진실의 방으로  
> **체크리스트:** [TEAM_KICKOFF_CHECKLIST.md](TEAM_KICKOFF_CHECKLIST.md) · [TRAINING_CHECKLIST.md](TRAINING_CHECKLIST.md)  
> **발표 초안:** [PRESENTATION.md](PRESENTATION.md)  
> **역할:** [docs/ROLES.md](docs/ROLES.md)  
> **마일스톤 매핑:** Data(ingest) → RAG → Agent → Eval → API → Demo  
> **현황 (2026-07-31):** RAG Hit@5 4/4 · LangGraph smoke · AutoGen ask · RAGAS n=30 · LoRA≤3B · Railway 라이브 · **남은 핵심은 Golden Route 데모 연출**

---

## DLthon2 — 완성 전략 · 4일 마일스톤

> **변동 가능:** 아래 Day 1~4 Task는 팀 상황·진도에 따라 조정한다.  
> 변경 시 본 표와 [TEAM_KICKOFF_CHECKLIST.md](TEAM_KICKOFF_CHECKLIST.md)를 같이 고치고, 전원에게 공유한다.

### 프로젝트 완성을 위한 전략

| 전략 | 내용 |
| :--- | :--- |
| **문서 중심 몹(Mob) 기획** | Day 1에 환경 세팅으로 시간을 뺏기지 않도록, 화이트보드·Notion으로 **세계관·시나리오·가짜 알리바이·증거 원문**을 전원 동시 설계한다. |
| **단계별 애자일 개발** | 먼저 **Backend(상태머신/API) ↔ Frontend(Streamlit)** 뼈대(mock)를 연결한 뒤, **RAG · 상세 AI 프롬프트**를 얹어 빠르고 안정적인 데모를 만든다. |

### DLthon2 기간 내 마일스톤 (초안 · 변경 가능)

| 구분 | 기간 | 상세 Task | 주 담당 (참고) | [ ] |
| :--- | :--- | :--- | :--- | :---: |
| **기획 / 데이터** | **Day 1** | 세계관·용의자 3 페르소나 기획 완료 · Smoking Gun(결정적 증거) 시나리오 확정 · 메신저/법인카드 등 가짜 데이터 대량 생성·정제 | 최병철 · 박정우 | |
| **코어 조립** | **Day 2** | RAG 파이프라인 구축·검색 테스트 · 상태머신(스트레스·증거) 흐름 뼈대 · 페르소나 시스템 프롬프트 1차 | 이근목 · 최승현 · 박정우 | |
| **통합 / 디버깅** | **Day 3** | Streamlit ↔ Backend(API/RAG/Agent) 연동 · 핑퐁 대화·프롬프트 미세조정 · 예외·로딩 | 천세문 · 전원 | |
| **QA / 폴리싱** | **Day 4** | 전원 플레이어 QA · 발표용 Golden Route(항상 성공하는 데모 루트) 준비 · PPT 확정·데모 리허설 | 천세문 · 최승현 · 전원 | |

**Day ↔ 레포 Phase 대략 매핑** (조정 시 함께 갱신)

| DLthon Day | CLAUDE Phase | 게이트 산출물 예 |
| :--- | :--- | :--- |
| Day 1 | 0 · 1a | `case_01` · personas · `data/raw/` · ingest |
| Day 2 | 1b · 1c · 1d | `runs/rag/` · `agent_graph --smoke` · eval 초안 |
| Day 3 | 2 · 3 | FastAPI session · Streamlit API only |
| Day 4 | 제출 · 발표 | README 메트릭 · Golden Route · 리허설 |

---

## 발표 역산 (발표일이 따로 있을 때)

| D-day | 날짜 (기입) | 이 날 하는 일 | 이 날 하지 말 것 |
| :---: | :--- | :--- | :--- |
| **D-3** | | **Code Freeze** — API·RAG/Agent 요약·README·PRT 초안 | 새 EXP · 대규모 리팩터 |
| **D-2** | | 발표 자료 · Golden Route 캡처 · [PRESENTATION.md](PRESENTATION.md) | 구조 변경 |
| **D-1** | | 전원 리허설 · Live Demo 2~3회 | README 대폭 수정 |
| **D-0** | | 발표 · Q&A | — |

| 항목 | 값 |
| :--- | :--- |
| **발표일 (D-0)** | `YYYY-MM-DD` |
| 발표 시간 / 장소 | |
| 발표 분량 | ___ 분 |

### D-3 Code Freeze 체크

- [ ] `python3 repro_manifest.py` → `runs/reproducibility_manifest.yaml`
- [ ] `runs/rag/index/` · `runs/rag/exp_*/` · `runs/agent/` · `runs/eval/`
- [ ] `README.md` 메트릭 표 기입
- [ ] `docs/PEER_REVIEW.md` 초안
- [ ] `python3 -m pytest tests/smoke -q` 녹색 (API 기동)
- [ ] Streamlit → API Golden Route 동작

### D-2 · D-1

- [ ] 슬라이드 확정 · 역할별 멘트
- [ ] 타임 리허설 · 데모 PC/네트워크 점검

---

## 일정 지연 시

| 상황 | 줄일 것 | 지키는 것 |
| :--- | :--- | :--- |
| RAG 실험 부족 | Advanced 실험 횟수 | Baseline + Advanced 1회 비교 |
| UI 미완 | 화려한 레이아웃 | API only · Golden Route 완주 |
| 문서 부족 | 장문 회고 | README + PRT 초안 |
| **절대 밀지 말 것** | — | **DLthon Day 산출물 · D-3 Freeze · D-1 리허설** |

---

## 관련 문서

| 문서 | 용도 |
| :--- | :--- |
| [TEAM_KICKOFF_CHECKLIST.md](TEAM_KICKOFF_CHECKLIST.md) | Phase별 할 일 |
| [TRAINING_CHECKLIST.md](TRAINING_CHECKLIST.md) | RAG/Agent 실험 체크 |
| [docs/ROLES.md](docs/ROLES.md) | 역할 |
| [PRESENTATION.md](PRESENTATION.md) | 슬라이드 원본 |
| [docs/PEER_REVIEW.md](docs/PEER_REVIEW.md) | PRT |
