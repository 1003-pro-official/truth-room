# TECH_SPEC — 진실의 방으로

> 구현의 Single Source of Truth. 변경 시 PR로 갱신.  
> 정본 YAML: `data/scenarios/case_01.yaml` · `data/personas/` · `configs/*.yaml`

---

## 1. 스택

| 레이어 | 현재 선택 | 비고 |
| :--- | :--- | :--- |
| LLM | OpenAI / 대체 가능 (env) | `.env` 키만 · UI에서 직결 금지 |
| Orchestration | **LangGraph** StateGraph (`lib/langgraph_runtime.py` · `agent_graph.py`) + **AutoGen GroupChat** 심문 턴 | 오프라인 smoke=`agent_graph --smoke` (langgraph) · 온라인 ask=`lib/autogen_runtime` |
| Multi-Agent | 용의자 · 포렌식 조수 · 심판 (pyautogen) | `configs/agent.yaml` `autogen.enabled` · 실패 시 스텁 폴백 |
| RAG | **로컬 Hybrid** (`lib/rag_core.py`) + **source soft routing** | Baseline=dense · Advanced=sparse+dense **RRF+rerank** · Hit@5 **4/4** · C-Prec **0.40** · 인덱스 `runs/rag/index/` |
| Tools | Function Calling | `check_card_history` · `run_forensic` · `search_messenger` · `request_cctv_log` (`lib/tools.py`) |
| Eval | 로컬 Faithfulness + **RAGAS** | `evaluate.py` · `scripts/eval_ragas.py` (Python 3.12 · **n=30** Faith≈0.64 · Prec≈0.75 · Recall≈0.77) · `scripts/plot_metrics.py` |
| API | FastAPI | `backend/` |
| UI | **React** (`web/game`) · Streamlit `app.py` 백업 | `/game` 정적 빌드 · API만 호출 · 레이어 모달 · WebP 에셋 |
| Deploy | Railway | https://web-production-072b8.up.railway.app (`/` 인트로 · `/game` · F5→인트로) |
| Config | YAML | `configs/*.yaml` · `langgraph.enabled` · `autogen.enabled` |

**UI 전환 (Streamlit → React):** 초기 데모는 Streamlit으로 API-only 골든 루트를 검증했고, 본선은 React로 이전했다.  
**직접 원인:** Streamlit의 위젯·세션 상태·다이얼로그·리렌더 모델이 심문/모달/인벤과 맞물리며 **오류·상태 꼬임이 반복**되어 데모 안정화가 어려웠다.  
**부가 이점:** 커스텀 게임 UX(레이아웃·모션·오디오) 제어, UI→API only 경계 고정, `/` 인트로·`/game/` 분리 배포. Streamlit은 백업 경로로 유지.

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
alibi: "라운지에서…"
secrets: ["지문 로그 위조", "라운지 Wi-Fi 100GB 전송", "동기 5억"]
leak_threshold: 0.7
prompt_vars:                   # 마스터 템플릿 치환값 (1템플릿·3인)
  이름: "이대리"
  is_culprit: "true"
  결정적_증거: "ev_net_01 …"
system_prompt: |               # 정적 스냅샷 · 런타임은 lib/persona_prompt.py
  …
```

마스터 템플릿: `data/personas/prompt_template.yaml` · 렌더: `lib/persona_prompt.render_suspect_prompt(persona, pressure=…)`

| id | 이름 | role |
| :--- | :--- | :--- |
| suspect_a | 김팀장 | 무고 |
| suspect_b | 이대리 | 범인 |
| suspect_c | 박신입 | 무고 |

### 2.3 증거 문서 — `data/raw/{messenger,logs,corporate_card,network}/`

청킹 후 `data/processed/chunks.jsonl` → **`runs/rag/index/`** (`vectors.json`)

메타데이터 권장: `source_type`, `timestamp`, `suspect_ids`, `evidence_id`

툴 페이로드: `data/tools/cctv.yaml`, `data/tools/forensic.yaml`, `data/tools/card.yaml`, `data/tools/messenger.yaml`  
조수 프롬프트: `data/assistant/prompt_template.yaml` · `configs/agent.yaml` `gm_system_prompt` · `lib/assistant_prompt.py`  
심판(GM) 프롬프트: `data/gm/prompt_template.yaml` · `judge_system_prompt` · `accuse_template` · `lib/gm_judge.py` (`lie_broken`|조합 지목 JSON, UI 미노출)

---

## 3. 파이프라인 스크립트

| 스크립트 | 역할 | 설정 |
| :--- | :--- | :--- |
| `ingest.py` | raw → chunks | `configs/ingest.yaml` |
| `build_index.py` | 로컬 하이브리드 인덱스 | `configs/rag.yaml` |
| `rag_pipeline.py` | Baseline / Advanced 검색 | `configs/rag.yaml` |
| `agent_graph.py` | 심문 상태머신 · ReAct 툴 (오프라인 smoke) | `configs/agent.yaml` |
| `lib/autogen_runtime.py` | ask 턴 AutoGen GroupChat | `configs/agent.yaml` `autogen` |
| `evaluate.py` | Faithfulness 등 | `configs/eval.yaml` |

---

## 4. API 계약

| Method | Path | 설명 |
| :--- | :--- | :--- |
| `GET` | `/health` | 헬스 |
| `POST` | `/api/v1/session` | 새 게임 세션 |
| `GET` | `/api/v1/session/{id}` | 상태 (수집 증거·압박) |
| `POST` | `/api/v1/session/{id}/ask` | 심문 `{suspect_id, question}` → `answer` · `agent_transcript` · `assistant_note` · `autogen` |
| `POST` | `/api/v1/session/{id}/search` | 증거 RAG `{query}` |
| `POST` | `/api/v1/session/{id}/tool` | `{name, args}` — CCTV / forensic |
| `POST` | `/api/v1/session/{id}/pass_turn` | 타임아웃 턴 패스 (pressure/break 미증가) |
| `POST` | `/api/v1/session/{id}/accuse` | 조합 지목 `{suspect_id, evidence_ids[2]}` |
| `POST` | `/api/v1/session/{id}/search` 응답 | `new_clues[]` · `useless_search` · `stamina` |
| `GET` | `/api/v1/case/public` | 세션 없이 공개 개요·`intro_scenes` (스크롤 인트로) |
| `GET` | `/api/v1/session/{id}/case` | 공개 사건개요 (`public_overview`, `culprit_id` 미포함) |
| `GET` | `/api/v1/session/{id}/suspects/{sid}/profile` | 공개 프로필 + `case_overview` (`secrets`/`role` 미포함) |

UI는 위 API만 호출. LLM/인덱스 직접 로드 금지. `culprit_id`는 `accuse` 판정에만 사용.

### 4.1 실서버 심문 로그 → 재학습 (opt-in)

실서버 플레이 테스트의 ask 턴을 JSONL로 모아 **말투** 소량 SFT/LoRA 재학습 후보로 쓴다.

| 항목 | 내용 |
| :--- | :--- |
| 구현 | `lib/conversation_log.py` · `scripts/export_conversation_log.py` |
| 설정 | `configs/agent.yaml` `conversation_log` · env `CONVERSATION_LOG=1` |
| 기본 | **OFF** (로컬). 실서버에서만 켠다 |
| 안정장치 | ask 비차단 · culprit/secrets 미기록 · 누수 문구 편집 · 길이 상한 · 말투 전용 · `runs/` gitignore |
| 문서 | [docs/CONVERSATION_LOG.md](docs/CONVERSATION_LOG.md) |

---

## 5. Agent 상태 (LangGraph)

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

노드 (공식 `langgraph` StateGraph · `lib/langgraph_runtime.py`):  
`START → route` → (conditional) `interrogate | retrieve_evidence | call_tool | judge_ending`  
→ `update_pressure → confront → judge_ending → END`  
(retrieve 목표는 smoke 내러티브상 `interrogate` 선행)

설정: `configs/agent.yaml` → `langgraph.enabled` (false 시 순수 Python 폴백)

**게임 룰 정본:** [docs/GAME_RULES.md](docs/GAME_RULES.md) (3-Out · 멘탈 붕괴 · 20초 · 수사 권한 · 조합 지목)

---

## 6. 평가

| 메트릭 | 대상 | 기준 |
| :--- | :--- | :--- |
| Context Precision / Recall | RAG | Baseline vs Advanced |
| Faithfulness / Answer Relevancy | 생성 | `evaluate.py` (로컬) · **RAGAS** `scripts/eval_ragas.py` (py3.12 · n=30) |
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
