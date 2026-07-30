# 방구석 프로파일러: 진실의 방으로

> **기술 리포트 (GitHub 메인)** — 데이터·RAG·Agent·평가 결과 분석  
> **실행·온보딩:** [GETTING_STARTED.md](GETTING_STARTED.md)  
> **리포트 동기화:** `python3 update_report.py` · Notion: `python3 update_notion.py`  
> **AIFFEL Peer Review(PRT):** [docs/PEER_REVIEW.md](docs/PEER_REVIEW.md)  
> **계획·스펙:** [MASTER_PLAN.md](MASTER_PLAN.md) · [TECH_SPEC.md](TECH_SPEC.md)

**케이스 `case_01`:** 「100억의 야근자들」— 2024-07-29 야근 중 Omega 가중치 불법 반출.  
용의자 3명(김팀장·이대리·박신입)을 심문하고, RAG·Function Calling으로 Smoking Gun을 모아 진범을 지목합니다.

```
심문 → 증거 RAG / CCTV·포렌식 툴 → 압박·대질 → 지목·자백
```

---

## 1. 데이터셋 구축 및 전처리

진술·현장기술·메신저·출입로그·법인카드·네트워크 로그를 `data/raw/`에 두고 `ingest.py`로 청킹했습니다. 청크는 `data/processed/chunks.jsonl`에 저장되고, `build_index.py`가 로컬 Hybrid 인덱스(`runs/rag/index/`)를 만듭니다. 재생성: `python3 scripts/generate_rag_dataset.py`.

### Ingest 결과

<!-- report:auto:ingest -->
- **갱신:** `runs/ingest/summary.yaml` · 2026-07-30 23:47:44
- **총 청크:** **4293**
- **evidence_id 포함 청크:** **4** (`ev_card_03` · `ev_msg_12` · `ev_log_07` · `ev_net_01`)

| source_type | 청크 수 |
| :--- | ---: |
| statements | 9 |
| forensics | 4 |
| messenger | 949 |
| logs | 2746 |
| corporate_card | 75 |
| network | 510 |
| **합계** | **4293** |
<!-- /report:auto:ingest -->

**핵심 증거 ID (win_condition)**

| evidence_id | 소스 | 역할 |
| :--- | :--- | :--- |
| `ev_card_03` | corporate_card | Phase 1 — 김팀장 룸살롱 → 현장 제외 |
| `ev_msg_12` | messenger | Phase 2 — 박신입 서버실 DM → 목격자화 |
| `ev_log_07` | logs | Phase 3 미끼 — 김팀장 지문(위조) |
| `ev_net_01` | network | Phase 3 결정타 — 라운지 Wi-Fi ~100GB · 이대리 MAC |

**저장 경로**

- raw: `data/raw/{statements,forensics,messenger,logs,corporate_card,network}/`
- chunks: `data/processed/chunks.jsonl`
- index: `runs/rag/index/vectors.json`
- eval set: `data/processed/eval_questions.jsonl` (n=6)

### 데이터 정책 · 한계

| 구분 | 본 프로젝트 |
| :--- | :--- |
| 코퍼스 규모 | 데모·파이프라인 완주용 **소량 합성 로그** (수만 줄 확장 가능 구조) |
| 분할 | RAG 검색 코퍼스 ≠ ML Train/Val/Test. 평가는 **별도 eval 질문셋** |
| 범인 정답 | `culprit_id=suspect_b`(이대리) — **API/UI 기본 응답에 미노출** |

---

## 2. Baseline vs Advanced RAG 비교

> **루브릭:** 베이스라인 대비 Advanced 검색의 정량·정성 차이

인덱스: 로컬 hashing dense + TF-IDF sparse · Advanced는 **RRF + evidence/키워드 rerank** (`lib/rag_core.py`).

### [정량] 파이프라인 비교

<!-- report:auto:rag -->
| 파이프라인 | 모드 | 대표 쿼리 | top-1 evidence | Hit@5 (목표 ID) | 비고 |
| :--- | :--- | :--- | :--- | :---: | :--- |
| **Baseline** | dense only | `김팀장 법인카드 23시` | `ev_msg_12` (비목표) | ✅ `ev_card_03` ∈ top-5 (rank 3) | 관련 카드가 뒤로 밀림 |
| **Advanced** | hybrid RRF + rerank | `라운지 Wi-Fi 100GB` | **`ev_net_01`** | ✅ `ev_net_01` top-1 | 결정타 증거 정밀 회수 |

- **자동 반영:** 2026-07-30 23:47:44
<!-- /report:auto:rag -->

상세 JSON: `runs/rag/exp_baseline/last_query.json` · `runs/rag/exp_advanced/last_query.json`

### [정성] 분석

- **Baseline 한계:** 의미 유사 청크(슬랙·시간대)가 먼저 올라와, 법인카드 Smoking Gun(`ev_card_03`)이 **3순위**로 밀림. 심문 초반 “카드 검색” UX에서 노이즈가 큼.
- **Advanced 개선:** sparse 키워드(Wi-Fi·100GB·MAC)와 evidence_id 가중 rerank로 **`ev_net_01`을 1순위**에 고정. Phase 3 자백 루프에 필요한 결정타를 안정적으로 공급.

---

## 3. 실험 로그 (Agent · Tools · Eval)

> **루브릭:** 개선 기법(Hybrid RAG · Function Calling · 상태머신)과 분기 결과

### EXP 요약

| 실험 | 내용 | 결과 | 산출물 |
| :--- | :--- | :--- | :--- |
| **EXP-RAG-B** | dense-only 검색 | 관련 증거 Hit@5는 되나 순위 불안정 | `runs/rag/exp_baseline/` |
| **EXP-RAG-A** | hybrid RRF + rerank | 결정 증거 top-1 회수 | `runs/rag/exp_advanced/` |
| **EXP-TOOL** | `request_cctv_log` · `run_forensic` | 로비 CCTV 결측 · 이대리 노트북 MAC 힌트 | `data/tools/` · API `/tool` |
| **EXP-AGENT** | ReAct: 심문→retrieve→CCTV→pressure | smoke 1턴 완주 · clue 3 · pressure 0.6 | `runs/agent/smoke.json` |
| **EXP-EVAL** | Faithfulness 로컬 루브릭 | 아래 §4 | `runs/eval/report.json` |

### Agent 스모크 (1턴)

<!-- report:auto:agent -->
- **상태:** `ok` · case `case_01` · 2026-07-30 23:47:44
- **목표 입력:** 김팀장 알리바이 검증 + CCTV
- **수집 evidence:** `ev_card_03`, `ev_log_07`, `ev_net_01`
- **clue / pressure:** 3 / 0.6
- **툴:** `request_cctv_log`(lobby) → status `unavailable` (폭우·정전으로 로비 CCTV 녹화 구간 결측 (23:00~24:00))
- **노드:** `route → interrogate → retrieve_evidence → call_tool → update_pressure → confront → judge_ending`
<!-- /report:auto:agent -->

### Function Calling (탐정 특수기)

| 툴 | 입력 예 | 역할 |
| :--- | :--- | :--- |
| `request_cctv_log` | `lounge` / `lobby` | RAG 대신 **시점·위치 고정 로그** 반환 (결측 포함) |
| `run_forensic` | `lee_laptop` | 삭제 메시지·MAC 힌트로 `ev_net_01` 교차검증 |

---

## 4. 평가 지표 및 해석

> **루브릭:** 데이터→검색→생성(답변) 사이클과 Faithfulness 중심 평가

### 메트릭 (eval_questions n=6)

<!-- report:auto:eval -->
| 메트릭 | 값 | 해석 |
| :--- | ---: | :--- |
| **Faithfulness** | **0.294** | 답변 토큰이 제공 컨텍스트에 근거하는 비율 (로컬 overlap) |
| **Context Precision** | **0.200** | 검색 top-k 중 골드 근거와 맞는 비율 |
| **Context Recall** | **1.000** | 골드 evidence_id가 검색 결과에 포함되는 비율 |
| **Answer Relevancy** | **0.067** | 질문–답변 토큰 겹침 proxy |

- **자동 반영:** 2026-07-30 23:47:44 · sample_size=6 · backend=`local_token_overlap_faithfulness`
<!-- /report:auto:eval -->

- **평가 백엔드:** `evaluate.py` 로컬 토큰 겹침 (RAGAS 패키지 미필수)
- **데이터:** `data/processed/eval_questions.jsonl`
- **환각 가드 샘플:** “창고 USB 절도” 유도 질문 → 코퍼스에 없음을 답하도록 설계 (`eq06`)

### 과적합·일반화 관점 (RAG)

| 기법 | 적용 | 역할 |
| :--- | :---: | :--- |
| Hybrid (dense+sparse) | ✅ | 키워드·의미 교차 |
| RRF + rerank | ✅ | Smoking Gun 순위 안정화 |
| eval 질문 분리 | ✅ | 검색 코퍼스와 평가 질의 분리 |
| OpenAI embedding / Chroma | ❌ (선택) | 현재는 로컬 인덱스로 재현성·오프라인 스모크 우선 |
| AutoGen | ❌ | 역할 분리로 대체 · 라이브러리 미도입 |

### 오류 패턴 (검색)

| 패턴 | 관찰 | 대응 |
| :--- | :--- | :--- |
| Baseline top-1 오탐 | 시간대·슬랙이 카드 쿼리를 가로챔 | Advanced sparse+RRF |
| Context Precision 낮음 | top-5에 관련·미관련 혼재 | chunk 경계·메타필터·임베딩 고도화 (Next) |
| Faithfulness 중간 | 짧은 한국어·동의어 | RAGAS/임베딩 기반 평가로 교체 검토 |

---

## 5. 데모 · 서비스 검증

| 항목 | 상태 |
| :--- | :--- |
| FastAPI `/health` · session/ask/search/**tool**/accuse | ✅ smoke |
| Streamlit → API only | ✅ |
| Golden Route (카드→슬랙→네트워크→이대리 지목) | 시나리오·데이터 준비 ✅ · UI 연출은 Phase 3 |

실행: [GETTING_STARTED.md](GETTING_STARTED.md)

---

## 6. 한계 및 Next

1. 코퍼스·eval n이 작아 **발표용 메트릭은 파이프라인 증명**에 가깝다. 데이터 증량 후 Hit@k·Faithfulness 재측정 필요.
2. Context Precision·Answer Relevancy proxy는 한국어에 약함 → RAGAS 또는 임베딩 유사도로 교체.
3. Agent는 LangGraph-**style** 순수 Python. `langgraph` 패키지·LLM 페르소나 실호출은 다음 스프린트.
4. AutoGen 실시간 티키타카는 **미구현** — 발표 시 “역할 분리 Multi-Agent”로 정확히 서술.

---

## 7. 팀 · 문서

| 문서 | 용도 |
| :--- | :--- |
| [GETTING_STARTED.md](GETTING_STARTED.md) | 설치·실행 |
| [docs/ROLES.md](docs/ROLES.md) | 역할 (최승현·최병철·박정우·이근목·천세문) |
| [PROJECT_SCHEDULE.md](PROJECT_SCHEDULE.md) | DLthon2 마일스톤 |
| [PRESENTATION.md](PRESENTATION.md) | 발표 초안 |
| [ARCHITECTURE.md](ARCHITECTURE.md) | 팀 OS |
