# TECH_SPEC — 진실의 방으로

> 구현의 Single Source of Truth. 변경 시 PR로 갱신.  
> 정본 YAML: `data/scenarios/case_01.yaml` · `data/personas/` · `configs/*.yaml`

---

## 1. 스택

| 레이어 | 현재 선택 | 비고 |
| :--- | :--- | :--- |
| LLM | OpenAI / 대체 가능 (env) | `.env` 키만 · UI에서 직결 금지 |
| Orchestration | **LangGraph-style 상태머신** (`agent_graph.py`) | 순수 Python 노드. `langgraph` 패키지 연동은 선택 고도화 |
| Multi-Agent | 페르소나·GM·툴 역할 분리 | **AutoGen 미적용** (선택 실험·범위 밖) |
| RAG | **로컬 Hybrid** (`lib/rag_core.py`) | Baseline=dense · Advanced=sparse+dense **RRF+rerank** · 인덱스 `runs/rag/index/` |
| Tools | Function Calling | `request_cctv_log` · `run_forensic` (`lib/tools.py`) |
| Eval | 로컬 Faithfulness + 시나리오 루브릭 | `evaluate.py` · RAGAS는 선택 |
| API | FastAPI | `backend/` |
| UI | Streamlit | `app.py` — **API만** 호출 |
| Config | YAML | `configs/*.yaml` |

---

## 2. 데이터 스키마

### 2.1 시나리오 — `data/scenarios/case_01.yaml`

```yaml
case_id: case_01
title: "진실의 방 — 100억의 야근자들"
culprit_id: suspect_b          # 이대리 · UI/API 기본 응답에 노출 금지
suspects: [suspect_a, suspect_b, suspect_c]
win_condition:
  accuse_culprit: true
  min_evidence_ids: [ev_card_03, ev_msg_12, ev_net_01]
```

핵심 증거: `ev_card_03`(법인카드) · `ev_msg_12`(슬랙) · `ev_log_07`(출입·미끼) · `ev_net_01`(Wi-Fi 전송·결정타)

### 2.2 페르소나 — `data/personas/suspect_*.yaml`

```yaml
id: suspect_b
name: "이대리"
role: "범인"                   # 내부용
alibi: "라운지에서 넷플릭스…"
secrets: ["지문 로그 위조", "라운지 Wi-Fi 100GB 전송", "동기 5억"]
leak_threshold: 0.7
system_prompt: |
  … ev_net_01 제시 전 자백 금지 …
```

| id | 이름 | role |
| :--- | :--- | :--- |
| suspect_a | 김팀장 | 무고 |
| suspect_b | 이대리 | 범인 |
| suspect_c | 박신입 | 무고 |

### 2.3 증거 문서 — `data/raw/{messenger,logs,corporate_card,network}/`

청킹 후 `data/processed/chunks.jsonl` → **`runs/rag/index/`** (`vectors.json`)

메타데이터 권장: `source_type`, `timestamp`, `suspect_ids`, `evidence_id`

툴 페이로드: `data/tools/cctv.yaml`, `data/tools/forensic.yaml`

---

## 3. 파이프라인 스크립트

| 스크립트 | 역할 | 설정 |
| :--- | :--- | :--- |
| `ingest.py` | raw → chunks | `configs/ingest.yaml` |
| `build_index.py` | 로컬 하이브리드 인덱스 | `configs/rag.yaml` |
| `rag_pipeline.py` | Baseline / Advanced 검색 | `configs/rag.yaml` |
| `agent_graph.py` | 심문 상태머신 · ReAct 툴 | `configs/agent.yaml` |
| `evaluate.py` | Faithfulness 등 | `configs/eval.yaml` |

---

## 4. API 계약

| Method | Path | 설명 |
| :--- | :--- | :--- |
| `GET` | `/health` | 헬스 |
| `POST` | `/api/v1/session` | 새 게임 세션 |
| `GET` | `/api/v1/session/{id}` | 상태 (수집 증거·압박) |
| `POST` | `/api/v1/session/{id}/ask` | 심문 `{suspect_id, question}` |
| `POST` | `/api/v1/session/{id}/search` | 증거 RAG `{query}` |
| `POST` | `/api/v1/session/{id}/tool` | `{name, args}` — CCTV / forensic |
| `POST` | `/api/v1/session/{id}/pass_turn` | 타임아웃 턴 패스 (pressure/break 미증가) |
| `POST` | `/api/v1/session/{id}/accuse` | 조합 지목 `{suspect_id, evidence_ids[2]}` |
| `POST` | `/api/v1/session/{id}/search` 응답 | `new_clues[]` · `useless_search` · `stamina` |
| `GET` | `/api/v1/session/{id}/case` | 공개 사건개요 (`public_overview`, `culprit_id` 미포함) |
| `GET` | `/api/v1/session/{id}/suspects/{sid}/profile` | 공개 프로필 + `case_overview` (`secrets`/`role` 미포함) |

UI는 위 API만 호출. LLM/인덱스 직접 로드 금지. `culprit_id`는 `accuse` 판정에만 사용.

---

## 5. Agent 상태 (LangGraph-style)

```
State:
  session_id, turn, suspect_id
  messages[]
  evidence_ids[]
  pressure: {suspect_a: float, ...}
  break_count: {suspect_a: int, ...}   # 알리바이 3-Out (docs/GAME_RULES.md)
  timeout_strikes: int                 # 턴 타임아웃 3진 아웃 (0..3)
  stamina / stamina_max                # 수사 권한 (명탐정 S 하트 대응)
  mental_break_suspects[]
  status: playing | mental_break | turn_out | authority_revoked
  last_retrieval[]
  tool_results[]
  clue_count
  phase: interrogate | retrieve | tool | confront | ending
```

노드: `route` → `interrogate` | `retrieve_evidence` | `call_tool` → `update_pressure` → `confront` → `judge_ending`

**게임 룰 정본:** [docs/GAME_RULES.md](docs/GAME_RULES.md) (3-Out · 멘탈 붕괴 · 20초 · 수사 권한 · 조합 지목)

---

## 6. 평가

| 메트릭 | 대상 | 기준 |
| :--- | :--- | :--- |
| Context Precision / Recall | RAG | Baseline vs Advanced |
| Faithfulness / Answer Relevancy | 생성 | `evaluate.py` (로컬) · RAGAS 선택 |
| Scenario clear rate | 에이전트 | Golden Route 데모 완주 |

---

## 7. 환경 변수

```
API_URL=http://localhost:8000
OPENAI_API_KEY=
# 선택
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
```

비밀값은 `.env` only — Git 커밋 금지.
