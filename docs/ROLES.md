# 팀 역할 분담 (Roles) — 진실의 방으로

> **역할 원본.** Harness Agent는 `CLAUDE.md`의 Phase 게이트와 함께 본 문서를 따릅니다.

---

## 역할 요약

| 역할 | 담당 | 주요 경로 | 실행 환경 |
| :--- | :--- | :--- | :--- |
| **Scenario / Prompt** | 사건·페르소나·자백 조건 | `data/scenarios/`, `data/personas/` | OS 무관 |
| **RAG / Data** | 증거 코퍼스·인덱싱·검색·평가셋 · Function Calling | `data/raw/`, `lib/`, `ingest.py`, `build_index.py`, `rag_pipeline.py`, `evaluate.py` | 로컬·Colab |
| **Agent / LangGraph-style** | 심문 상태머신·압력·툴 연쇄 · AutoGen ask | `agent_graph.py`, `lib/autogen_runtime.py`, `configs/agent.yaml` | 로컬 (API 키) |
| **Service / Demo** | API·UI·데모 | `backend/`, `app.py`, `configs/api.yaml` | 데모 PC |
| **PM / Docs** (선택) | 리포트·발표·PRT | `README.md`, `PRESENTATION.md`, `docs/PEER_REVIEW.md` | — |

> **팀원 → main:** [INTEGRATION.md](INTEGRATION.md) · **CI:** `.github/workflows/smoke.yml`

---

## 담당자 기입 (kickoff)

| 역할 (레포) | 담당자 | 발표 역할 | GitHub | OS · 비고 |
| :--- | :--- | :--- | :--- | :--- |
| **Agent / LangGraph** · PM | 최승현 (팀장) | 아키텍처 · LangGraph 상태/노드 · 에이전트 연결 | [@toryhyeon80](https://github.com/toryhyeon80) | 레포 owner |
| **Scenario** (세계관·증거 원문) | 최병철 | 시나리오 기획 · 알리바이/모순 · RAG 원천 데이터 생성 | [@choi0310](https://github.com/choi0310) | `data/scenarios/`, `data/raw/` |
| **Prompt** (페르소나) | 박성우 | 용의자 3 + 조수 프롬프트 · 스트레스별 대사 | [@parkjw8](https://github.com/parkjw8) | `data/personas/`, `gm_system_prompt` |
| **RAG / Data** · Tools | 이근목 | Vector DB · Retrieval 최적화 · Function Calling | [@snarmse](https://github.com/snarmse) | `ingest`·`build_index`·`rag_pipeline`·`lib/` |
| **Service / Demo** · QA | 천세문 | Streamlit 심문 UI · API 연동 · 데모·QA | [@1003-pro-official](https://github.com/1003-pro-official) | `app.py`, `backend/` |

> **초대 상태 (2026-07-31):** 전원 GitHub ID 확인 · collaborator(write) 초대 발송. 각자 메일/알림에서 수락 필요.  
> [.github/CODEOWNERS](../.github/CODEOWNERS) 역할별 리뷰어 반영.  
> 인원 5명 기준: Scenario와 Prompt를 분리. 발표의「RAG 데이터 설계」는 최병철(원문) + 이근목(인덱싱/검색)으로 핸드오프.

---

## Scenario / Prompt

**목표:** 일관된 사건·알리바이·자백 조건

| 작업 | 산출물 |
| :--- | :--- |
| 사건 설계 | `data/scenarios/case_01.yaml` |
| 페르소나 3 | `data/personas/suspect_*.yaml` |
| 승패 조건 | `win_condition` · `leak_threshold` |

**PR 전:** 범인 스포일러가 API 기본 응답에 없는지 · 증거 ID와 시나리오 링크 일치

---

## RAG / Data

**목표:** 재현 가능한 코퍼스 · Baseline vs Advanced 비교

| 작업 | 산출물 | 스크립트 |
| :--- | :--- | :--- |
| Ingest | `data/processed/chunks.jsonl`, `runs/ingest/` | `ingest.py` |
| Index | **`runs/rag/index/`** (로컬 Hybrid · `vectors.json`) | `build_index.py` |
| EXP | `runs/rag/exp_*/` | `rag_pipeline.py` |
| Eval | `runs/eval/` | `evaluate.py` |
| Tools | `data/tools/*.yaml`, `lib/tools.py` | API `/tool` |

**PR 전:** `configs/rag.yaml`만 사용 · 메트릭 표 README 반영 · 평가셋 오염 금지

---

## Agent / LangGraph-style

**목표:** 심문 → 검색 → 툴 → 압박 → 엔딩. 온라인 ask는 AutoGen GroupChat, 오프라인 smoke는 `agent_graph.py`.

| 작업 | 산출물 |
| :--- | :--- |
| 그래프 | `agent_graph.py` · `runs/agent/` |
| AutoGen ask | `lib/autogen_runtime.py` · `scripts/smoke_autogen_ask.py` |
| 스모크 | `agent_graph.py --smoke` · `scripts/smoke_autogen_ask.py` |

**Handoff → Service:** 세션 상태 스키마 · 툴 입출력 JSON을 API PR에 링크

---

## Service / Demo

**목표:** 게임 API 단일 경로 +「진실의 방」UI

| 작업 | 산출물 | 실행 |
| :--- | :--- | :--- |
| REST | `/api/v1/session*` | `uvicorn backend.main:app --port 8000` |
| Demo | Streamlit → API only | `streamlit run app.py` |

**PR 전:** Swagger `/docs` · UI에서 LLM 직접 호출 없음 · 5분 데모 스크립트

---

## 발표 멘트 (한 줄)

| 역할 | 예시 |
| :--- | :--- |
| Scenario | 「용의자 3 · 핵심 증거 4 ID(카드·슬랙·출입·네트워크) · 자백 임계값」 |
| RAG | 「Baseline vs Hybrid/RRF+rerank, Faithfulness로 비교」 |
| Agent | 「LangGraph-style 상태머신으로 심문-증거-툴-대질 루프」 |
| Service | 「FastAPI 세션 + Streamlit 진실의 방 데모」 |

---

## Only Me 방지

| 안티패턴 | 대응 |
| :--- | :--- |
| Agent/RAG 1인 독점 | EXP마다 PR + 다른 역할 리뷰 |
| 노트북만 존재 | 정본은 `.py` + yaml |
| UI에서 모델 직결 | API 우회 금지 |
