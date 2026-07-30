# MASTER_PLAN — 방구석 프로파일러: 진실의 방으로

> **한 줄:** 플레이어가 용의자 3명을 심문하고, 메신저·로그·법인카드·네트워크 증거를 RAG로 수집하며, Multi-Agent 역할(용의자·GM·툴)이 자백을 유도하는 인터랙티브 텍스트 미스터리.

---

## 1. 목표 (DLthon)

| 항목 | 내용 |
| :--- | :--- |
| **제품** | 인터랙티브 심문 게임 (웹 데모) |
| **케이스** | `case_01` — 「100억의 야근자들」· Omega 가중치 유출 |
| **핵심 기술** | Advanced RAG (Hybrid/RRF) · Function Calling · LangGraph-style 상태머신 · LLM |
| **차별점** | 단순 Q&A가 아니라 **심문 → 증거 → 자백** 루프 |
| **제출물** | GitHub 리포트(`README.md`) · 데모 · Peer Review · 발표 |
| **일정** | DLthon2 4일 전략·마일스톤 → [PROJECT_SCHEDULE.md](PROJECT_SCHEDULE.md) (**변경 가능**) |

**완성 전략 (요약):** Day 1 문서·몹 기획으로 시나리오/데이터 동시 설계 → 상태머신↔Streamlit 뼈대 먼저 연결 → RAG·프롬프트를 얹어 데모 안정화.

> **AutoGen:** 발표 멘트의 “멀티에이전트”는 역할 분리(용의자·포렌식 툴·GM)로 구현. AutoGen 라이브러리는 **미적용·선택 실험**.

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
| **1c** | Agent | LangGraph-style 루프 · `runs/agent/` · `--smoke` |
| **1d** | Eval | Faithfulness 등 · `runs/eval/` |
| **2** | API | FastAPI 심문/증거/세션/툴 |
| **3** | Demo | Streamlit「진실의 방」UI |
| **제출** | Docs | README · PRT · 발표 |

---

## 4. 팀 (5인 · kickoff)

| 역할 | 담당자 | 담당 |
| :--- | :--- | :--- |
| **Agent / LangGraph · PM** | 최승현 | 아키텍처 · 상태 그래프 |
| **Scenario** | 최병철 | 세계관 · 증거 원문 |
| **Prompt** | 박정우 | 페르소나 · 조수 프롬프트 |
| **RAG / Data · Tools** | 이근목 | 인덱스 · Retrieval · Function Calling |
| **Service / Demo · QA** | 천세문 | Streamlit · API 연동 · 데모 |

상세 → [docs/ROLES.md](docs/ROLES.md)

---

## 5. 성공 기준 (초안)

- [ ] 용의자 3명 페르소나가 일관되게 대답
- [ ] 핵심 증거 ID 회수 (Hit@k 팀 합의) · win_condition `[ev_card_03, ev_msg_12, ev_net_01]`
- [ ] 심문 세션이 API → UI 단일 경로로 동작
- [ ] Baseline RAG vs Advanced RAG 비교 수치 1회 이상
- [ ] 5분 Golden Route 데모 (범인 지목 → 자백) 완주
- [ ] 게임 룰: 3-Out · 멘탈 붕괴 · (선택) 20초 타이머 — [docs/GAME_RULES.md](docs/GAME_RULES.md)

---

## 6. 비범위 (Out of scope · 초안)

- 실시간 음성 / 3D
- 대규모 파인튜닝 (LoRA는 선택·시간 남으면)
- 상용 배포 (로컬·Colab 데모면 충분)
- AutoGen 필수 도입 · OpenAI embedding/Chroma 필수화 (선택 고도화)
- 객체탐지(YOLO) · CV 학습 파이프라인

상세 기술 → [TECH_SPEC.md](TECH_SPEC.md) · 코딩 규칙 → [AI_CONVENTION.md](AI_CONVENTION.md)
