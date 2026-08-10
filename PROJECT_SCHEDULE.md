# 프로젝트 일정표 (PROJECT_SCHEDULE)

> **용도:** 발표일이 정해져 있을 때 **역산** 일정 · 마일스톤 · Code Freeze  
> **프로젝트:** 방구석 프로파일러: 진실의 방으로  
> **체크리스트:** [TEAM_KICKOFF_CHECKLIST.md](TEAM_KICKOFF_CHECKLIST.md) · [TRAINING_CHECKLIST.md](TRAINING_CHECKLIST.md)  
> **발표:** [PRESENTATION.md](PRESENTATION.md) · 대본 [PRESENTATION_SCRIPT.md](PRESENTATION_SCRIPT.md) · Gamma [PRESENTATION_GAMMA.md](PRESENTATION_GAMMA.md)  
> **역할:** [docs/ROLES.md](docs/ROLES.md)  
> **마일스톤 매핑:** Data(ingest) → RAG → Agent → Eval → API → Demo  
> **현황 (2026-08-10):** Phase 0~3 🟢 · 수집·retrain ✅ · **시연·슬라이드·대본 ✅** · **앞:** **8/11 오전 리허설 · 14:00 발표 15분 + Q&A 10분**

---

## 완료 일정 (2026-07-30 ~ 08-07)

> DLthon Day 1~4 + 8/3 배포·관측 + 8/4~7 수집·재학습까지 **전부 완료**. 남은 일정은 아래 절.

| 날짜 | 요일 | DLthon | 한 일 | 상태 |
| :--- | :---: | :---: | :--- | :---: |
| **7/30** | 목 | **Day 1** | 제안서 작성 · 팀 역할 확정 · 세계관·용의자 3 페르소나 기획 · Smoking Gun 시나리오 확정 · 메신저/법인카드 등 가짜 데이터 대량 생성·정제 | ✅ |
| **7/31** | 금 | **Day 2** | RAG 파이프라인·검색 테스트 · 상태머신(스트레스·증거) 뼈대 · 페르소나 시스템 프롬프트 1차 · **실험:** Hit@5 **0/4→4/4** · RAGAS **n=30** · LoRA **≤3B** · **AutoGen** ask | ✅ |
| **8/1~8/2** | 토~일 | **Day 3·4** | Frontend ↔ Backend(API/RAG/Agent) 연동 · 핑퐁 대화·프롬프트 미세조정(자백 밸런스) · 예외·로딩 최적화 · Streamlit→**React** 본선 · **플레이어 QA** · **Golden Route UI** 연출(증거 책상·지목·검거) · 데모 루트 안정화 | ✅ |
| **8/3** | 월 | **후속** | Railway **실서버 배포** · 모바일 화면 개선 · 오류 테스트·수정 · **Langfuse** API 연동·관측 게시판 | ✅ |
| **8/4** | 화 | **수집** | `auto_ask_collect` Day1 **45턴 완료** (ok 45) | ✅ |
| **8/5** | 수 | **수집** | Day2 증거 압박 **45턴** (ok 45) | ✅ |
| **8/6** | 목 | **수집** | Day3 압박·모순 **45턴** (ok 45) | ✅ |
| **8/7** | 금 | **수집·재학습** | Day4 보충 **30턴** → 누적 **165** · export+merge **243** · **3B LoRA** loss≈2.72 · after 붕괴 → **본선 ask 미적용** | ✅ |

**Day ↔ 실제 날짜**

| DLthon Day | 실제 | Phase 게이트 (대략) |
| :--- | :--- | :--- |
| Day 1 기획/데이터 | **7/30** | 0 · 1a |
| Day 2 코어 조립 + 실험 | **7/31** | 1b · 1c · 1d |
| Day 3·4 통합 + QA/데모 | **8/1~8/2** | 2 · 3 · Golden Route ✅ |
| 배포·관측 | **8/3** | Railway · Langfuse |
| 수집 Day1 | **8/4** | ask JSONL **45** |
| 수집 Day2~4 · retrain | **8/5~8/7** | **165턴** · `local_lora_qwen3b_retrain` ✅ |

---

## 남은 확정 스케줄 (2026-08-08 ~ 08-11)

> **정본.** 수집·재학습·**시연·슬라이드·대본 완료** → **화요일 오전 리허설 · 오후 2시 발표 (15분) + Q&A (10분)**.  
> 세부: [docs/CONVERSATION_LOG.md](docs/CONVERSATION_LOG.md) · [PRESENTATION_SCRIPT.md](PRESENTATION_SCRIPT.md)  
> **8/4~8/10은 완료** (아래 표 · 중복 없음).

| 날짜 | 요일 | 목표 | 턴 / 산출 | 상태 |
| :--- | :---: | :--- | :--- | :---: |
| **8/8** | 토 | (버퍼) | 슬라이드 초안 · 멘트 메모 | ✅ |
| **8/9** | 일 | **시연 영상 녹화** | 발표 컷(B) · HQ mp4 | ✅ |
| **8/10** | 월 | **발표 준비** | Gamma 슬라이드 · 대본·Q&A · 에셋 · 영상 정리 | ✅ |
| **8/11 오전** | 화 | **최종 리허설** | 라이브 데모 · PC/네트워크 · **영상 재생** 점검 | ⬜ |
| **8/11 14:00** | 화 | **발표 (D-0)** | 슬라이드 + 녹화 데모 **15분** · **Q&A 10분** | ⬜ |

**한 줄:** 시연·문서 ✅ · **화 오전 리허설 · 14:00 발표**.  
발표용 영상: `.presentation_media/cut_b_sharp.mp4` (gitignore).

```bash
# 재학습 재현 (본선 ask 교체 없음)
python3 scripts/export_conversation_log.py
python3 scripts/local_lora_persona.py \
  --model Qwen/Qwen2.5-3B-Instruct \
  --data runs/sft/persona_sft_merged_0807.jsonl \
  --max-steps 12 --max-len 320 \
  --out-dir runs/sft/local_lora_qwen3b_retrain
```

---

## DLthon2 — 완성 전략 · 4일 마일스톤

> **변동 가능:** 아래 Day 1~4 Task는 팀 상황·진도에 따라 조정한다.  
> **실제 소화일:** 위 [완료 일정](#완료-일정-2026-07-30--08-07) (7/30~8/2 ≈ Day 1~4 · **8/3 배포·관측** · **8/4~7 수집·재학습 ✅**).  
> 변경 시 본 표와 [TEAM_KICKOFF_CHECKLIST.md](TEAM_KICKOFF_CHECKLIST.md)를 같이 고치고, 전원에게 공유한다.

### 프로젝트 완성을 위한 전략

| 전략 | 내용 |
| :--- | :--- |
| **문서 중심 몹(Mob) 기획** | Day 1에 환경 세팅으로 시간을 뺏기지 않도록, 화이트보드·Notion으로 **세계관·시나리오·가짜 알리바이·증거 원문**을 전원 동시 설계한다. |
| **단계별 애자일 개발** | 먼저 **Backend(상태머신/API) ↔ Frontend** 뼈대(mock)를 연결한 뒤, **RAG · 상세 AI 프롬프트**를 얹어 빠르고 안정적인 데모를 만든다. UI는 Streamlit 프로토타입 → **React 본선**. |

### DLthon2 기간 내 마일스톤 (초안 · 실날짜 매핑)

| 구분 | 기간 | 실제 | 상세 Task | 주 담당 (참고) | [ ] |
| :--- | :--- | :--- | :--- | :--- | :---: |
| **기획 / 데이터** | **Day 1** | **7/30** | 세계관·용의자 3 페르소나 · Smoking Gun 확정 · 가짜 데이터 대량 생성·정제 · 제안서·역할 | 최병철 · 박정우 | ✅ |
| **코어 조립** | **Day 2** | **7/31** | RAG·검색 · 상태머신 뼈대 · 페르소나 프롬프트 1차 · Hit@5/RAGAS/LoRA/AutoGen 실험 | 이근목 · 최승현 · 박정우 | ✅ |
| **통합 · QA / 데모** | **Day 3·4** | **8/1~8/2** | FE↔BE 연동 · 핑퐁·프롬프트 · React 본선 · 플레이어 QA · Golden Route UI ✅ | 천세문 · 최승현 · 전원 | ✅ |
| **배포 · 관측** | **후속** | **8/3** | Railway · 모바일 · 오류 수정 · Langfuse 게시판 | 최승현 · 전원 | ✅ |
| **수집 Day1** | **후속** | **8/4** | `auto_ask_collect` **45턴** | 최승현 | ✅ |

**Day ↔ 레포 Phase 대략 매핑** (조정 시 함께 갱신)

| DLthon Day | CLAUDE Phase | 게이트 산출물 예 |
| :--- | :--- | :--- |
| Day 1 (7/30) | 0 · 1a | `case_01` · personas · `data/raw/` · ingest |
| Day 2 (7/31) | 1b · 1c · 1d | `runs/rag/` · `agent_graph --smoke` · eval · LoRA |
| Day 3·4 (8/1~2) | 2 · 3 · 데모 | FastAPI · **React** · Golden Route UI ✅ |
| 8/3 | 운영 | Railway · Langfuse |
| 8/4 | 수집 | ask **45턴** ✅ |

---

## 발표 역산 (**확정** · D-0 = 2026-08-11)

| D-day | 날짜 | 이 날 하는 일 | 이 날 하지 말 것 |
| :---: | :--- | :--- | :--- |
| **D-7~D-4** | 8/4~8/7 | 자동 심문 수집 · **8/7 오후 재학습** | 새 EXP · 본선 ask 모델 교체 |
| **D-3** | **8/8** | 버퍼 · 슬라이드 초안 · PRT | 대규모 리팩터 |
| **D-2** | **8/9** | **시연 영상 녹화** (발표 컷 B + 풀 A) | 녹화에 의존할 새 UI 변경 |
| **D-1** | **8/10** | **발표자 확정** · 슬라이드·Q&A · 영상 삽입 · 예비 리허설 | 본 녹화 첫 시도 · 코드 손대기 |
| **D-0 오전** | **8/11** | **최종 리허설** — 영상 재생·라이브 폴백 · PC/네트워크 | 코드 변경 |
| **D-0 14:00** | **8/11** | **발표 15분** · Q&A | — |

| 항목 | 값 |
| :--- | :--- |
| **발표일 (D-0)** | **2026-08-11 14:00** |
| **시연 녹화** | **2026-08-09** |
| **발표 준비 (D-1)** | **2026-08-10** (발표자·슬라이드) |
| **당일 리허설** | **2026-08-11 오전** |
| 발표 시간 / 장소 | **오후 2시** / (장소 팀 기입) |
| 발표 분량 | **15분** |

### D-3 Code Freeze 체크

- [ ] `python3 repro_manifest.py` → `runs/reproducibility_manifest.yaml`
- [ ] `runs/rag/index/` · `runs/rag/exp_*/` · `runs/agent/` · `runs/eval/`
- [ ] `README.md` 메트릭 표 기입
- [ ] `docs/PEER_REVIEW.md` 초안
- [ ] `python3 -m pytest tests/smoke -q` 녹색 (API 기동)
- [x] **React** → API Golden Route 동작 · Streamlit 백업
- [x] Railway 라이브 데모 (https://web-production-072b8.up.railway.app)

### D-1 · D-0

- [ ] **8/9** 시연 녹화 (발표 컷 B · 가능하면 풀 A)
- [ ] **8/10** 발표자 확정 · 슬라이드·멘트 · 영상 삽입
- [ ] **8/11 오전** 최종 리허설 · 데모 PC/네트워크 · 영상 재생 점검
- [ ] **8/11 14:00** 발표 15분

---

## 일정 지연 시

| 상황 | 줄일 것 | 지키는 것 |
| :--- | :--- | :--- |
| RAG 실험 부족 | Advanced 실험 횟수 | Baseline + Advanced 1회 비교 |
| UI 미완 | 화려한 레이아웃 | API only · Golden Route 완주 |
| 문서 부족 | 장문 회고 | README + PRT 초안 |
| **절대 밀지 말 것** | — | **8/7 재학습 · 8/9 시연 녹화 · 8/11 오전 리허설 · 14:00 발표** |

---

## 관련 문서

| 문서 | 용도 |
| :--- | :--- |
| [TEAM_KICKOFF_CHECKLIST.md](TEAM_KICKOFF_CHECKLIST.md) | Phase별 할 일 |
| [TRAINING_CHECKLIST.md](TRAINING_CHECKLIST.md) | RAG/Agent 실험 체크 |
| [docs/ROLES.md](docs/ROLES.md) | 역할 |
| [PRESENTATION.md](PRESENTATION.md) | 슬라이드 원본 |
| [docs/CONVERSATION_LOG.md](docs/CONVERSATION_LOG.md) | 8/4~7 수집 · 금 재학습 · 안정장치 |
| [docs/PEER_REVIEW.md](docs/PEER_REVIEW.md) | PRT |
