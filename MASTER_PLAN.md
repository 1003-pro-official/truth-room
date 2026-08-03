# MASTER_PLAN — 방구석 프로파일러: 진실의 방으로

> **한 줄:** 플레이어가 용의자 3명을 심문하고, 메신저·로그·법인카드·네트워크 증거를 RAG로 수집하며, Multi-Agent 역할(용의자·GM·툴)이 자백을 유도하는 인터랙티브 텍스트 미스터리.

---

## 1. 목표 (DLthon)

| 항목 | 내용 |
| :--- | :--- |
| **제품** | 인터랙티브 심문 게임 (웹 데모) |
| **케이스** | `case_01` — 「100억의 야근자들」· Omega 가중치 유출 |
| **핵심 기술** | Advanced RAG (Hybrid/RRF) · Function Calling · **LangGraph** StateGraph · **AutoGen** · LLM |
| **차별점** | 단순 Q&A가 아니라 **심문 → 증거 → 자백** 루프 |
| **제출물** | GitHub 리포트(`README.md`) · 데모 · Peer Review · 발표 |
| **일정** | DLthon2 4일 전략·마일스톤 → [PROJECT_SCHEDULE.md](PROJECT_SCHEDULE.md) (**변경 가능**) |

**완성 전략 (요약):** Day 1 문서·몹 기획으로 시나리오/데이터 동시 설계 → 상태머신↔UI 뼈대 먼저 연결 → RAG·프롬프트를 얹어 데모 안정화.  
**UI:** 초기 Streamlit → 본선 **React** (`web/game`). **직접 원인** — Streamlit 한계로 상태·다이얼로그 **오류 반복**. Streamlit `app.py` 백업.

> **AutoGen:** 심문 ask 본선 — `lib/autogen_runtime.py` GroupChat(용의자·포렌식 조수·심판). `configs/agent.yaml` `autogen.enabled` · 실패 시 스텁 폴백.  
> **LangGraph:** 오프라인 상태머신 smoke — `lib/langgraph_runtime.py` 공식 StateGraph · `agent_graph.py` 노드 · `langgraph.enabled` (false/미설치 시 순수 Python 폴백).

---

## 2. 유저 루프

```
플레이어 질문
    ↓
심문 에이전트(용의자 페르소나) 응답
    ↓
증거 RAG (메신저 / 출입로그 / 법인카드 / 네트워크) + CCTV·포렌식 툴
    ↓
모순·알리바이 탐지 → 압박 프롬프트
    ↓
자백 유도 or 다음 용의자 / 엔딩
```

---

## 3. Phase (템플릿 매핑)

| Phase | 이름 | 게이트 산출물 |
| :---: | :--- | :--- |
| **0** | 레포·팀 | `docs/ROLES.md` 담당 · `.env` · configs |
| **1a** | Data | 시나리오 YAML · 증거 코퍼스 · `runs/ingest/` |
| **1b** | RAG | `runs/rag/index/` · Baseline/Advanced · `runs/rag/exp_*/` |
| **1c** | Agent | **LangGraph** StateGraph · `lib/langgraph_runtime.py` · `runs/agent/` · `--smoke` |
| **1d** | Eval | Faithfulness · **RAGAS n=30** · `runs/eval/` |
| **2** | API | FastAPI 심문/증거/세션/툴 |
| **3** | Demo | **React**「진실의 방」UI (`web/game`) · Streamlit 백업 |
| **제출** | Docs | README · PRT · 발표 |

---

## 4. 팀 (5인 · kickoff)

| 역할 | 담당자 | 담당 |
| :--- | :--- | :--- |
| **Agent / LangGraph · PM** | 최승현 | 아키텍처 · 상태 그래프 |
| **Scenario** | 최병철 | 세계관 · 증거 원문 |
| **Prompt** | 박성우 | 페르소나 · 조수 프롬프트 |
| **RAG / Data · Tools** | 이근목 | 인덱스 · Retrieval · Function Calling |
| **Service / Demo · QA** | 천세문 | React UI · API 연동 · 데모 |

상세 → [docs/ROLES.md](docs/ROLES.md)

---

## 5. 성공 기준 (초안)

- [x] 용의자 3명 페르소나가 일관되게 대답
- [x] 핵심 증거 ID 회수 — Advanced Hit@5 **4/4** · win_condition `[ev_card_03, ev_msg_12, ev_net_01]`
- [x] 심문 세션이 API → UI 단일 경로로 동작 (AutoGen ask 본선)
- [x] Baseline RAG vs Advanced RAG 비교 (Hit@5 **0/4 → 4/4**)
- [x] 5분 Golden Route 데모 (범인 지목 → 자백) 완주 · UI 연출  
  (라이브: https://web-production-072b8.up.railway.app · 인트로→심문→증거 책상→조합 지목·검거 도장)
- [x] 게임 룰: 3-Out · 멘탈 붕괴 · 타이머 — [docs/GAME_RULES.md](docs/GAME_RULES.md)
- [ ] 심문 로그 수집 → 말투 재학습 사이클 — **확정:** 8/4~7 ≈165턴(`auto_ask_collect`) → 8/7 오후 3B LoRA → **8/10 준비 · 8/11 오전 리허설 · 14:00 발표** ([PROJECT_SCHEDULE.md](PROJECT_SCHEDULE.md) · [docs/CONVERSATION_LOG.md](docs/CONVERSATION_LOG.md))

### 중장기 (PRT 이후 · 발표 Next)

- [ ] 진범 랜덤 — **변형 케이스 세트** 세션 로드 (ID만 스왑 금지)
- [ ] 용의자 확장 — 권장 `case_02` 신규 사건 (인원·구성은 설계에 따름)

상세·Q&A 멘트: [docs/ROADMAP_EXPANSION.md](docs/ROADMAP_EXPANSION.md)

---

## 6. 비범위 (Out of scope · 초안)

- 실시간 음성 / 3D
- **대규모** LLM 파인튜닝 (소량 로컬 LoRA는 **완료**: SmolLM→0.5B→1.5B→**3B** · 7B는 16GB `memory_limit`)
- 상용 필수화 (로컬·Colab도 가능 — **Railway 데모:** https://web-production-072b8.up.railway.app )
- 무제한 AutoGen 티키타카(상한·폴백 없는) · OpenAI embedding/Chroma 필수화 (선택 실험만 · Hit@5에서 Advanced 미상회)
- 객체탐지(YOLO) · CV 학습 파이프라인
- **PRT 범위 밖:** 진범 세션 랜덤 · 용의자 확장 — 중장기로만 ([docs/ROADMAP_EXPANSION.md](docs/ROADMAP_EXPANSION.md))

상세 기술 → [TECH_SPEC.md](TECH_SPEC.md) · 코딩 규칙 → [AI_CONVENTION.md](AI_CONVENTION.md)
